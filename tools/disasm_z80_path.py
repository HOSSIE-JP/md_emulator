#!/usr/bin/env python3
"""Disassemble $7F5C, $7F92, and related routines."""
import requests, struct

def read_mem(addr, length):
    resp = requests.get(f'http://localhost:8080/api/v1/cpu/memory?addr={addr}&len={length}')
    return bytes(resp.json()['data'])

def disasm(data, base, max_inst=60):
    i = 0
    count = 0
    while i < len(data) - 1 and count < max_inst:
        addr = base + i
        w = (data[i] << 8) | data[i+1]
        note = ''
        consumed = 2
        
        if w == 0x4E75: note = 'RTS'
        elif w == 0x4E73: note = 'RTE'
        elif w == 0x4EB9 and i+5 < len(data):
            t = struct.unpack_from('>I', data, i+2)[0]
            note = f'JSR ${t:08X}'
            consumed = 6
        elif w == 0x0839 and i+7 < len(data):
            bit = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'BTST #{bit}, (${ea:08X})'
            consumed = 8
        elif w == 0x0879 and i+7 < len(data):
            bit = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'BSET #{bit}, (${ea:08X})'
            consumed = 8
        elif w == 0x08B9 and i+7 < len(data):
            bit = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'BCLR #{bit}, (${ea:08X})'
            consumed = 8
        elif w == 0x0240 and i+3 < len(data):
            imm = struct.unpack_from('>H', data, i+2)[0]
            note = f'ANDI.W #${imm:04X}, D0'
            consumed = 4
        elif w == 0x0040 and i+3 < len(data):
            note = f'ORI.W #${struct.unpack_from(">H", data, i+2)[0]:04X}, D0'
            consumed = 4
        elif w == 0x0079 and i+7 < len(data):
            imm = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'ORI.W #${imm:04X}, (${ea:08X})'
            consumed = 8
        elif w == 0x0279 and i+7 < len(data):
            imm = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'ANDI.W #${imm:04X}, (${ea:08X})'
            consumed = 8
        elif w == 0x33FC and i+7 < len(data):
            imm = struct.unpack_from('>H', data, i+2)[0]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'MOVE.W #${imm:04X}, (${ea:08X})'
            consumed = 8
        elif w == 0x13FC and i+7 < len(data):
            imm = data[i+3]
            ea = struct.unpack_from('>I', data, i+4)[0]
            note = f'MOVE.B #${imm:02X}, (${ea:08X})'
            consumed = 8
        elif w == 0x3039 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVE.W (${ea:08X}), D0'
            consumed = 6
        elif w == 0x33C0 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVE.W D0, (${ea:08X})'
            consumed = 6
        elif w == 0x33C1 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVE.W D1, (${ea:08X})'
            consumed = 6
        elif w == 0x33C2 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVE.W D2, (${ea:08X})'
            consumed = 6
        elif w == 0x2079 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVEA.L (${ea:08X}), A0'
            consumed = 6
        elif w == 0x207C and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVEA.L #${ea:08X}, A0'
            consumed = 6
        elif w == 0x23C0 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'MOVE.L D0, (${ea:08X})'
            consumed = 6
        elif w == 0x46FC and i+3 < len(data):
            sr = struct.unpack_from('>H', data, i+2)[0]
            note = f'MOVE #${sr:04X}, SR'
            consumed = 4
        elif w == 0x4A40: note = 'TST.W D0'
        elif w == 0x4A79 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'TST.W (${ea:08X})'
            consumed = 6
        elif w == 0x4A39 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'TST.B (${ea:08X})'
            consumed = 6
        elif w == 0x4AB9 and i+5 < len(data):
            ea = struct.unpack_from('>I', data, i+2)[0]
            note = f'TST.L (${ea:08X})'
            consumed = 6
        elif (w >> 12) == 6:
            cc_names = {0:'BRA',1:'BSR',2:'BHI',3:'BLS',4:'BCC',5:'BCS',6:'BNE',7:'BEQ',8:'BVC',9:'BVS',10:'BPL',11:'BMI',12:'BGE',13:'BLT',14:'BGT',15:'BLE'}
            cc = (w >> 8) & 0xF
            d = w & 0xFF
            if d == 0 and i+3 < len(data):
                d = struct.unpack_from('>h', data, i+2)[0]
                consumed = 4
            elif d >= 0x80:
                d -= 0x100
            t = (addr + 2 + d) & 0xFFFFFF
            note = f'{cc_names.get(cc, "B??")} ${t:06X}'
        elif w == 0x4E90:
            note = 'JSR (A0)'
        elif w == 0x4ED0:
            note = 'JMP (A0)'
        
        print(f'  ${addr:06X}: {w:04X}  {note}')
        i += consumed
        count += 1
        if note in ('RTS', 'RTE'):
            break

# Check $FFA820 value 
print("=== Current $FFA820 (Z80 bus access counter) ===")
data = read_mem(0xFFA820, 4)
print(f"  $FFA820 = ${(data[0]<<8)|data[1]:04X}")
print(f"  $FFA822 = ${(data[2]<<8)|data[3]:04X}")

# Check $FF019C-$FF01A0
print("\n=== Current $FF019C-$FF01A0 ===")
data = read_mem(0xFF019C, 8)
for off in range(0, 8, 2):
    v = (data[off]<<8)|data[off+1]
    print(f"  ${0xFF019C+off:06X} = ${v:04X}")

# Check $FF0064 (VBlank flag)
print("\n=== $FF0064 (VBlank flag) ===")
data = read_mem(0xFF0064, 4)
print(f"  $FF0064 = ${(data[0]<<8)|data[1]:04X}")
print(f"  $FF0066 = ${(data[2]<<8)|data[3]:04X}")

print("\n=== $7F5C (Z80 access skip target) ===")
data7f = read_mem(0x7F5C, 128)
disasm(data7f, 0x7F5C)

print("\n=== $7F92 (Z80 bus not granted target) ===")
data7f2 = read_mem(0x7F92, 128)
disasm(data7f2, 0x7F92)

# Also look at $7C3C-$7DF6 more carefully (bit2 handler leading to Z80 access)
print("\n=== $7C3C (bit 2 handler -> Z80 path) ===")
data7c = read_mem(0x7C3C, 448)
disasm(data7c, 0x7C3C, max_inst=100)
