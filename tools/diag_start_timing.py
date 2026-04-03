#!/usr/bin/env python3
"""Check M68K behavior with different START timing. Also trace M68K PC."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

# Load and reset
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

# Part 1: Check controller read
print("=== Controller test ===")
for frame in range(10):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Set START
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Read controller I/O ports
io_data1 = requests.get(f"{API}/cpu/memory", params={"addr": 0xA10003, "len": 1}).json().get("data", [0])
io_data2 = requests.get(f"{API}/cpu/memory", params={"addr": 0xA10009, "len": 1}).json().get("data", [0])
print(f"IO port 0xA10003 (P1 data): {io_data1}")
print(f"IO port 0xA10009 (P1 ctrl): {io_data2}")

# Release
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Part 2: Full run - press START at different timings
requests.post(f"{API}/emulator/reset")

prev_vint = None
start_phases = [(50, 60), (100, 110), (150, 160), (250, 260), (400, 410)]
start_active = set()

for frame in range(1200):
    # Check start press schedule
    for (start, end) in start_phases:
        if frame == start:
            requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
            start_active.add((start, end))
        if frame == end:
            requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})
            start_active.discard((start, end))

    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

    # Sample at key frames
    if frame % 100 == 0 or frame in [49, 59, 110, 124, 125, 126, 127, 160, 260, 410]:
        apu = requests.get(f"{API}/apu/state").json()
        vint_en = apu.get("vdp_vint_enabled")
        bank = apu.get("z80_bank_68k_addr", "?")
        vint_count = apu.get("vint_delivered", 0)
        changed = ""
        if vint_en != prev_vint:
            changed = " <<< CHANGED"
        print(f"Frame {frame:4d}: VINT={'ON' if vint_en else 'OFF':3s} bank={bank} "
              f"vints={vint_count} z80_pc=0x{apu.get('z80_pc',0):04X}"
              f" start={'HELD' if start_active else 'OFF':4s}{changed}")
        prev_vint = vint_en

# Final
apu = requests.get(f"{API}/apu/state").json()
cpu = requests.get(f"{API}/cpu/state").json()
m68k = cpu["cpu"]["m68k"]
print(f"\n=== Final ===")
print(f"M68K PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")
print(f"VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'} delivered={apu.get('vint_delivered')}")
print(f"Bank={apu.get('z80_bank_68k_addr')} DAC={apu.get('dac_enabled')}")
print(f"output_nonzero={apu.get('debug_output_nonzero')}")
