"""Analyze the demo screen stripe artifacts at the pixel level."""
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
print("At frame ~3000")

# Get frame
fdata = get("/video/frame")
w, h = fdata["width"], fdata["height"]
pixels = fdata["pixels_argb"]

# Save as PPM (no PIL needed)
with open("stripe_frame.ppm", "wb") as f:
    f.write(f"P6\n{w} {h}\n255\n".encode())
    for argb in pixels:
        r = (argb >> 16) & 0xFF
        g = (argb >> 8) & 0xFF
        b = argb & 0xFF
        f.write(bytes([r, g, b]))
print(f"Saved stripe_frame.ppm ({w}x{h})")

# Vertical slice at x=5 (vine background area, left edge)
print("\n--- Vertical slice at x=5 (first 50 lines) ---")
for y in range(0, min(h, 50)):
    argb = pixels[y * w + 5]
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    print(f"  y={y:3d}: RGB=({r:3d},{g:3d},{b:3d})  #{r:02x}{g:02x}{b:02x}")

# Vertical slice at x=160 (middle of screen)
print("\n--- Vertical slice at x=160 (first 50 lines) ---")
for y in range(0, min(h, 50)):
    argb = pixels[y * w + 160]
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    print(f"  y={y:3d}: RGB=({r:3d},{g:3d},{b:3d})  #{r:02x}{g:02x}{b:02x}")

# Check for row-to-row color discontinuities in vine area
print("\n--- Row-to-row color jumps at x=5 (full screen) ---")
jumps = 0
prev_r, prev_g, prev_b = 0, 0, 0
for y in range(h):
    argb = pixels[y * w + 5]
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    if y > 0:
        dr = abs(r - prev_r)
        dg = abs(g - prev_g)
        db = abs(b - prev_b)
        total = dr + dg + db
        if total > 100:  # significant jump
            jumps += 1
            if jumps <= 30:
                print(f"  y={y:3d}: ({prev_r},{prev_g},{prev_b})->({r},{g},{b}) delta={total}")
    prev_r, prev_g, prev_b = r, g, b
print(f"  Total significant jumps: {jumps}")

# Check Plane B nametable
print("\n--- Plane B nametable (rows 0-30, cols 0-5) ---")
d = get("/vdp/plane?name=B")
entries = d["entries"]
sw = d["width_cells"]
for row in range(min(30, len(entries) // sw)):
    tiles = []
    for col in range(min(6, sw)):
        e = entries[row * sw + col]
        tiles.append(f"{e:04X}")
    print(f"  row {row:2d}: {' '.join(tiles)}")

# Check VSRAM
vsram_data = get("/vdp/vsram")
vs = vsram_data.get("vsram") or vsram_data.get("data")
print(f"\n--- VSRAM (first 20 pairs, hex) ---")
non_zero_vs = 0
for i in range(0, min(80, len(vs)), 2):
    val = (vs[i] << 8) | vs[i+1] if i+1 < len(vs) else vs[i] << 8
    col = i // 4
    plane = "A" if (i % 4) < 2 else "B"
    if val != 0:
        print(f"  [{i:2d}] col{col:2d} plane{plane}: 0x{val:04X} ({val})")
        non_zero_vs += 1
if non_zero_vs == 0:
    print("  (All zero)")

# Check VDP registers for scroll config 
regs_data = get("/vdp/registers")
regs = regs_data.get("registers") or regs_data.get("data")
if regs:
    r0b = regs[0x0B] if len(regs) > 0x0B else 0
    r10 = regs[0x10] if len(regs) > 0x10 else 0
    vs_mode = (r0b >> 2) & 1
    hs_mode = r0b & 3
    scroll_w = r10 & 3
    scroll_h = (r10 >> 4) & 3
    print(f"\nVDP scroll config: VS_mode={vs_mode}, HS_mode={hs_mode}, scroll_size({scroll_w},{scroll_h})")
    
    # H40 mode?
    r0c = regs[0x0C] if len(regs) > 0x0C else 0
    h40 = (r0c & 0x81) != 0
    print(f"H40_mode={h40}")
    
    # Plane addrs
    r02 = regs[0x02] if len(regs) > 0x02 else 0
    r04 = regs[0x04] if len(regs) > 0x04 else 0
    plane_a_addr = (r02 & 0x38) << 10
    plane_b_addr = (r04 & 0x07) << 13
    print(f"Plane A addr: 0x{plane_a_addr:04X}, Plane B addr: 0x{plane_b_addr:04X}")
