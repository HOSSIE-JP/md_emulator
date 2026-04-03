#!/usr/bin/env python3
"""Check if R1 ever re-enables VINT over a long run (1000+ frames)."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Run 130 frames to get into VINT-disabled state
requests.post(BASE + '/emulator/step', json={'frames': 130})
vdp = requests.get(BASE + '/vdp/registers').json()
r1 = vdp['registers'][1]
print('Frame 130: R1=0x%02X VINT=%s' % (r1, 'ON' if r1 & 0x20 else 'OFF'))

# Check R1 every 10 frames for the next 2000 frames
r1_prev = r1
for f in range(140, 2000, 10):
    requests.post(BASE + '/emulator/step', json={'frames': 10})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        print('Frame %d: R1 CHANGED 0x%02X -> 0x%02X VINT=%s PC=0x%06X' % (
            f, r1_prev, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc']))
        r1_prev = r1

# End state
cpu = requests.get(BASE + '/cpu/state').json()
m = cpu['cpu']['m68k']
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc = int.from_bytes(mem['data'], 'big')
print('\nFrame 2000: R1=0x%02X VINT=%s PC=0x%06X FC=%d' % (
    r1, 'ON' if r1 & 0x20 else 'OFF', m['pc'], fc))

# Check if the game made any progress
mem66 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0066, 'len': 2}).json()
print('$FF0066 = 0x%04X' % int.from_bytes(mem66['data'], 'big'))

# Check key RAM locations
for addr_name in [
    (0xFF0042, 'delay_counter'),
    (0xFF005E, 'func_ptr'),
    (0xFF0062, 'sound_mgr'),
    (0xFF019A, 'completion'),
    (0xFF019E, 'init_flag'),
]:
    addr, name = addr_name
    m_ = requests.get(BASE + '/cpu/memory', params={'addr': addr, 'len': 4}).json()
    v = int.from_bytes(m_['data'], 'big')
    print('$%06X (%s) = 0x%08X' % (addr, name, v))

# Now try: send START and see if R1 changes over next 100 frames
print('\n=== Pressing START ===')
requests.post(BASE + '/input/controller', json={'player': 1, 'buttons': 0x0080})
r1_prev = r1
for f in range(2000, 2200, 5):
    requests.post(BASE + '/emulator/step', json={'frames': 5})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        print('Frame %d: R1 CHANGED 0x%02X -> 0x%02X VINT=%s PC=0x%06X' % (
            f, r1_prev, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc']))
        r1_prev = r1

# Release START
requests.post(BASE + '/input/controller', json={'player': 1, 'buttons': 0x0000})

print('\nAfter START: R1=0x%02X' % r1)
cpu2 = requests.get(BASE + '/cpu/state').json()
m2 = cpu2['cpu']['m68k']
mem2 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc2 = int.from_bytes(mem2['data'], 'big')
print('PC=0x%06X FC=%d' % (m2['pc'], fc2))
