#!/usr/bin/env python3
"""Disassemble key areas to understand dispatch chain re-invocation."""
import json
import urllib.request
import sys

BASE = 'http://localhost:8080'

def fetch(addr, length):
    url = f'{BASE}/api/v1/cpu/memory?addr={addr}&len={length}'
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())['data']

def w16(data, i):
    return (data[i] << 8) | data[i+1]

def w32(data, i):
    return (data[i]<<24)|(data[i+1]<<16)|(data[i+2]<<8)|data[i+3]

def signed16(v):
    return v - 0x10000 if v >= 0x8000 else v

def signed8(v):
    return v - 0x100 if v >= 0x80 else v

CC_NAMES = {0:'BRA',1:'BSR',2:'BHI',3:'BLS',4:'BCC',5:'BCS',6:'BNE',7:'BEQ',
            8:'BVC',9:'BVS',10:'BPL',11:'BMI',12:'BGE',13:'BLT',14:'BGT',15:'BLE'}
DBCC_NAMES = {0:'DBT',1:'DBRA',2:'DBHI',3:'DBLS',4:'DBCC',5:'DBCS',6:'DBNE',7:'DBEQ',
              8:'DBVC',9:'DBVS',10:'DBPL',11:'DBMI',12:'DBGE',13:'DBLT',14:'DBGT',15:'DBLE'}

