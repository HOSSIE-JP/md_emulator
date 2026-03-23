"""Capture title screen from target33 and save as BMP."""
import urllib.request, json, struct

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Get video frame  
frame = api_get("/video/frame")
width = frame["width"]
height = frame["height"]
pixels = frame["pixels_argb"]

print(f"Frame: {width}x{height}, {len(pixels)} pixels")

# Save as BMP
def save_bmp(filename, w, h, pixel_list):
    row_size = w * 3
    pad = (4 - row_size % 4) % 4
    row_padded = row_size + pad
    pixel_size = row_padded * h
    
    with open(filename, 'wb') as f:
        f.write(b'BM')
        f.write(struct.pack('<I', 54 + pixel_size))
        f.write(struct.pack('<HH', 0, 0))
        f.write(struct.pack('<I', 54))
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
        
        for y in range(h-1, -1, -1):
            for x in range(w):
                argb = pixel_list[y * w + x] & 0xFFFFFFFF
                r_val = (argb >> 16) & 0xFF
                g_val = (argb >> 8) & 0xFF
                b_val = argb & 0xFF
                f.write(bytes([b_val, g_val, r_val]))
            f.write(b'\x00' * pad)

save_bmp("title_t33.bmp", width, height, pixels)
print("Saved title_t33.bmp")
