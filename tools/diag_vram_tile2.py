"""
Comprehensive VRAM diagnostic: find where tile data actually lives vs where sprites expect it.
"""
import urllib.request
import json
import base64

BASE = "http://localhost:8114/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# 1. Get sprites
sprites = api("/vdp/sprites")["sprites"]
print(f"=== {len(sprites)} sprites ===")
for s in sprites[:5]:
    print(f"  idx={s['index']} x={s['x']} y={s['y']} tile={s['tile']} "
          f"w={s['width']} h={s['height']} pal={s['palette']} pri={s['priority']} "
          f"hflip={s['hflip']} vflip={s['vflip']} link={s['link']}")

# 2. Get VRAM
vram_data = api("/vdp/vram")
vram_b64 = vram_data.get("base64") or vram_data.get("vram_base64") or vram_data.get("data")
if isinstance(vram_b64, str):
    vram = base64.b64decode(vram_b64)
else:
    print("ERROR: Cannot decode VRAM, keys:", list(vram_data.keys()))
    exit(1)
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

# 4. Check SAT data directly in VRAM
print(f"\n=== SAT entries from VRAM at 0x{sat_base:04X} ===")
for i in range(10):
    base_addr = sat_base + i * 8
    if base_addr + 7 >= len(vram):
        break
    y_raw = (vram[base_addr] << 8) | vram[base_addr + 1]
    y_pos = (y_raw & 0x03FF) - 128
    size_byte = vram[base_addr + 2]
    h_cells = ((size_byte >> 2) & 3) + 1
    v_cells = (size_byte & 3) + 1
    link = vram[base_addr + 3] & 0x7F
    attr = (vram[base_addr + 4] << 8) | vram[base_addr + 5]
    x_raw = (vram[base_addr + 6] << 8) | vram[base_addr + 7]
    x_pos = (x_raw & 0x1FF) - 128
    tile_index = attr & 0x07FF
    palette = (attr >> 13) & 3
    priority = (attr >> 15) & 1
    hflip = (attr >> 11) & 1
    vflip = (attr >> 12) & 1
    
    tile_addr = tile_index * 32
    tile_data_nonzero = sum(1 for b in vram[tile_addr:tile_addr+32] if b != 0)
    
    print(f"  SAT[{i}]: y={y_pos:4d} x={x_pos:4d} size={h_cells}x{v_cells} "
          f"tile={tile_index:4d}(0x{tile_index:03X}) addr=0x{tile_addr:05X} "
          f"pal={palette} pri={priority} hf={hflip} vf={vflip} link={link} "
          f"tile_nonzero={tile_data_nonzero}/32")

# 5. For first few sprites with non-zero position, show full tile data range
print("\n=== Tile data at sprite addresses ===")
for s in sprites[:8]:
    tile = s['tile']
    h_cells = s['width'] // 8
    v_cells = s['height'] // 8
    total_tiles = h_cells * v_cells
    addr = tile * 32
    end_addr = (tile + total_tiles) * 32
    nonzero = sum(1 for b in vram[addr:end_addr] if b != 0)
    print(f"  Sprite {s['index']}: tile {tile}..{tile+total_tiles-1} "
          f"addr 0x{addr:05X}..0x{end_addr-1:05X} nonzero={nonzero}/{end_addr-addr}")
    if nonzero > 0:
        # Show first 32 bytes (first tile)
        print(f"    First tile bytes: {' '.join(f'{b:02X}' for b in vram[addr:addr+32])}")

# 6. SCAN entire VRAM for non-zero regions  
print("\n=== VRAM non-zero regions (tile granularity, 32 bytes per tile) ===")
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
          f"addr 0x{start_addr:05X}..0x{end_addr-1:05X} nonzero_bytes={total_nonzero}")

# 7. Specifically check where sprite tile indices should be vs where data is
print("\n=== Sprite tile index vs VRAM data analysis ===")
sprite_tiles = set()
for s in sprites:
    tile = s['tile']
    h_cells = s['width'] // 8
    v_cells = s['height'] // 8
    for c in range(h_cells):
        for r in range(v_cells):
            sprite_tiles.add(tile + c * v_cells + r)

print(f"Unique tiles referenced by sprites: {len(sprite_tiles)}")
tiles_with_data = 0
tiles_without_data = 0
for t in sorted(sprite_tiles):
    addr = t * 32
    if addr + 32 <= len(vram):
        has_data = any(vram[addr + b] != 0 for b in range(32))
        if has_data:
            tiles_with_data += 1
        else:
            tiles_without_data += 1

print(f"Tiles WITH data: {tiles_with_data}")
print(f"Tiles WITHOUT data: {tiles_without_data}")

# 8. Show first 5 sprite tiles - hex dump
print("\n=== Hex dump of first 5 sprite tile addresses ===")
for t in sorted(sprite_tiles)[:5]:
    addr = t * 32
    data = vram[addr:addr+32]
    row1 = ' '.join(f'{b:02X}' for b in data[:16])
    row2 = ' '.join(f'{b:02X}' for b in data[16:32])
    print(f"  Tile {t:4d} (0x{addr:05X}): {row1}")
    print(f"                        {row2}")

# 9. Check if there's a byte-swap issue - check if tile data exists at addr^1
print("\n=== Byte-swap check: tile data at addr XOR 1? ===")
for s in sprites[:3]:
    tile = s['tile']
    addr = tile * 32
    print(f"  Sprite {s['index']}, tile {tile}:")
    # Normal
    normal = vram[addr:addr+32]
    print(f"    Normal  : {' '.join(f'{b:02X}' for b in normal[:16])}")
    # XOR 1
    xored = bytes(vram[(addr + i) ^ 1] if (addr + i) ^ 1 < len(vram) else 0 for i in range(32))
    print(f"    XOR'd   : {' '.join(f'{b:02X}' for b in xored[:16])}")

print("\n=== CRAM check ===")
cram_data = api("/vdp/cram")
cram_colors = cram_data.get("colors_argb") or cram_data.get("colors") or []
non_black = [i for i, c in enumerate(cram_colors) if c != 0xFF000000 and c != 0]
print(f"Non-black CRAM entries: {len(non_black)} / {len(cram_colors)}")
for i in non_black[:16]:
    print(f"  CRAM[{i}] = 0x{cram_colors[i]:08X}")
