"""Save Puyo Puyo framebuffer as PNG image at frame 900"""
import requests, struct

BASE = "http://127.0.0.1:8113/api/v1"

def api(method, path, **kw):
    r = getattr(requests, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

# Get video frame (pixels_argb is array of u32 ARGB values)
resp = api("get", "/video/frame")
width = resp["width"]
height = resp["height"]
pixels_argb = resp["pixels_argb"]  # array of u32

print(f"Frame size: {width}x{height}, pixel count: {len(pixels_argb)}")

# Count non-black
non_black = 0
for p in pixels_argb:
    r = (p >> 16) & 0xFF
    g = (p >> 8) & 0xFF
    b = p & 0xFF
    if r or g or b:
        non_black += 1
print(f"Non-black pixels: {non_black}/{width*height}")

# Sample colors
print("Top-left 5 pixels (R,G,B):")
for x in range(5):
    p = pixels_argb[x]
    r = (p >> 16) & 0xFF
    g = (p >> 8) & 0xFF
    b = p & 0xFF
    print(f"  ({r},{g},{b})", end="")
print()

def save_bmp(filename, w, h, argb_u32_pixels):
    row_size = w * 3
    pad = (4 - row_size % 4) % 4
    padded_row = row_size + pad
    pixel_data_size = padded_row * h
    file_size = 54 + pixel_data_size

    with open(filename, 'wb') as f:
        f.write(b'BM')
        f.write(struct.pack('<I', file_size))
        f.write(struct.pack('<HH', 0, 0))
        f.write(struct.pack('<I', 54))
        f.write(struct.pack('<I', 40))
        f.write(struct.pack('<i', w))
        f.write(struct.pack('<i', h))
        f.write(struct.pack('<HH', 1, 24))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', pixel_data_size))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<i', 2835))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', 0))

        for y in range(h - 1, -1, -1):
            for x in range(w):
                p = argb_u32_pixels[y * w + x]
                r = (p >> 16) & 0xFF
                g = (p >> 8) & 0xFF
                b = p & 0xFF
                f.write(bytes([b, g, r]))
            f.write(b'\x00' * pad)

save_bmp("tools/puyo_frame900.bmp", width, height, pixels_argb)
print(f"Saved tools/puyo_frame900.bmp")

# Run to 1800 (demo) 
api("post", "/emulator/step", json={"frames": 900})
resp2 = api("get", "/video/frame")
save_bmp("tools/puyo_frame1800.bmp", resp2["width"], resp2["height"], resp2["pixels_argb"])
print(f"Saved tools/puyo_frame1800.bmp")

# Non-black at 1800
nb2 = sum(1 for p in resp2["pixels_argb"] if (p & 0xFFFFFF) != 0)
print(f"Non-black at 1800: {nb2}/{width*height}")

# Sprites at 1800
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
    sprites += 1
    link = sat_bytes[off+3] & 0x7F
    if link == 0:
        break
    idx = link
print(f"Sprite chain at 1800: {sprites}")

for i in range(min(10, len(sat_bytes)//8)):
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
    print(f"  [{i}] Y={y-128:4d} X={x-128:4d} {w}x{h} tile=0x{tile:03X} p{pal} pri={pri} link={link}")

# DMA stats at 1800
vdp = api("get", "/vdp/registers")
print(f"\nDMA count: {vdp.get('dma_68k_count')}")
print(f"DMA total words: {vdp.get('dma_68k_total_words')}")
print(f"Last DMA: target=0x{vdp.get('last_dma_target_addr',0):04X} src=0x{vdp.get('last_dma_source',0):06X} len={vdp.get('last_dma_length',0)}")
