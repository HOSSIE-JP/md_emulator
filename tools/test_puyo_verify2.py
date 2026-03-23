"""Extended Puyo verification - run more frames and check rendering"""
import urllib.request
import json

BASE = "http://127.0.0.1:8111"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Run 600 more frames (total ~900)
print("Running 600 more frames...")
for i in range(600):
    api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})

# Check VDP regs
r = api("GET", "/api/v1/vdp/registers")
regs = r["registers"]
print(f"Frame: {r.get('frame')}")
print(f"R00=0x{regs[0]:02X} R01=0x{regs[1]:02X} R02=0x{regs[2]:02X}")
print(f"R0B=0x{regs[0x0B]:02X} R0C=0x{regs[0x0C]:02X} R10=0x{regs[0x10]:02X}")
print(f"ctrl_writes={r.get('ctrl_writes')} data_writes={r.get('data_writes')}")
print(f"dma_writes={r.get('dma_writes')} dma_length_total={r.get('dma_length_total')}")

# Check CRAM
r_cram = api("GET", "/api/v1/vdp/cram")
cram = r_cram.get("cram", [])
nz_cram = sum(1 for c in cram if c != 0)
print(f"\nCRAM non-zero: {nz_cram}/64")

# Check frame
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
unique = len(set(pixels))
nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"Frame: {unique} colors, {nb}/{len(pixels)} non-black")

# Check VRAM for tile data
r = api("GET", "/api/v1/vdp/vram?addr=0&len=65536")
vram = r.get("data", [])
# Count non-zero bytes in each 4K region
for region in range(16):
    start = region * 4096
    end = start + 4096
    nz = sum(1 for b in vram[start:end] if b != 0)
    if nz > 0:
        print(f"VRAM 0x{start:04X}-0x{end:04X}: {nz} non-zero bytes")

# Check nametable at Plane A
plane_a = (regs[2] & 0x38) << 10
print(f"\nPlane A base: 0x{plane_a:04X}")
nt = vram[plane_a:plane_a+2048]
nz_entries = 0
tile_set = set()
for i in range(0, len(nt)-1, 2):
    val = (nt[i] << 8) | nt[i+1]
    if val != 0:
        nz_entries += 1
        tile_idx = val & 0x7FF
        tile_set.add(tile_idx)
print(f"Plane A nametable: {nz_entries} non-zero entries, {len(tile_set)} unique tiles")
print(f"Tile indices: {sorted(list(tile_set))[:20]}...")

# Check Plane B
plane_b = (regs[4] & 0x07) << 13
print(f"\nPlane B base: 0x{plane_b:04X}")
nt_b = vram[plane_b:plane_b+2048]
nz_b = 0
for i in range(0, len(nt_b)-1, 2):
    if (nt_b[i] << 8) | nt_b[i+1] != 0:
        nz_b += 1
print(f"Plane B nametable: {nz_b} non-zero entries")

# Check SAT raw data
sat_addr = (regs[5] & 0x7F) << 9
print(f"\nSAT base: 0x{sat_addr:04X}")
sat_raw = vram[sat_addr:sat_addr+640]
# Print first 16 sprites raw
for i in range(16):
    entry = sat_raw[i*8:(i+1)*8]
    y = ((entry[0] << 8) | entry[1]) & 0x3FF
    sz = entry[2]
    link = entry[3] & 0x7F
    attr = (entry[4] << 8) | entry[5]
    x = ((entry[6] << 8) | entry[7]) & 0x1FF
    if y != 0 or x != 0 or link != 0 or attr != 0 or sz != 0:
        print(f"  SAT[{i:2d}] y={y:3d} sz=0x{sz:02X} link={link} attr=0x{attr:04X} x={x:3d}")

# Check CRAM in detail
print("\nCRAM values:")
for i, c in enumerate(cram):
    if c != 0:
        r_c = (c >> 1) & 7
        g_c = (c >> 5) & 7
        b_c = (c >> 9) & 7
        print(f"  [{i:2d}] 0x{c:04X} = R{r_c} G{g_c} B{b_c}")
