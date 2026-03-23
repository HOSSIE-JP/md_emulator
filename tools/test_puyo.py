"""Test script for Puyo Puyo ROM analysis"""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8110"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Reset and load
api("POST", "/api/v1/emulator/reset")
print("Loading Puyo ROM...")
r = api("POST", "/api/v1/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
print(f"Load: {r}")

# Run 300 frames (~5 seconds)
print("Running 300 frames...")
for i in range(300):
    api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
print(f"Done")

# CPU state
r = api("GET", "/api/v1/cpu/state")
m68k = r.get("cpu", {}).get("m68k", {})
print(f"\nM68K PC: 0x{m68k.get('pc', 0):06X} SR: 0x{m68k.get('sr', 0):04X}")
print(f"Stopped: {m68k.get('stopped', False)} Exception: {m68k.get('last_exception', None)}")

# VDP registers
r = api("GET", "/api/v1/vdp/registers")
regs = r.get("registers", [])
print(f"\nVDP Registers:")
for i, v in enumerate(regs):
    if v != 0:
        print(f"  reg[0x{i:02X}] = 0x{v:02X} ({v})")

# Check mode
if len(regs) > 0x0C:
    h40 = (regs[0x0C] & 0x81) in (0x81, 0x01)
    print(f"\nH40 mode: {h40}")
    hint_enabled = (regs[0] & 0x10) != 0
    vint_enabled = (regs[1] & 0x20) != 0
    disp_enabled = (regs[1] & 0x40) != 0
    dma_enabled = (regs[1] & 0x10) != 0
    print(f"HInt enabled: {hint_enabled}, VInt enabled: {vint_enabled}")
    print(f"Display enabled: {disp_enabled}, DMA enabled: {dma_enabled}")
    print(f"HInt counter (R10): {regs[0x0A]}")

    # Plane addresses
    plane_a = (regs[2] & 0x38) << 10
    plane_b = (regs[4] & 0x07) << 13
    window = (regs[3] & 0x3E) << 10
    sat = (regs[5] & 0x7F) << 9
    hscroll = (regs[0x0D] & 0x3F) << 10
    print(f"\nPlane A @ 0x{plane_a:04X}, Plane B @ 0x{plane_b:04X}")
    print(f"Window @ 0x{window:04X}")
    print(f"SAT @ 0x{sat:04X}, HScroll @ 0x{hscroll:04X}")

# Sprites
r = api("GET", "/api/v1/vdp/sprites")
sprites = r.get("sprites", [])
visible = [s for s in sprites if s.get("x", -128) >= -32 and s.get("x", -128) < 352
           and s.get("y", -128) >= -32 and s.get("y", -128) < 256]
print(f"\nTotal sprites: {len(sprites)}, Visible: {len(visible)}")
for s in visible[:30]:
    print(f"  [{s['index']:2d}] x={s['x']:4d} y={s['y']:4d} {s['width']}x{s['height']} "
          f"tile=0x{s['tile']:03X} pal={s['palette']} pri={s['priority']} link={s['link']}")

# CRAM - check raw
r = api("GET", "/api/v1/vdp/cram")
cram = r.get("colors", r.get("cram", []))
non_zero = sum(1 for c in cram if c != 0)
print(f"\nCRAM non-zero: {non_zero}/{len(cram)}")
# Show first palette
if len(cram) >= 16:
    print(f"Palette 0: {['0x{:06X}'.format(c & 0xFFFFFF) for c in cram[:16]]}")
    print(f"Palette 1: {['0x{:06X}'.format(c & 0xFFFFFF) for c in cram[16:32]]}")

# Frame analysis
r = api("GET", "/api/v1/video/frame")
pixels = r.get("pixels_argb", [])
unique = len(set(pixels))
non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"\nFrame: {unique} unique colors, {non_black}/{len(pixels)} non-black")

# Row analysis
print("\nRow analysis (non-empty rows):")
row_count = 0
for y in range(224):
    row = pixels[y*320:(y+1)*320]
    uniq = len(set(row))
    nb = sum(1 for p in row if (p & 0xFFFFFF) != 0)
    if uniq > 1 or nb > 0:
        row_count += 1
        if row_count <= 15:
            print(f"  row {y:3d}: {uniq:3d} colors, {nb:3d} non-black px")
print(f"Total non-empty rows: {row_count}/224")

# Audio
r = api("GET", "/api/v1/audio/samples?frames=800")
samples = r.get("samples", [])
max_amp = max(abs(s) for s in samples) if samples else 0
non_silent = sum(1 for s in samples if abs(s) > 0.001)
print(f"\nAudio: {len(samples)} samples, max={max_amp:.4f}, non-silent={non_silent}")
