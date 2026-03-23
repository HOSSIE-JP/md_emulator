"""Analyze Plane B nametable for stripe pattern"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

regs = api("/vdp/registers")["registers"]
plane_b_addr = (regs[4] & 0x07) << 13  # 0xE000
scroll_w = 64  # from R16=0x11
scroll_h = 64

print(f"Plane B at 0x{plane_b_addr:04X}, size {scroll_w}x{scroll_h}")

# Read plane B nametable from VRAM
nt_size = scroll_w * scroll_h * 2
vram = bytes(api(f"/vdp/vram?addr={plane_b_addr}&len={nt_size}")["data"])

# Show first 40 columns x 32 rows (visible area)
print("\nPlane B nametable (first 40 cols x 28 rows):")
for row in range(28):
    tiles = []
    for col in range(40):
        offset = (row * scroll_w + col) * 2
        entry = (vram[offset] << 8) | vram[offset + 1]
        tile_idx = entry & 0x07FF
        tiles.append(tile_idx)
    # Check if this row differs from the previous
    unique = len(set(tiles))
    print(f"  Row {row:2d}: tiles {tiles[0]:4d}..{tiles[-1]:4d} unique={unique} "
          f"first8=[{','.join(str(t) for t in tiles[:8])}]")

# Check for row repeating patterns
print("\nRow comparison (which rows are identical?):")
rows_data = []
for row in range(32):
    tiles = []
    for col in range(40):
        offset = (row * scroll_w + col) * 2
        entry = (vram[offset] << 8) | vram[offset + 1]
        tiles.append(entry)
    rows_data.append(tuple(tiles))

for i in range(32):
    matches = [j for j in range(32) if j != i and rows_data[j] == rows_data[i]]
    if matches and i < matches[0]:
        print(f"  Row {i} == Rows {matches}")
