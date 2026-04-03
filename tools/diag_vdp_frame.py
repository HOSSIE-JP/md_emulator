"""Check VDP frame output and game state for 北へPM"""
import requests
import struct
BASE = "http://localhost:8080/api/v1"

s = requests.Session()
# Still using the current state (after START presses + 500 frames)

# Get frame dimensions and a small sample of pixels
frame = s.get(f"{BASE}/video/frame").json()
width = frame.get("width", 0)
height = frame.get("height", 0)
pixels = frame.get("pixels_argb", [])
print(f"Frame: {width}x{height}, pixel count: {len(pixels)}")

# Sample some pixels to check what's on screen
if pixels:
    # Sample center, top-left, corners
    for name, x, y in [("top-left", 10, 10), ("center", width//2, height//2),
                         ("top-center", width//2, 10), ("bottom-center", width//2, height-10)]:
        idx = y * width + x
        if idx < len(pixels):
            argb = pixels[idx]
            a = (argb >> 24) & 0xFF
            r = (argb >> 16) & 0xFF
            g = (argb >> 8) & 0xFF
            b = argb & 0xFF
            print(f"  {name} ({x},{y}): ARGB=({a},{r},{g},{b})")

    # Count unique colors
    unique_colors = set()
    for p in pixels:
        unique_colors.add(p & 0xFFFFFF)
    print(f"  Unique colors: {len(unique_colors)}")

    # Check if all black (stuck/blank screen)
    non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
    print(f"  Non-black pixels: {non_black}/{len(pixels)}")

# Check VDP registers for mode info
vdp = s.get(f"{BASE}/vdp/registers").json()
regs = vdp.get("registers", [])
if len(regs) > 12:
    print(f"\nVDP Mode:")
    print(f"  Reg 0: 0x{regs[0]:02X} (H-int: {bool(regs[0] & 0x10)})")
    print(f"  Reg 1: 0x{regs[1]:02X} (Display: {bool(regs[1] & 0x40)}, V-int: {bool(regs[1] & 0x20)})")
    print(f"  Reg 12: 0x{regs[12]:02X} (H40: {bool(regs[12] & 0x81)})")
    print(f"  Frame: {vdp.get('frame')}")

# Check M68K state
cpu = s.get(f"{BASE}/cpu/state").json().get("cpu", {})
m68k = cpu.get("m68k", {})
print(f"\nM68K PC: 0x{m68k.get('pc', 0):06X}")
print(f"M68K D regs: {[f'0x{d:08X}' for d in m68k.get('d', [])]}")
print(f"M68K A regs: {[f'0x{a:08X}' for a in m68k.get('a', [])]}")
