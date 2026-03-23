"""Analyze where stripe pixels come from - check if tile 3FE/3FF have transparent pixels"""
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

# Reset and step to demo gameplay
post("/emulator/reset")
post("/emulator/step", {"frames": 3000})

# Check tiles 0x3FE and 0x3FF from VRAM
# Tile data is at tile_index * 32 bytes
for tile_id in [0x3FE, 0x3FF]:
    addr = tile_id * 32
    vram = get(f"/vdp/vram?addr={addr}&len=32")
    data = vram.get("data") or vram.get("vram")
    print(f"Tile 0x{tile_id:03X} at VRAM 0x{addr:04X}:")
    transparent = 0
    for row in range(8):
        pixels = []
        for col in range(8):
            byte_idx = row * 4 + (col >> 1)
            byte_val = data[byte_idx]
            if col & 1 == 0:
                px = byte_val >> 4
            else:
                px = byte_val & 0x0F
            pixels.append(px)
            if px == 0:
                transparent += 1
        print(f"  row {row}: {pixels}")
    print(f"  Transparent pixels: {transparent}/64\n")

# Now check the compositing frame: look at pixels in the vine area
# The main stripe area should be around y=16-80 which is rows 2-10 in nametable
# Plane A has 83FE/83FF for cols 2-39 (x=16-319)
# Plane B has vine tiles

# Let's check what the composite looks like vs what plane B alone looks like
# at the stripe locations
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]

# Check Plane A render
pa_data = get("/vdp/plane?name=A")
pa_w = pa_data["width"]
pa_pixels = pa_data["pixels_argb"]

# Check Plane B render
pb_data = get("/vdp/plane?name=B")
pb_w = pb_data["width"]
pb_pixels = pb_data["pixels_argb"]

# Compare pixel sources at various positions
# The vine area visible on screen (where Plane A has 83FE/83FF, should be dark)
# Let's look at x=40 (which is in the "field" area, col 5 of the nametable)
# and several y positions to see if stripe patterns exist

print("=== Pixel comparison at x=40 (field area, Plane A has 83FE/83FF) ===")
print(f"{'y':>3} | {'Composite':>12} | {'Plane A':>12} | {'Plane B':>12} | Note")
for y in range(0, 80):
    comp = pixels[y * w + 40]
    # For plane renders, they are full nametable size (512x512), but we need
    # the screen-position equivalent. With vscroll=0 and hscroll=0, 
    # screen x=40 maps to nametable x=40, and screen y maps to nametable y
    pa_px = pa_pixels[y * pa_w + 40] if y * pa_w + 40 < len(pa_pixels) else 0
    pb_px = pb_pixels[y * pb_w + 40] if y * pb_w + 40 < len(pb_pixels) else 0
    
    c_r = (comp >> 16) & 0xFF
    c_g = (comp >> 8) & 0xFF
    c_b = comp & 0xFF
    
    a_r = (pa_px >> 16) & 0xFF
    a_g = (pa_px >> 8) & 0xFF
    a_b = pa_px & 0xFF
    
    b_r = (pb_px >> 16) & 0xFF
    b_g = (pb_px >> 8) & 0xFF
    b_b = pb_px & 0xFF
    
    # Determine source
    note = ""
    if (c_r, c_g, c_b) == (a_r, a_g, a_b):
        note = "=PlaneA"
    elif (c_r, c_g, c_b) == (b_r, b_g, b_b):
        note = "=PlaneB ***"
    else:
        note = "=OTHER???"
    
    print(f"{y:3d} | ({c_r:3d},{c_g:3d},{c_b:3d}) | ({a_r:3d},{a_g:3d},{a_b:3d}) | ({b_r:3d},{b_g:3d},{b_b:3d}) | {note}")
