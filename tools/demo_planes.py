"""Analyze the demo gameplay screen at frame 3000.
Reset, go to frame 3000, and examine Plane B nametable."""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Reset and go to frame 3000  
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 3000})

regs = api_get("/vdp/registers")["registers"]
r16 = regs[16]
sw = {0:32, 1:64, 3:128}.get(r16 & 3, 32)
sh = {0:32, 1:64, 3:128}.get((r16 >> 4) & 3, 32)

# Plane addresses
pa_addr = (regs[2] & 0x38) << 10
pb_addr = (regs[4] & 0x07) << 13
print(f"Plane A: 0x{pa_addr:04X}")
print(f"Plane B: 0x{pb_addr:04X}")
print(f"Scroll size: {sw}x{sh}")
print(f"R11=0x{regs[11]:02X} (HS={regs[11]&3}, VS={(regs[11]>>2)&1})")

# Read Plane B nametable (just first 4 rows, sw columns)
size = sw * min(sh, 4) * 2
pb_data = api_get(f"/vdp/vram?addr={pb_addr}&len={size}")["data"]

print(f"\nPlane B nametable (first 4 rows, first 20 cols):")
for row in range(4):
    line = []
    for col in range(min(20, sw)):
        off = (row * sw + col) * 2
        entry = (pb_data[off] << 8) | pb_data[off + 1]
        tile = entry & 0x7FF
        pal = (entry >> 13) & 3
        pri = (entry >> 15) & 1
        line.append(f"{tile:03X}")
    print(f"  Row {row}: {' '.join(line)}")

# Check Plane A too (might contain the playfield)
pa_data = api_get(f"/vdp/vram?addr={pa_addr}&len={size}")["data"]
print(f"\nPlane A nametable (first 4 rows, first 20 cols):")
for row in range(4):
    line = []
    for col in range(min(20, sw)):
        off = (row * sw + col) * 2
        entry = (pa_data[off] << 8) | pa_data[off + 1]
        tile = entry & 0x7FF
        pal = (entry >> 13) & 3
        pri = (entry >> 15) & 1
        line.append(f"{tile:03X}")
    print(f"  Row {row}: {' '.join(line)}")

# Check VSRAM
vsram = api_get("/vdp/vsram")["vsram"]
any_nonzero = any(v != 0 for v in vsram)
print(f"\nVSRAM has non-zero? {any_nonzero}")
if any_nonzero:
    for i, v in enumerate(vsram):
        if v != 0:
            print(f"  VSRAM[{i}] = {v}")

# Render Plane A and B separately as debug images
# Actually let's use the existing debug endpoint if available
