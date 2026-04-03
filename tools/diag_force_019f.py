#!/usr/bin/env python3
"""Force $FF019F bit 0 to see if game progresses past the stuck loop."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

# Check current state
cpu = requests.get(BASE + '/cpu/state').json()
m = cpu['cpu']['m68k']
vdp = requests.get(BASE + '/vdp/registers').json()
r1 = vdp['registers'][1]
print('Before: R1=0x%02X PC=0x%06X' % (r1, m['pc']))

# Check $FF019F
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019F, 'len': 1}).json()
print('$FF019F = 0x%02X (bit 0=%d)' % (mem['data'][0], mem['data'][0] & 1))

# Force $FF019F bit 0 = 1
requests.post(BASE + '/cpu/memory', json={'addr': 0xFF019F, 'data': [0x01]})
mem2 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019F, 'len': 1}).json()
print('Forced $FF019F = 0x%02X' % mem2['data'][0])

# Run 20 frames and track R1
r1_prev = r1
for f in range(20):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        print('Frame %d: R1 CHANGED 0x%02X -> 0x%02X VINT=%s PC=0x%06X' % (
            201+f, r1_prev, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc']))
        r1_prev = r1

# Check if VBlank handler fires (frame counter should change)
mem_fc = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc = int.from_bytes(mem_fc['data'], 'big')
print('Frame counter = %d' % fc)

# Check sound flag
mem67 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0067, 'len': 1}).json()
print('$FF0067 = 0x%02X (sound bit3=%s)' % (mem67['data'][0], 'SET' if mem67['data'][0] & 8 else 'NOT SET'))

# Check $FF019C
mem19c = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019C, 'len': 2}).json()
v19c = int.from_bytes(mem19c['data'], 'big')
print('$FF019C = 0x%04X (%s)' % (v19c, 'CLEARED' if v19c == 0 else 'still pending'))

# Check function pointers
for addr, name in [(0xFF005E, 'scene_ctrl'), (0xFF005A, 'scene_ctrl2')]:
    m_ = requests.get(BASE + '/cpu/memory', params={'addr': addr, 'len': 4}).json()
    v = int.from_bytes(m_['data'], 'big')
    print('$%06X (%s) = $%06X' % (addr, name, v))

# Final state
cpu_f = requests.get(BASE + '/cpu/state').json()
mf = cpu_f['cpu']['m68k']
vdp_f = requests.get(BASE + '/vdp/registers').json()
print('\nFinal: R1=0x%02X PC=0x%06X SR=0x%04X' % (vdp_f['registers'][1], mf['pc'], mf['sr']))
