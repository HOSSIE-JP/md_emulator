#!/usr/bin/env python3
"""Search full ROM for instructions that set bit 3 of $FF0066/$FF0067."""
import sys

ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

print(f'ROM size: {len(rom)} bytes (0x{len(rom):X})')
print()

# === Find ALL references to FF0066 and FF0067 ===
refs = []
for i in range(len(rom) - 3):
    if rom[i] == 0x00 and rom[i+1] == 0xFF and rom[i+2] == 0x00:
        if rom[i+3] in (0x66, 0x67):
            refs.append((i, rom[i+3]))

print(f'=== ALL references to FF0066/FF0067 ({len(refs)} total) ===')
for addr, lo in refs:
    start = max(0, addr - 12)
    end = min(len(rom), addr + 8)
    ctx = ' '.join('%02X' % rom[j] for j in range(start, end))
    print(f'  FF00{lo:02X} @ ${addr:06X}: {ctx}')
print()

# === BSET #3, (xxx).L targeting FF006x ===
print('=== BSET #3 targeting FF006x ===')
found_bset = False
for i in range(len(rom) - 7):
    if rom[i] == 0x08 and rom[i+2] == 0x00 and rom[i+3] == 0x03:
        op2 = rom[i+1]
        # abs.long
        if op2 == 0xF9 and i + 7 < len(rom):
            t = (rom[i+4]<<24)|(rom[i+5]<<16)|(rom[i+6]<<8)|rom[i+7]
            if 0xFF0060 <= t <= 0xFF006F:
                s = max(0, i-4); e = min(len(rom), i+12)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  BSET #3, (${t:08X}).L @ ${i:06X}: {ctx}')
                found_bset = True
        # abs.short
        if op2 == 0xF8 and i + 5 < len(rom):
            t = (rom[i+4]<<8)|rom[i+5]
            if t >= 0x8000:
                t |= 0xFFFF0000
            if 0xFF0060 <= (t & 0xFFFFFFFF) <= 0xFF006F:
                s = max(0, i-4); e = min(len(rom), i+8)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  BSET #3, (${t&0xFFFFFFFF:08X}).W @ ${i:06X}: {ctx}')
                found_bset = True
if not found_bset:
    print('  (none found)')
print()

# === BSET #3 with ANY addressing mode (check if addr is from A-reg indirect) ===
print('=== ALL BSET #3 instructions in ROM (first 50) ===')
count = 0
for i in range(len(rom) - 3):
    if rom[i] == 0x08 and rom[i+2] == 0x00 and rom[i+3] == 0x03:
        op2 = rom[i+1]
        s = max(0, i-2); e = min(len(rom), i+12)
        ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
        # Decode EA mode
        mode = ""
        if 0xC0 <= op2 <= 0xC7: mode = f"Dn (D{op2-0xC0})"
        elif 0xD0 <= op2 <= 0xD7: mode = f"(A{op2-0xD0})"
        elif 0xD8 <= op2 <= 0xDF: mode = f"(A{op2-0xD8})+"
        elif 0xE8 <= op2 <= 0xEF: mode = f"d16(A{op2-0xE8})"
        elif 0xF0 <= op2 <= 0xF7: mode = f"d8(A{op2-0xF0},Xn)"
        elif op2 == 0xF8: mode = "(xxx).W"
        elif op2 == 0xF9: mode = "(xxx).L"
        elif 0x28 <= op2 <= 0x2F: mode = f"d16(A{op2-0x28}) [BTST]"
        else: mode = f"op2=0x{op2:02X}"
        print(f'  ${i:06X}: {ctx}  [{mode}]')
        count += 1
        if count >= 50:
            print('  ... (truncated)')
            break
print()

