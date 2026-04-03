#!/usr/bin/env python3
"""Check VDP VINT enable state and interrupt delivery."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

vdp = requests.get(BASE + '/vdp/registers').json()
regs = vdp.get('registers', [])
print('=== VDP Registers ===')
for i, v in enumerate(regs):
    extra = ''
    if i == 0:
        hint = 'YES' if v & 0x10 else 'NO'
        extra = '  HINT_EN=' + hint
    elif i == 1:
        vint = 'YES' if v & 0x20 else 'NO'
        dma = 'YES' if v & 0x10 else 'NO'
        disp = 'ON' if v & 0x40 else 'OFF'
        extra = '  VINT_EN=' + vint + ' DMA=' + dma + ' Display=' + disp
    elif i == 12:
        h40 = 'YES' if v & 0x81 else 'NO'
        extra = '  H40=' + h40
    print('  R%02d = 0x%02X%s' % (i, v, extra))

cpu = requests.get(BASE + '/cpu/state').json()
sr = cpu.get('sr', 0)
ipl_mask = (sr >> 8) & 7
print('\n=== CPU State ===')
print('  PC=0x%06X  SR=0x%04X  IPL=%d' % (cpu['pc'], sr, ipl_mask))
print('  stopped=%s' % cpu.get('stopped', 'N/A'))

mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
fc = int.from_bytes(mem['data'], 'big')
print('  Frame counter ($FF004C) = %d' % fc)

mem67 = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF0067, 'len': 1}).json()
v67 = mem67['data'][0]
snd = 'SET' if v67 & 8 else 'NOT SET'
print('  $FF0067 = 0x%02X (sound bit3=%s)' % (v67, snd))

r1 = regs[1] if len(regs) > 1 else 0
vint_en = 'YES' if r1 & 0x20 else 'NO'
can_fire = 'YES' if 6 > ipl_mask else 'NO'
print('\n=== Interrupt Analysis ===')
print('  VDP R1=0x%02X: VINT_EN=%s' % (r1, vint_en))
print('  CPU IPL mask=%d' % ipl_mask)
print('  VBlank (level 6) can fire: %s' % can_fire)

print('\n=== FC tracking over 10 frames ===')
for i in range(10):
    requests.post(BASE + '/emulator/step', json={'frames': 1})
    c = requests.get(BASE + '/cpu/state').json()
    m = requests.get(BASE + '/cpu/memory', params={'addr': 0xFF004C, 'len': 4}).json()
    fv = int.from_bytes(m['data'], 'big')
    s = c['sr']
    print('  Frame %d: PC=0x%06X SR=0x%04X IPL=%d FC=%d' % (201+i, c['pc'], s, (s>>8)&7, fv))
