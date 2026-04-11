#!/usr/bin/env python3
"""Reproduce state: load ROM, run frames, press START, check GEMS state."""
import requests, time

API = 'http://localhost:8080/api/v1'

# Step 500 frames
r = requests.post(f'{API}/emulator/step', json={'frames': 500})
print(f'500 frames: PC={hex(r.json()["cpu"]["m68k"]["pc"])}')

# Press START
requests.post(f'{API}/input/controller', json={'player': 1, 'buttons': 128})
requests.post(f'{API}/emulator/step', json={'frames': 30})

# Release
requests.post(f'{API}/input/controller', json={'player': 1, 'buttons': 0})
requests.post(f'{API}/emulator/step', json={'frames': 1200})

print('\n=== After ~1730 frames ===')

# Check GEMS state
base = f'{API}/cpu/memory'

print('\n--- GEMS Work RAM ---')
for name, addr in [
    ('FF0066 flags', 0xFF0066),
    ('FF0116 (pending cmd)', 0xFF0116),
    ('FF0198 (cmd table ptr)', 0xFF0198),
    ('FF019A (table offset)', 0xFF019A),
    ('FF019C', 0xFF019C),
    ('FF019E (sound flag)', 0xFF019E),
    ('FF01A0 (dispatch step)', 0xFF01A0),
    ('FF0062 (next step)', 0xFF0062),
    ('FF0064', 0xFF0064),
    ('FFA820 (timer)', 0xFFA820),
]:
    r = requests.get(f'{base}?addr={addr}&len=2')
    data = r.json()['data']
    val = data[0]*256 + data[1]
    print(f'  {name}: 0x{val:04X}')

print('\n--- Z80 RAM ---')
z80 = 0xA00000
for name, off in [
    ('$0100 status', 0x0100),
    ('$0102 ready', 0x0102),
    ('$0112 busy', 0x0112),
    ('$0113 cmd cnt', 0x0113),
    ('$0161 tick', 0x0161),
]:
    r = requests.get(f'{base}?addr={z80+off}&len=1')
    data = r.json()['data']
    print(f'  {name}: 0x{data[0]:02X}')

# Check CPU state
r = requests.get(f'{API}/cpu/state')
st = r.json()['cpu']['m68k']
print(f'\nPC: {hex(st["pc"])}, SR: {hex(st["sr"])}')
print(f'SR int mask: {(st["sr"] >> 8) & 7}')
