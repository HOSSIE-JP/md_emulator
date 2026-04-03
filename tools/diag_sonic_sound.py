#!/usr/bin/env python3
"""Quick sound test with sonic.gen."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

requests.post(f"{API}/emulator/load-rom-path", json={"path": "roms/sonic.gen"})
requests.post(f"{API}/emulator/reset")

# Run 60 frames
for i in range(60):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Press START
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
for i in range(10):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Run 200 more frames
for i in range(200):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

apu = requests.get(f"{API}/apu/state").json()
print(f"Sonic after ~270 frames:")
print(f"  VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'} delivered={apu.get('vint_delivered')}")
print(f"  Z80 PC=0x{apu.get('z80_pc',0):04X} halted={apu.get('z80_halted')}")
print(f"  Bank={apu.get('z80_bank_68k_addr')}")
print(f"  DAC enabled={apu.get('dac_enabled')}")
print(f"  YM writes={apu.get('ym_write_total')}")
print(f"  output_nonzero={apu.get('debug_output_nonzero')}")
print(f"  read_status_vblank={apu.get('vdp_read_status_vblank_count')}/{apu.get('vdp_read_status_total')}")

# Check FM channels
channels = apu.get('channels', [])
for i, ch in enumerate(channels):
    key_on = any(op.get('key_on') for op in ch.get('operators', []))
    fnum = ch.get('fnum', 0)
    if key_on or fnum > 0:
        print(f"  CH{i+1}: fnum={fnum} block={ch.get('block')} algo={ch.get('algorithm')} key_on={key_on}")
