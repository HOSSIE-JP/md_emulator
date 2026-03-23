"""Deep diagnostic: check sprite rendering specifics for Puyo Puyo.
Test if render_sprites_line computes correct Y ranges, tile addresses,
and pixel values for actual sprites on a specific scanline."""
import urllib.request, json, struct

BASE = "http://localhost:8114/api/v1"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

# Reset and load ROM
print("=== Reset & Load ===")
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

# Get registers
regs = api_get("/vdp/registers")['registers']
sat_addr = (regs[5] & 0x7F) << 9
h40 = (regs[0x0C] & 0x81) != 0
print(f"SAT addr: 0x{sat_addr:04X}, H40: {h40}")

# Get sprites from our API
sprites = api_get("/vdp/sprites")['sprites']
print(f"Sprites in chain: {len(sprites)}")

# Find a sprite that should be visible on screen
visible = []
for s in sprites:
    sx, sy = s['x'], s['y']
    sw, sh = s['width'] * 8, s['height'] * 8
    if sx + sw > 0 and sx < 320 and sy >= 0 and sy + sh > 0 and sy < 224:
        visible.append(s)

print(f"Visible on-screen sprites: {len(visible)}")
for s in visible[:10]:
    sw, sh = s['width'] * 8, s['height'] * 8
    print(f"  #{s['index']:2d}: ({s['x']},{s['y']}) size {sw}x{sh} tile=0x{s['tile']:03X} pal={s['palette']} pri={s['priority']} hf={s['hflip']} vf={s['vflip']}")

if not visible:
    print("No visible sprites found! Exiting.")
    exit()

# Pick first visible sprite and check a scanline through it
test_spr = visible[0]
sy = test_spr['y']
sw = test_spr['width'] * 8
sh = test_spr['height'] * 8
test_line = sy + sh // 2  # middle scanline of sprite
if test_line < 0: test_line = max(sy, 0)
if test_line >= 224: test_line = min(sy + sh - 1, 223)

print(f"\n=== Testing scanline {test_line} for sprite #{test_spr['index']} ===")
print(f"Sprite Y range: {sy} to {sy+sh-1}")
print(f"Sprite X range: {test_spr['x']} to {test_spr['x']+sw-1}")

# Now manually replicate what render_sprites_line should do
# Walk the SAT link chain and find what pixels this sprite contributes
idx = test_spr['index']
entry_base = sat_addr + idx * 8
raw_sat = api_get(f"/vdp/vram?addr={entry_base}&len=8")['data']
print(f"\nRaw SAT entry at 0x{entry_base:04X}: {[f'0x{b:02X}' for b in raw_sat]}")

y_pos = ((raw_sat[0] << 8) | raw_sat[1]) & 0x3FF
sprite_y_raw = y_pos
sprite_y = sprite_y_raw - 128
size_byte = raw_sat[2]
h_cells = ((size_byte >> 2) & 3) + 1
v_cells = (size_byte & 3) + 1
next_link = raw_sat[3] & 0x7F
attr = (raw_sat[4] << 8) | raw_sat[5]
x_pos = ((raw_sat[6] << 8) | raw_sat[7]) & 0x1FF
sprite_x = x_pos - 128

tile_index = attr & 0x7FF
palette = (attr >> 13) & 3
priority = (attr & 0x8000) != 0
hflip = (attr & 0x0800) != 0
vflip = (attr & 0x1000) != 0

print(f"Decoded: y_pos={y_pos} -> screen_y={sprite_y}, x_pos={x_pos} -> screen_x={sprite_x}")
print(f"Size: {h_cells}x{v_cells} cells = {h_cells*8}x{v_cells*8} px")
print(f"Tile=0x{tile_index:03X} pal={palette} pri={priority} hf={hflip} vf={vflip}")

# Check Y-range match for test_line
sprite_h = v_cells * 8
iy = test_line
in_range = (iy >= sprite_y and iy < sprite_y + sprite_h)
print(f"\nScanline {test_line}: sprite_y={sprite_y}, sprite_y+h={sprite_y+sprite_h}, in_range={in_range}")

if in_range:
    py = (sprite_h - 1 - (iy - sprite_y)) if vflip else (iy - sprite_y)
    cell_row = py // 8
    row_in_cell = py % 8
    print(f"py={py}, cell_row={cell_row}, row_in_cell={row_in_cell}")
    
    # Get pixel data for this sprite line
    pixel_line = []
    for cx in range(h_cells):
        cell_col = (h_cells - 1 - cx) if hflip else cx
        tile = tile_index + cell_col * v_cells + cell_row
        tile_addr = tile * 32
        row_addr = tile_addr + row_in_cell * 4
        row_data = api_get(f"/vdp/vram?addr={row_addr}&len=4")['data']
        
        for px_in_cell in range(8):
            fx = 7 - px_in_cell if hflip else px_in_cell
            byte_val = row_data[fx >> 1]
            if (fx & 1) == 0:
                pixel_val = byte_val >> 4
            else:
                pixel_val = byte_val & 0x0F
            pixel_line.append(pixel_val)
    
    nz = sum(1 for p in pixel_line if p != 0)
    print(f"Sprite pixel line: {nz}/{len(pixel_line)} non-zero")
    print(f"  Values: {pixel_line}")
    
    # Now check what's in the framebuffer at those positions  
    frame = api_get("/video/frame")
    fb_pixels = frame['pixels_argb']
    fb_w = frame['width']
    
    print(f"\n--- Framebuffer comparison at scanline {test_line} ---")
    for i, pval in enumerate(pixel_line):
        sx_screen = sprite_x + i
        if 0 <= sx_screen < 320 and 0 <= test_line < 224:
            fb_color = fb_pixels[test_line * fb_w + sx_screen]
            r = (fb_color >> 16) & 0xFF
            g = (fb_color >> 8) & 0xFF
            b = fb_color & 0xFF
            
            # What color should this pixel be?
            if pval != 0:
                color_idx = palette * 16 + pval
                # Get CRAM color
                cram_data = api_get(f"/vdp/vram?addr=0&len=0")  # dummy
                colors = api_get("/vdp/colors")
                clist = colors.get('colors_argb', [])
                if color_idx < len(clist):
                    expected = clist[color_idx]
                    er = (expected >> 16) & 0xFF
                    eg = (expected >> 8) & 0xFF
                    eb = expected & 0xFF
                    match = (r == er and g == eg and b == eb)
                    if not match:
                        print(f"  x={sx_screen}: spr_pixel={pval} pal_idx={color_idx} -> expected=({er},{eg},{eb}) got=({r},{g},{b}) {'MATCH' if match else 'MISMATCH!'}")
                else:
                    print(f"  x={sx_screen}: color_idx {color_idx} out of CRAM range")

# Also check a row of framebuffer pixels on that scanline
frame = api_get("/video/frame")
fb_pixels = frame['pixels_argb']
fb_w = frame['width']
print(f"\n=== Full scanline {test_line} sample (every 8th pixel) ===")
for x in range(0, 320, 8):
    p = fb_pixels[test_line * fb_w + x]
    r = (p >> 16) & 0xFF
    g = (p >> 8) & 0xFF
    b = p & 0xFF
    marker = '*' if (r or g or b) else '.'
    if (r or g or b):
        print(f"  x={x:3d}: ({r:3d},{g:3d},{b:3d}) {marker}")

print("\nDone!")
