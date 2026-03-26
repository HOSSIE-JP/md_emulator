#!/usr/bin/env python3
"""Disassemble M68K sound handler at $7378."""
import struct, os

with open("roms/puyo.bin", "rb") as f:
    rom = f.read()

def read16(addr):
    return struct.unpack('>H', rom[addr:addr+2])[0]

def read32(addr):
    return struct.unpack('>I', rom[addr:addr+4])[0]

# Simple 68K disassembler for common instructions
def disasm(start, count=60):
    pc = start
    for _ in range(count):
        if pc >= len(rom):
            break
        op = read16(pc)
        mnemonic = f"{op:04X}"
        size = 2

        # Common patterns
        if op == 0x4E75:
            mnemonic = "RTS"
        elif op == 0x4E73:
            mnemonic = "RTE"
        elif (op & 0xFF00) == 0x6100:
            d = op & 0xFF
            if d == 0:
                d = struct.unpack('>h', rom[pc+2:pc+4])[0]
                size = 4
                mnemonic = f"BSR.W ${pc+2+d:06X}"
            else:
                if d > 0x7F: d -= 256
                mnemonic = f"BSR.S ${pc+2+d:06X}"
        elif (op & 0xF000) == 0x6000 and (op & 0x0F00) != 0x0100:
            cc_names = {0:"BRA",2:"BHI",3:"BLS",4:"BCC",5:"BCS",6:"BNE",7:"BEQ",8:"BVC",9:"BVS",10:"BPL",11:"BMI",12:"BGE",13:"BLT",14:"BGT",15:"BLE"}
            cc = (op >> 8) & 0xF
            d = op & 0xFF
            if d == 0:
                d = struct.unpack('>h', rom[pc+2:pc+4])[0]
                size = 4
            else:
                if d > 0x7F: d -= 256
            name = cc_names.get(cc, f"B{cc}")
            mnemonic = f"{name} ${pc+2+d:06X}"
        elif op == 0x4EB9:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"JSR ${addr:08X}"
        elif op == 0x4EF9:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"JMP ${addr:08X}"
        elif (op & 0xFFF8) == 0x4A00:
            mnemonic = f"TST.B D{op&7}"
        elif op == 0x4A39:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"TST.B ${addr:08X}"
        elif op == 0x4A79:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"TST.W ${addr:08X}"
        elif (op & 0xFF00) == 0x0C00 and (op & 0x38) == 0x38 and (op & 0x07) == 0x01:
            # CMPI.B #xx,abs.L
            imm = rom[pc+3]
            addr = read32(pc+4)
            size = 8
            mnemonic = f"CMPI.B #${imm:02X},${addr:08X}"
        elif op == 0x1039:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"MOVE.B ${addr:08X},D0"
        elif op == 0x13FC:
            val = rom[pc+3]
            addr = read32(pc+4)
            size = 8
            mnemonic = f"MOVE.B #${val:02X},${addr:08X}"
        elif op == 0x0839:
            bit = read16(pc+2) & 0xFF
            addr = read32(pc+4)
            size = 8
            mnemonic = f"BTST #${bit:02X},${addr:08X}"
        elif (op & 0xFFC0) == 0x08C0:
            bit = read16(pc+2) & 0xFF
            addr = read32(pc+4)
            size = 8
            mnemonic = f"BSET #${bit:02X},${addr:08X}"
        elif (op & 0xFFC0) == 0x0880:
            bit = read16(pc+2) & 0xFF
            addr = read32(pc+4)
            size = 8
            mnemonic = f"BCLR #${bit:02X},${addr:08X}"
        elif op == 0x4279:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"CLR.W ${addr:08X}"
        elif op == 0x4239:
            addr = read32(pc+2)
            size = 6
            mnemonic = f"CLR.B ${addr:08X}"

        raw = ' '.join(f'{rom[pc+i]:02X}' for i in range(min(size, 8)))
        print(f"  ${pc:06X}: {raw:24s} {mnemonic}")
        pc += size

print("=== Sound handler at $7378 ===")
disasm(0x7378, 40)

print("\n=== Sound handler at $73D2 (called from $7378?) ===")
disasm(0x73D2, 30)

print("\n=== Code around $73AE (reads $A00027) ===")
disasm(0x73A0, 20)

# Also check the code at $7420 and $745E  
print("\n=== Code at $7420 ===")
disasm(0x7420, 20)

print("\n=== Code at $745E ===")
disasm(0x745E, 20)
