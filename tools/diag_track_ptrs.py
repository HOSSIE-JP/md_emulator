#!/usr/bin/env python3
"""Track $FF005E (scene function pointer) alongside $FF019C."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

prev_5e = None
prev_9c = None
prev_42 = None
for f in range(0, 140):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    mem5e = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF005E, 'len': 4}).json()
    v5e = int.from_bytes(mem5e['data'], 'big')
    mem9c = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019C, 'len': 2}).json()
    v9c = int.from_bytes(mem9c['data'], 'big')
    mem42 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0042, 'len': 2}).json()
    v42 = int.from_bytes(mem42['data'], 'big')
    
    changed = (v5e != prev_5e) or (v9c != prev_9c) or (v42 != prev_42)
    if changed:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        vdp = requests.get(BASE + '/vdp/registers').json()
        r1 = vdp['registers'][1]
        fc_mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
        fc = int.from_bytes(fc_mem['data'], 'big')
        
        changes = []
        if v5e != prev_5e: changes.append('$5E=$%06X' % v5e)
        if v9c != prev_9c: changes.append('$019C=%04X' % v9c)
        if v42 != prev_42: changes.append('$42=%04X' % v42)
        
        print('F%3d: %s  R1=%02X FC=%d PC=%06X' % (
            f+1, ' '.join(changes), r1, fc, m['pc']))
        prev_5e = v5e
        prev_9c = v9c
        prev_42 = v42
