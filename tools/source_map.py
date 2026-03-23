"""Check what layer each pixel comes from by adding debug output to compositing.
Focus on understanding if sprites cause the stripe appearance."""
import urllib.request, json
from PIL import Image

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

# Get sprites
sprites = get("/vdp/sprites")
sprite_list = sprites["sprites"]
print(f"Sprites: {len(sprite_list)}")
for s in sprite_list[:20]:
    print(f"  x={s.get('x',0):4d} y={s.get('y',0):4d} w={s.get('width',0)} h={s.get('height',0)} tile={s.get('tile',0):#x} pri={s.get('priority',0)} pal={s.get('palette',0)}")

# Get frame and compose a "source map" - for each pixel, determine the source layer
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]

# Get both plane renders (at full nametable size, scroll identity since all are 0)
pa = get("/vdp/plane?name=A")
pb = get("/vdp/plane?name=B")
pa_w = pa["width"]
pb_w = pb["width"]
pa_pixels = pa["pixels_argb"]
pb_pixels = pb["pixels_argb"]

# Get BG color
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")
bg_pal = (rdata[7] >> 4) & 3
bg_idx = rdata[7] & 0x0F
print(f"\nBG color: palette {bg_pal}, index {bg_idx}")

# Get CRAM to find BG color value
cram = get("/vdp/colors")
colors = cram["colors_argb"]
bg_color = colors[bg_pal * 16 + bg_idx]
bg_r = (bg_color >> 16) & 0xFF
bg_g = (bg_color >> 8) & 0xFF
bg_b = bg_color & 0xFF
print(f"BG color value: RGB({bg_r},{bg_g},{bg_b}) = #{bg_r:02x}{bg_g:02x}{bg_b:02x}")

# Create a "source map" image
# Red = Plane A, Blue = Plane B, Green = Sprite, Gray = BG
src_img = Image.new("RGB", (w, h))
for y in range(h):
    for x in range(w):
        comp = pixels[y * w + x]
        c_r = (comp >> 16) & 0xFF
        c_g = (comp >> 8) & 0xFF
        c_b = comp & 0xFF
        
        # Check Plane A at scroll position (scroll=0)
        pa_idx = y * pa_w + x
        pa_px = pa_pixels[pa_idx] if pa_idx < len(pa_pixels) else 0
        a_r = (pa_px >> 16) & 0xFF
        a_g = (pa_px >> 8) & 0xFF
        a_b = pa_px & 0xFF
        
        # Check Plane B
        pb_idx = y * pb_w + x
        pb_px = pb_pixels[pb_idx] if pb_idx < len(pb_pixels) else 0
        b_r = (pb_px >> 16) & 0xFF
        b_g = (pb_px >> 8) & 0xFF
        b_b = pb_px & 0xFF
        
        if (c_r, c_g, c_b) == (a_r, a_g, a_b) and (c_r, c_g, c_b) != (b_r, b_g, b_b):
            src_img.putpixel((x, y), (255, 0, 0))  # Red = exclusively Plane A
        elif (c_r, c_g, c_b) == (b_r, b_g, b_b) and (c_r, c_g, c_b) != (a_r, a_g, a_b):
            src_img.putpixel((x, y), (0, 0, 255))  # Blue = exclusively Plane B
        elif (c_r, c_g, c_b) == (a_r, a_g, a_b) and (c_r, c_g, c_b) == (b_r, b_g, b_b):
            src_img.putpixel((x, y), (128, 0, 128))  # Purple = both match
        elif (c_r, c_g, c_b) == (bg_r, bg_g, bg_b):
            src_img.putpixel((x, y), (64, 64, 64))  # Gray = BG
        else:
            src_img.putpixel((x, y), (0, 255, 0))  # Green = sprite/other

src_img.save("source_map.png")
print(f"Saved source_map.png")

# Count sources
from collections import Counter
counter = Counter()
for y in range(h):
    for x in range(w):
        px = src_img.getpixel((x, y))
        if px == (255, 0, 0): counter["PlaneA"] += 1
        elif px == (0, 0, 255): counter["PlaneB"] += 1
        elif px == (128, 0, 128): counter["Both"] += 1
        elif px == (64, 64, 64): counter["BG"] += 1
        else: counter["Sprite/Other"] += 1

total = w * h
for k, v in counter.most_common():
    print(f"  {k}: {v} ({v*100//total}%)")
