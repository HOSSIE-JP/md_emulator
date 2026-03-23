"""Comprehensive sprite rendering diagnostic for Puyo Puyo."""
import urllib.request, json, struct, sys

BASE = "http://localhost:8114/api/v1"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def get_vram(addr, length):
    return api_get(f"/vdp/vram?addr={addr}&len={length}")

# Reset and load ROM fresh
print("=== Resetting emulator ===")
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step to frame 900
print("Stepping to frame 900...")
result = api_post("/emulator/step", {"frames": 900})
print(f"Step result: {result}")

# Get VDP registers
regs = api_get("/vdp/registers")
r = regs['registers']
sat_addr = (r[5] & 0x7F) << 9
print(f"\n=== VDP Setup ===")
print(f"  SAT base: 0x{sat_addr:04X}")
print(f"  Scroll A: 0x{((r[2]&0x38)<<10):04X}")
print(f"  Scroll B: 0x{((r[4]&0x07)<<13):04X}")
print(f"  Reg 0x0A HInt: {r[10]}")
print(f"  H40: {(r[12]&0x81)!=0}")
print(f"  DMA count: {regs.get('dma_68k_count',0)}")

# Get sprites
sprites = api_get("/vdp/sprites")
spr_list = sprites.get('sprites', [])
print(f"\n=== Sprites ({len(spr_list)} in chain) ===")
for s in spr_list:
    print(f"  #{s['index']:2d}: pos=({s['x']:4d},{s['y']:4d}) size={s['width']}x{s['height']} tile=0x{s['tile']:03X}(vram=0x{s['tile']*32:05X}) pal={s['palette']} pri={s['priority']}")

# Check tile data for each sprite
print(f"\n=== Sprite Tile Data ===")
for s in spr_list[:10]:
    tile_addr = s['tile'] * 32
    total_cells = s['width'] * s['height']
    tile_bytes = total_cells * 32
    resp = get_vram(tile_addr, tile_bytes)
    data = resp.get('data', [])
    nonzero = sum(1 for b in data if b != 0)
    print(f"  Sprite #{s['index']:2d} tile=0x{s['tile']:03X} vram=0x{tile_addr:05X} cells={total_cells}: {nonzero}/{len(data)} bytes non-zero")
    if nonzero > 0:
        # Show first cell, first 4 rows
        for row in range(min(4, 8)):
            row_data = data[row*4:(row+1)*4]
            pixels = []
            for b in row_data:
                pixels.append(b >> 4)
                pixels.append(b & 0x0F)
            print(f"    row {row}: {pixels}")
    elif nonzero == 0 and s['tile'] != 0:
        # The tile data is empty! Let's check nearby VRAM
        # Look around the expected address
        print(f"    EMPTY! Checking nearby VRAM areas...")
        for check_off in [0, 0x20, -0x20, 0x100, -0x100]:
            check_addr = tile_addr + check_off
            if check_addr >= 0 and check_addr < 0x10000:
                nearby = get_vram(check_addr, 32)
                nz = sum(1 for b in nearby.get('data',[]) if b != 0)
                if nz > 0:
                    print(f"    VRAM 0x{check_addr:05X}: {nz}/32 non-zero")

# Check what's actually in VRAM around sprite tile areas
print(f"\n=== VRAM Non-zero regions scan ===")
for region_start in range(0, 0x10000, 0x1000):
    resp = get_vram(region_start, 0x1000)
    data = resp.get('data', [])
    nonzero = sum(1 for b in data if b != 0)
    if nonzero > 0:
        print(f"  0x{region_start:05X}-0x{region_start+0xFFF:05X}: {nonzero}/4096 bytes non-zero ({nonzero*100//4096}%)")

# Get frame and save BMP
print(f"\n=== Frame Output ===")
frame = api_get("/video/frame")
width = frame['width']
height = frame['height']
pixels = frame['pixels_argb']
non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"  {width}x{height}, {non_black}/{len(pixels)} non-black")

# Check sprite positions for pixel values
for s in spr_list[:5]:
    sx, sy = s['x'], s['y']
    sw, sh = s['width'] * 8, s['height'] * 8
    if 0 <= sx < width and 0 <= sy < height:
        cx = min(sx + sw//2, width-1)
        cy = min(sy + sh//2, height-1)
        if cx >= 0 and cy >= 0:
            p = pixels[cy * width + cx]
            r_val = (p >> 16) & 0xFF
            g_val = (p >> 8) & 0xFF
            b_val = p & 0xFF
            print(f"  Sprite #{s['index']} center ({cx},{cy}): RGB=({r_val},{g_val},{b_val}) 0x{p:08X}")

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

save_bmp("tools/puyo_diag_f900.bmp", width, height, pixels)
print(f"  Saved tools/puyo_diag_f900.bmp")

# CRAM colors
colors = api_get("/vdp/colors")
if 'colors' in colors:
    print(f"\n=== CRAM ===")
    for p in range(4):
        entries = []
        for i in range(16):
            c = colors['colors'][p*16+i]
            rv = (c >> 16) & 0xFF
            gv = (c >> 8) & 0xFF
            bv = c & 0xFF
            if rv or gv or bv:
                entries.append(f"{i}:({rv},{gv},{bv})")
        if entries:
            print(f"  Pal {p}: {' '.join(entries)}")

print("\nDone!")

