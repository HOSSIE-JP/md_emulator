#!/usr/bin/env python3
"""Check APU state after running more frames."""
import requests

API = "http://localhost:8080/api/v1"

# Run 50 more frames
resp = requests.post(f"{API}/emulator/step", json={"frames": 50})
print(f"Step 50 frames: {resp.status_code}")

# Get APU state
apu = requests.get(f"{API}/apu/state").json()
print(f"audio_buffer_len: {apu.get('audio_buffer_len', 0)}")
print(f"ym_write_total: {apu.get('ym_write_total', 'N/A')}")

# Check if any channels have non-default settings
for i, ch in enumerate(apu.get('channels', [])):
    algo = ch.get('algorithm', 0)
    block = ch.get('block', 0)
    fnum = ch.get('fnum', 0)
    # Check operators
    any_active = False
    for op in ch.get('operators', []):
        if op.get('attenuation', 1023) < 1023 or op.get('key_on', False):
            any_active = True
    if algo != 0 or block != 0 or fnum != 0 or any_active:
        print(f"  Ch{i}: algo={algo} block={block} fnum={fnum}")
        for j, op in enumerate(ch.get('operators', [])):
            print(f"    Op{j}: att={op['attenuation']} env={op['env_phase']} key={op['key_on']}")

# Check DAC
dac_enabled = apu.get('dac_enabled', 'N/A')
print(f"DAC enabled: {dac_enabled}")

# Check PSG
psg = apu.get('psg', 'N/A')
if psg != 'N/A':
    print(f"PSG: {psg}")

# Check bus stats  
state = requests.get(f"{API}/cpu/state").json()
bus_info = state.get('bus', {})
print(f"z80_m68k_write_count: {bus_info.get('z80_m68k_write_count', 'N/A')}")
print(f"z80_bank_write_count: {bus_info.get('z80_bank_write_count', 'N/A')}")
print(f"z80_bank_68k_addr: ${bus_info.get('z80_bank_68k_addr', 0):06X}")
