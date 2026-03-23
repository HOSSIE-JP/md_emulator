"""Check actual CRAM values and debug rendering issues"""
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

# Check raw CRAM
r = api("GET", "/api/v1/vdp/cram")
cram_raw = r.get("cram", [])
print(f"Raw CRAM (u16, {len(cram_raw)} entries):")
for pal in range(4):
    row = cram_raw[pal*16:(pal+1)*16]
    nz = sum(1 for c in row if c != 0)
    print(f"  Pal {pal}: {['0x{:04X}'.format(c) for c in row]} ({nz} non-zero)")

# Check ARGB colors
r = api("GET", "/api/v1/vdp/colors")
colors = r.get("colors_argb", [])
print(f"\nCRAM as ARGB ({len(colors)} entries):")
for pal in range(4):
    row = colors[pal*16:(pal+1)*16]
    nz = sum(1 for c in row if (c & 0xFFFFFF) != 0)
    if nz > 0:
        print(f"  Pal {pal}: {['0x{:08X}'.format(c) for c in row[:8]]}")
        print(f"           {['0x{:08X}'.format(c) for c in row[8:16]]}")

# Get VDP debug state
r = api("GET", "/api/v1/vdp/registers")
code = r.get("code")
addr = r.get("address")
status = r.get("status")
frame = r.get("frame")
dw = r.get("data_writes")
cw = r.get("ctrl_writes")
print(f"\nVDP: code={code} address=0x{addr:04X} status=0x{status:04X}")
print(f"Frame: {frame}, data_writes: {dw}, ctrl_writes: {cw}")

# Run 60 more frames and check again
print("\nRunning 60 more frames...")
for _ in range(60):
    api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})

r = api("GET", "/api/v1/vdp/cram")
cram_after = r.get("cram", [])
nz_after = sum(1 for c in cram_after if c != 0)
print(f"CRAM after 60 more frames: {nz_after} non-zero")
for pal in range(4):
    row = cram_after[pal*16:(pal+1)*16]
    nz = sum(1 for c in row if c != 0)
    if nz > 0:
        print(f"  Pal {pal}: {['0x{:04X}'.format(c) for c in row]}")

# Check DMA write count
r2 = api("GET", "/api/v1/vdp/registers")
dw2 = r2.get("data_writes")
cw2 = r2.get("ctrl_writes")
print(f"Data writes: {dw} -> {dw2} (+{dw2-dw})")
print(f"Ctrl writes: {cw} -> {cw2} (+{cw2-cw})")

# Check frame now
r = api("GET", "/api/v1/video/frame")
pixels = r["pixels_argb"]
unique = len(set(pixels))
nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
print(f"\nFrame: {unique} colors, {nb}/{len(pixels)} non-black")
# Show sample of pixel colors
sample_colors = list(set(pixels))[:20]
print(f"Sample colors: {['0x{:08X}'.format(c) for c in sample_colors]}")
