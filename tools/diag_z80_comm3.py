#!/usr/bin/env python3
"""Check Z80 communication blocking the main loop."""
import requests
BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

print('=== Z80 RAM 0x140-0x17F ===')
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00140, 'len': 64}).json()
for i in range(0, 64, 16):
    addr = 0xA00140 + i
    h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
    print('$%06X: %s' % (addr, h))

print('\n=== ROM $7E00-$7F80 ===')
for base in range(0x7E00, 0x7F80, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    for i in range(0, 64, 16):
        addr = base + i
        h = ' '.join('%02X' % b for b in mem['data'][i:i+16])
        print('$%06X: %s' % (addr, h))

print('\n=== Trace (last 30) ===')
trace = requests.get(BASE + '/debug/trace').json()
for t in trace.get('trace', [])[-30:]:
    print('  $%06X: %s (%d)' % (t.get('pc',0), t.get('mnemonic','?'), t.get('cycles',0)))

print('\n=== Key RAM ===')
for a, n in [(0xFF019C,'cmd'), (0xFFA820,'tmr'), (0xFF0066,'flg')]:
    m = requests.get(BASE + '/cpu/memory', params={'addr': a, 'len': 2}).json()
    print('  $%06X(%s)=0x%04X' % (a, n, int.from_bytes(m['data'],'big')))

cpu = requests.get(BASE + '/cpu/state').json()
z = cpu['cpu']['z80']
print('\n=== Z80: PC=0x%04X halt=%s iff=%s ===' % (z['pc'], z['halted'], z['iff1']))

print('\n=== Z80 $0161 tracking ===')
for f in range(10):
    m = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00160, 'len': 4}).json()
    print('  F%d: %s' % (200+f, ' '.join('%02X' % b for b in m['data'])))
    requests.post(BASE + '/emulator/step', json={'frames': 1})

apu = requests.get(BASE + '/apu/state').json()
print('\n=== bus_req=%s reset=%s bank=%s ===' % (
    apu.get('z80_bus_requested','?'), apu.get('z80_reset','?'), apu.get('z80_bank_68k_addr','?')))
