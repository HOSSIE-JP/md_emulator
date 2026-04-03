#!/usr/bin/env python3
"""Trace VDP register 1 changes across frames."""
import requests, sys

API = "http://localhost:8080/api/v1"

# Load ROM
r = requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {r.status_code} {r.text[:100]}")
r = requests.post(f"{API}/emulator/reset")
print(f"Reset: {r.status_code}")

prev_reg1 = None

# Check initial state
r = requests.get(f"{API}/vdp/registers")
regs = r.json()
if isinstance(regs, list) and len(regs) > 1:
    prev_reg1 = regs[1]
elif isinstance(regs, dict):
    prev_reg1 = regs.get("registers", [0,0])[1] if "registers" in regs else None
print(f"Frame 0: VDP reg1 = 0x{prev_reg1:02X} (VINT={'ON' if prev_reg1 & 0x20 else 'OFF'}, DISP={'ON' if prev_reg1 & 0x40 else 'OFF'}, DMA={'ON' if prev_reg1 & 0x10 else 'OFF'})")

# Step frame by frame, check reg1
FRAME_CYCLES = 128056  # ~1 NTSC frame
for frame in range(1, 201):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    
    r = requests.get(f"{API}/vdp/registers")
    data = r.json()
    if isinstance(data, list):
        regs = data
    elif isinstance(data, dict) and "registers" in data:
        regs = data["registers"]
    else:
        continue
    
    if len(regs) > 1:
        reg1 = regs[1]
        if reg1 != prev_reg1:
            print(f"Frame {frame}: VDP reg1 CHANGED 0x{prev_reg1:02X} -> 0x{reg1:02X} (VINT={'ON' if reg1 & 0x20 else 'OFF'}, DISP={'ON' if reg1 & 0x40 else 'OFF'}, DMA={'ON' if reg1 & 0x10 else 'OFF'})")
            prev_reg1 = reg1
    
    if frame % 50 == 0:
        cr = requests.get(f"{API}/cpu/state")
        cpu = cr.json()
        pc = cpu.get("pc", 0)
        print(f"Frame {frame}: reg1=0x{prev_reg1:02X}, M68K PC=0x{pc:06X}")

print(f"\nFinal: VDP reg1 = 0x{prev_reg1:02X}")
