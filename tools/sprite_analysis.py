"""Analyze sprites on demo screen - find speech window edge sprites and puyo shadow sprites"""
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

# Step to demo gameplay with speech window
post("/emulator/reset")
# The demo mode should have a speech window during the intro before gameplay
# Try various frames to find it
for target in [2500, 2800, 3100, 3500, 4000]:
    post("/emulator/reset")
    post("/emulator/step", {"frames": target})
    
    sprites = get("/vdp/sprites")
    sl = sprites["sprites"]
    
    fdata = get("/video/frame")
    w, h = fdata["width"], fdata["height"]
    pixels = fdata["pixels_argb"]
    non_black = sum(1 for p in pixels if (p & 0x00FFFFFF) != 0)
    
    # Check VDP registers
    regs = get("/vdp/registers")
    rdata = regs.get("registers") or regs.get("data")
    r0c = rdata[0x0C]
    she = (r0c >> 3) & 1  # Shadow/Highlight Enable bit
    
    print(f"\n=== Frame {target} ===")
    print(f"  Sprites: {len(sl)}, non-black pixels: {non_black}")
    print(f"  R0C=0x{r0c:02X}, Shadow/Highlight={'ON' if she else 'OFF'}")
    
    # Show sprites with position info
    visible = [(s, i) for i, s in enumerate(sl) 
               if s.get('x', -128) > -100 and s.get('y', -128) > -100 
               and s.get('x', 400) < 350 and s.get('y', 300) < 250]
    print(f"  Visible sprites: {len(visible)}")
    for s, idx in visible[:20]:
        x = s.get('x', 0)
        y_pos = s.get('y', 0)
        sw = s.get('width', 1)
        sh = s.get('height', 1)
        tile = s.get('tile', 0)
        pal = s.get('palette', 0)
        pri = s.get('priority', False)
        print(f"    #{idx:2d}: x={x:4d} y={y_pos:4d} size={sw}x{sh} tile=0x{tile:03X} pal={pal} pri={pri}")
    
    # Save frame
    img = Image.new("RGB", (w, h))
    for i, argb in enumerate(pixels):
        r = (argb >> 16) & 0xFF
        g = (argb >> 8) & 0xFF
        b = argb & 0xFF
        img.putpixel((i % w, i // w), (r, g, b))
    img.save(f"demo_f{target}.png")
    print(f"  Saved demo_f{target}.png")
