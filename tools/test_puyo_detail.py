"""Detailed sprite/SAT/rendering analysis at frame 900"""
import urllib.request
import json

BASE = "http://127.0.0.1:8111"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# The ROM is already loaded from prior test, just continue

# Get frame pixels and analyze row by row
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
print("=== Row-by-row analysis (every 8th row) ===")
for y in range(0, 224, 8):
    row = pixels[y*320:(y+1)*320]
    unique = set(row)
    nb = sum(1 for p in row if (p & 0xFFFFFF) != 0)
    if len(unique) > 1:
        print(f"Row {y:3d}: {len(unique):2d} colors, {nb:3d}/320 non-black")

# Check SAT in detail - dump all 80 entries raw
r = api("GET", "/api/v1/vdp/registers")
regs = r["registers"]
sat_addr = (regs[5] & 0x7F) << 9
print(f"\n=== SAT at 0x{sat_addr:04X} ===")
r = api("GET", f"/api/v1/vdp/vram?addr={sat_addr}&len=640")
sat_data = r.get("data", [])

# Follow linked list
link = 0
chain = []
for i in range(80):
    base = link * 8
    if base + 7 >= len(sat_data):
        print(f"SAT link out of range: link={link}")
        break
    entry = sat_data[base:base+8]
    y_pos = ((entry[0] << 8) | entry[1]) & 0x3FF
    sz = entry[2]
    next_link = entry[3] & 0x7F
    attr = (entry[4] << 8) | entry[5]
    x_pos = ((entry[6] << 8) | entry[7]) & 0x1FF
    
    sprite_y = y_pos - 128
    sprite_x = x_pos - 128
    h_cells = ((sz >> 2) & 3) + 1
    v_cells = (sz & 3) + 1
    tile = attr & 0x7FF
    pal = (attr >> 13) & 3
    pri = (attr >> 15) & 1
    hf = (attr >> 11) & 1
    vf = (attr >> 12) & 1
    
    chain.append(link)
    print(f"  SAT[{link:2d}] raw=[{' '.join(f'{b:02X}' for b in entry)}] "
          f"y={sprite_y:4d} x={sprite_x:4d} {h_cells}x{v_cells} tile=0x{tile:03X} "
          f"pal={pal} pri={pri} hf={hf} vf={vf} link={next_link}")
    
    if next_link == 0:
        break
    link = next_link

print(f"\nSprite chain: {chain}")
print(f"Chain length: {len(chain)}")

# Check what tiles are at tile indices used by SAT
print("\n=== Tile data check ===")
for idx in chain[:5]:
    base = idx * 8
    entry = sat_data[base:base+8]
    attr = (entry[4] << 8) | entry[5]
    tile = attr & 0x7FF
    tile_addr = tile * 32
    r_tile = api("GET", f"/api/v1/vdp/vram?addr={tile_addr}&len=32")
    tile_data = r_tile.get("data", [])
    nz = sum(1 for b in tile_data if b != 0)
    print(f"  Sprite[{idx}] tile 0x{tile:03X} @ 0x{tile_addr:04X}: {nz}/32 non-zero bytes")

# Check VRAM around SAT region
print(f"\n=== VRAM around SAT 0x{sat_addr:04X} ===")
r = api("GET", f"/api/v1/vdp/vram?addr={sat_addr}&len=64")
raw = r.get("data", [])
print("First 64 bytes:")
for row in range(4):
    offset = row * 16
    hex_str = ' '.join(f'{raw[offset+i]:02X}' for i in range(16))
    print(f"  0x{sat_addr + offset:04X}: {hex_str}")
