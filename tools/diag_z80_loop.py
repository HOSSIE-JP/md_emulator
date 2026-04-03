#!/usr/bin/env python3
"""Analyze Z80 main loop at $0BFA and command check at $0B85."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

# Read Z80 RAM at key areas
for start, name in [
    (0x0B70, 'Around $0B85 (cmd check)'),
    (0x0BF0, 'Around $0BFA (main loop)'),
    (0x0860, 'Around $086E (timer)'),
    (0x0100, 'Stack area ($0100)'),
]:
    print('=== %s ===' % name)
    for base in range(start, start + 48, 16):
        mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000 + base, 'len': 16}).json()
        h = ' '.join('%02X' % b for b in mem['data'])
        print('$%04X: %s' % (base, h))
    print()

# Check what address the Z80 reads at $0BFA
# $0BFA: 3A xx yy → LD A, (yyxx)
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00BFA, 'len': 3}).json()
lo, hi = mem['data'][1], mem['data'][2]
read_addr = (hi << 8) | lo
print('Z80 $0BFA: LD A, ($%04X)' % read_addr)

# Read what's at that address
mem2 = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00000 + read_addr, 'len': 4}).json()
print('Value at $%04X: %s' % (read_addr, ' '.join('%02X' % b for b in mem2['data'])))

# Check $0B85 context more carefully
mem3 = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00B80, 'len': 16}).json()
print('\nZ80 $0B80: %s' % ' '.join('%02X' % b for b in mem3['data']))

# Decode Z80 instructions at $0BFA loop
mem4 = requests.get(BASE + '/cpu/memory', params={'addr': 0xA00BF0, 'len': 32}).json()
data = mem4['data']
print('\n=== Z80 instruction decode at $0BF0 ===')
i = 0
addr = 0x0BF0
while i < len(data) and addr <= 0x0C10:
    b = data[i]
    if b == 0x3A:  # LD A, (nn)
        nn = data[i+1] | (data[i+2] << 8)
        print('$%04X: LD A, ($%04X)' % (addr, nn))
        i += 3; addr += 3
    elif b == 0x1F:  # RRA
        print('$%04X: RRA' % addr)
        i += 1; addr += 1
    elif b == 0x30:  # JR NC, d
        d = data[i+1]
        if d >= 0x80: d -= 0x100
        target = addr + 2 + d
        print('$%04X: JR NC, $%04X' % (addr, target))
        i += 2; addr += 2
    elif b == 0x20:  # JR NZ, d
        d = data[i+1]
        if d >= 0x80: d -= 0x100
        target = addr + 2 + d
        print('$%04X: JR NZ, $%04X' % (addr, target))
        i += 2; addr += 2
    elif b == 0x28:  # JR Z, d
        d = data[i+1]
        if d >= 0x80: d -= 0x100
        target = addr + 2 + d
        print('$%04X: JR Z, $%04X' % (addr, target))
        i += 2; addr += 2
    elif b == 0x18:  # JR d
        d = data[i+1]
        if d >= 0x80: d -= 0x100
        target = addr + 2 + d
        print('$%04X: JR $%04X' % (addr, target))
        i += 2; addr += 2
    elif b == 0xC3:  # JP nn
        nn = data[i+1] | (data[i+2] << 8)
        print('$%04X: JP $%04X' % (addr, nn))
        i += 3; addr += 3
    elif b == 0xCD:  # CALL nn
        nn = data[i+1] | (data[i+2] << 8)
        print('$%04X: CALL $%04X' % (addr, nn))
        i += 3; addr += 3
    elif b == 0xC9:  # RET
        print('$%04X: RET' % addr)
        i += 1; addr += 1
    elif b == 0xCB:  # CB prefix
        cb = data[i+1]
        if (cb & 0xC0) == 0x40:  # BIT
            bit = (cb >> 3) & 7
            reg = cb & 7
            regnames = ['B','C','D','E','H','L','(HL)','A']
            print('$%04X: BIT %d, %s' % (addr, bit, regnames[reg]))
        else:
            print('$%04X: CB %02X' % (addr, cb))
        i += 2; addr += 2
    elif b == 0x21:  # LD HL, nn
        nn = data[i+1] | (data[i+2] << 8)
        print('$%04X: LD HL, $%04X' % (addr, nn))
        i += 3; addr += 3
    elif b == 0x36:  # LD (HL), n
        print('$%04X: LD (HL), $%02X' % (addr, data[i+1]))
        i += 2; addr += 2
    elif b == 0xAF:  # XOR A
        print('$%04X: XOR A' % addr)
        i += 1; addr += 1
    elif b == 0x77:  # LD (HL), A
        print('$%04X: LD (HL), A' % addr)
        i += 1; addr += 1
    elif b == 0xFB:  # EI
        print('$%04X: EI' % addr)
        i += 1; addr += 1
    elif b == 0xF3:  # DI
        print('$%04X: DI' % addr)
        i += 1; addr += 1
    else:
        print('$%04X: %02X (undecoded)' % (addr, b))
        i += 1; addr += 1
