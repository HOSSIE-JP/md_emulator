"""Load ROM into new server and test"""
import urllib.request, json

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

# Load ROM
rom_path = "D:/homebrew/puyo.bin"
result = post("/emulator/load-rom-path", {"path": rom_path})
print(f"Load ROM: {result}")

# Reset and step
post("/emulator/reset")
post("/emulator/step", {"frames": 10})
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")
r01 = rdata[0x01]
print(f"After 10 frames: R01=0x{r01:02X}, display={'ON' if (r01 & 0x40) else 'OFF'}")

# Step to demo
post("/emulator/step", {"frames": 2990})
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]
non_black = sum(1 for p in pixels if (p & 0x00FFFFFF) != 0)
print(f"After 3000 frames: {non_black}/{len(pixels)} non-black pixels")

from PIL import Image
img = Image.new("RGB", (w, h))
for i, argb in enumerate(pixels):
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    img.putpixel((i % w, i // w), (r, g, b))
img.save("fixed_demo2.png")
print(f"Saved fixed_demo2.png")

# Also title screen
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
img2.save("fixed_title2.png")
print(f"Saved fixed_title2.png")
