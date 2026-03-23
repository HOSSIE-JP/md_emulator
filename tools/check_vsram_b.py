"""Check VSRAM[1] = Plane B vscroll, and also add debug for per-scanline VSRAM[2]."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

vsram = api_get("/vdp/vsram")
entries = vsram["vsram"]
print(f"VSRAM entries (word-level): {entries[:10]}")
print(f"VSRAM[0] = {entries[0]} (Plane A vscroll)")
print(f"VSRAM[1] = {entries[1]} (Plane B vscroll)")

# VSRAM[1] = 0xFDE2 → signed = -542
v = entries[1]
if v > 32767: v -= 65536
print(f"VSRAM[1] signed = {v}")

# Now, the real question: is the wave effect visible on the title screen?
# If Plane A is all transparent, the wave on Plane A is invisible.
# The background pattern IS on Plane B with constant vscroll.
# So the "stripes" might be referring to something else entirely.

# Let me render Plane A and B separately to check
# Actually, let me look at the framebuffer to see where pixel colors come from

# Get framebuffer
frame = api_get("/video/frame")
pixels = frame["pixels_argb"]
width = frame["width"]

# Check a few scanlines - if plane A is transparent, all visible pixels come from plane B
# Let's check if the vscroll wave is visible
print(f"\nSample pixels along column 160 (center):")
for y in range(0, 224, 8):
    px = pixels[y * width + 160]
    r = (px >> 16) & 0xFF
    g = (px >> 8) & 0xFF
    b = px & 0xFF
    print(f"  Line {y:3d}: pixel = ({r:3d}, {g:3d}, {b:3d}) = 0x{px:08X}")
