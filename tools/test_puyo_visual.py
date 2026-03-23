"""Save Puyo Puyo framebuffer as PNG image at frame 900"""
import requests, struct

BASE = "http://127.0.0.1:8113/api/v1"

def api(method, path, **kw):
    r = getattr(requests, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

# Get video frame
resp = api("get", "/video/frame")
width = resp["width"]
height = resp["height"]
pixels_argb = resp["pixels_argb"]

print(f"Frame size: {width}x{height}, pixels: {len(pixels_argb)}")

# Count non-black pixels
non_black = 0
for i in range(0, len(pixels_argb) - 3, 4):
    a, r, g, b = pixels_argb[i], pixels_argb[i+1], pixels_argb[i+2], pixels_argb[i+3]
    if r or g or b:
        non_black += 1
print(f"Non-black pixels: {non_black}/{width*height}")

# Sample some pixel colors
print("Top-left 10x1:")
for x in range(10):
    idx = x * 4
    print(f"  ({pixels_argb[idx+1]:3d},{pixels_argb[idx+2]:3d},{pixels_argb[idx+3]:3d})", end="")
print()

# Save as BMP (no PIL needed)
def save_bmp(filename, w, h, argb_pixels):
    row_size = w * 3
    pad = (4 - row_size % 4) % 4
    padded_row = row_size + pad
    pixel_data_size = padded_row * h
    file_size = 54 + pixel_data_size

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
        f.write(struct.pack('<I', 0))  # compression
        f.write(struct.pack('<I', pixel_data_size))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))

        # Pixel data (BMP is bottom-up, BGR)
        for y in range(h - 1, -1, -1):
            for x in range(w):
                idx = (y * w + x) * 4
                a = argb_pixels[idx]
                r = argb_pixels[idx + 1]
                g = argb_pixels[idx + 2]
                b = argb_pixels[idx + 3]
                f.write(bytes([b, g, r]))
            f.write(b'\x00' * pad)

save_bmp("tools/puyo_frame900.bmp", width, height, pixels_argb)
print(f"Saved tools/puyo_frame900.bmp")

# Also get a frame earlier - run to 1800 (demo play) and save
api("post", "/emulator/step", json={"frames": 900})
resp2 = api("get", "/video/frame")
save_bmp("tools/puyo_frame1800.bmp", resp2["width"], resp2["height"], resp2["pixels_argb"])
print(f"Saved tools/puyo_frame1800.bmp (frame 1800)")

# Count sprites at 1800
sat_data = api("get", "/vdp/vram", params={"addr": 0xBC00, "len": 640})
sat_bytes = bytes(sat_data["data"])
sprites = 0
idx = 0
visited = set()
while True:
    off = idx * 8
    if off + 8 > len(sat_bytes) or idx in visited:
        break
    visited.add(idx)
    entry = sat_bytes[off:off+8]
    if any(b != 0 for b in entry):
        sprites += 1
    link = entry[3] & 0x7F
    if link == 0:
        break
    idx = link
print(f"Sprites at frame 1800: {sprites}")

# Parse first 10 sprites
for i in range(min(10, sprites)):
    off = i * 8
    y = ((sat_bytes[off] << 8) | sat_bytes[off+1]) & 0x3FF
    size = sat_bytes[off+2]
    link = sat_bytes[off+3] & 0x7F
    attr = (sat_bytes[off+4] << 8) | sat_bytes[off+5]
    x = ((sat_bytes[off+6] << 8) | sat_bytes[off+7]) & 0x1FF
    h = ((size >> 2) & 3) + 1
    w = (size & 3) + 1
    tile = attr & 0x7FF
    pal = (attr >> 13) & 3
    pri = (attr >> 15) & 1
    hf = (attr >> 11) & 1
    vf = (attr >> 12) & 1
    print(f"  [{i}] Y={y-128:4d} X={x-128:4d} size={w}x{h} tile=0x{tile:03X} pal={pal} pri={pri} hf={hf} vf={vf} link={link}")
