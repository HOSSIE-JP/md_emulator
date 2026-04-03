#!/usr/bin/env python3
"""Analyze polling loop at $798E and check VINT disable timing."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Run initial frames and check when VINT gets disabled
print('=== Tracking R1 (VINT enable) across frames ===')
r1_prev = None
for f in range(0, 120, 5):
    requests.post(BASE + '/emulator/step', json={'frames': 5})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    vint_en = bool(r1 & 0x20)
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
        fc = int.from_bytes(mem['data'], 'big')
        print('  Frame ~%3d: R1=0x%02X VINT=%s PC=0x%06X SR=0x%04X FC=%d' % (
            f+5, r1, 'ON' if vint_en else 'OFF', m['pc'], m['sr'], fc))
        r1_prev = r1

# Now read ROM bytes at polling loop
print('\n=== ROM bytes at $7980-$79C0 ===')
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0x7980, 'len': 64}).json()
data = mem['data']
for i in range(0, len(data), 16):
    addr = 0x7980 + i
    hexs = ' '.join('%02X' % b for b in data[i:i+16])
    print('  $%06X: %s' % (addr, hexs))

# Also read context: what calls the polling loop
print('\n=== ROM bytes at $7960-$79A0 ===')
mem2 = requests.get(BASE + '/cpu/memory', params={'addr': 0x7960, 'len': 64}).json()
data2 = mem2['data']
for i in range(0, len(data2), 16):
    addr = 0x7960 + i
    hexs = ' '.join('%02X' % b for b in data2[i:i+16])
    print('  $%06X: %s' % (addr, hexs))

# Check the VBlank handler at $026C
print('\n=== VBlank vector and handler ===')
vec = requests.get(BASE + '/cpu/memory', params={'addr': 0x78, 'len': 4}).json()
handler = int.from_bytes(vec['data'], 'big')
print('  Level 6 vector ($78) -> $%06X' % handler)

hmem = requests.get(BASE + '/cpu/memory', params={'addr': handler, 'len': 48}).json()
hdata = hmem['data']
print('  Handler bytes:')
for i in range(0, len(hdata), 16):
    addr = handler + i
    hexs = ' '.join('%02X' % b for b in hdata[i:i+16])
    print('  $%06X: %s' % (addr, hexs))

# Check stack for return addresses
cpu = requests.get(BASE + '/cpu/state').json()
m68k = cpu['cpu']['m68k']
sp = m68k['a'][7]
print('\n=== Stack (SP=$%08X) ===' % sp)
if sp > 0xFF0000:
    sp_addr = sp & 0xFFFF
    smem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0000 + sp_addr, 'len': 32}).json()
    sdata = smem['data']
    for i in range(0, len(sdata), 4):
        val = int.from_bytes(sdata[i:i+4], 'big')
        print('  SP+%02d: $%08X' % (i, val))

# Check what's at the return addresses on stack (to understand call chain)
print('\n=== Current M68K state ===')
print('  D: %s' % ', '.join('$%08X' % d for d in m68k['d']))
print('  A: %s' % ', '.join('$%08X' % a for a in m68k['a']))
print('  PC=$%06X SR=$%04X' % (m68k['pc'], m68k['sr']))
