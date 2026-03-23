"""Comprehensive sprite rendering diagnostic for Puyo Puyo."""
import urllib.request, json, struct, sys

BASE = "http://localhost:8113/api/v1"

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

# Reset and load ROM fresh
print("=== Resetting emulator ===")
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step to frame 900 (demo screen should be active)
print("Stepping to frame 900...")
result = api_post("/emulator/step", {"frames": 900})
print(f"Step result: frame={result.get('frame')}, cycles={result.get('total_cycles')}")

# Get VDP registers
regs = api_get("/vdp/registers")
print(f"\n=== VDP Registers ===")
if 'registers' in regs:
    r = regs['registers']
    print(f"  Reg 0x00: 0x{r[0]:02X}  (HInt enable: {(r[0]&0x10)!=0})")
    print(f"  Reg 0x01: 0x{r[1]:02X}  (Display enable: {(r[1]&0x40)!=0}, VInt enable: {(r[1]&0x20)!=0}, DMA: {(r[1]&0x10)!=0})")
    print(f"  Reg 0x02: 0x{r[2]:02X}  (Scroll A addr: 0x{((r[2]&0x38)<<10):04X})")
    print(f"  Reg 0x03: 0x{r[3]:02X}  (Window addr: 0x{((r[3]&0x3E)<<10):04X})")
    print(f"  Reg 0x04: 0x{r[4]:02X}  (Scroll B addr: 0x{((r[4]&0x07)<<13):04X})")
    print(f"  Reg 0x05: 0x{r[5]:02X}  (SAT addr: 0x{((r[5]&0x7F)<<9):04X})")
    print(f"  Reg 0x07: 0x{r[7]:02X}  (BG color: pal {r[7]>>4}, idx {r[7]&0x0F})")
    print(f"  Reg 0x0A: 0x{r[10]:02X} (HInt counter: {r[10]})")
    print(f"  Reg 0x0B: 0x{r[11]:02X} (Scroll mode: H={r[11]&3}, V={(r[11]>>2)&1})")
    print(f"  Reg 0x0C: 0x{r[12]:02X} (H40: {(r[12]&0x81)!=0})")
    print(f"  Reg 0x0D: 0x{r[13]:02X} (HScroll addr: 0x{((r[13]&0x3F)<<10):04X})")
    print(f"  Reg 0x0F: 0x{r[15]:02X} (Auto-increment: {r[15]})")
    print(f"  Reg 0x10: 0x{r[16]:02X} (Scroll size: W={[32,64,32,128][r[16]&3]}, H={[32,64,32,128][(r[16]>>4)&3]})")
    sat_addr = (r[5] & 0x7F) << 9
else:
    print("  No register data")
    sys.exit(1)

# Get DMA debug info
for k in ['dma_68k_count', 'dma_68k_total_words', 'dma_fill_count', 'dma_copy_count',
          'last_dma_target_addr', 'last_dma_source', 'last_dma_length']:
    if k in regs:
        v = regs[k]
        if isinstance(v, int) and v > 255:
            print(f"  {k}: {v} (0x{v:X})")
        else:
            print(f"  {k}: {v}")

# Get sprites
sprites = api_get("/vdp/sprites")
print(f"\n=== Sprites ({len(sprites.get('sprites',[]))} in chain) ===")
for s in sprites.get('sprites', []):
    print(f"  #{s['index']:2d}: pos=({s['x']:4d},{s['y']:4d}) size={s['width']}x{s['height']} tile=0x{s['tile']:03X} pal={s['palette']} pri={s['priority']} hf={s['hflip']} vf={s['vflip']} link={s['link']}")
    # Check tile data in VRAM
    tile_vram_addr = s['tile'] * 32
    tile_size_bytes = s['width'] * s['height'] * 32  # total bytes for all cells

