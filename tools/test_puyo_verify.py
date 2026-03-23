"""Verify Puyo Puyo with fixed DMA/HInt/Window"""
import urllib.request
import json
import time

BASE = "http://127.0.0.1:8111"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

time.sleep(2)

# Load ROM
print("Loading Puyo ROM...")
r = api("POST", "/api/v1/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
print(f"Load: {r}")

# Run 300 frames
print("Running 300 frames...")
for i in range(300):
    api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})

# Check state
r = api("GET", "/api/v1/cpu/state")
m68k = r["cpu"]["m68k"]
print(f"\nPC: 0x{m68k['pc']:06X} SR: 0x{m68k['sr']:04X} stopped={m68k['stopped']}")

# VDP registers
r = api("GET", "/api/v1/vdp/registers")
regs = r["registers"]
print(f"\nVDP Regs (non-zero):")
for i, v in enumerate(regs):
    if v != 0:
        print(f"  R{i:02d} (0x{i:02X}) = 0x{v:02X}")
print(f"Frame: {r.get('frame')}, data_writes: {r.get('data_writes')}, ctrl_writes: {r.get('ctrl_writes')}")

# Sprites 
r = api("GET", "/api/v1/vdp/sprites")
sprites = r["sprites"]
visible = [s for s in sprites if -32 <= s['x'] < 352 and -32 <= s['y'] < 256]
print(f"\nTotal sprites: {len(sprites)}, Visible: {len(visible)}")
for s in visible[:20]:
    print(f"  [{s['index']:2d}] x={s['x']:4d} y={s['y']:4d} {s['width']}x{s['height']} "
          f"tile=0x{s['tile']:03X} pal={s['palette']} pri={s['priority']} link={s['link']}")

# CRAM
r = api("GET", "/api/v1/vdp/colors")
colors = r.get("colors_argb", [])
nz = sum(1 for c in colors if (c & 0xFFFFFF) != 0)
print(f"\nCRAM ARGB non-zero: {nz}/64")

# Frame 
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
unique = len(set(pixels))
nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"Frame: {unique} colors, {nb}/{len(pixels)} non-black")

# Row analysis
print("\nRow analysis (showing rows with >2 colors):")
rows_with_content = 0
for y in range(224):
    row = pixels[y*320:(y+1)*320]
    uniq = len(set(row))
    if uniq > 2:
        rows_with_content += 1
print(f"Rows with >2 colors: {rows_with_content}/224")

# Check SAT
sat_addr = (regs[5] & 0x7F) << 9
r = api("GET", f"/api/v1/vdp/vram?addr={sat_addr}&len=640")
sat_data = r.get("data", [])
link = 0
sprite_count = 0
for i in range(80):
    base = link * 8
    if base + 7 >= len(sat_data):
        break
    entry = sat_data[base:base+8]
    y_pos = ((entry[0] << 8) | entry[1]) & 0x3FF
    next_link = entry[3] & 0x7F
    attr = (entry[4] << 8) | entry[5]
    x_pos = ((entry[6] << 8) | entry[7]) & 0x1FF
    if y_pos > 0 or x_pos > 0 or next_link > 0 or attr > 0:
        sprite_count += 1
    if next_link == 0:
        break
    link = next_link
print(f"\nSAT linked sprites: {sprite_count}")

# Check nametable
plane_a = (regs[2] & 0x38) << 10
sw_bits = regs[0x10] & 3
sw = [32, 64, 32, 64][sw_bits]
r = api("GET", f"/api/v1/vdp/vram?addr={plane_a}&len={2048}")
nt = r.get("data", [])
nz_nt = sum(1 for i in range(0, len(nt)-1, 2) if (nt[i] << 8 | nt[i+1]) != 0)
print(f"Plane A nametable non-zero entries: {nz_nt}")

# Audio check
r = api("GET", "/api/v1/audio/samples?frames=800")
samples = r.get("samples", [])
max_amp = max(abs(s) for s in samples) if samples else 0
print(f"\nAudio: {len(samples)} samples, max_amp={max_amp:.4f}")
