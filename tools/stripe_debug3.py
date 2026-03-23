"""Deep analysis of stripe artifacts at demo gameplay frame ~3000"""
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
print("At frame ~3000")

# Get VDP registers
regs_data = get("/vdp/registers")
regs = regs_data.get("registers") or regs_data.get("data")
r0b = regs[0x0B]
r10 = regs[0x10]
vs_mode = (r0b >> 2) & 1
hs_mode = r0b & 3
sw_code = r10 & 3
sh_code = (r10 >> 4) & 3
sw_map = {0: 32, 1: 64, 3: 128}
sh_map = {0: 32, 1: 64, 3: 128}
sw = sw_map.get(sw_code, 32)
sh = sh_map.get(sh_code, 32)

r02 = regs[0x02]
r04 = regs[0x04]
plane_a_addr = (r02 & 0x38) << 10
plane_b_addr = (r04 & 0x07) << 13
r0c = regs[0x0C]
h40 = (r0c & 0x81) != 0

print(f"VS={vs_mode}, HS={hs_mode}, scroll={sw}x{sh}, H40={h40}")
print(f"Plane A addr=0x{plane_a_addr:04X}, Plane B addr=0x{plane_b_addr:04X}")

# Read Plane B nametable from VRAM
nt_size = sw * sh * 2  # bytes
vram_b = get(f"/vdp/vram?addr={plane_b_addr}&len={nt_size}")
vb = vram_b.get("data") or vram_b.get("vram")
print(f"\nPlane B nametable ({sw}x{sh} cells, {nt_size} bytes):")

# Print first 30 rows x first 8 cols
for row in range(min(30, sh)):
    tiles = []
    for col in range(min(8, sw)):
        off = (row * sw + col) * 2
        if off + 1 < len(vb):
            entry = (vb[off] << 8) | vb[off + 1]
            tiles.append(f"{entry:04X}")
    print(f"  row {row:2d}: {' '.join(tiles)}")

# Read Plane A nametable from VRAM
vram_a = get(f"/vdp/vram?addr={plane_a_addr}&len={nt_size}")
va = vram_a.get("data") or vram_a.get("vram")
print(f"\nPlane A nametable ({sw}x{sh} cells, {nt_size} bytes):")
for row in range(min(30, sh)):
    tiles = []
    for col in range(min(8, sw)):
        off = (row * sw + col) * 2
        if off + 1 < len(va):
            entry = (va[off] << 8) | va[off + 1]
            tiles.append(f"{entry:04X}")
    print(f"  row {row:2d}: {' '.join(tiles)}")

# Now capture the frame and each plane as PNG  
fdata = get("/video/frame")
w, h_scr = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]
img = Image.new("RGB", (w, h_scr))
for i, argb in enumerate(pixels):
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    img.putpixel((i % w, i // w), (r, g, b))
img.save("stripe_frame3.png")
print(f"\nSaved stripe_frame3.png ({w}x{h_scr})")

# Render Plane A
pa = get("/vdp/plane?name=A")
pw, ph = pa["width"], pa["height"]
pimg = Image.new("RGB", (pw, ph))
for i, argb in enumerate(pa["pixels_argb"]):
    r2 = (argb >> 16) & 0xFF
    g2 = (argb >> 8) & 0xFF
    b2 = argb & 0xFF
    pimg.putpixel((i % pw, i // pw), (r2, g2, b2))
pimg.save("stripe_planeA.png")
print(f"Saved stripe_planeA.png ({pw}x{ph})")

# Render Plane B
pb = get("/vdp/plane?name=B")
pw2, ph2 = pb["width"], pb["height"]
pimg2 = Image.new("RGB", (pw2, ph2))
for i, argb in enumerate(pb["pixels_argb"]):
    r3 = (argb >> 16) & 0xFF
    g3 = (argb >> 8) & 0xFF
    b3 = argb & 0xFF
    pimg2.putpixel((i % pw2, i // pw2), (r3, g3, b3))
pimg2.save("stripe_planeB.png")
print(f"Saved stripe_planeB.png ({pw2}x{ph2})")

# Check VSRAM
vsram_data = get("/vdp/vsram")
vs_entries = vsram_data["vsram"]
print(f"\nVSRAM entries (first 40): {vs_entries[:40]}")
non_zero = sum(1 for v in vs_entries if v != 0)
print(f"Non-zero VSRAM entries: {non_zero}/{len(vs_entries)}")

# Now look at specific scanlines that might show striping
# Get the scanline-level VSRAM data
svs = get("/vdp/scanline-vsram")
scanline_vs = svs["scanline_vsram_a"]
print(f"\nScanline VSRAM A (first 30):")
for i in range(min(30, len(scanline_vs))):
    print(f"  line {i:3d}: {scanline_vs[i]}")