# === ORI targeting FF006x with bit 3 ===
print('=== ORI.B/ORI.W with bit 3 to FF006x ===')
found_ori = False
# ORI.B #imm, (xxx).L = 00 39 00 imm addr32
for i in range(len(rom) - 7):
    if rom[i] == 0x00 and rom[i+1] == 0x39:
        imm = rom[i+3]
        if imm & 0x08:
            t = (rom[i+4]<<24)|(rom[i+5]<<16)|(rom[i+6]<<8)|rom[i+7]
            if t == 0x00FF0066 or t == 0x00FF0067:
                s = max(0, i-4); e = min(len(rom), i+12)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  ORI.B #${imm:02X}, (${t:08X}).L @ ${i:06X}: {ctx}')
                found_ori = True
# ORI.W #imm16, (xxx).L = 00 79 imm16 addr32
for i in range(len(rom) - 9):
    if rom[i] == 0x00 and rom[i+1] == 0x79:
        imm = (rom[i+2]<<8)|rom[i+3]
        if imm & 0x0008:
            t = (rom[i+4]<<24)|(rom[i+5]<<16)|(rom[i+6]<<8)|rom[i+7]
            if t == 0x00FF0066 or t == 0x00FF0067:
                s = max(0, i-4); e = min(len(rom), i+12)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  ORI.W #${imm:04X}, (${t:08X}).L @ ${i:06X}: {ctx}')
                found_ori = True
if not found_ori:
    print('  (none found)')
print()

# === MOVE.B/MOVE.W #imm with bit 3 to FF006x ===
print('=== MOVE with bit 3 to FF006x ===')
found_move = False
# MOVE.B #imm, (xxx).L = 13FC 00 imm addr32
for i in range(len(rom) - 7):
    if rom[i] == 0x13 and rom[i+1] == 0xFC:
        imm = rom[i+3]
        if imm & 0x08:
            t = (rom[i+4]<<24)|(rom[i+5]<<16)|(rom[i+6]<<8)|rom[i+7]
            if t == 0x00FF0066 or t == 0x00FF0067:
                s = max(0, i-4); e = min(len(rom), i+12)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  MOVE.B #${imm:02X}, (${t:08X}).L @ ${i:06X}: {ctx}')
                found_move = True
# MOVE.W #imm16, (xxx).L = 33FC imm16 addr32
for i in range(len(rom) - 9):
    if rom[i] == 0x33 and rom[i+1] == 0xFC:
        imm = (rom[i+2]<<8)|rom[i+3]
        if imm & 0x0008:
            t = (rom[i+4]<<24)|(rom[i+5]<<16)|(rom[i+6]<<8)|rom[i+7]
            if t == 0x00FF0066 or t == 0x00FF0067:
                s = max(0, i-4); e = min(len(rom), i+12)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  MOVE.W #${imm:04X}, (${t:08X}).L @ ${i:06X}: {ctx}')
                found_move = True
if not found_move:
    print('  (none found)')
print()

# === Check for register-indirect writes ===
# If code uses An register pointing to FF0066 area, look for LEA/MOVEA patterns
# LEA ($FF0060).L, Ax = 41F9 00FF0060 (x=0), 43F9 (x=1), 45F9 (x=2), etc.
print('=== LEA to FF006x area ===')
for i in range(len(rom) - 5):
    if rom[i+1] == 0xF9:  # abs.long
        op1 = rom[i]
        # LEA (xxx).L, An = 4xF9 where x = 1,3,5,7,9,B,D,F for A0-A7
        if op1 in (0x41, 0x43, 0x45, 0x47, 0x49, 0x4B, 0x4D, 0x4F):
            t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
            if 0x00FF0060 <= t <= 0x00FF006F:
                an = (op1 - 0x41) // 2
                s = max(0, i-4); e = min(len(rom), i+10)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  LEA (${t:08X}).L, A{an} @ ${i:06X}: {ctx}')

