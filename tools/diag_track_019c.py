#!/usr/bin/env python3
"""Track when $FF019C changes from 0 to $0161."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

prev = 0
for f in range(0, 200, 1):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019C, 'len': 2}).json()
    v = int.from_bytes(mem['data'], 'big')
    if v != prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        vdp = requests.get(BASE + '/vdp/registers').json()
        r1 = vdp['registers'][1]
        fc_mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
        fc = int.from_bytes(fc_mem['data'], 'big')
        print('Frame %3d: $FF019C=%04X->%04X R1=0x%02X PC=0x%06X FC=%d' % (
            f+1, prev, v, r1, m['pc'], fc))
        prev = v

print('\nFinal: $FF019C=0x%04X' % prev)
