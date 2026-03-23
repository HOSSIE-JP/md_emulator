"""Check if sprites are rendering in the frame at frame 900."""
import urllib.request, json, struct

BASE = "http://localhost:8114/api/v1"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

def save_bmp(filename, w, h, argb_pixels):
    row_bytes = w * 3
    padding = (4 - row_bytes % 4) % 4
    data_size = (row_bytes + padding) * h
    file_size = 54 + data_size
    with open(filename, 'wb') as f:
        f.write(b'BM')
        f.write(struct.pack('<I', file_size))
        f.write(b'\x00\x00\x00\x00')
        f.write(struct.pack('<I', 54))
        f.write(struct.pack('<I', 40))
        f.write(struct.pack('<i', w))
        f.write(struct.pack('<i', h))
        f.write(struct.pack('<HH', 1, 24))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', data_size))
        f.write(b'\x00' * 16)
        for y_row in range(h-1, -1, -1):
            for x_col in range(w):
                p = argb_pixels[y_row * w + x_col]
                rv = (p >> 16) & 0xFF
                gv = (p >> 8) & 0xFF
                bv = p & 0xFF
                f.write(bytes([bv, gv, rv]))
            f.write(b'\x00' * padding)

# Reset and load ROM
print("=== Reset & Load ===")
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step to frame 900
api_post("/emulator/step", {"frames": 900})

# Get VDP state
regs = api_get("/vdp/registers")
r = regs['registers']
sat_addr = (r[5] & 0x7F) << 9
h40 = (r[0x0C] & 0x81) != 0
screen_w = 320 if h40 else 256
print(f"H40: {h40}, screen: {screen_w}x224")
print(f"SAT base: 0x{sat_addr:04X}")

# Get sprites via API
sprites = api_get("/vdp/sprites")
spr_list = sprites.get('sprites', [])
print(f"\nSprites in chain: {len(spr_list)}")
for s in spr_list[:30]:
    print(f"  #{s['index']:2d}: pos=({s['x']:4d},{s['y']:4d}) {s['width']}x{s['height']} tile=0x{s['tile']:03X} pal={s['palette']} pri={s['priority']} link={s['link']}")

# Get frame
frame = api_get("/video/frame")
width = frame['width']
height = frame['height']
pixels = frame['pixels_argb']
non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"\nFrame: {width}x{height}, {non_black}/{len(pixels)} non-black pixels")

# Check pixels at sprite positions
print("\n=== Pixel check at sprite positions ===")
for s in spr_list[:15]:
    sx, sy = s['x'], s['y']
    sw, sh = s['width'] * 8, s['height'] * 8
    # Check center of sprite
    cx = sx + sw // 2
    cy = sy + sh // 2
    if 0 <= cx < width and 0 <= cy < height:
        p = pixels[cy * width + cx]
        r_val = (p >> 16) & 0xFF
        g_val = (p >> 8) & 0xFF
        b_val = p & 0xFF
        print(f"  Sprite #{s['index']:2d} center ({cx:3d},{cy:3d}): RGB=({r_val},{g_val},{b_val}) {'NON-BLACK' if (p & 0xFFFFFF) != 0 else 'BLACK'}")
    else:
        print(f"  Sprite #{s['index']:2d} center ({cx:3d},{cy:3d}): OFFSCREEN")

# Check tile data for first visible sprite
print("\n=== Tile check for visible sprites ===")
for s in spr_list[:15]:
    if s['x'] >= 0 and s['y'] >= 0 and s['x'] < screen_w and s['y'] < 224:
        tile = s['tile']
        tile_addr = tile * 32
        total_cells = s['width'] * s['height']
        tile_bytes = total_cells * 32
        resp = api_get(f"/vdp/vram?addr={tile_addr}&len={tile_bytes}")
        data = resp.get('data', [])
        nz = sum(1 for b in data if b != 0)
        print(f"  Sprite #{s['index']:2d} tile=0x{tile:03X} vram=0x{tile_addr:05X}: {nz}/{len(data)} non-zero bytes")

# Save frame
save_bmp("tools/puyo_f900_check.bmp", width, height, pixels)
print(f"\nSaved tools/puyo_f900_check.bmp")

# Also get the CRAM colors to see what palettes look like
colors = api_get("/vdp/colors")
clist = colors.get('colors_argb', colors.get('colors', []))
if clist:
    print(f"\n=== CRAM Palettes ===")
    for p in range(4):
        entries = []
        for i in range(16):
            c = clist[p*16+i]
            rv = (c >> 16) & 0xFF
            gv = (c >> 8) & 0xFF
            bv = c & 0xFF
            if rv or gv or bv:
                entries.append(f"{i}:({rv},{gv},{bv})")
        if entries:
            print(f"  Pal {p}: {' '.join(entries)}")

print("\nDone!")