def disasm(data, base):
    """Simple M68K disassembler covering common instructions."""
    result = []
    i = 0
    while i + 1 < len(data):
        w = w16(data, i)
        pc = base + i
        s = 2
        t = None

        # --- Control flow ---
        if w == 0x4E71: t = 'NOP'
        elif w == 0x4E75: t = 'RTS'
        elif w == 0x4E73: t = 'RTE'
        elif (w & 0xFFF0) == 0x4E40: t = f'TRAP #{w&0xF}'
        elif w == 0x4EB9 and i+5<len(data):
            t = f'JSR ${w32(data,i+2):08X}'; s=6
        elif w == 0x4EB8 and i+3<len(data):
            t = f'JSR (${w16(data,i+2):04X}).W'; s=4
        elif w == 0x4EF9 and i+5<len(data):
            t = f'JMP ${w32(data,i+2):08X}'; s=6
        elif w == 0x4EF8 and i+3<len(data):
            t = f'JMP (${w16(data,i+2):04X}).W'; s=4

        # BSR.W
        elif w == 0x6100 and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'BSR.W ${pc+2+d:06X}'; s=4
        # BSR.B
        elif (w & 0xFF00)==0x6100 and (w&0xFF)!=0:
            d = signed8(w&0xFF)
            t = f'BSR.B ${pc+2+d:06X}'
        # Bcc.W
        elif (w & 0xF0FF)==0x6000 and i+3<len(data):
            cc = (w>>8)&0xF
            d = signed16(w16(data,i+2))
            t = f'{CC_NAMES.get(cc,"B???")}.W ${pc+2+d:06X}'; s=4
        # Bcc.B
        elif (w & 0xF000)==0x6000 and (w&0xFF)!=0:
            cc = (w>>8)&0xF
            d = signed8(w&0xFF)
            t = f'{CC_NAMES.get(cc,"B???")}.B ${pc+2+d:06X}'
        # DBcc
        elif (w & 0xF0F8)==0x50C8 and i+3<len(data):
            cc = (w>>8)&0xF; dn = w&7
            d = signed16(w16(data,i+2))
            t = f'{DBCC_NAMES.get(cc,"DB??")}.W D{dn}, ${pc+2+d:06X}'; s=4

        # --- MOVE immediate ---
        elif w == 0x33FC and i+7<len(data):
            t = f'MOVE.W #${w16(data,i+2):04X}, (${w32(data,i+4):08X})'; s=8
        elif w == 0x13FC and i+7<len(data):
            t = f'MOVE.B #${data[i+3]:02X}, (${w32(data,i+4):08X})'; s=8
        elif w == 0x23FC and i+9<len(data):
            t = f'MOVE.L #${w32(data,i+2):08X}, (${w32(data,i+6):08X})'; s=10
        elif (w&0xF1FF)==0x303C and i+3<len(data):
            t = f'MOVE.W #${w16(data,i+2):04X}, D{(w>>9)&7}'; s=4
        elif (w&0xF1FF)==0x203C and i+5<len(data):
            t = f'MOVE.L #${w32(data,i+2):08X}, D{(w>>9)&7}'; s=6
        elif (w&0xF1FF)==0x207C and i+5<len(data):
            t = f'MOVEA.L #${w32(data,i+2):08X}, A{(w>>9)&7}'; s=6
        elif (w&0xF1FF)==0x307C and i+3<len(data):
            t = f'MOVEA.W #${w16(data,i+2):04X}, A{(w>>9)&7}'; s=4

        # --- MOVE abs.l ---
        elif (w&0xF1FF)==0x3039 and i+5<len(data):
            t = f'MOVE.W (${w32(data,i+2):08X}), D{(w>>9)&7}'; s=6
        elif (w&0xF1FF)==0x1039 and i+5<len(data):
            t = f'MOVE.B (${w32(data,i+2):08X}), D{(w>>9)&7}'; s=6
        elif (w&0xF1FF)==0x2039 and i+5<len(data):
            t = f'MOVE.L (${w32(data,i+2):08X}), D{(w>>9)&7}'; s=6
        elif (w&0xFFF8)==0x33C0 and i+5<len(data):
            t = f'MOVE.W D{w&7}, (${w32(data,i+2):08X})'; s=6
        elif (w&0xFFF8)==0x13C0 and i+5<len(data):
            t = f'MOVE.B D{w&7}, (${w32(data,i+2):08X})'; s=6
        elif (w&0xFFF8)==0x23C0 and i+5<len(data):
            t = f'MOVE.L D{w&7}, (${w32(data,i+2):08X})'; s=6
        elif (w&0xF1FF)==0x3079 and i+5<len(data):
            t = f'MOVEA.W (${w32(data,i+2):08X}), A{(w>>9)&7}'; s=6
        elif (w&0xF1FF)==0x2079 and i+5<len(data):
            t = f'MOVEA.L (${w32(data,i+2):08X}), A{(w>>9)&7}'; s=6
        elif w==0x33F9 and i+9<len(data):
            t = f'MOVE.W (${w32(data,i+2):08X}), (${w32(data,i+6):08X})'; s=10

        # --- MOVE (d16,An) ---
        elif (w&0xF1F8)==0x3028 and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVE.W (${d&0xFFFF:04X},A{w&7}), D{(w>>9)&7}'; s=4
        elif (w&0xF1F8)==0x2028 and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVE.L (${d&0xFFFF:04X},A{w&7}), D{(w>>9)&7}'; s=4
        elif (w&0xF138)==0x3100 and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVE.W D{w&7}, (${d&0xFFFF:04X},A{(w>>9)&7})'; s=4
        elif (w&0xFFF8)==0x33E8 and i+7<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVE.W (${d&0xFFFF:04X},A{w&7}), (${w32(data,i+4):08X})'; s=8

        # --- MOVE register ---
        elif (w&0xF1F8)==0x3000: t = f'MOVE.W D{w&7}, D{(w>>9)&7}'
        elif (w&0xF1F8)==0x2000: t = f'MOVE.L D{w&7}, D{(w>>9)&7}'
        elif (w&0xF1F8)==0x3010: t = f'MOVE.W (A{w&7}), D{(w>>9)&7}'
        elif (w&0xF1F8)==0x2010: t = f'MOVE.L (A{w&7}), D{(w>>9)&7}'
        elif (w&0xF1F8)==0x3018: t = f'MOVE.W (A{w&7})+, D{(w>>9)&7}'
        elif (w&0xF1F8)==0x2018: t = f'MOVE.L (A{w&7})+, D{(w>>9)&7}'
        elif (w&0xF1F8)==0x2048: t = f'MOVEA.L A{w&7}, A{(w>>9)&7}'
        elif (w&0xF1F8)==0x2040: t = f'MOVEA.L D{w&7}, A{(w>>9)&7}'
        elif (w&0xF1F8)==0x2068 and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVEA.L (${d&0xFFFF:04X},A{w&7}), A{(w>>9)&7}'; s=4
        elif (w&0xF1F8)==0x3080: t = f'MOVE.W D{w&7}, (A{(w>>9)&7})'

        # MOVE PC-relative
        elif (w&0xF1FF)==0x303A and i+3<len(data):
            d = signed16(w16(data,i+2))
            t = f'MOVE.W (${pc+2+d:06X},PC), D{(w>>9)&7}'; s=4

        # --- SR ---
        elif (w&0xFFF8)==0x40C0: t = f'MOVE SR, D{w&7}'
        elif (w&0xFFF8)==0x46C0: t = f'MOVE D{w&7}, SR'
        elif w==0x46FC and i+3<len(data):
            t = f'MOVE #${w16(data,i+2):04X}, SR'; s=4

        # --- LEA ---
        elif (w&0xF1FF)==0x41F9 and i+5<len(data):
            t = f'LEA (${w32(data,i+2):08X}), A{(w>>9)&7}'; s=6

        # --- CLR ---
        elif w==0x4279 and i+5<len(data):
            t = f'CLR.W (${w32(data,i+2):08X})'; s=6
        elif w==0x4239 and i+5<len(data):
            t = f'CLR.B (${w32(data,i+2):08X})'; s=6
        elif (w&0xFFF8)==0x4240: t = f'CLR.W D{w&7}'
        elif (w&0xFFF8)==0x4200: t = f'CLR.B D{w&7}'

        # --- CMP ---
        elif (w&0xFFF8)==0x0C40 and i+3<len(data):
            t = f'CMPI.W #${w16(data,i+2):04X}, D{w&7}'; s=4
        elif w==0x0C79 and i+9<len(data):
            t = f'CMPI.W #${w16(data,i+2):04X}, (${w32(data,i+4):08X})'; s=8
        elif w==0x0C39 and i+7<len(data):
            t = f'CMPI.B #${data[i+3]:02X}, (${w32(data,i+4):08X})'; s=8
        elif (w&0xF1FF)==0xB079 and i+5<len(data):
            t = f'CMP.W (${w32(data,i+2):08X}), D{(w>>9)&7}'; s=6
        elif (w&0xF1F8)==0xB040: t = f'CMP.W D{w&7}, D{(w>>9)&7}'
        elif (w&0xF1F8)==0xB000: t = f'CMP.B D{w&7}, D{(w>>9)&7}'

        # --- TST ---
        elif w==0x4A79 and i+5<len(data):
            t = f'TST.W (${w32(data,i+2):08X})'; s=6
        elif w==0x4A39 and i+5<len(data):
            t = f'TST.B (${w32(data,i+2):08X})'; s=6
        elif (w&0xFFF8)==0x4A40: t = f'TST.W D{w&7}'
        elif (w&0xFFF8)==0x4A00: t = f'TST.B D{w&7}'

        # --- Arithmetic ---
        elif (w&0xF1F8)==0x5040:
            n=(w>>9)&7; t = f'ADDQ.W #{n or 8}, D{w&7}'
        elif (w&0xF1F8)==0x5088:
            n=(w>>9)&7; t = f'ADDQ.L #{n or 8}, A{w&7}'
        elif (w&0xF1F8)==0x5140:
            n=(w>>9)&7; t = f'SUBQ.W #{n or 8}, D{w&7}'
        elif (w&0xFFF8)==0x0640 and i+3<len(data):
            t = f'ADDI.W #${w16(data,i+2):04X}, D{w&7}'; s=4
        elif (w&0xFFF8)==0x0440 and i+3<len(data):
            t = f'SUBI.W #${w16(data,i+2):04X}, D{w&7}'; s=4
        elif (w&0xFFF8)==0x0680 and i+5<len(data):
            t = f'ADDI.L #${w32(data,i+2):08X}, D{w&7}'; s=6
        elif (w&0xF1F8)==0xD040: t = f'ADD.W D{w&7}, D{(w>>9)&7}'

        # --- Logic ---
        elif (w&0xFFF8)==0x0240 and i+3<len(data):
            t = f'ANDI.W #${w16(data,i+2):04X}, D{w&7}'; s=4
        elif (w&0xFFF8)==0x0040 and i+3<len(data):
            t = f'ORI.W #${w16(data,i+2):04X}, D{w&7}'; s=4
        elif w==0x0079 and i+7<len(data):
            t = f'ORI.W #${w16(data,i+2):04X}, (${w32(data,i+4):08X})'; s=8
        elif w==0x0279 and i+7<len(data):
            t = f'ANDI.W #${w16(data,i+2):04X}, (${w32(data,i+4):08X})'; s=8

        # --- Bit ops ---
        elif w==0x0839 and i+7<len(data):
            t = f'BTST #{w16(data,i+2)}, (${w32(data,i+4):08X})'; s=8
        elif w==0x08F9 and i+7<len(data):
            t = f'BSET #{w16(data,i+2)}, (${w32(data,i+4):08X})'; s=8
        elif w==0x0879 and i+7<len(data):
            t = f'BCLR #{w16(data,i+2)}, (${w32(data,i+4):08X})'; s=8

        # --- Shift ---
        elif (w&0xF1F8)==0xE148:
            n=(w>>9)&7; t = f'LSL.W #{n or 8}, D{w&7}'
        elif (w&0xF1F8)==0xE048:
            n=(w>>9)&7; t = f'LSR.W #{n or 8}, D{w&7}'
        elif (w&0xF1F8)==0xE140:
            n=(w>>9)&7; t = f'ASL.W #{n or 8}, D{w&7}'
        elif (w&0xF1F8)==0xE040:
            n=(w>>9)&7; t = f'ASR.W #{n or 8}, D{w&7}'

        # --- Misc ---
        elif (w&0xFFF8)==0x4880: t = f'EXT.W D{w&7}'
        elif (w&0xFFF8)==0x4840: t = f'SWAP D{w&7}'
        elif (w&0xFFF8)==0xC0C0: t = f'MULU D{w&7}, D{(w>>9)&7}'
        elif (w&0xFFF8)==0x48E0 and i+3<len(data):
            t = f'MOVEM.L #${w16(data,i+2):04X}, -(A{w&7})'; s=4
        elif (w&0xFFF8)==0x4CD8 and i+3<len(data):
            t = f'MOVEM.L (A{w&7})+, #${w16(data,i+2):04X}'; s=4

        if t is None:
            t = f'DC.W ${w:04X}'

        hx = ' '.join(f'{data[i+j]:02X}' for j in range(min(s, len(data)-i)))
        result.append(f'  ${pc:06X}: {hx:<24s} {t}')
        i += s
    return result

