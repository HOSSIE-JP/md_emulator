"""Analyze the demo screen stripe artifacts at the pixel level.
Capture individual plane renders at the compositing level."""
import urllib.request, json, struct
from PIL import Image

BASE = "http://127.0.0.1:8117/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def get_bytes(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return r.read()

# Step to demo gameplay (frame ~3000)
get("/debug/reset")
for _ in range(30):
    get("/debug/step-frame?count=100")
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
img.save("stripe_frame.png")
print(f"Saved stripe_frame.png ({w}x{h})")

# Analyze horizontal patterns - look at pixel colors across rows
# Focus on a column in the vine background area (col ~5)
print("\n--- Vertical slice at x=5 ---")
for y in range(0, min(h, 50)):
    argb = pixels[y * w + 5]
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    print(f"  y={y:3d}: RGB=({r:3d},{g:3d},{b:3d})")

# Look at Plane B nametable rows more carefully
print("\n--- Plane B nametable (first 40 rows, col 0-5) ---")
d = get("/vdp/plane?name=B")
entries = d["entries"]
sw = d["width_cells"]
for row in range(min(40, len(entries) // sw)):
    tiles = []
    for col in range(min(6, sw)):
        e = entries[row * sw + col]
        tiles.append(f"{e:04X}")
    print(f"  row {row:2d}: {' '.join(tiles)}")

# Also check the actual VSRAM values more carefully
vsram_data = get("/vdp/vsram")
vs = vsram_data.get("vsram") or vsram_data.get("data")
print(f"\n--- VSRAM (first 40 words, hex) ---")
for i in range(0, min(80, len(vs)), 2):
    val = (vs[i] << 8) | vs[i+1] if i+1 < len(vs) else vs[i] << 8
    col = i // 4  # column index
    plane = "A" if (i % 4) < 2 else "B"
    print(f"  [{i:2d}] col{col:2d} plane{plane}: 0x{val:04X} ({val})")

# Check hscroll
hs_data = get("/vdp/registers")
regs = hs_data.get("registers") or hs_data.get("data")
if regs:
    r0d = regs[0x0D] if len(regs) > 0x0D else 0
    hs_addr = (r0d & 0x3F) << 10
    print(f"\nHscroll addr: 0x{hs_addr:04X}")
    
    # Read hscroll table from VRAM
    vram_resp = get(f"/vdp/vram?addr={hs_addr}&len=896")
    vdata = vram_resp.get("data") or vram_resp.get("vram")
    if vdata:
        print("--- Hscroll table (first 56 entries = 224 lines) ---")
        non_zero = 0
        for line in range(min(224, len(vdata) // 4)):
            off = line * 4
            a = ((vdata[off] << 8) | vdata[off+1]) if off+1 < len(vdata) else 0
            b = ((vdata[off+2] << 8) | vdata[off+3]) if off+3 < len(vdata) else 0
            if a != 0 or b != 0:
                print(f"  line {line:3d}: A=0x{a:04X} B=0x{b:04X}")
                non_zero += 1
        print(f"  Non-zero lines: {non_zero}")
        if non_zero == 0:
            print("  (All hscroll values are 0)")
