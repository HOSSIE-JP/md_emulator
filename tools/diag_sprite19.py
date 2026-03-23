"""Check sprite 19 tile data (palette 3, y=44, 4x3 cells)"""
import urllib.request, json
BASE = "http://localhost:8114/api/v1"
vram = bytes(json.loads(urllib.request.urlopen(f'{BASE}/vdp/vram?addr=0&len=65536').read())['data'])

tile_base = 896
v_cells = 3
h_cells = 4
print("Sprite 19: tile=896, 4x3 cells, palette 3")
for c in range(h_cells):
    for r in range(v_cells):
        t = tile_base + c * v_cells + r
        addr = t * 32
        nz = sum(1 for b in vram[addr:addr+32] if b != 0)
        row0 = vram[addr:addr+4]
        print(f"  col={c} row={r} tile={t} addr=0x{addr:05X} nz={nz}/32 "
              f"row0={' '.join(f'{b:02X}' for b in row0)}")

# Check rendering on y=44 for this sprite
print("\nRendering on scanline 44:")
sprite_y = 44
sprite_x = 68
iy = 44
py = iy - sprite_y  # = 0
cell_row = py // 8   # = 0
row_in_cell = py % 8  # = 0

for cx in range(h_cells):
    cell_col = cx  # no hflip
    tile = tile_base + cell_col * v_cells + cell_row
    tile_addr = tile * 32
    row_addr = tile_addr + row_in_cell * 4
    row_bytes = vram[row_addr:row_addr+4]
    pixels = []
    for px_in_cell in range(8):
        byte_idx = row_addr + (px_in_cell >> 1)
        b = vram[byte_idx] if byte_idx < len(vram) else 0
        pixel = (b >> 4) if (px_in_cell & 1) == 0 else (b & 0x0F)
        pixels.append(pixel)
    print(f"  cx={cx} tile={tile} addr=0x{tile_addr:05X} row_bytes={' '.join(f'{b:02X}' for b in row_bytes)} "
          f"pixels={pixels}")

# Check the CRAM palette 3
cram_data = json.loads(urllib.request.urlopen(f'{BASE}/vdp/cram').read())['cram']
print("\nPalette 3 CRAM entries:")
for i in range(48, 64):
    v = cram_data[i]
    if v != 0:
        b_c = (v >> 9) & 7
        g_c = (v >> 5) & 7
        r_c = (v >> 1) & 7
        print(f"  CRAM[{i}] ({i-48} in pal3) = 0x{v:04X}  r={r_c} g={g_c} b={b_c}")

# Check the actual framebuffer at y=44
frame = json.loads(urllib.request.urlopen(f'{BASE}/video/frame').read())
fb = frame['pixels_argb']
print("\nFramebuffer at y=44, x=68..99:")
for x in range(68, 100):
    c = fb[44 * 320 + x] & 0xFFFFFFFF
    print(f"  x={x}: 0x{c:08X}", end="")
    if (x - 68) % 8 == 7:
        print()
