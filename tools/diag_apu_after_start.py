#!/usr/bin/env python3
"""Full APU diagnostic after START press."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

# Load and reset
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

# Run 200 frames
for i in range(200):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
print("Frame 200 reached")

# Press START for 5 frames
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
for i in range(5):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Run 800 more frames to reach frame ~1005
for i in range(800):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
print("Frame 1005 reached")

# Get full state
cpu_data = requests.get(f"{API}/cpu/state").json()
vdp_data = requests.get(f"{API}/vdp/registers").json()

# Get APU state
apu_data = requests.get(f"{API}/apu/state").json() if True else {}

# Check Z80 comm area
z80_comm = requests.get(f"{API}/cpu/memory", params={"addr": 0xA00100, "len": 32}).json().get("data", [])

m68k = cpu_data["cpu"]["m68k"]
z80 = cpu_data["cpu"]["z80"]
regs = vdp_data["registers"]

print(f"\n=== CPU State ===")
print(f"M68K: PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X} cycles={m68k['total_cycles']}")
print(f"Z80: PC=0x{z80['pc']:04X} halted={z80['halted']}")

print(f"\n=== VDP State ===")
print(f"Reg1=0x{regs[1]:02X} (VINT={'ON' if regs[1]&0x20 else 'OFF'}, DISP={'ON' if regs[1]&0x40 else 'OFF'})")
print(f"VINT delivered: {vdp_data.get('vint_delivered', '?')}")
print(f"Frame: {vdp_data.get('frame', '?')}")

print(f"\n=== Z80 Communication ===")
print(f"Bytes: {' '.join(f'{b:02X}' for b in z80_comm[:32])}")

print(f"\n=== APU State ===")
if isinstance(apu_data, dict):
    for key in sorted(apu_data.keys()):
        val = apu_data[key]
        if isinstance(val, list) and len(val) > 10:
            print(f"  {key}: [{len(val)} items] first10: {val[:10]}")
        elif isinstance(val, dict):
            print(f"  {key}:")
            for k2, v2 in sorted(val.items()):
                if isinstance(v2, list) and len(v2) > 10:
                    print(f"    {k2}: [{len(v2)} items]")
                else:
                    print(f"    {k2}: {v2}")
        else:
            print(f"  {key}: {val}")
