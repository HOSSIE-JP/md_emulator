"""Capture title screen from target33 and save as PNG."""
import urllib.request, json, struct

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get_bytes(p):
    return urllib.request.urlopen(f"{BASE}{p}").read()

# Step 1 more frame to make sure it rendered
api_post("/emulator/step", {"frames": 1})

# Get framebuffer
fb_data = api_get_bytes("/emulator/framebuffer")

# Save as BMP
width, height = 320, 224

# BMP header
def save_bmp(filename, w, h, argb_data):
    """Save ARGB u32 data as BMP file."""
    pixels = struct.unpack(f'<{w*h}I', argb_data[:w*h*4])
    row_size = w * 3
    pad = (4 - row_size % 4) % 4
    row_padded = row_size + pad
    pixel_size = row_padded * h
    
    with open(filename, 'wb') as f:
        # BMP header
        f.write(b'BM')
        f.write(struct.pack('<I', 54 + pixel_size))
        f.write(struct.pack('<HH', 0, 0))
        f.write(struct.pack('<I', 54))
        # DIB header
        f.write(struct.pack('<I', 40))
        f.write(struct.pack('<i', w))
        f.write(struct.pack('<i', h))
        f.write(struct.pack('<HH', 1, 24))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', pixel_size))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))
        
        # Pixel data (BMP is bottom-up)
        for y in range(h-1, -1, -1):
            for x in range(w):
                argb = pixels[y * w + x]
                r = (argb >> 16) & 0xFF
                g = (argb >> 8) & 0xFF
                b = argb & 0xFF
                f.write(bytes([b, g, r]))
            f.write(b'\x00' * pad)

save_bmp("title_t33.bmp", width, height, fb_data)
print("Saved title_t33.bmp")

# Also get per-scanline VSRAM
sv = json.loads(urllib.request.urlopen(f"{BASE}/vdp/scanline-vsram").read().decode())
data = sv["scanline_vsram_a"]

# Print signed values
print("\nPer-scanline VSRAM[0] as signed (first 160 lines):")
for i in range(min(160, len(data))):
    v = data[i]
    if v > 32767:
        v -= 65536
    print(f"  Line {i:3d}: vscroll = {v:+5d}")