# Get VRAM for SAT and sprite tile data
print(f"\n=== VRAM SAT at 0x{sat_addr:04X} ===")
vram_resp = api_get(f"/vdp/vram?address={sat_addr}&length=640")  # 80 sprites * 8 bytes
if 'data' in vram_resp:
    vram_hex = vram_resp['data']
    vram_bytes = bytes.fromhex(vram_hex)
    # Parse first 10 SAT entries
    for i in range(min(10, len(vram_bytes)//8)):
        off = i * 8
        y_pos = (vram_bytes[off] << 8 | vram_bytes[off+1]) & 0x3FF
        size_byte = vram_bytes[off+2]
        hcells = ((size_byte >> 2) & 3) + 1
        vcells = (size_byte & 3) + 1
        link = vram_bytes[off+3] & 0x7F
        attr = (vram_bytes[off+4] << 8) | vram_bytes[off+5]
        x_pos = ((vram_bytes[off+6] << 8) | vram_bytes[off+7]) & 0x1FF
        tile = attr & 0x7FF
        pal = (attr >> 13) & 3
        pri = (attr >> 15) & 1
        print(f"  SAT[{i}]: Y={y_pos}({y_pos-128:+d}) X={x_pos}({x_pos-128:+d}) size={hcells}x{vcells} tile=0x{tile:03X}(VRAM:0x{tile*32:05X}) pal={pal} pri={pri} link={link}")

# Check tile data for first few sprites from chain
print(f"\n=== Sprite Tile Data Check ===")
for s in sprites.get('sprites', [])[:5]:
    tile_addr = s['tile'] * 32
    tile_bytes = s['width'] * s['height'] * 32
    vram_tile = api_get(f"/vdp/vram?address={tile_addr}&length={tile_bytes}")
    if 'data' in vram_tile:
        data = bytes.fromhex(vram_tile['data'])
        nonzero = sum(1 for b in data if b != 0)
        print(f"  Sprite #{s['index']} tile=0x{s['tile']:03X} VRAM=0x{tile_addr:05X}: {nonzero}/{len(data)} bytes non-zero")
        if nonzero > 0:
            # Show first tile's first few rows
            for row in range(min(4, 8)):
                row_data = data[row*4:(row+1)*4]
                pixels = []
                for b in row_data:
                    pixels.append(b >> 4)
                    pixels.append(b & 0x0F)
                print(f"    row {row}: {pixels}")
    else:
        print(f"  Sprite #{s['index']} - no VRAM data returned")

# Get frame and analyze pixel coverage
print(f"\n=== Frame Analysis ===")
frame = api_get("/video/frame")
width = frame['width']
height = frame['height']
pixels = frame['pixels_argb']
print(f"  Size: {width}x{height}")

# Count non-black pixels
non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"  Non-black pixels: {non_black}/{len(pixels)}")

# Check specific sprite positions for pixel data
for s in sprites.get('sprites', [])[:5]:
    sx, sy = s['x'], s['y']
    sw, sh = s['width'] * 8, s['height'] * 8
    if 0 <= sx < width and 0 <= sy < height:
        # Check center of sprite
        cx = min(sx + sw//2, width-1)
        cy = min(sy + sh//2, height-1)
        if cx >= 0 and cy >= 0:
            p = pixels[cy * width + cx]
            r = (p >> 16) & 0xFF
            g = (p >> 8) & 0xFF
            b = p & 0xFF
            print(f"  Sprite #{s['index']} center ({cx},{cy}): RGB=({r},{g},{b}) raw=0x{p:08X}")

# Save BMP
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
                r_val = (p >> 16) & 0xFF
                g_val = (p >> 8) & 0xFF
                b_val = p & 0xFF
                f.write(bytes([b_val, g_val, r_val]))
            f.write(b'\x00' * padding)

save_bmp("tools/puyo_diag_f900.bmp", width, height, pixels)
print(f"\n  Saved frame to tools/puyo_diag_f900.bmp")

# Also get CRAM colors
colors = api_get("/vdp/colors")
if 'colors' in colors:
    print(f"\n=== CRAM Colors ===")
    for p in range(4):
        pal_str = ""
        for i in range(16):
            c = colors['colors'][p*16+i]
            r_val = (c >> 16) & 0xFF
            g_val = (c >> 8) & 0xFF
            b_val = c & 0xFF
            if r_val or g_val or b_val:
                pal_str += f" {i}:({r_val},{g_val},{b_val})"
        print(f"  Pal {p}:{pal_str}")

print("\nDone!")
