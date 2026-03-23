"""
Replicate render_sprites_line exactly as the Rust code does it,
for a specific scanline, using live VRAM data.
"""
import urllib.request
import json

BASE = "http://localhost:8114/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# Get VRAM
vram = bytes(api("/vdp/vram?addr=0&len=65536")["data"])
print(f"VRAM: {len(vram)} bytes")

# Get registers
regs = api("/vdp/registers")
reg_vals = regs.get("registers", regs.get("values", []))
if isinstance(reg_vals, dict):
    reg_vals = [reg_vals.get(str(i), 0) for i in range(32)]

reg5 = reg_vals[5]
sat_base = (reg5 & 0x7F) << 9
h40 = (reg_vals[0x0C] & 0x81) != 0
screen_w = 320 if h40 else 256
max_sprites = 80 if h40 else 64
max_per_line = 20 if h40 else 16
print(f"SAT base=0x{sat_base:04X}, H40={h40}, screen_w={screen_w}")

# Get sprites info for reference
sprites = api("/vdp/sprites")["sprites"]
print(f"Sprites from API: {len(sprites)}")

# Find a visible sprite to test
# Pick sprite at y=112, x=88, that's scanlines 112..127 (4x2 cells = 32x16 px)
test_scanline = 115  # Should be within sprite at y=112..127

def get_tile_pixel(tile_addr, px, py):
    row_offset = tile_addr + py * 4
    byte_idx = row_offset + (px >> 1)
    if byte_idx >= len(vram):
        return 0
    b = vram[byte_idx]
    if (px & 1) == 0:
        return b >> 4
    else:
        return b & 0x0F

print(f"\n=== Rendering sprites on scanline {test_scanline} ===")
sprite_buf = [(0, False)] * screen_w
sprites_on_line = 0
link = 0
sprite_count = 0

for _ in range(max_sprites):
    entry_base = sat_base + link * 8
    if entry_base + 7 >= len(vram):
        break

    y_raw = (vram[entry_base] << 8) | vram[entry_base + 1]
    y_pos = y_raw & 0x03FF
    sprite_y = y_pos - 128
    size_byte = vram[entry_base + 2]
    h_cells = ((size_byte >> 2) & 3) + 1
    v_cells = (size_byte & 3) + 1
    sprite_h = v_cells * 8
    next_link = vram[entry_base + 3] & 0x7F

    attr = (vram[entry_base + 4] << 8) | vram[entry_base + 5]
    x_raw = (vram[entry_base + 6] << 8) | vram[entry_base + 7]
    x_pos = x_raw & 0x1FF
    sprite_x = x_pos - 128

    tile_index = attr & 0x07FF
    palette = (attr >> 13) & 3
    priority = (attr & 0x8000) != 0
    hflip = (attr & 0x0800) != 0
    vflip = (attr & 0x1000) != 0

    iy = test_scanline
    if iy >= sprite_y and iy < sprite_y + sprite_h:
        sprites_on_line += 1
        py = (sprite_h - 1 - (iy - sprite_y)) if vflip else (iy - sprite_y)
        cell_row = py // 8
        row_in_cell = py % 8

        print(f"\n  Sprite link={link} y={sprite_y} x={sprite_x} "
              f"sz={h_cells}x{v_cells} tile={tile_index}(0x{tile_index:03X}) "
              f"pal={palette} pri={priority} hflip={hflip} vflip={vflip}")
        print(f"    iy={iy} py={py} cell_row={cell_row} row_in_cell={row_in_cell}")

        for cx in range(h_cells):
            cell_col = (h_cells - 1 - cx) if hflip else cx
            tile = tile_index + cell_col * v_cells + cell_row
            tile_addr = tile * 32
            
            # Show what data is at this tile address
            tile_data = vram[tile_addr:tile_addr+32]
            nz = sum(1 for b in tile_data if b != 0)
            
            print(f"    cx={cx} cell_col={cell_col} tile={tile}(0x{tile:03X}) "
                  f"addr=0x{tile_addr:05X} nz={nz}/32")
            
            # Show the specific row we're reading
            row_addr = tile_addr + row_in_cell * 4
            row_bytes = vram[row_addr:row_addr+4]
            print(f"      Row {row_in_cell} @0x{row_addr:05X}: "
                  f"{' '.join(f'{b:02X}' for b in row_bytes)}")
            
            pixels = []
            for px_in_cell in range(8):
                fx = (7 - px_in_cell) if hflip else px_in_cell
                pixel = get_tile_pixel(tile_addr, fx, row_in_cell)
                screen_x = sprite_x + cx * 8 + px_in_cell
                pixels.append(pixel)
                
                if pixel != 0 and 0 <= screen_x < screen_w:
                    sx = screen_x
                    existing, _ = sprite_buf[sx]
                    if existing == 0:
                        sprite_buf[sx] = (palette * 16 + pixel, priority)
            
            print(f"      Pixels: {pixels}")

    link = next_link
    if link == 0:
        break
    sprite_count += 1

print(f"\n  Total sprites on line: {sprites_on_line}")

# Check result buffer
non_zero = [(x, sprite_buf[x]) for x in range(screen_w) if sprite_buf[x][0] != 0]
print(f"  Non-zero sprite pixels on line: {len(non_zero)}")
if non_zero:
    for x, (idx, pri) in non_zero[:20]:
        print(f"    x={x}: color_idx={idx} priority={pri}")

# Also replicate what the actual frame looks like at this scanline
frame = api("/video/frame")
fb = frame.get("pixels_argb") or frame.get("framebuffer") or frame.get("pixels") or []

if fb:
    print(f"\n=== Actual framebuffer line {test_scanline} ===")
    row_start = test_scanline * 320
    row = fb[row_start:row_start + 320]
    # Check what colors appear
    unique_colors = {}
    for x, c in enumerate(row):
        cv = c & 0xFFFFFFFF
        if cv not in unique_colors:
            unique_colors[cv] = []
        unique_colors[cv].append(x)
    print(f"  Unique colors: {len(unique_colors)}")
    for cv, xs in sorted(unique_colors.items()):
        print(f"    0x{cv:08X}: {len(xs)} pixels (first: x={xs[0]})")
else:
    print(f"\nFrame keys: {list(frame.keys()) if isinstance(frame,dict) else 'not dict'}")
