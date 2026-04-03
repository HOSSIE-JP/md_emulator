#!/usr/bin/env python3
"""Disassemble ROM code at key addresses."""
import struct

rom_path = "frontend/roms/北へPM 鮎.bin"
with open(rom_path, "rb") as f:
    rom = f.read()

def read16(addr):
    return (rom[addr] << 8) | rom[addr+1]

def read32(addr):
    return (rom[addr]<<24) | (rom[addr+1]<<16) | (rom[addr+2]<<8) | rom[addr+3]

# Simple M68K disassembler for common patterns
def disasm_region(start, length=64):
    print(f"\n=== Code at 0x{start:06X} ===")
    addr = start
    end = start + length
    while addr < end and addr < len(rom):
        w = read16(addr)
        s = f"  0x{addr:06X}: {w:04X}"
        
        # NOP
        if w == 0x4E71:
            s += "  NOP"
        # RTS
        elif w == 0x4E75:
            s += "  RTS"
        # STOP
        elif w == 0x4E72:
            w2 = read16(addr+2)
            s += f" {w2:04X}  STOP #${w2:04X}"
            addr += 2
        # BRA
        elif (w & 0xFF00) == 0x6000:
            disp = w & 0xFF
            if disp == 0:
                disp = read16(addr+2)
                if disp >= 0x8000: disp -= 0x10000
                s += f" {read16(addr+2):04X}  BRA.W 0x{(addr+2+disp) & 0xFFFFFF:06X}"
                addr += 2
            else:
                if disp >= 0x80: disp -= 0x100
                s += f"  BRA.S 0x{(addr+2+disp) & 0xFFFFFF:06X}"
        # BEQ/BNE/Bcc
        elif (w & 0xF000) == 0x6000:
            cc = (w >> 8) & 0xF
            cc_names = {0:'BRA',1:'BSR',2:'BHI',3:'BLS',4:'BCC',5:'BCS',6:'BNE',7:'BEQ',
                       8:'BVC',9:'BVS',10:'BPL',11:'BMI',12:'BGE',13:'BLT',14:'BGT',15:'BLE'}
            disp = w & 0xFF
            if disp == 0:
                disp = read16(addr+2)
                if disp >= 0x8000: disp -= 0x10000
                s += f" {read16(addr+2):04X}  {cc_names.get(cc,'B??')}.W 0x{(addr+2+disp) & 0xFFFFFF:06X}"
                addr += 2
            else:
                if disp >= 0x80: disp -= 0x100
                s += f"  {cc_names.get(cc,'B??')}.S 0x{(addr+2+disp) & 0xFFFFFF:06X}"
        # MOVE.W to (Ax)
        elif (w & 0xF000) == 0x3000:
            s += f"  MOVE.W ..."
        # MOVE.L
        elif (w & 0xF000) == 0x2000:
            s += f"  MOVE.L ..."
        # JSR
        elif w == 0x4EB9:
            target = read32(addr+2)
            s += f" {read16(addr+2):04X} {read16(addr+4):04X}  JSR ${target:08X}"
            addr += 4
        elif w == 0x4EBA:
            disp = read16(addr+2)
            if disp >= 0x8000: disp -= 0x10000
            s += f" {read16(addr+2):04X}  JSR d16(PC) -> 0x{(addr+2+disp) & 0xFFFFFF:06X}"
            addr += 2
        # JMP
        elif w == 0x4EF9:
            target = read32(addr+2)
            s += f" {read16(addr+2):04X} {read16(addr+4):04X}  JMP ${target:08X}"
            addr += 4
        # VDP register write
        elif (w & 0xC000) == 0x8000:
            reg = (w >> 8) & 0x1F
            val = w & 0xFF
            s += f"  VDP reg{reg}=0x{val:02X}"
        # MOVE.W #imm, (Ax)
        elif (w & 0xFFC0) == 0x30BC:
            imm = read16(addr+2)
            dest_reg = (w >> 9) & 7
            s += f" {imm:04X}  MOVE.W #${imm:04X}, (A{dest_reg})"
            addr += 2
        # MOVE.W Dx, (Ax)
        elif (w & 0xF1F8) == 0x3080:
            src = w & 7
            dst = (w >> 9) & 7
            s += f"  MOVE.W D{src}, (A{dst})"
        
        print(s)
        addr += 2

# Check key areas
disasm_region(0x0005D0, 32)   # Code around 0x5E2 (where PC goes during transition) 
disasm_region(0x009280, 48)   # VDP write area (around 0x92A0)
disasm_region(0x007980, 48)   # Main loop area (0x7990-79A0)
disasm_region(0x000200, 48)   # Entry point
disasm_region(0x00D8A0, 48)   # VDP init table area

# Also check key SGDK VDP register cache area
# Look for MOVE.W reg1 pattern near 0x92A0
print("\n=== Raw bytes around 0x9280-0x92B0 ===")
for i in range(0x9280, 0x92B0, 2):
    print(f"  0x{i:06X}: {rom[i]:02X} {rom[i+1]:02X}", end="")
    w = read16(i)
    if (w & 0xC000) == 0x8000:
        reg = (w >> 8) & 0x1F
        val = w & 0xFF
        print(f"  [VDP reg{reg}=0x{val:02X}]", end="")
    print()
