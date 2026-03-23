"""Determine which planes have content on the title screen.
Check if the wave effect is on the correct plane (A or B).
The HInt handler writes to VSRAM address 0 = Plane A vscroll.
"""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

regs = api_get("/vdp/registers")
r = regs["registers"]

# Plane addresses
plane_a_addr = (r[2] & 0x38) << 10
plane_b_addr = (r[4] & 0x07) << 13
window_addr = (r[3] & 0x3E) << 10
sprite_addr = (r[5] & 0x7F) << 9

print(f"Plane A nametable: 0x{plane_a_addr:04X}")
print(f"Plane B nametable: 0x{plane_b_addr:04X}")
print(f"Window nametable:  0x{window_addr:04X}")
print(f"Sprite table:      0x{sprite_addr:04X}")

# Read some plane A and B entries to see which has the background
# Scroll size
r16 = r[16]
sw = {0:32, 1:64, 3:128}.get(r16 & 3, 32)
sh = {0:32, 1:64, 3:128}.get((r16 >> 4) & 3, 32)
print(f"Scroll size: {sw}x{sh}")

# Read first row of Plane A nametable
pa_data = api_get(f"/vdp/vram?addr={plane_a_addr}&len={sw*2}")["data"]
print(f"\nPlane A first row (first 20 entries):")
for i in range(min(20, sw)):
    entry = (pa_data[i*2] << 8) | pa_data[i*2+1]
    tile = entry & 0x7FF
    pal = (entry >> 13) & 3
    pri = (entry >> 15) & 1
    hf = (entry >> 11) & 1
    vf = (entry >> 12) & 1
    print(f"  col {i:2d}: tile=0x{tile:03X} pal={pal} pri={pri} hf={hf} vf={vf}")

# Read first row of Plane B nametable  
pb_data = api_get(f"/vdp/vram?addr={plane_b_addr}&len={sw*2}")["data"]
print(f"\nPlane B first row (first 20 entries):")
for i in range(min(20, sw)):
    entry = (pb_data[i*2] << 8) | pb_data[i*2+1]
    tile = entry & 0x7FF
    pal = (entry >> 13) & 3
    pri = (entry >> 15) & 1
    hf = (entry >> 11) & 1
    vf = (entry >> 12) & 1
    print(f"  col {i:2d}: tile=0x{tile:03X} pal={pal} pri={pri} hf={hf} vf={vf}")

# Count non-zero tiles in each plane
pa_nonzero = 0
pb_nonzero = 0
for i in range(sw * sh):
    a = (pa_data[i*2] << 8) | pa_data[i*2+1] if i*2+1 < len(pa_data) else 0
    if a & 0x7FF: pa_nonzero += 1

# Need to read more data for full plane
pa_full = api_get(f"/vdp/vram?addr={plane_a_addr}&len={sw*sh*2}")["data"]
pb_full = api_get(f"/vdp/vram?addr={plane_b_addr}&len={sw*sh*2}")["data"]

pa_nonzero = sum(1 for i in range(sw*sh) if i*2+1 < len(pa_full) and ((pa_full[i*2] << 8) | pa_full[i*2+1]) & 0x7FF)
pb_nonzero = sum(1 for i in range(sw*sh) if i*2+1 < len(pb_full) and ((pb_full[i*2] << 8) | pb_full[i*2+1]) & 0x7FF)

print(f"\nPlane A non-zero tiles: {pa_nonzero} / {sw*sh}")
print(f"Plane B non-zero tiles: {pb_nonzero} / {sw*sh}")
