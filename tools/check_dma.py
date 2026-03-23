"""Check what DMA operations have been performed, and verify tile 3FE/3FF should be non-zero"""
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

# Fresh reset
post("/emulator/reset")
# Step fewer frames to see early state
post("/emulator/step", {"frames": 100})

# Check DMA stats
cpu = get("/cpu/state")
m68k = cpu.get("m68k") or cpu.get("cpu")
print("After 100 frames:")
print(f"  PC: 0x{m68k.get('pc', 0):06X}")

# Get VDP state
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")

# Check DMA counters - these are in the VDP debug state
# Let's check the VDP status from a different angle
vdp_state = get("/vdp/state")
print(f"\nVDP state keys: {list(vdp_state.keys())}")

# Check tile 3FE at VRAM 0x7FC0
addr = 0x3FE * 32  # = 0x7FC0
vram = get(f"/vdp/vram?addr={addr}&len=32")
data = vram.get("data") or vram.get("vram")
non_zero = sum(1 for b in data if b != 0)
print(f"\nTile 0x3FE at VRAM 0x{addr:04X}: non-zero bytes = {non_zero}")
if non_zero > 0:
    print(f"  Data: {[f'{b:02X}' for b in data]}")
else:
    print(f"  ALL ZERO")

# Check a wider range - tiles near 3FE/3FF
print("\n--- Tile data survey (tile 0x3F0 - 0x400) ---")
for tile in range(0x3F0, 0x400):
    addr = tile * 32
    vram = get(f"/vdp/vram?addr={addr}&len=32")
    data = vram.get("data") or vram.get("vram")
    non_zero = sum(1 for b in data if b != 0)
    if non_zero > 0:
        print(f"  Tile 0x{tile:03X}: {non_zero} non-zero bytes")

# Now step to frame 3000 and check again
post("/emulator/step", {"frames": 2900})
print("\n\nAfter 3000 frames:")

# Check tile 3FE again
addr = 0x3FE * 32
vram = get(f"/vdp/vram?addr={addr}&len=32")
data = vram.get("data") or vram.get("vram")
non_zero = sum(1 for b in data if b != 0)
print(f"Tile 0x3FE: non-zero bytes = {non_zero}")

# Check tile 3FF
addr = 0x3FF * 32
vram = get(f"/vdp/vram?addr={addr}&len=32")
data = vram.get("data") or vram.get("vram")
non_zero = sum(1 for b in data if b != 0)
print(f"Tile 0x3FF: non-zero bytes = {non_zero}")

# Let's check what BG index is
print(f"\nBG color index: {rdata[7] & 0x3F}")

# Check CRAM palette 0 (which 83FE uses)
cram = get("/vdp/colors")
colors = cram["colors_argb"]
print("\nPalette 0 colors:")
for i in range(16):
    c = colors[i]
    r = (c >> 16) & 0xFF
    g = (c >> 8) & 0xFF
    b = c & 0xFF
    print(f"  [{i:2d}] #{r:02x}{g:02x}{b:02x} = RGB({r},{g},{b})")

# Check if tile 3FE/3FF should actually be solid colored
# In Puyo Puyo, the playfield background is usually dark blue
# The nametable entry 83FE means:
# - bit 15 = 1 (priority)
# - bits 14:13 = 00 (palette 0)
# - bit 12 = 0 (no vflip)
# - bit 11 = 0 (no hflip)
# - bits 10:0 = 0x3FE
# 
# If tile 0x3FE is all zeros, the pixel index is 0 for all pixels
# Color = palette 0, index 0 = BG color
# This means the field background IS the BG color if tile 3FE is all zeros.
# 
# The actual compositing would then show:
# - Plane A pixel = 0 (transparent) 
# - Plane A priority = true (priority 1)
# But in compositing, priority only matters when pixel is non-zero!
# So transparent Plane A with priority doesn't block Plane B.

print("\n--- Conclusion ---")
print("Tile 0x3FE/0x3FF are all zeros (transparent).")
print("Plane A entry 0x83FE: palette 0, priority 1, tile 0x3FE")
print("Since all pixels are 0 (transparent), Plane A doesn't cover Plane B here.")
print("This means Plane B vine pattern shows through in the field area.")
print("Is this correct? In real Puyo Puyo:")
print("  - The field background should be a solid dark color")
print("  - This could mean DMA fill to tile 3FE/3FF is not working properly")
print("  - OR the game uses a different mechanism to show the field background")
