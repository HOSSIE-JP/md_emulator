#!/usr/bin/env python3
"""Narrow trace around frame 126 where VINT gets disabled."""
import requests

API = "http://localhost:8080/api/v1"

r = requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {r.status_code}")
requests.post(f"{API}/emulator/reset")

FRAME_CYCLES = 128056

# Fast-forward to frame 120
print("Fast-forwarding to frame 120...")
for frame in range(120):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Check state at frame 120
cr = requests.get(f"{API}/cpu/state")
cpu = cr.json()["cpu"]["m68k"]
vr = requests.get(f"{API}/vdp/registers")
regs = vr.json()["registers"]
print(f"Frame 120: PC=0x{cpu['pc']:06X} SR=0x{cpu['sr']:04X} reg1=0x{regs[1]:02X} cycles={cpu['total_cycles']}")

# Frame-by-frame from 120 to 135
prev_reg1 = regs[1]
for frame in range(121, 136):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    
    cr = requests.get(f"{API}/cpu/state")
    cpu = cr.json()["cpu"]["m68k"]
    vr = requests.get(f"{API}/vdp/registers")
    regs = vr.json()["registers"]
    reg1 = regs[1]
    
    print(f"Frame {frame}: PC=0x{cpu['pc']:06X} SR=0x{cpu['sr']:04X} reg1=0x{reg1:02X} cycles={cpu['total_cycles']}", end="")
    if reg1 != prev_reg1:
        print(f"  ** CHANGED from 0x{prev_reg1:02X}!", end="")
    print()
    prev_reg1 = reg1

# Now step by scanlines around the transition
# First, let's see what's at frame 126 start
print("\n--- Investigating frame 126 region ---")
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

# Fast-forward to frame 125
for frame in range(125):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

cr = requests.get(f"{API}/cpu/state")
cpu = cr.json()["cpu"]["m68k"]
vr = requests.get(f"{API}/vdp/registers")
regs = vr.json()["registers"]
print(f"Frame 125: PC=0x{cpu['pc']:06X} SR=0x{cpu['sr']:04X} reg1=0x{regs[1]:02X}")

# Step in smaller chunks through frame 126
SCANLINE_CYCLES = 488  # M68K cycles per scanline
prev_r1 = regs[1]
for chunk in range(262):  # 262 scanlines per NTSC frame
    requests.post(f"{API}/emulator/step", json={"cycles": SCANLINE_CYCLES})
    vr = requests.get(f"{API}/vdp/registers")
    r1 = vr.json()["registers"][1]
    if r1 != prev_r1:
        cr2 = requests.get(f"{API}/cpu/state")
        cpu2 = cr2.json()["cpu"]["m68k"]
        print(f"  Scanline ~{chunk}: reg1 CHANGED 0x{prev_r1:02X} -> 0x{r1:02X} "
              f"PC=0x{cpu2['pc']:06X} SR=0x{cpu2['sr']:04X} cycles={cpu2['total_cycles']}")
        print(f"  D regs: {['0x{:08X}'.format(d) for d in cpu2['d']]}")
        print(f"  A regs: {['0x{:08X}'.format(a) for a in cpu2['a']]}")
        prev_r1 = r1
