"""Capture multiple gameplay frames to find puyo shadow rendering"""
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

def capture_frame(filename):
    fdata = get("/video/frame")
    w, h = fdata["width"], fdata["height"]
    pixels = fdata["pixels_argb"]
    img = Image.new("RGB", (w, h))
    for i, argb in enumerate(pixels):
        r_val = (argb >> 16) & 0xFF
        g_val = (argb >> 8) & 0xFF
        b_val = argb & 0xFF
        img.putpixel((i % w, i // w), (r_val, g_val, b_val))
    img.save(filename)
    return pixels

# Capture gameplay frames at various points
post("/emulator/load-rom-path", {"path": "/Users/hossie/development/md_emulator/roms/puyo.bin"})
print("ROM loaded")

# Step to demo gameplay (after instructions)
for batch in range(10):
    post("/emulator/step", {"frames": 500})

capture_frame("demo_gameplay_f5000.png")
print("Saved demo_gameplay_f5000.png")

for batch in range(4):
    post("/emulator/step", {"frames": 500})

capture_frame("demo_gameplay_f7000.png")
print("Saved demo_gameplay_f7000.png")

for batch in range(4):
    post("/emulator/step", {"frames": 500})

capture_frame("demo_gameplay_f9000.png")
print("Saved demo_gameplay_f9000.png")
