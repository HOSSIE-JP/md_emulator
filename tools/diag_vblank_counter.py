#!/usr/bin/env python3
"""Check VDP read_status debug counters to verify M68K sees VBlank."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056

requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

# Run 125 frames (VINT goes OFF at frame 125)
for i in range(126):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

apu = requests.get(f"{API}/apu/state").json()
print(f"After 126 frames:")
print(f"  VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'}")
print(f"  VDP scanline={apu.get('vdp_scanline')}")
print(f"  VDP status={apu.get('vdp_status')}")
print(f"  read_status total={apu.get('vdp_read_status_total')}")
print(f"  read_status vblank_count={apu.get('vdp_read_status_vblank_count')}")

# Run 10 more frames (VINT is OFF, M68K should be polling VDP status)
for i in range(10):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

apu = requests.get(f"{API}/apu/state").json()
print(f"\nAfter 136 frames:")
print(f"  VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'}")
print(f"  VDP scanline={apu.get('vdp_scanline')}")
print(f"  VDP status={apu.get('vdp_status')}")
print(f"  read_status total={apu.get('vdp_read_status_total')}")
print(f"  read_status vblank_count={apu.get('vdp_read_status_vblank_count')}")

# Run 100 more frames
for i in range(100):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

apu = requests.get(f"{API}/apu/state").json()
print(f"\nAfter 236 frames:")
print(f"  VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'}")
print(f"  VDP scanline={apu.get('vdp_scanline')}")
print(f"  VDP status={apu.get('vdp_status')}")
print(f"  read_status total={apu.get('vdp_read_status_total')}")
print(f"  read_status vblank_count={apu.get('vdp_read_status_vblank_count')}")
print(f"  vdp_frame={apu.get('vdp_frame')}")

# Calculate ratio
total = apu.get('vdp_read_status_total', 1)
vblank = apu.get('vdp_read_status_vblank_count', 0)
print(f"\n  VBlank ratio: {vblank}/{total} = {vblank/max(total,1)*100:.1f}%")