# Also check MOVEA.L #imm, An = 207C/227C/247C/267C/287C/2A7C/2C7C/2E7C
for i in range(len(rom) - 5):
    op = (rom[i]<<8)|rom[i+1]
    if op in (0x207C, 0x227C, 0x247C, 0x267C, 0x287C, 0x2A7C, 0x2C7C, 0x2E7C):
        t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
        if 0x00FF0060 <= t <= 0x00FF006F:
            an = (op - 0x207C) // 0x200
            s = max(0, i-4); e = min(len(rom), i+10)
            ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
            print(f'  MOVEA.L #${t:08X}, A{an} @ ${i:06X}: {ctx}')
print()

# === Broader: LEA near FF0000 base (could use offset to reach 0x66/0x67) ===
print('=== LEA/MOVEA to FF0000 base area (within $FF0000-$FF00FF) ===')
base_refs = []
for i in range(len(rom) - 5):
    if rom[i+1] == 0xF9:
        op1 = rom[i]
        if op1 in (0x41, 0x43, 0x45, 0x47, 0x49, 0x4B, 0x4D, 0x4F):
            t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
            if 0x00FF0000 <= t <= 0x00FF00FF:
                an = (op1 - 0x41) // 2
                s = max(0, i-4); e = min(len(rom), i+10)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                base_refs.append(f'  LEA (${t:08X}).L, A{an} @ ${i:06X}: {ctx}')

for i in range(len(rom) - 5):
    op = (rom[i]<<8)|rom[i+1]
    if op in (0x207C, 0x227C, 0x247C, 0x267C, 0x287C, 0x2A7C, 0x2C7C, 0x2E7C):
        t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
        if 0x00FF0000 <= t <= 0x00FF00FF:
            an = (op - 0x207C) // 0x200
            s = max(0, i-4); e = min(len(rom), i+10)
            ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
            base_refs.append(f'  MOVEA.L #${t:08X}, A{an} @ ${i:06X}: {ctx}')

for r in base_refs[:30]:
    print(r)
if len(base_refs) > 30:
    print(f'  ... ({len(base_refs)} total, showing first 30)')
elif not base_refs:
    print('  (none found)')
print()

# === Decode what each FF0066/FF0067 reference does ===
print('=== DECODED instruction for each FF0066/FF0067 reference ===')
for addr, lo in refs:
    # The 00FF00xx starts at addr. The instruction starts BEFORE.
    # Try to figure out what instruction this belongs to.
    target = f'FF00{lo:02X}'
    
    # Check preceding bytes for known opcodes
    # Common patterns:
    # BTST #n, (xxx).L  = 08 39 00 nn 00FF00xx  (instruction at addr-4)
    # BSET #n, (xxx).L  = 08 F9 00 nn 00FF00xx  (instruction at addr-4)
    # BCLR #n, (xxx).L  = 08 B9 00 nn 00FF00xx  (instruction at addr-4)
    # BCHG #n, (xxx).L  = 08 79 00 nn 00FF00xx  (instruction at addr-4)
    # ORI.B #i, (xxx).L = 00 39 00 ii 00FF00xx  (instruction at addr-4)
    # ORI.W #i, (xxx).L = 00 79 ii ii 00FF00xx  (instruction at addr-4)
    # ANDI.B #i,(xxx).L = 02 39 00 ii 00FF00xx  (instruction at addr-4)
    # MOVE.B X,(xxx).L  = 13xx xxxx 00FF00xx    (varies)
    # MOVE.W X,(xxx).L  = 33xx xxxx 00FF00xx    (varies)
    # CLR.B (xxx).L     = 42 39 00FF00xx        (instruction at addr-2)
    # TST.B (xxx).L     = 4A 39 00FF00xx        (instruction at addr-2)
    # TST.W (xxx).L     = 4A 79 00FF00xx        (instruction at addr-2)
    
    decoded = "???"
    
    if addr >= 4:
        pre4 = (rom[addr-4]<<8)|rom[addr-3]
        pre2_val = rom[addr-2:addr]
        bit_n = rom[addr-1]
        
        if pre4 == 0x0839:
            decoded = f'BTST #{bit_n}, (${target}).L'
        elif pre4 == 0x08F9:
            decoded = f'BSET #{bit_n}, (${target}).L'
        elif pre4 == 0x08B9:
            decoded = f'BCLR #{bit_n}, (${target}).L'
        elif pre4 == 0x0879:
            decoded = f'BCHG #{bit_n}, (${target}).L'
        elif pre4 == 0x0039:
            decoded = f'ORI.B #${bit_n:02X}, (${target}).L'
        elif pre4 == 0x0079:
            imm16 = (rom[addr-2]<<8)|rom[addr-1]
            decoded = f'ORI.W #${imm16:04X}, (${target}).L'
        elif pre4 == 0x0239:
            decoded = f'ANDI.B #${bit_n:02X}, (${target}).L'
        elif pre4 == 0x0279:
            imm16 = (rom[addr-2]<<8)|rom[addr-1]
            decoded = f'ANDI.W #${imm16:04X}, (${target}).L'
    
    if decoded == "???" and addr >= 2:
        pre2 = (rom[addr-2]<<8)|rom[addr-1]
        if pre2 == 0x4239:
            decoded = f'CLR.B (${target}).L'
        elif pre2 == 0x4279:
            decoded = f'CLR.W (${target}).L'
        elif pre2 == 0x4A39:
            decoded = f'TST.B (${target}).L'
        elif pre2 == 0x4A79:
            decoded = f'TST.W (${target}).L'
    
    if decoded == "???":
        # Try MOVE.B/MOVE.W patterns
        # MOVE.B xxx, (xxx).L: opcode 13xx
        # Need to look further back
        s = max(0, addr - 8)
        ctx_before = ' '.join('%02X' % rom[j] for j in range(s, addr+4))
        decoded = f'(undecoded) ctx: {ctx_before}'
    
    inst_addr = addr - 4 if decoded.startswith(('BTST','BSET','BCLR','BCHG','ORI','ANDI')) else addr - 2
    print(f'  ${addr:06X} -> {decoded}  (inst~${inst_addr:06X})')

