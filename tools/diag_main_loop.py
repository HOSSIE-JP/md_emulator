#!/usr/bin/env python3
"""Deeply analyze the main loop and VBlank handler full path to find VINT re-enable."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Read large blocks of ROM code at key areas

# 1. Main loop at $7A5E (after VBlank poll returns)
print('=== Main loop at $7A5E-$7E00 ===')
for base in range(0x7A5E, 0x7E00, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# 2. Function at $78B4 (called from main loop with arg=1)
print('\n=== Function $78B4 ===')
for base in range(0x78B4, 0x7990, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# 3. Function pointer target $1C2E (scene controller)
print('\n=== Scene controller $1C2E ===')
for base in range(0x1C2E, 0x1D00, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# 4. Search ROM for VDP register 1 writes with value 0x74 (VINT ON)
# Pattern: 8174 for MOVE.W #$8174, ($C00004)
print('\n=== Search for R1 writes ===')
# Read ROM and search for $81 $74 and $81 $54
rom = requests.get(BASE + '/cpu/memory', params={'addr': 0, 'len': 0x40000}).json()
rom_data = rom['data']

for pattern, desc in [
    ([0x81, 0x74], 'R1=0x74 (VINT ON)'),
    ([0x81, 0x54], 'R1=0x54 (VINT OFF)'),
    ([0x81, 0x64], 'R1=0x64 (VINT ON, Display OFF)'),
    ([0x81, 0x34], 'R1=0x34 (VINT ON, Display OFF, DMA)'),
]:
    matches = []
    for i in range(len(rom_data) - 1):
        if rom_data[i] == pattern[0] and rom_data[i+1] == pattern[1]:
            matches.append(i)
    if matches:
        print('  %s: found at %s' % (desc, ', '.join('$%06X' % a for a in matches[:20])))
    else:
        print('  %s: NOT FOUND' % desc)

# 5. Check VBlank handler full path more deeply
print('\n=== Full VBlank handler $028E-$0340 ===')
for base in range(0x028E, 0x0340, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# 6. Check stack setup (SSP area) 
print('\n=== SSP area (initial supervisor stack check) ===')
# Read from $FF0000 area where the handler saved state
for addr in [0xFF0000, 0xFF000A]:
    mem = requests.get(BASE + '/cpu/memory', params={'addr': addr, 'len': 16}).json()
    data = mem['data']
    hexs = ' '.join('%02X' % b for b in data)
    print('$%06X: %s' % (addr, hexs))
