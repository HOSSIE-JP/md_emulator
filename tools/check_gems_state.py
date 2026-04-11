#!/usr/bin/env python3
import requests

base = 'http://localhost:8080/api/v1/cpu/memory'

print("=== GEMS Work RAM Variables ===")
for name, addr in [
    ('FF0116 (pending cmd count)', 0xFF0116),
    ('FF0198 (cmd table ptr)', 0xFF0198),
    ('FF019A (table offset)', 0xFF019A),
]:
    r = requests.get(f'{base}?addr={addr}&len=2')
    data = r.json()['data']
    val = data[0]*256 + data[1]
    print(f'  {name}: 0x{val:04X} ({val})')

print("\n=== Z80 RAM (GEMS) ===")
z80_base = 0xA00000
for name, off in [
    ('$0100 (status)', 0x0100),
    ('$0112 (busy flag)', 0x0112),
    ('$0113 (cmd counter)', 0x0113),
    ('$0161 (frame tick)', 0x0161),
]:
    r = requests.get(f'{base}?addr={z80_base + off}&len=1')
    data = r.json()['data']
    print(f'  {name}: 0x{data[0]:02X}')

print("\n=== Status Flags ===")
# Work RAM is at $FF0000-$FFFFFF, API might want physical addr
for addr_try in [0xFF0066, 0x00FF0066]:
    r = requests.get(f'{base}?addr={addr_try}&len=2')
    if r.status_code == 200 and r.text.strip():
        try:
            data = r.json()['data']
            print(f'  FF0066 (addr={hex(addr_try)}): 0x{data[0]:02X}')
            print(f'  FF0067: 0x{data[1]:02X}')
            print(f'  FF0067 bit3: {(data[1] >> 3) & 1}')
            break
        except Exception:
            print(f'  addr={hex(addr_try)}: parse error, trying next')
    else:
        print(f'  addr={hex(addr_try)}: status={r.status_code}, empty={not r.text.strip()}')

# Also check if there's a GEMS command table in work RAM around $FF0100-$FF01FF
print("\n=== GEMS Command Area ($FF0100-$FF01A0) ===")
r = requests.get(f'{base}?addr=0xFF0100&len=160')
if r.status_code == 200 and r.text.strip():
    data = r.json()['data']
    for i in range(0, len(data), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        addr_str = f'${0xFF0100 + i:06X}'
        print(f'  {addr_str}: {hex_str}')
else:
    print(f'  Error: status={r.status_code}')
