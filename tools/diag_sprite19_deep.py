"""Check framebuffer at scanlines where sprite 19 has actual tile data"""
import urllib.request, json
BASE = "http://localhost:8114/api/v1"

vram = bytes(json.loads(urllib.request.urlopen(f'{BASE}/vdp/vram?addr=0&len=65536').read())['data'])
frame = json.loads(urllib.request.urlopen(f'{BASE}/video/frame').read())
fb = frame['pixels_argb']
cram = json.loads(urllib.request.urlopen(f'{BASE}/vdp/cram').read())['cram']

# Sprite 19: y=44, x=68, tile=896, 4x3 cells, palette 3
# Data is in tile rows 1-2, so y=52..67
# Check scanline 60 (cell_row=2, row_in_cell=0)

def get_tile_pixel(tile_addr, px, py):
    row_offset = tile_addr + py * 4
    byte_idx = row_offset + (px >> 1)
    if byte_idx >= len(vram):
        return 0
    b = vram[byte_idx]
    return (b >> 4) if (px & 1) == 0 else (b & 0x0F)

for test_y in [55, 60, 63]:
    print(f"\n=== Scanline {test_y} ===")
    sprite_y = 44
    sprite_x = 68
    v_cells = 3
    h_cells = 4
    tile_base = 896
    palette = 3
    
    py = test_y - sprite_y
    cell_row = py // 8
    row_in_cell = py % 8
    
    print(f"  py={py} cell_row={cell_row} row_in_cell={row_in_cell}")
    
    rendered_pixels = {}
    for cx in range(h_cells):
        cell_col = cx
        tile = tile_base + cell_col * v_cells + cell_row
        tile_addr = tile * 32
        row_addr = tile_addr + row_in_cell * 4
        row_bytes = vram[row_addr:row_addr+4]
        
        pixels = []
        for px_in_cell in range(8):
            pixel = get_tile_pixel(tile_addr, px_in_cell, row_in_cell)
            screen_x = sprite_x + cx * 8 + px_in_cell
            pixels.append(pixel)
            if pixel != 0:
                color_idx = palette * 16 + pixel
                cram_word = cram[color_idx] if color_idx < len(cram) else 0
                rendered_pixels[screen_x] = (pixel, color_idx, cram_word)
        
        print(f"  cx={cx} tile={tile} row_bytes={' '.join(f'{b:02X}' for b in row_bytes)} pixels={pixels}")
    
    if rendered_pixels:
        print(f"  Non-zero sprite pixels: {len(rendered_pixels)}")
        for x in sorted(rendered_pixels.keys())[:10]:
            pv, ci, cw = rendered_pixels[x]
            # What does the framebuffer actually show?
            actual = fb[test_y * 320 + x] & 0xFFFFFFFF
            # What should the sprite color be?
            b = (cw >> 9) & 7
            g = (cw >> 5) & 7
            r = (cw >> 1) & 7
            def s38(v): return (v << 5) | (v << 2) | (v >> 1)
            expected = 0xFF000000 | (s38(r) << 16) | (s38(g) << 8) | s38(b)
            match = "MATCH" if actual == expected else "MISMATCH"
            print(f"    x={x}: pix={pv} cram_idx={ci} cram=0x{cw:04X} "
                  f"expected=0x{expected:08X} actual=0x{actual:08X} {match}")
    else:
        print(f"  All pixels transparent")
    
    # Show framebuffer at sprite positions
    print(f"  Framebuffer x=68..99:")
    for x in range(68, 100):
        c = fb[test_y * 320 + x] & 0xFFFFFFFF
        is_sprite = x in rendered_pixels
        marker = "*" if is_sprite else " "
        if (x - 68) % 8 == 0:
            print(f"    ", end="")
        print(f"{marker}0x{c:08X}", end=" ")
        if (x - 68) % 8 == 7:
            print()
