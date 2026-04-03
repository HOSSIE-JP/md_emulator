#!/usr/bin/env python3
"""Find who clears $FF019C and test if clearing it unblocks the game."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Search ROM for writes to $FF019C (pattern: E0 FF 01 9C in absolute addressing)
# Also search for 01 9C as the last 2 bytes of an address
print('=== Searching ROM for $FF019C references ===')
rom = requests.get(BASE + '/cpu/memory', params={'addr': 0, 'len': 0x100000}).json()
data = rom['data']

pattern = [0xE0, 0xFF, 0x01, 0x9C]
matches = []
for i in range(len(data) - 3):
    if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x01 and data[i+3] == 0x9C:
        # Get 4 bytes before for context
        ctx = data[max(0,i-4):i+8]
        matches.append((i, ctx))

print('Found %d references to $FF019C:' % len(matches))
for addr, ctx in matches[:30]:
    h = ' '.join('%02X' % b for b in ctx)
    # Check if it's a write instruction (33C0=MOVE.W D0,abs / 42B9=CLR.L abs / 33FC=MOVE.W #imm,abs)
    pre = ctx[:4] if len(ctx) >= 8 else ctx
    pre_h = ' '.join('%02X' % b for b in pre)
    print('  $%06X: ctx=%s' % (addr-4, h))

# Now force $FF019C = 0 and see if game progresses
print('\n=== Forcing $FF019C = 0 ===')
requests.post(BASE + '/emulator/step', json={'frames': 200})

vdp_before = requests.get(BASE + '/vdp/registers').json()
print('Before: R1=0x%02X' % vdp_before['registers'][1])

requests.post(BASE + '/cpu/memory', json={'addr': 0xFF019C, 'data': [0x00, 0x00]})
# Also clear bit 2 of $FF0066 to exit the Z80 communication path
# requests.post(BASE + '/cpu/memory', json={'addr': 0xFF0066, 'data': [0x00, 0x00]})

# Run 200 frames
r1_prev = vdp_before['registers'][1]
for f in range(200):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    vdp = requests.get(BASE + '/vdp/registers').json()
    r1 = vdp['registers'][1]
    if r1 != r1_prev:
        cpu = requests.get(BASE + '/cpu/state').json()
        m = cpu['cpu']['m68k']
        fc_mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
        fc = int.from_bytes(fc_mem['data'], 'big')
        print('Frame %d: R1 0x%02X->0x%02X VINT=%s PC=0x%06X FC=%d' % (
            201+f, r1_prev, r1, 'ON' if r1 & 0x20 else 'OFF', m['pc'], fc))
        r1_prev = r1

# Check final state
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF019C, 'len': 2}).json()
print('\n$FF019C = 0x%04X' % int.from_bytes(mem['data'], 'big'))
mem66 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0066, 'len': 2}).json()
print('$FF0066 = 0x%04X' % int.from_bytes(mem66['data'], 'big'))
fc_mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
print('FC = %d' % int.from_bytes(fc_mem['data'], 'big'))
vdp_f = requests.get(BASE + '/vdp/registers').json()
print('R1 = 0x%02X' % vdp_f['registers'][1])
cpu = requests.get(BASE + '/cpu/state').json()
print('PC = 0x%06X' % cpu['cpu']['m68k']['pc'])
