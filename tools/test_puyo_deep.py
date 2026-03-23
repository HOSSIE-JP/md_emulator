"""Deep analysis - run Puyo for 600 frames, check SAT, VRAM, DMA"""
import urllib.request
import json

BASE = "http://127.0.0.1:8110"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Already loaded, just run more frames
print("Running 600 more frames (total ~900)...")
for i in range(600):
    api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
print("Done")

# Check state
r = api("GET", "/api/v1/cpu/state")
m68k = r["cpu"]["m68k"]
print(f"\nPC: 0x{m68k['pc']:06X} SR: 0x{m68k['sr']:04X} stopped={m68k['stopped']}")
print(f"D: {['0x{:08X}'.format(d) for d in m68k['d']]}")

# VDP regs
r = api("GET", "/api/v1/vdp/registers")
regs = r["registers"]
print(f"\nVDP Regs (non-zero):")
for i, v in enumerate(regs):
    if v != 0:
        print(f"  R{i:02d} (0x{i:02X}) = 0x{v:02X}")

# CRAM
r = api("GET", "/api/v1/vdp/cram")
cram = r.get("colors", [])
for pal in range(4):
    row = cram[pal*16:(pal+1)*16]
    nz = sum(1 for c in row if c != 0)
    if nz > 0:
        print(f"\nPalette {pal} ({nz} non-zero):")
        print(f"  {['0x{:06X}'.format(c & 0xFFFFFF) for c in row]}")

# Sprites
r = api("GET", "/api/v1/vdp/sprites")
sprites = r["sprites"]
print(f"\nSprites: {len(sprites)} total")
for s in sprites[:10]:
    print(f"  [{s['index']:2d}] x={s['x']:4d} y={s['y']:4d} {s['width']}x{s['height']} "
          f"tile=0x{s['tile']:03X} pal={s['palette']} link={s['link']}")

# Check SAT raw memory
sat_addr = (regs[5] & 0x7F) << 9
print(f"\n--- SAT raw at 0x{sat_addr:04X} ---")
r = api("GET", f"/api/v1/vdp/vram")
vram_data = r.get("vram", r.get("data", []))
print(f"VRAM size: {len(vram_data)}")
if len(vram_data) > sat_addr + 80*8:
    for i in range(min(20, 80)):
        base = sat_addr + i * 8
        entry = vram_data[base:base+8]
        y = ((entry[0] << 8) | entry[1]) & 0x3FF
        size = entry[2]
        link = entry[3] & 0x7F
        attr = (entry[4] << 8) | entry[5]
        x = ((entry[6] << 8) | entry[7]) & 0x1FF
        if y != 0 or x != 0 or link != 0 or attr != 0:
            print(f"  SAT[{i:2d}]: y={y-128:4d} size=0x{size:02X} link={link:2d} "
                  f"attr=0x{attr:04X} x={x-128:4d}")
        else:
            print(f"  SAT[{i:2d}]: empty")
        if link == 0 and i > 0:
            break

# Frame color analysis
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
unique = len(set(pixels))
non_black = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"\nFrame: {unique} colors, {non_black}/{len(pixels)} non-black")

# Check plane data
print("\n--- Plane A nametable check ---")
plane_a = (regs[2] & 0x38) << 10
scroll_w, scroll_h = {0: (32,32), 1: (64,32), 2: (32,64), 3: (64,64)}.get(regs[0x10] & 3, (32,32))
print(f"Plane A at 0x{plane_a:04X}, scroll size: {scroll_w}x{scroll_h}")
non_zero_entries = 0
for row in range(min(scroll_h, 28)):
    for col in range(min(scroll_w, 40)):
        addr = plane_a + (row * scroll_w + col) * 2
        if addr + 1 < len(vram_data):
            word = (vram_data[addr] << 8) | vram_data[addr+1]
            if word != 0:
                non_zero_entries += 1
print(f"Non-zero nametable entries: {non_zero_entries}")

# Check VRAM usage
non_zero_vram = sum(1 for b in vram_data if b != 0)
print(f"Total non-zero VRAM bytes: {non_zero_vram}/{len(vram_data)}")

