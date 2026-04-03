#!/usr/bin/env python3
"""Trace VINT enable/disable around START press and bank register changes."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

# Load and reset
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

prev_vint_en = None
prev_bank = None
prev_vint_count = 0

for frame in range(1200):
    # Press START at frames 120-130 (before VINT gets disabled at ~126)
    if frame == 120:
        requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
    if frame == 130:
        requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})
    # Press START again at 200-210
    if frame == 200:
        requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
    if frame == 210:
        requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

    # Check every 10 frames, or critical frames
    if frame % 50 == 0 or (120 <= frame <= 140) or (200 <= frame <= 220):
        apu = requests.get(f"{API}/apu/state").json()
        vint_en = apu.get("vdp_vint_enabled", None)
        bank = apu.get("z80_bank_68k_addr", "?")
        vint_count = apu.get("vint_delivered", 0)
        new_vints = vint_count - prev_vint_count

        changed = ""
        if vint_en != prev_vint_en:
            changed += " [VINT CHANGED]"
        if bank != prev_bank:
            changed += f" [BANK CHANGED from {prev_bank}]"

        if changed or frame % 200 == 0 or (120 <= frame <= 140):
            print(f"Frame {frame:4d}: VINT={'ON' if vint_en else 'OFF'} bank={bank} "
                  f"vints={vint_count}(+{new_vints}) z80_pc=0x{apu.get('z80_pc',0):04X}{changed}")

        prev_vint_en = vint_en
        prev_bank = bank
        prev_vint_count = vint_count

# Final state
apu = requests.get(f"{API}/apu/state").json()
cpu = requests.get(f"{API}/cpu/state").json()
z80_comm = requests.get(f"{API}/cpu/memory", params={"addr": 0xA00100, "len": 32}).json().get("data", [])
m68k = cpu["cpu"]["m68k"]
print(f"\n=== Final State (frame ~1200) ===")
print(f"M68K PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")
print(f"Z80 PC=0x{apu.get('z80_pc',0):04X} halted={apu.get('z80_halted')}")
print(f"VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'} delivered={apu.get('vint_delivered')}")
print(f"Bank=0x{apu.get('z80_bank_68k_addr','0'):08X}" if isinstance(apu.get('z80_bank_68k_addr'), int) else f"Bank={apu.get('z80_bank_68k_addr')}")
print(f"DAC enabled={apu.get('dac_enabled')} YM writes={apu.get('ym_write_total')}")
print(f"Z80 comm: {' '.join(f'{b:02X}' for b in z80_comm[:16])}")
print(f"debug_output_nonzero={apu.get('debug_output_nonzero')}")
