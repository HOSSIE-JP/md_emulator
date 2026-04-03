#!/usr/bin/env python3
"""Analyze function $048C and $04A4 which control game state transitions."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Read code at $048C and $04A4
print('=== Function $048C ===')
for base in range(0x0480, 0x0560, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

print('\n=== Function $04A4 ===')
for base in range(0x04A4, 0x0560, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

# Also check what $19C2 does (called from main loop)
print('\n=== Function $19C2 ===')
for base in range(0x19C0, 0x1A40, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

# Run 200 frames then check what $048C returns (D0) 
requests.post(BASE + '/emulator/step', json={'frames': 200})

# Repeatedly force $FF019F=1 every frame for 50 frames
print('\n=== Force $FF019F=1 for 50 frames ===')
for f in range(50):
    requests.post(BASE + '/cpu/memory', json={'addr': 0xFF019F, 'data': [0x01]})
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != 0x54:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        print('Frame %d: R1=0x%02X VINT=%s PC=0x%06X' % (
            201+f, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc']))

# Check state after forcing
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019C, 'len': 2}).json()
print('$FF019C = 0x%04X' % int.from_bytes(mem['data'], 'big'))
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0066, 'len': 2}).json()
print('$FF0066 = 0x%04X' % int.from_bytes(mem['data'], 'big'))
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0062, 'len': 2}).json()
print('$FF0062 = 0x%04X' % int.from_bytes(mem['data'], 'big'))
cpu = requests.get(BASE + '/cpu/state').json()
vdp = requests.get(BASE + '/vdp/registers').json()
print('R1=0x%02X PC=0x%06X' % (vdp['registers'][1], cpu['cpu']['m68k']['pc']))