# ========== Main ==========
print("=" * 70)
print("DISPATCH CHAIN RE-INVOCATION ANALYSIS")
print("=" * 70)

regions = [
    ('$048C: set_next_step / read_step', 0x048C, 64),
    ('$8DFC: chain handler? (called from $B6CA)', 0x8DFC, 64),
    ('$8BBC: dispatch function', 0x8BBC, 192),
    ('$7A5E: main loop', 0x7A5E, 224),
    ('$B6CA: script engine context', 0xB6CA, 80),
]

for name, addr, length in regions:
    data = fetch(addr, length)
    print(f'\n{"="*60}')
    print(f'  {name}')
    print(f'{"="*60}')
    for line in disasm(data, addr):
        print(line)

# --- Current state ---
print(f'\n{"="*60}')
print('  CURRENT RUNTIME STATE')
print(f'{"="*60}')
for name, addr in [('FF01A0 completed_step', 0xFF01A0),
                    ('FF0062 next_step', 0xFF0062),
                    ('FF005E scene_ctrl', 0xFF005E),
                    ('FF0060', 0xFF0060),
                    ('FF019E', 0xFF019E)]:
    d = fetch(addr, 4)
    print(f'  {name}: ${w16(d,0):04X} ({w16(d,0)})')

url = f'{BASE}/api/v1/cpu/state'
with urllib.request.urlopen(url) as r:
    cpu = json.loads(r.read())
sr = cpu.get('sr', 0)
print(f'  SR=${sr:04X} bits10-8={(sr>>8)&7} PC=${cpu.get("pc",0):08X}')
