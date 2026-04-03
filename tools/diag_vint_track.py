#!/usr/bin/env python3
"""Track exactly when R1 changes to disable VINT, and check main loop behavior."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Run 90 frames to get past initial setup
requests.post(BASE + '/emulator/step', json={'frames': 90})
vdp0 = requests.get(BASE + '/vdp/registers').json()
r1_prev = vdp0['registers'][1]
cpu0 = requests.get(BASE + '/cpu/state').json()
m = cpu0['cpu']['m68k']
print('Frame 90: R1=0x%02X VINT=%s PC=0x%06X' % (
    r1_prev, 'ON' if r1_prev & 0x20 else 'OFF', m['pc']))

# Track R1 frame by frame from 90 to 200
for f in range(91, 250):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
        fc = int.from_bytes(mem['data'], 'big')
        print('Frame %3d: R1 CHANGED 0x%02X->0x%02X VINT=%s PC=0x%06X SR=0x%04X FC=%d' % (
            f, r1_prev, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc'], m['sr'], fc))
        # Check stack
        sp = m['a'][7]
        if sp > 0xFF0000:
            sp_addr = sp & 0xFFFF
            smem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0000 + sp_addr, 'len': 16}).json()
            sdata = smem['data']
            ret_addrs = []
            for i in range(0, len(sdata), 4):
                val = int.from_bytes(sdata[i:i+4], 'big')
                ret_addrs.append('$%08X' % val)
            print('  Stack: %s' % ', '.join(ret_addrs))
        r1_prev = r1

# Check final state
vdp_final = requests.get(BASE + '/vdp/registers').json()
r1_final = vdp_final['registers'][1]
cpu_final = requests.get(BASE + '/cpu/state').json()
mf = cpu_final['cpu']['m68k']
print('\nFrame 250: R1=0x%02X VINT=%s PC=0x%06X' % (
    r1_final, 'ON' if r1_final & 0x20 else 'OFF', mf['pc']))

# Check if frame counter changes over next 10 frames
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc1 = int.from_bytes(mem['data'], 'big')
requests.post(BASE + '/emulator/step', json={'frames': 10})
mem2 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc2 = int.from_bytes(mem2['data'], 'big')
print('Frame counter: %d -> %d (%s)' % (fc1, fc2, 'ADVANCING' if fc2 > fc1 else 'STUCK'))

# Check what code runs after VBlank wait
# Read code at return addresses from stack
for addr in [0x7A5E, 0x5C4C]:
    code = requests.get(BASE + '/cpu/memory', params={'addr': addr, 'len': 32}).json()
    hexs = ' '.join('%02X' % b for b in code['data'])
    print('\nCode at $%06X: %s' % (addr, hexs))
