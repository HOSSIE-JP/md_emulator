#!/usr/bin/env python3
"""Search $67CE function for $FF0066 bit 3 set pattern."""
import requests, sys

base_url = 'http://localhost:8080/api/v1/cpu/memory'
rom_addr = 0x67CE
length = 320

r = requests.get(f'{base_url}?addr={rom_addr}&len={length}')
d = r.json()['data']

print(f'Searching ${rom_addr:04X}-${rom_addr+length:04X} for $FF0066 references...\n')

for i in range(len(d)-3):
    # ORI.W #$0008,D0
    if d[i]==0x00 and d[i+1]==0x40 and d[i+2]==0x00 and d[i+3]==0x08:
        print(f'  ORI.W #$0008 at ${rom_addr+i:04X}')
    # E0FF0066 pattern (absolute long address)
    if d[i]==0xE0 and d[i+1]==0xFF and d[i+2]==0x00 and d[i+3]==0x66:
        start = max(0, i-4)
        ctx = ' '.join(f'{d[j]:02X}' for j in range(start, min(i+8, len(d))))
        print(f'  $FF0066 ref at ${rom_addr+i:04X}, context: {ctx}')
    # E0FF019E pattern (sound enable flag)
    if d[i]==0xE0 and d[i+1]==0xFF and d[i+2]==0x01 and d[i+3]==0x9E:
        start = max(0, i-4)
        ctx = ' '.join(f'{d[j]:02X}' for j in range(start, min(i+8, len(d))))
        print(f'  $FF019E ref at ${rom_addr+i:04X}, context: {ctx}')
    # BTST #0 pattern (08 39 00 00)
    if d[i]==0x08 and d[i+1]==0x39 and d[i+2]==0x00 and d[i+3]==0x00:
        ctx = ' '.join(f'{d[j]:02X}' for j in range(i, min(i+10, len(d))))
        print(f'  BTST #0 at ${rom_addr+i:04X}: {ctx}')

print('\nFull hex dump:')
for i in range(0, len(d), 16):
    h = ' '.join(f'{d[j]:02X}' for j in range(i, min(i+16, len(d))))
    print(f'  ${rom_addr+i:04X}: {h}')
