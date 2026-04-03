#!/usr/bin/env python3
"""Analyze Z80 driver code to understand how it processes commands at $0161."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

# Get Z80 state
cpu = requests.get(BASE + '/cpu/state').json()
z80 = cpu['cpu']['z80']
print('=== Z80 State ===')
print('PC=0x%04X SP=0x%04X HL=0x%04X DE=0x%04X BC=0x%04X' % (
    z80['pc'], z80['sp'], (z80['h']<<8)|z80['l'], (z80['d']<<8)|z80['e'], (z80['b']<<8)|z80['c']))
print('A=0x%02X F=0x%02X halted=%s iff1=%s' % (z80['a'], z80['f'], z80['halted'], z80['iff1']))

# Read Z80 RAM - the entire program
print('\n=== Z80 RAM around PC ($%04X) ===' % z80['pc'])
for base in range(max(0, z80['pc'] - 32), min(0x2000, z80['pc'] + 96), 16):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000 + base, 'len': 16}).json()
    h = ' '.join('%02X' % b for b in mem['data'])
    print('$%04X: %s' % (base, h))

# Read Z80 RAM around $0161 (command area)
print('\n=== Z80 RAM around $0161 ===')
for base in range(0x0150, 0x01A0, 16):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000 + base, 'len': 16}).json()
    h = ' '.join('%02X' % b for b in mem['data'])
    print('$%04X: %s' % (base, h))

# Read Z80 driver entry point ($0000-$0040)
print('\n=== Z80 Entry ($0000-$0060) ===')
for base in range(0x0000, 0x0060, 16):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000 + base, 'len': 16}).json()
    h = ' '.join('%02X' % b for b in mem['data'])
    print('$%04X: %s' % (base, h))

# Check Z80 interrupt vector at $0038
print('\n=== Z80 INT vector ($0038) ===')
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00038, 'len': 8}).json()
print('$0038: %s' % ' '.join('%02X' % b for b in mem['data']))

# Check if Z80 code references $0161
print('\n=== Z80 references to $0161 ===')
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000, 'len': 0x2000}).json()
data = mem['data']
# Search for $61 $01 (LD addr $0161 in Z80 little-endian)
for i in range(len(data) - 1):
    if data[i] == 0x61 and data[i+1] == 0x01:
        ctx = data[max(0,i-2):min(len(data), i+4)]
        h = ' '.join('%02X' % b for b in ctx)
        print('  $%04X: ...%s...' % (i, h))

# Also check the Z80 trace ring
apu = requests.get(BASE + '/apu/state').json()
z80_traces = apu.get('z80_trace_ring', [])
if z80_traces:
    print('\n=== Z80 trace (last 20) ===')
    for t in z80_traces[-20:]:
        print('  %s' % t)
