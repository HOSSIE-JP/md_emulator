"""Check tile 3FE/3FF and surrounding VRAM area"""
import urllib.request, json

BASE = "http://127.0.0.1:8117/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    d = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=d,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

# Fresh reset
post("/emulator/reset")

# Step to frame 3000
for i in range(30):
    post("/emulator/step", {"frames": 100})
print("At frame ~3000")

# Check VRAM area around tiles 3FE/3FF (addresses 0x7F00-0x8000)
# Read a larger chunk
vram_resp = get("/vdp/vram?addr=32640&len=128")  # 0x7F80 = 32640
data = vram_resp.get("data") or vram_resp.get("vram")
print(f"\nVRAM 0x7F80-0x7FFF ({len(data)} bytes):")
for i in range(0, len(data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
    addr = 0x7F80 + i
    print(f"  {addr:04X}: {hex_str}")

# Check VRAM area 0x7FC0-0x7FFF (tiles 3FE-3FF)
print(f"\nTile 0x3FE (0x7FC0-0x7FDF):")
for row in range(8):
    off = 0x40 + row * 4  # offset within our read (0x7FC0 - 0x7F80 = 0x40)
    if off + 3 < len(data):
        row_data = data[off:off+4]
        pixels = []
        for b in row_data:
            pixels.append(b >> 4)
            pixels.append(b & 0x0F)
        print(f"  Row {row}: {pixels}")

print(f"\nTile 0x3FF (0x7FE0-0x7FFF):")
for row in range(8):
    off = 0x60 + row * 4
    if off + 3 < len(data):
        row_data = data[off:off+4]
        pixels = []
        for b in row_data:
            pixels.append(b >> 4)
            pixels.append(b & 0x0F)
        print(f"  Row {row}: {pixels}")

# Get CRAM palette 0 (used by tile 83FE)
cram = get("/vdp/colors")
colors = cram["colors_argb"]
print("\nCRAM Palette 0:")
for i in range(16):
    c = colors[i]
    r = (c >> 16) & 0xFF
    g = (c >> 8) & 0xFF
    b = c & 0xFF
    print(f"  [{i:2d}] #{r:02x}{g:02x}{b:02x}")

# Check BG color
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")
bg_reg = rdata[7]
bg_pal = (bg_reg >> 4) & 3
bg_idx = bg_reg & 0x0F
print(f"\nBG: palette {bg_pal}, index {bg_idx}")
bg_c = colors[bg_pal * 16 + bg_idx]
bg_r = (bg_c >> 16) & 0xFF
bg_g = (bg_c >> 8) & 0xFF
bg_b = bg_c & 0xFF
print(f"BG color: #{bg_r:02x}{bg_g:02x}{bg_b:02x}")

# Now let's look at what Plane B looks like in the field area
# Plane B is at 0xE000, 64x64 cells
# The field area starts at row 2 (y=16)
# Let's check Plane B rows 2-10, cols 2-10 (inside the field border)
plane_b_addr = 0xE000
vram2 = get(f"/vdp/vram?addr={plane_b_addr + 64*2*2}&len={64*9*2}")  # rows 2-10
pdata = vram2.get("data") or vram2.get("vram")
print(f"\nPlane B nametable rows 2-10, cols 2-20:")
for row in range(9):
    tiles = []
    for col in range(2, min(20, 64)):
        off = (row * 64 + col) * 2
        if off + 1 < len(pdata):
            entry = (pdata[off] << 8) | pdata[off+1]
            tile_idx = entry & 0x07FF
            pal = (entry >> 13) & 3
            pri = (entry >> 15) & 1
            tiles.append(f"{tile_idx:03X}p{pal}{'P' if pri else ' '}")
    print(f"  row {row+2:2d}: {' '.join(tiles[:10])}")

# Check one of the Plane B field-area tiles to see if it's transparent too
# e.g., tile at row 2, col 2 of Plane B
off = 0 * 2  # col 2 is at offset 0 in our read (we started from col 0 of row 2)
entry = (pdata[2*2] << 8) | pdata[2*2+1]  # col 2 of row 2
tile_idx = entry & 0x07FF
pal = (entry >> 13) & 3
print(f"\nPlane B row 2, col 2: tile=0x{tile_idx:03X}, palette={pal}")
addr = tile_idx * 32
vram3 = get(f"/vdp/vram?addr={addr}&len=32")
tdata = vram3.get("data") or vram3.get("vram")
non_zero = sum(1 for b in tdata if b != 0)
print(f"  Non-zero bytes: {non_zero}/32")
if non_zero > 0:
    for row in range(8):
        row_data = tdata[row*4:row*4+4]
        pixels = []
        for b in row_data:
            pixels.append(b >> 4)
            pixels.append(b & 0x0F)
        print(f"  Row {row}: {pixels}")
