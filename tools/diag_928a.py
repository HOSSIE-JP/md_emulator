#!/usr/bin/env python3
"""Analyze the code at $928A that writes R1=0x54."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Read ROM at $9280-$9300
print('=== Code at $9280 (R1 VINT disable write) ===')
for base in range(0x9240, 0x9340, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

# Also check $92D8 (called from VBlank handler when $FF0067 bit 1 set) 
print('\n=== Function $92D8 ===')
for base in range(0x92D0, 0x9350, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

# And check $A890 (VINT enable write)
print('\n=== Code at $A890 (R1 VINT enable write) ===')
for base in range(0xA870, 0xA8C0, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

# Search for what calls $9280ish area
print('\n=== References to $92xx area ===')
rom = requests.get(BASE + '/cpu/memory', params={'addr': 0, 'len': 0x100000}).json()
data = rom['data']
for i in range(len(data) - 5):
    if data[i] == 0x4E and data[i+1] == 0xB9:
        target = (data[i+2]<<24) | (data[i+3]<<16) | (data[i+4]<<8) | data[i+5]
        if 0x9200 <= target <= 0x9300:
            print('  $%06X: JSR $%06X' % (i, target))
