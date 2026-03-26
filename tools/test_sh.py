"""Test Shadow/Highlight rendering"""
import urllib.request, json
from PIL import Image

BASE = "http://127.0.0.1:8118/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    d = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=d,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

# Load ROM and step to demo screen
post("/emulator/load-rom-path", {"path": "/Users/hossie/development/md_emulator/roms/puyo.bin"})
print("ROM loaded")

# Step in smaller batches to avoid timeout
for batch in range(6):
    post("/emulator/step", {"frames": 500})
    print(f"  batch {batch+1}/6 done")
print("Stepped to frame 3000")

# Capture frame
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]
img = Image.new("RGB", (w, h))
for i, argb in enumerate(pixels):
    r_val = (argb >> 16) & 0xFF
    g_val = (argb >> 8) & 0xFF
    b_val = argb & 0xFF
    img.putpixel((i % w, i // w), (r_val, g_val, b_val))
img.save("demo_sh_f3000.png")

# Count shadowed pixels (dim colors that are not black)
shadow_count = 0
non_black = 0
for argb in pixels:
    r_val = (argb >> 16) & 0xFF
    g_val = (argb >> 8) & 0xFF
    b_val = argb & 0xFF
    if r_val == 0 and g_val == 0 and b_val == 0:
        continue
    non_black += 1
    if r_val <= 127 and g_val <= 127 and b_val <= 127:
        shadow_count += 1

print(f"Image: {w}x{h}")
print(f"Shadow pixels (all RGB <= 127): {shadow_count}")
print(f"Non-black pixels: {non_black}")
print("Saved demo_sh_f3000.png")

# Also capture a gameplay frame where puyo shadows should be visible
post("/emulator/reset")
post("/emulator/step", {"frames": 300})
fdata2 = get("/video/frame")
pixels2 = fdata2["pixels_argb"]
img2 = Image.new("RGB", (w, h))
for i, argb in enumerate(pixels2):
    r_val = (argb >> 16) & 0xFF
    g_val = (argb >> 8) & 0xFF
    b_val = argb & 0xFF
    img2.putpixel((i % w, i // w), (r_val, g_val, b_val))
img2.save("title_sh_f300.png")
print("Saved title_sh_f300.png")
