#!/usr/bin/env python3
"""Disassemble M68K VBlank sound handler around the $A00027 check."""
import json, urllib.request

API = "http://localhost:8081/api/v1"

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{API}{path}").read())

api_get("/health")  # verify server

# Read ROM at $7380 (VBlank sound handler) with enough context
for start, length, label in [
    (0x7380, 0x80, "VBlank sound handler $7380"),
    (0x7280, 0x80, "M68K Z80 init area $7280"),
    (0x7200, 0x80, "M68K Z80 upload $7200"),
]:
    rom = api_get(f"/cpu/memory?addr={start}&len={length}")
    data = rom.get("data", [])
    print(f"=== {label} ===")
    # Simple M68K disassembler for common instructions
    i = 0
    while i < len(data) - 1:
        addr = start + i
        w = (data[i] << 8) | data[i+1]
        
        if w == 0x4E75:
            print(f"  {addr:06X}: RTS")
            i += 2
        elif w == 0x4E73:
            print(f"  {addr:06X}: RTE")
            i += 2
        elif w == 0x4E71:
            print(f"  {addr:06X}: NOP")
            i += 2
        elif (w & 0xFF00) == 0x6100 and (w & 0xFF) != 0:
            # BSR.S
            offset = w & 0xFF
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            print(f"  {addr:06X}: BSR.S ${target:06X}")
            i += 2
        elif w == 0x6100:
            # BSR.W
            if i+3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp & 0x8000: disp -= 0x10000
                target = addr + 2 + disp
                print(f"  {addr:06X}: BSR.W ${target:06X}")
                i += 4
            else:
                print(f"  {addr:06X}: BSR.W ???")
                i += 2
        elif (w & 0xFF00) == 0x6700 and (w & 0xFF) != 0:
            # BEQ.S
            offset = w & 0xFF
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            print(f"  {addr:06X}: BEQ.S ${target:06X}")
            i += 2
        elif w == 0x6700:
            # BEQ.W
            if i+3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp & 0x8000: disp -= 0x10000
                target = addr + 2 + disp
                print(f"  {addr:06X}: BEQ.W ${target:06X}")
                i += 4
            else:
                print(f"  {addr:06X}: BEQ.W ???")
                i += 2
        elif (w & 0xFF00) == 0x6600 and (w & 0xFF) != 0:
            offset = w & 0xFF
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            print(f"  {addr:06X}: BNE.S ${target:06X}")
            i += 2
        elif w == 0x6600:
            if i+3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp & 0x8000: disp -= 0x10000
                target = addr + 2 + disp
                print(f"  {addr:06X}: BNE.W ${target:06X}")
                i += 4
            else:
                i += 2
        elif (w & 0xFFF8) == 0x4A00:
            # TST.B Dn
            print(f"  {addr:06X}: TST.B D{w&7}")
            i += 2
        elif w == 0x4A39 and i+5 < len(data):
            # TST.B (xxx).L
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: TST.B (${addr32:08X}).L")
            i += 6
        elif w == 0x1039 and i+5 < len(data):
            # MOVE.B (xxx).L,D0
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: MOVE.B (${addr32:08X}).L,D0")
            i += 6
        elif w == 0x1239 and i+5 < len(data):
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: MOVE.B (${addr32:08X}).L,D1")
            i += 6
        elif (w & 0xFFF8) == 0x1200 and i+3 < len(data):
            # MOVE.B D0,Dn or variants
            print(f"  {addr:06X}: MOVE.B ... (word={w:04X})")
            i += 2
        elif w == 0x13C0 and i+5 < len(data):
            # MOVE.B D0,(xxx).L
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: MOVE.B D0,(${addr32:08X}).L")
            i += 6
        elif w == 0x13C1 and i+5 < len(data):
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: MOVE.B D1,(${addr32:08X}).L")
            i += 6
        elif w == 0x13C2 and i+5 < len(data):
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: MOVE.B D2,(${addr32:08X}).L")
            i += 6
        elif w == 0x13FC and i+7 < len(data):
            # MOVE.B #imm,(xxx).L
            imm = data[i+3]  # byte immediate (word-aligned: high byte ignored)
            addr32 = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
            print(f"  {addr:06X}: MOVE.B #${imm:02X},(${addr32:08X}).L")
            i += 8
        elif w == 0x4239 and i+5 < len(data):
            # CLR.B (xxx).L
            addr32 = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            print(f"  {addr:06X}: CLR.B (${addr32:08X}).L")
            i += 6
        elif w == 0x33FC and i+7 < len(data):
            # MOVE.W #imm,(xxx).L
            imm16 = (data[i+2] << 8) | data[i+3]
            addr32 = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
            print(f"  {addr:06X}: MOVE.W #${imm16:04X},(${addr32:08X}).L")
            i += 8
        elif (w & 0xFFF0) == 0x0800 and i+3 < len(data):
            # BTST #n,Dn
            bit = data[i+3]
            print(f"  {addr:06X}: BTST #${bit:02X},D{w&7}")
            i += 4
        elif (w & 0xFF00) == 0x0C00 and i+3 < len(data):
            # CMP.B #imm,Dn
            imm = data[i+3]
            print(f"  {addr:06X}: CMPI.B #${imm:02X},D{w&7}")
            i += 4
        elif (w & 0xFF00) == 0x0600 and i+3 < len(data):
            # ADDI.B #imm,...
            imm = data[i+3]
            print(f"  {addr:06X}: ADDI.B #${imm:02X},... (word={w:04X})")
            i += 4
        elif w == 0x0839 and i+7 < len(data):
            # BTST #n,(xxx).L
            bit = data[i+3]
            addr32 = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
            print(f"  {addr:06X}: BTST #${bit:02X},(${addr32:08X}).L")
            i += 8
        elif (w & 0xFF00) == 0x8000:
            # OR.B Dn,...
            src = (w >> 9) & 7
            print(f"  {addr:06X}: OR.B D{src},... (word={w:04X})")
            i += 2
        elif (w & 0xFF00) == 0xB400:
            # CMP.B ...,Dn
            print(f"  {addr:06X}: CMP.B ...,D{(w>>9)&7} (word={w:04X})")
            i += 2
        elif w & 0xF000 == 0x2000:
            # MOVE.L variants  
            print(f"  {addr:06X}: MOVE.L ... (word={w:04X})")
            i += 2
        elif w & 0xF000 == 0x3000:
            # MOVE.W variants
            print(f"  {addr:06X}: MOVE.W ... (word={w:04X})")
            i += 2
        elif w & 0xF000 == 0x1000:
            # MOVE.B variants (more complex)
            print(f"  {addr:06X}: MOVE.B ... (word={w:04X})")
            i += 2
        else:
            print(f"  {addr:06X}: DC.W ${w:04X}")
            i += 2
    print()

