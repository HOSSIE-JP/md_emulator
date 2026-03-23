"""
Comprehensive VRAM diagnostic: find where tile data lives vs where sprites expect it.
Uses correct API: /vdp/vram?addr=0&len=65536
"""
import urllib.request
import json

BASE = "http://localhost:8114/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# 1. Get sprites
sprites = api("/vdp/sprites")["sprites"]
print(f"=== {len(sprites)} sprites ===")
for s in sprites[:10]:
    print(f"  idx={s['index']} x={s['x']} y={s['y']} tile={s['tile']} "
          f"w={s['width']} h={s['height']} pal={s['palette']} pri={s['priority']} link={s['link']}")

# 2. Get full VRAM (64KB) as raw byte array
vram_data = api("/vdp/vram?addr=0&len=65536")
vram = bytes(vram_data["data"])
print(f"\nVRAM size: {len(vram)} bytes")

# 3. Get registers
regs = api("/vdp/registers")
reg_vals = regs.get("registers") or regs.get("values") or regs
if isinstance(reg_vals, list):
    reg5 = reg_vals[5] if len(reg_vals) > 5 else 0
else:
    reg5 = reg_vals.get("5", 0)
sat_base = (reg5 & 0x7F) << 9
print(f"Register 5 = 0x{reg5:02X}, SAT base = 0x{sat_base:04X}")

# 4. Check SAT data directly from VRAM
print(f"\n=== SAT entries from VRAM at 0x{sat_base:04X} ===")
link = 0
for _ in range(80):
    base_addr = sat_base + link * 8
    if base_addr + 7 >= len(vram):
        break
    y_raw = (vram[base_addr] << 8) | vram[base_addr + 1]
    y_pos = (y_raw & 0x03FF) - 128
    size_byte = vram[base_addr + 2]
    h_cells = ((size_byte >> 2) & 3) + 1
    v_cells = (size_byte & 3) + 1
    next_link = vram[base_addr + 3] & 0x7F
    attr = (vram[base_addr + 4] << 8) | vram[base_addr + 5]
    x_raw = (vram[base_addr + 6] << 8) | vram[base_addr + 7]
    x_pos = (x_raw & 0x1FF) - 128
    tile_index = attr & 0x07FF
    palette = (attr >> 13) & 3
    priority = (attr >> 15) & 1
    hflip = (attr >> 11) & 1
    vflip = (attr >> 12) & 1

    tile_addr = tile_index * 32
    # Count nonzero bytes in first tile
    first_tile_nz = sum(1 for b in vram[tile_addr:tile_addr+32] if b != 0)
    # Count across all tiles of this sprite
    total_tiles = h_cells * v_cells
    all_tile_nz = 0
    for c in range(h_cells):
        for r in range(v_cells):
            t = tile_index + c * v_cells + r
            ta = t * 32
            all_tile_nz += sum(1 for b in vram[ta:ta+32] if b != 0)

    print(f"  [{link:2d}] y={y_pos:4d} x={x_pos:4d} sz={h_cells}x{v_cells} "
          f"tile={tile_index:4d}(0x{tile_index:03X}) @0x{tile_addr:05X} "
          f"pal={palette} pri={priority} hf={hflip} vf={vflip} link={next_link} "
          f"1st_nz={first_tile_nz}/32 all_nz={all_tile_nz}/{total_tiles*32}")
    
    link = next_link
    if link == 0:
        break