print()
print('=== SUMMARY ===')
writes = [d for (a, lo) in refs for d in [None] if False]  # placeholder
# Re-decode to find writes
write_count = 0
for addr, lo in refs:
    target = f'FF00{lo:02X}'
    if addr >= 4:
        pre4 = (rom[addr-4]<<8)|rom[addr-3]
        if pre4 in (0x08F9, 0x0879, 0x0039, 0x0079, 0x0239, 0x0279):
            write_count += 1
            if pre4 == 0x08F9:
                bit_n = rom[addr-1]
                print(f'  WRITE: BSET #{bit_n}, (${target}).L @ ${addr-4:06X}')
            elif pre4 == 0x0039:
                imm = rom[addr-1]
                print(f'  WRITE: ORI.B #${imm:02X}, (${target}).L @ ${addr-4:06X}')
            elif pre4 == 0x0079:
                imm = (rom[addr-2]<<8)|rom[addr-1]
                print(f'  WRITE: ORI.W #${imm:04X}, (${target}).L @ ${addr-4:06X}')
            elif pre4 == 0x0239:
                imm = rom[addr-1]
                print(f'  WRITE: ANDI.B #${imm:02X}, (${target}).L @ ${addr-4:06X}')
            elif pre4 == 0x0279:
                imm = (rom[addr-2]<<8)|rom[addr-1]
                print(f'  WRITE: ANDI.W #${imm:04X}, (${target}).L @ ${addr-4:06X}')
    if addr >= 2:
        pre2 = (rom[addr-2]<<8)|rom[addr-1]
        if pre2 in (0x4239, 0x4279):
            write_count += 1
            if pre2 == 0x4239:
                print(f'  WRITE: CLR.B (${target}).L @ ${addr-2:06X}')
            elif pre2 == 0x4279:
                print(f'  WRITE: CLR.W (${target}).L @ ${addr-2:06X}')

print(f'\nTotal write instructions found: {write_count}')
