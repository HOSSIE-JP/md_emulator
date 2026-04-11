#!/usr/bin/env python3
"""Disassemble key routines around $78B4 (VBlank wait) and $7DF6 (Z80 access)."""
import requests, struct

resp = requests.get('http://localhost:8080/api/v1/cpu/memory?addr=30900&len=1600')
data = bytes(resp.json()['data'])
base = 0x78B4

def u16(off):
    return struct.unpack_from('>H', data, off)[0]

def u32(off):
    return struct.unpack_from('>I', data, off)[0]

def s16(off):
    return struct.unpack_from('>h', data, off)[0]

# Print raw hex with 16 bytes per line, annotating key addresses
for off in range(0, min(len(data), 1600), 2):
    addr = base + off
    w = u16(off)
    
    # Only print up to $7F00
    if addr > 0x7F00:
        break
    
    # Mark key addresses
    marker = ""
    if addr == 0x78B4: marker = " <<<< VBlank_wait entry"
    elif addr == 0x792A: marker = " <<<< VBlank=0 branch target"
    elif addr == 0x79A2: marker = " <<<< arg=0 branch target"
    elif addr == 0x79B0: marker = " <<<< NTSC branch target"
    elif addr == 0x7A5E: marker = " <<<< main_loop entry"
    elif addr == 0x7A66: marker = " <<<< BSR VBlank_wait"
    elif addr == 0x7C3C: marker = " <<<< bit2 handler"
    elif addr == 0x7DF6: marker = " <<<< Z80 access path"
    elif addr == 0x78F4: marker = " <<<< VBlank=1 fallthrough"
    elif addr == 0x790C: marker = " <<<< post-VBlank-wait"
    elif addr == 0x7912: marker = " <<<< PAL test"
    
    # Decode some instructions
    decode = ""
    if w == 0x4E75: decode = "RTS"
    elif w == 0x4E73: decode = "RTE"
    elif w == 0x4EB9 and off+5 < len(data):
        t = u32(off+2)
        decode = f"JSR ${t:08X}"
    elif w == 0x4EBA and off+3 < len(data):
        d = s16(off+2)
        decode = f"JSR (PC) -> ${(addr+2+d)&0xFFFFFF:06X}"
    elif (w >> 8) == 0x61:  # BSR
        d = w & 0xFF
        if d == 0 and off+3 < len(data):
            d = s16(off+2)
            decode = f"BSR ${(addr+2+d)&0xFFFFFF:06X}"
        elif d != 0:
            if d >= 0x80: d -= 0x100
            decode = f"BSR.B ${(addr+2+d)&0xFFFFFF:06X}"
    elif (w >> 8) == 0x60:  # BRA
        d = w & 0xFF
        if d == 0 and off+3 < len(data):
            d = s16(off+2)
            decode = f"BRA ${(addr+2+d)&0xFFFFFF:06X}"
        elif d != 0:
            if d >= 0x80: d -= 0x100
            decode = f"BRA.B ${(addr+2+d)&0xFFFFFF:06X}"
    elif (w >> 12) == 0x6 and (w >> 8) not in (0x60, 0x61):  # Bcc
        cc_names = {2:'BHI',3:'BLS',4:'BCC',5:'BCS',6:'BNE',7:'BEQ',8:'BVC',9:'BVS',10:'BPL',11:'BMI',12:'BGE',13:'BLT',14:'BGT',15:'BLE'}
        cc = (w >> 8) & 0xF
        d = w & 0xFF
        if d == 0 and off+3 < len(data):
            d = s16(off+2)
        elif d >= 0x80:
            d -= 0x100
        decode = f"{cc_names.get(cc,'B??')} ${(addr+2+d)&0xFFFFFF:06X}"
    elif w == 0x0839 and off+7 < len(data):  # BTST #n, abs.L
        bit = u16(off+2)
        ea = u32(off+4)
        decode = f"BTST #{bit}, (${ea:08X})"
    elif w == 0x0800 and off+3 < len(data):
        bit = u16(off+2)
        decode = f"BTST #{bit}, D0"
    elif w == 0x0804 and off+3 < len(data):
        bit = u16(off+2)
        decode = f"BTST #{bit}, D4"
    elif w == 0x0240 and off+3 < len(data):
        imm = u16(off+2)
        decode = f"ANDI.W #${imm:04X}, D0"
    elif w == 0x4A40: decode = "TST.W D0"
    elif w == 0x4A2F and off+3 < len(data):
        d = s16(off+2)
        decode = f"TST.B {d}(SP)"
    elif w == 0x3039 and off+5 < len(data):
        ea = u32(off+2)
        decode = f"MOVE.W (${ea:08X}), D0"
    elif w == 0x33C0 and off+5 < len(data):
        ea = u32(off+2)
        decode = f"MOVE.W D0, (${ea:08X})"
    elif w == 0x33C1 and off+5 < len(data):
        ea = u32(off+2)
        decode = f"MOVE.W D1, (${ea:08X})"
    elif w == 0x33FC and off+7 < len(data):
        imm = u16(off+2)
        ea = u32(off+4)
        decode = f"MOVE.W #${imm:04X}, (${ea:08X})"
    elif w == 0x13FC and off+7 < len(data):
        imm = data[off+3]
        ea = u32(off+4)
        decode = f"MOVE.B #${imm:02X}, (${ea:08X})"
    elif w == 0x23F9 and off+9 < len(data):
        src = u32(off+2)
        dst = u32(off+6)
        decode = f"MOVE.L (${src:08X}), (${dst:08X})"
    elif w == 0x2079 and off+5 < len(data):
        ea = u32(off+2)
        decode = f"MOVEA.L (${ea:08X}), A0"
    elif w == 0x207C and off+5 < len(data):
        ea = u32(off+2)
        decode = f"MOVEA.L #${ea:08X}, A0"
    
    info = decode if decode else ""
    if marker:
        info = info + marker if info else marker.strip()
    
    if info:
        print(f"${addr:06X}: {w:04X}  {info}")
    else:
        print(f"${addr:06X}: {w:04X}")