# 5. SCAN entire VRAM for non-zero regions
print("\n=== VRAM non-zero regions (tile granularity) ===")
tile_ranges = []
in_range = False
range_start = -1
for tile_num in range(0, len(vram) // 32):
    addr = tile_num * 32
    has_data = any(vram[addr + b] != 0 for b in range(32))
    if has_data and not in_range:
        range_start = tile_num
        in_range = True
    elif not has_data and in_range:
        tile_ranges.append((range_start, tile_num - 1))
        in_range = False
if in_range:
    tile_ranges.append((range_start, len(vram) // 32 - 1))

for start_t, end_t in tile_ranges:
    count = end_t - start_t + 1
    start_addr = start_t * 32
    end_addr = (end_t + 1) * 32
    total_nonzero = sum(1 for b in vram[start_addr:end_addr] if b != 0)
    print(f"  Tiles {start_t:4d}..{end_t:4d} ({count:4d} tiles) "
          f"addr 0x{start_addr:05X}..0x{end_addr-1:05X} nz={total_nonzero}")

# 6. Collect all sprite tile refs
print("\n=== Sprite tile vs data summary ===")
sprite_tiles_set = set()
for s in sprites:
    tile = s['tile']
    h_cells = s['width'] // 8
    v_cells = s['height'] // 8
    for c in range(h_cells):
        for r in range(v_cells):
            sprite_tiles_set.add(tile + c * v_cells + r)

with_data = 0
without_data = 0
for t in sorted(sprite_tiles_set):
    addr = t * 32
    if addr + 32 <= len(vram):
        has = any(vram[addr + b] != 0 for b in range(32))
        if has:
            with_data += 1
        else:
            without_data += 1

print(f"Total unique sprite tiles: {len(sprite_tiles_set)}")
print(f"  WITH data: {with_data}")
print(f"  WITHOUT data: {without_data}")
if sprite_tiles_set:
    min_t = min(sprite_tiles_set)
    max_t = max(sprite_tiles_set)
    print(f"  Range: tiles {min_t}..{max_t} (0x{min_t*32:05X}..0x{max_t*32:05X})")

# 7. Hex dump of first 3 sprite tile addresses
print("\n=== Hex dump of first 3 sprite tile addrs ===")
for t in sorted(sprite_tiles_set)[:3]:
    addr = t * 32
    data = vram[addr:addr+32]
    row1 = ' '.join(f'{b:02X}' for b in data[:16])
    row2 = ' '.join(f'{b:02X}' for b in data[16:32])
    print(f"  Tile {t:4d} (0x{addr:05X}): {row1}")
    print(f"                        {row2}")

# 8. Check non-zero VRAM regions that overlap sprite tile range
if sprite_tiles_set:
    min_addr = min(sprite_tiles_set) * 32
    max_addr = (max(sprite_tiles_set) + 1) * 32
    print(f"\n=== VRAM in sprite tile range 0x{min_addr:05X}..0x{max_addr:05X} ===")
    nz_in_range = sum(1 for b in vram[min_addr:max_addr] if b != 0)
    print(f"  Non-zero bytes: {nz_in_range}/{max_addr - min_addr}")
    
    # Sample: check every 256th byte for pattern
    print("  Sampling every 1024 bytes:")
    for off in range(min_addr, min(max_addr, min_addr + 32768), 1024):
        chunk = vram[off:off+16]
        nz = sum(1 for b in chunk if b != 0)
        if nz > 0:
            print(f"    0x{off:05X}: {' '.join(f'{b:02X}' for b in chunk)} nz={nz}")

# 9. CRAM check
print("\n=== CRAM check ===")
cram_data = api("/vdp/cram")
cram_colors = cram_data.get("colors_argb") or cram_data.get("colors") or []
non_black = [i for i, c in enumerate(cram_colors) if c != 0xFF000000 and c != 0]
print(f"Non-black CRAM entries: {len(non_black)} / {len(cram_colors)}")
for i in non_black[:16]:
    print(f"  CRAM[{i}] = 0x{cram_colors[i]:08X}")

# 10. Check if plane tiles reference data in expected locations
# to see if BG planes work properly
print("\n=== Plane A nametable sample ===")
if isinstance(reg_vals, list):
    reg2 = reg_vals[2] if len(reg_vals) > 2 else 0
else:
    reg2 = reg_vals.get("2", 0)
scroll_a_addr = (reg2 & 0x38) << 10
print(f"Register 2 = 0x{reg2:02X}, Scroll A base = 0x{scroll_a_addr:04X}")
for row in range(2):
    for col in range(5):
        entry_addr = scroll_a_addr + (row * 64 + col) * 2  # assuming 64-wide
        if entry_addr + 1 < len(vram):
            entry = (vram[entry_addr] << 8) | vram[entry_addr + 1]
            tile_idx = entry & 0x07FF
            pal = (entry >> 13) & 3
            pri = (entry >> 15) & 1
            tile_nz = sum(1 for b in vram[tile_idx*32:(tile_idx+1)*32] if b != 0)
            print(f"  [{row},{col}] entry=0x{entry:04X} tile={tile_idx} pal={pal} pri={pri} tile_nz={tile_nz}/32")