# Also search for CLR.B $A00027 in broader ROM area
print("=== Searching for writes to $A00027 in ROM ===")
for chunk_start in range(0x7000, 0x7600, 0x100):
    rom = api_get(f"/cpu/memory?addr={chunk_start}&len=256")
    data = rom.get("data", [])
    for i in range(len(data) - 5):
        # Check for CLR.B ($A00027).L = 42 39 00 A0 00 27
        # Check for MOVE.B #00,($A00027).L = 13 FC 00 00 00 A0 00 27
        # Check for MOVE.B D0,($A00027).L = 13 C0 00 A0 00 27
        if i+5 < len(data):
            b0,b1,b2,b3,b4,b5 = data[i],data[i+1],data[i+2],data[i+3],data[i+4],data[i+5]
            if b2==0x00 and b3==0xA0 and b4==0x00 and b5==0x27:
                addr = chunk_start + i
                ctx = ' '.join(f'{b:02X}' for b in data[max(0,i-2):min(len(data),i+8)])
                print(f"  Reference to $A00027 at ${addr:06X}: {ctx}")
            # Also check for A00027 starting at b3
            if b3==0x00 and b4==0xA0 and i+7 < len(data) and data[i+5]==0x00 and data[i+6]==0x27:
                addr = chunk_start + i
                ctx = ' '.join(f'{b:02X}' for b in data[max(0,i-2):min(len(data),i+10)])
                print(f"  Reference to $00A00027 at ${addr:06X}: {ctx}")
