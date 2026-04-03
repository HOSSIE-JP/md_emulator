#!/usr/bin/env python3
"""Check VDP VBlank status bit at scanline granularity."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056

requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

for i in range(127):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

print("Stepping in small increments to catch VBlank...")
for i in range(600):
    requests.post(f"{API}/emulator/step", json={"cycles": 488})
    vdp = requests.get(f"{API}/vdp/registers").json()
    scanline = vdp.get("scanline", "?")
    frame = vdp.get("frame", "?")
    status = vdp.get("status", 0)
    vblank_bit = (status >> 3) & 1

    if i < 5 or vblank_bit or i % 100 == 0:
        print(f"  step {i:3d}: scanline={scanline} frame={frame} status=0x{status:04X} VBlank={vblank_bit}")

    if vblank_bit:
        print(f"  >>> VBlank FOUND at step {i}!")
        break
else:
    print("  VBlank NOT found in 600 scanlines!")
    vdp = requests.get(f"{API}/vdp/registers").json()
    print(f"  Final: scanline={vdp.get('scanline')} frame={vdp.get('frame')} status=0x{vdp.get('status',0):04X}")
