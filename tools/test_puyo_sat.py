"""Check SAT, nametables, VRAM usage after Puyo is running"""
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

# Get VDP registers
r = api("GET", "/api/v1/vdp/registers")
regs = r["registers"]

sat_addr = (regs[5] & 0x7F) << 9
plane_a = (regs[2] & 0x38) << 10
plane_b = (regs[4] & 0x07) << 13
window_addr = (regs[3] & 0x3E) << 10
print(f"SAT @ 0x{sat_addr:04X}, Plane A @ 0x{plane_a:04X}, B @ 0x{plane_b:04X}, Window @ 0x{window_addr:04X}")
hint_en = (regs[0] & 0x10) != 0
print(f"R00=0x{regs[0]:02X} HInt={hint_en}, R0A={regs[0x0A]} (hint counter)")
print(f"R0B=0x{regs[0x0B]:02X} (hscroll/vscroll mode)")

# Read SAT from VRAM
r = api("GET", f"/api/v1/vdp/vram?addr={sat_addr}&len=640")
sat_data = r.get("data", [])
print(f"\n--- SAT ({len(sat_data)} bytes) ---")
link = 0
for i in range(80):
    base = link * 8
    if base + 7 >= len(sat_data):
        break
    entry = sat_data[base:base+8]
    y = ((entry[0] << 8) | entry[1]) & 0x3FF
    sz = entry[2]
    h_cells = ((sz >> 2) & 3) + 1
    v_cells = (sz & 3) + 1
    next_link = entry[3] & 0x7F
    attr = (entry[4] << 8) | entry[5]
    x = ((entry[6] << 8) | entry[7]) & 0x1FF
    tile = attr & 0x7FF
    pal = (attr >> 13) & 3
    pri = (attr >> 15) & 1
    print(f"  SAT[{link:2d}]: y={y-128:4d} {h_cells}x{v_cells} link={next_link:2d} "
          f"tile=0x{tile:03X} pal={pal} pri={pri} x={x-128:4d}")
    if next_link == 0:
        break
    link = next_link

# Read plane A nametable
sw_bits = regs[0x10] & 3
sw = [32, 64, 32, 64][sw_bits]
sh_bits = (regs[0x10] >> 4) & 3
sh = [32, 32, 64, 64][sh_bits]
print(f"\n--- Plane A nametable (scroll={sw}x{sh}) ---")
r = api("GET", f"/api/v1/vdp/vram?addr={plane_a}&len={sw*sh*2}")
nt_data = r.get("data", [])
nz = 0
sample = []
for row in range(sh):
    for col in range(sw):
        idx = (row * sw + col) * 2
        if idx + 1 < len(nt_data):
            word = (nt_data[idx] << 8) | nt_data[idx + 1]
            if word != 0:
                nz += 1
                if len(sample) < 10:
                    sample.append((row, col, word))
print(f"Non-zero: {nz}")
for row, col, word in sample:
    tile = word & 0x7FF
    pal = (word >> 13) & 3
    pri = (word >> 15) & 1
    print(f"  [{row:2d},{col:2d}] tile=0x{tile:03X} pal={pal} pri={pri}")

# VRAM usage map
r = api("GET", f"/api/v1/vdp/vram?addr=0&len=65536")
vram = r.get("data", [])
print(f"\n--- VRAM usage per 4KB region ---")
total_nz = 0
for start in range(0, 65536, 4096):
    region = vram[start:start+4096]
    rnz = sum(1 for b in region if b != 0)
    total_nz += rnz
    if rnz > 0:
        print(f"  0x{start:04X}-0x{start+4095:04X}: {rnz:5d} non-zero bytes")
print(f"Total: {total_nz} non-zero bytes")

# CRAM
r = api("GET", "/api/v1/vdp/cram")
cram = r.get("colors", [])
print(f"\n--- CRAM ---")
for pal in range(4):
    row = cram[pal*16:(pal+1)*16]
    nz = sum(1 for c in row if c != 0)
    if nz > 0:
        print(f"Pal {pal} ({nz} colors): {['0x{:06X}'.format(c & 0xFFFFFF) for c in row]}")

# Frame
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
unique = len(set(pixels))
nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"\nFrame: {unique} colors, {nb}/{len(pixels)} non-black pixels")
