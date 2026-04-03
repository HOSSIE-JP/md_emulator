#!/usr/bin/env python3
"""Analyze the code at $0005F4 where VINT gets disabled."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Read ROM bytes at $0005C0 - $0640 (around the VINT disable point)
for base_addr in [0x0580, 0x05C0, 0x0600]:
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base_addr, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base_addr + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))
    print()

# Also read the VBlank handler for context
print('=== VBlank handler at $026C ===')
for base_addr in [0x026C, 0x02AC, 0x02EC]:
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base_addr, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base_addr + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))
    print()

# Run to frame 125 and check state just before the change
requests.post(BASE + '/emulator/step', json={'frames': 125})
cpu = requests.get(BASE + '/cpu/state').json()
m = cpu['cpu']['m68k']
vdp = requests.get(BASE + '/vdp/registers').json()
print('=== State at frame 125 ===')
print('R1=0x%02X PC=0x%06X SR=0x%04X' % (vdp['registers'][1], m['pc'], m['sr']))
print('D: %s' % ', '.join('$%08X' % d for d in m['d']))
print('A: %s' % ', '.join('$%08X' % a for a in m['a']))

# Now step instruction by instruction to catch the exact write
print('\n=== Stepping instruction by instruction to catch R1 write ===')
r1_now = vdp['registers'][1]
for i in range(5000):
    requests.post(BASE + '/emulator/step', json={'cycles': 1})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_now:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        print('After %d steps: R1 CHANGED 0x%02X -> 0x%02X' % (i+1, r1_now, r1))
        print('  PC=0x%06X SR=0x%04X' % (m['pc'], m['sr']))
        print('  D: %s' % ', '.join('$%08X' % d for d in m['d']))
        print('  A: %s' % ', '.join('$%08X' % a for a in m['a']))
        
        # Get execution trace
        trace_resp = requests.get(BASE + '/debug/trace').json()
        traces = trace_resp.get('trace', [])
        if traces:
            print('  Last 10 instructions:')
            for t in traces[-10:]:
                print('    $%06X: %s (%d cycles)' % (t.get('pc', 0), t.get('mnemonic', '?'), t.get('cycles', 0)))
        
        if r1 == 0x54:
            print('\n  *** VINT disabled! ***')
            break
        r1_now = r1
