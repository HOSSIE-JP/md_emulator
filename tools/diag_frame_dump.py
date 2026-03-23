"""
Render the framebuffer to a BMP to see what's actually showing.
Also test specific sprite rendering on multiple scanlines.
"""
import urllib.request
import json
import struct

BASE = "http://localhost:8114/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# Get frame
frame = api("/video/frame")
keys = list(frame.keys())
print(f"Frame response keys: {keys}")

fb = frame.get("pixels_argb") or frame.get("framebuffer") or frame.get("pixels") or []
width = frame.get("width", 320)
height = frame.get("height", 224)
print(f"Frame: {width}x{height}, pixels: {len(fb)}")

if not fb:
    print("No framebuffer data!")
    exit(1)

# Count unique colors in entire frame
color_counts = {}
for c in fb:
    c = c & 0xFFFFFFFF
    color_counts[c] = color_counts.get(c, 0) + 1

print(f"\nTotal unique colors in frame: {len(color_counts)}")
# Sort by count
for cv, cnt in sorted(color_counts.items(), key=lambda x: -x[1])[:20]:
    pct = cnt * 100 / len(fb)
    print(f"  0x{cv:08X}: {cnt:6d} px ({pct:5.1f}%)")

# Check if black (0xFF000000) dominates the sprite area
# Sprites are at y=112 (palette 0), y=167-184 (palette 1), y=44 (palette 3)
for check_y in [44, 112, 115, 120, 167, 175, 204]:
    if check_y >= height:
        continue
    row_start = check_y * width
    row = fb[row_start:row_start + width]
    non_bg = [(x, c & 0xFFFFFFFF) for x, c in enumerate(row) if (c & 0xFFFFFFFF) != (fb[0] & 0xFFFFFFFF)]
    if non_bg:
        unique = set(c for _, c in non_bg)
        print(f"\n  Line {check_y}: {len(non_bg)} non-bg pixels, {len(unique)} unique colors")
        for cv in sorted(unique):
            xs = [x for x, c in non_bg if c == cv]
            print(f"    0x{cv:08X}: {len(xs)} px (x={xs[0]}..{xs[-1]})")
    else:
        bg_color = fb[0] & 0xFFFFFFFF
        print(f"\n  Line {check_y}: all background (0x{bg_color:08X})")

# Save as BMP
def save_bmp(filename, w, h, pixels):
    row_size = w * 3
    pad = (4 - row_size % 4) % 4
    data_size = (row_size + pad) * h
    file_size = 54 + data_size
    
    with open(filename, 'wb') as f:
        # BMP header
        f.write(b'BM')
        f.write(struct.pack('<I', file_size))
        f.write(struct.pack('<HH', 0, 0))
        f.write(struct.pack('<I', 54))
        # DIB header
        f.write(struct.pack('<I', 40))
        f.write(struct.pack('<i', w))
        f.write(struct.pack('<i', h))
        f.write(struct.pack('<HH', 1, 24))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', data_size))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))
        
        # Pixel data (bottom-up)
        for y in range(h - 1, -1, -1):
            for x in range(w):
                argb = pixels[y * w + x] & 0xFFFFFFFF
                r = (argb >> 16) & 0xFF
                g = (argb >> 8) & 0xFF
                b = argb & 0xFF
                f.write(bytes([b, g, r]))
            f.write(b'\x00' * pad)

save_bmp('tools/current_frame.bmp', width, height, fb)
print(f"\nSaved current_frame.bmp")
