#!/usr/bin/env python3
"""Disassemble $B6CA (script engine main loop)."""
import requests, struct

def read_mem(addr, length):
    resp = requests.get(f'http://localhost:8080/api/v1/cpu/memory?addr={addr}&len={length}')
    return bytes(resp.json()['data'])

data = read_mem(0xB6CA, 256)
print("=== $B6CA (script engine?) ===")
for i in range(0, len(data)-1, 2):
    w = struct.unpack_from('>H', data, i)[0]
    addr = 0xB6CA + i
    note = ''
    consumed = 2
    
    if w == 0x4E75: note = 'RTS'
    elif w == 0x4EB9 and i+5 < len(data):
        t = struct.unpack_from('>I', data, i+2)[0]
        note = f'JSR ${t:08X}'
        consumed = 6
    elif w == 0x4EBA and i+3 < len(data):
        d = struct.unpack_from('>h', data, i+2)[0]
        note = f'JSR (PC)->${(addr+2+d)&0xFFFFFF:06X}'
        consumed = 4
    elif (w >> 12) == 6:
        cc = {0:'BRA',1:'BSR',2:'BHI',3:'BLS',4:'BCC',5:'BCS',6:'BNE',7:'BEQ',
              8:'BVC',9:'BVS',10:'BPL',11:'BMI',12:'BGE',13:'BLT',14:'BGT',15:'BLE'}
        c = (w >> 8) & 0xF
        d = w & 0xFF
        if d == 0 and i+3 < len(data):
            d = struct.unpack_from('>h', data, i+2)[0]
            consumed = 4
        elif d >= 0x80:
            d -= 0x100
        note = f'{cc.get(c, "B??")} ${(addr+2+d)&0xFFFFFF:06X}'
    elif w == 0x41F9 and i+5 < len(data):
        ea = struct.unpack_from('>I', data, i+2)[0]
        note = f'LEA (${ea:08X}), A0'
        consumed = 6
    elif w == 0x43F9 and i+5 < len(data):
        ea = struct.unpack_from('>I', data, i+2)[0]
        note = f'LEA (${ea:08X}), A1'
        consumed = 6
    elif w == 0x4E90: note = 'JSR (A0)'
    elif w == 0x4ED0: note = 'JMP (A0)'
    elif w == 0x4A79 and i+5 < len(data):
        ea = struct.unpack_from('>I', data, i+2)[0]
        note = f'TST.W (${ea:08X})'
        consumed = 6
    elif w == 0x4AB9 and i+5 < len(data):
        ea = struct.unpack_from('>I', data, i+2)[0]
        note = f'TST.L (${ea:08X})'
        consumed = 6
    elif w == 0x4A39 and i+5 < len(data):
        ea = struct.unpack_from('>I', data, i+2)[0]
        note = f'TST.B (${ea:08X})'
        consumed = 6
    
    print(f'  ${addr:06X}: {w:04X}  {note}')
    if note == 'RTS':
        break
    if i > 200:
        break
