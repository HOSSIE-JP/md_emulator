"""Test the window plane fix - capture demo gameplay frame and compare"""
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

# Reset and step to demo gameplay
post("/emulator/reset")
post("/emulator/step", {"frames": 3000})
print("At frame ~3000")

# Get frame
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]

img = Image.new("RGB", (w, h))
for i, argb in enumerate(pixels):
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    img.putpixel((i % w, i // w), (r, g, b))
img.save("fixed_demo.png")
print(f"Saved fixed_demo.png ({w}x{h})")

# Also capture title screen
post("/emulator/reset")
post("/emulator/step", {"frames": 900})
fdata2 = get("/video/frame")
w2, h2 = fdata2["width"], fdata2["height"]
pixels2 = fdata2["pixels_argb"]
img2 = Image.new("RGB", (w2, h2))
for i, argb in enumerate(pixels2):
    r2 = (argb >> 16) & 0xFF
    g2 = (argb >> 8) & 0xFF
    b2 = argb & 0xFF
    img2.putpixel((i % w2, i // w2), (r2, g2, b2))
img2.save("fixed_title.png")
print(f"Saved fixed_title.png ({w2}x{h2})")
