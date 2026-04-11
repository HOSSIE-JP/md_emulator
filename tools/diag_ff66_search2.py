#!/usr/bin/env python3
"""Search full ROM for instructions referencing $FF0066/$FF0067 via E0FF prefix."""
ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

print(f'ROM size: {len(rom)} bytes (0x{len(rom):X})')
print()

# The game encodes absolute long addresses with upper byte E0:
# $FF0066 -> E0 FF 00 66, $FF0067 -> E0 FF 00 67
refs = []
for i in range(len(rom) - 3):
    if rom[i] == 0xE0 and rom[i+1] == 0xFF and rom[i+2] == 0x00:
        if rom[i+3] in (0x66, 0x67):
            refs.append((i, rom[i+3]))

print(f'=== ALL refs via E0FF00xx ({len(refs)} total) ===')
for addr, lo in refs:
    s = max(0, addr - 12)
    e = min(len(rom), addr + 8)
    ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
    
    # Decode instruction
    decoded = "???"
    inst_addr = 0
    
    if addr >= 4:
        pre4 = (rom[addr-4]<<8)|rom[addr-3]
        bit_n = rom[addr-1]
        
        if pre4 == 0x0839:
            decoded = f'BTST #{bit_n}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x08F9:
            decoded = f'BSET #{bit_n}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x08B9:
            decoded = f'BCLR #{bit_n}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x0879:
            decoded = f'BCHG #{bit_n}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x0039:
            decoded = f'ORI.B #${bit_n:02X}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x0079:
            imm16 = (rom[addr-2]<<8)|rom[addr-1]
            decoded = f'ORI.W #${imm16:04X}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x0239:
            decoded = f'ANDI.B #${bit_n:02X}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        elif pre4 == 0x0279:
            imm16 = (rom[addr-2]<<8)|rom[addr-1]
            decoded = f'ANDI.W #${imm16:04X}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
    
    if decoded == "???" and addr >= 2:
        pre2 = (rom[addr-2]<<8)|rom[addr-1]
        if pre2 == 0x4239:
            decoded = f'CLR.B ($FF00{lo:02X}).L'
            inst_addr = addr - 2
        elif pre2 == 0x4279:
            decoded = f'CLR.W ($FF00{lo:02X}).L'
            inst_addr = addr - 2
        elif pre2 == 0x4A39:
            decoded = f'TST.B ($FF00{lo:02X}).L'
            inst_addr = addr - 2
        elif pre2 == 0x4A79:
            decoded = f'TST.W ($FF00{lo:02X}).L'
            inst_addr = addr - 2
        elif pre2 == 0x13F9:
            # MOVE.B (xxx).L, (xxx).L - source addr precedes, dest is at addr
            decoded = f'MOVE.B (xxx).L, ($FF00{lo:02X}).L [dest]'
            inst_addr = addr - 10  # approx
    
    if decoded == "???":
        # Check for MOVE.B #imm: 13FC 00 ii E0FF00xx
        if addr >= 4 and rom[addr-4] == 0x13 and rom[addr-3] == 0xFC:
            imm = rom[addr-1]
            decoded = f'MOVE.B #${imm:02X}, ($FF00{lo:02X}).L'
            inst_addr = addr - 4
        # MOVE.W #imm: 33FC iiii E0FF00xx
        elif addr >= 6 and rom[addr-6] == 0x33 and rom[addr-5] == 0xFC:
            imm = (rom[addr-4]<<8)|rom[addr-3]
            # But we need to check if addr-2 is part of imm or not
            # 33FC imm_hi imm_lo E0 FF 00 xx  -> at addr = position of E0
            decoded = f'MOVE.W #${imm:04X}, ($FF00{lo:02X}).L (check)'
            inst_addr = addr - 6
    
    if decoded == "???":
        # Try more patterns
        # MOVE.B Dn, (xxx).L = 13C0+n E0FF00xx (2 bytes before E0FF)
        if addr >= 2:
            pre2 = (rom[addr-2]<<8)|rom[addr-1]
            if 0x13C0 <= pre2 <= 0x13C7:
                dn = pre2 - 0x13C0
                decoded = f'MOVE.B D{dn}, ($FF00{lo:02X}).L'
                inst_addr = addr - 2
            elif 0x33C0 <= pre2 <= 0x33C7:
                dn = pre2 - 0x33C0
                decoded = f'MOVE.W D{dn}, ($FF00{lo:02X}).L'
                inst_addr = addr - 2
            # MOVE.B (An), (xxx).L = 13D0+n E0FF00xx
            elif 0x13D0 <= pre2 <= 0x13D7:
                an = pre2 - 0x13D0
                decoded = f'MOVE.B (A{an}), ($FF00{lo:02X}).L'
                inst_addr = addr - 2
            # MOVE.B (An)+, (xxx).L = 13D8+n E0FF00xx
            elif 0x13D8 <= pre2 <= 0x13DF:
                an = pre2 - 0x13D8
                decoded = f'MOVE.B (A{an})+, ($FF00{lo:02X}).L'
                inst_addr = addr - 2
    
    if decoded == "???":
        # Check for MOVE.B (d16,An),(xxx).L = 13E8+n d16 E0FF00xx
        if addr >= 4:
            op2 = (rom[addr-4]<<8)|rom[addr-3]
            if 0x13E8 <= op2 <= 0x13EF:
                an = op2 - 0x13E8
                d16 = (rom[addr-2]<<8)|rom[addr-1]
                if d16 >= 0x8000: d16 -= 0x10000
                decoded = f'MOVE.B (${d16:+d},A{an}), ($FF00{lo:02X}).L'
                inst_addr = addr - 4
    
    if decoded == "???":
        # Last resort: show raw context
        s2 = max(0, addr - 8)
        ctx2 = ' '.join('%02X' % rom[j] for j in range(s2, min(len(rom), addr+4)))
        decoded = f'(raw: {ctx2})'
        inst_addr = addr

    is_write = any(w in decoded for w in ['BSET','BCLR','BCHG','ORI','ANDI','CLR','MOVE'])
    marker = ' <<< WRITE' if is_write else ''
    bit3_marker = ''
    if 'BSET #3' in decoded or '#$08' in decoded or '#$0008' in decoded:
        bit3_marker = ' *** BIT 3 ***'
    # Check for ORI with bit 3
    if 'ORI' in decoded:
        # Extract immediate value
        import re
        m = re.search(r'#\$([0-9A-F]+)', decoded)
        if m:
            val = int(m.group(1), 16)
            if val & 0x08:
                bit3_marker = ' *** BIT 3 ***'
    # Check MOVE immediate with bit 3
    if 'MOVE' in decoded and '#$' in decoded:
        import re
        m = re.search(r'#\$([0-9A-F]+)', decoded)
        if m:
            val = int(m.group(1), 16)
            if val & 0x08:
                bit3_marker = ' *** BIT 3 ***'
    
    print(f'  ${inst_addr:06X}: {decoded}{marker}{bit3_marker}')
    print(f'           ctx: {ctx}')

# === Also search for E0FF0060-E0FF006F to find base address loads ===
print()
print('=== LEA/MOVEA to $FF006x area (E0FF encoding) ===')
for i in range(len(rom) - 5):
    if rom[i+2] == 0xE0 and rom[i+3] == 0xFF and rom[i+4] == 0x00:
        if 0x60 <= rom[i+5] <= 0x6F:
            op1 = rom[i]
            # LEA (xxx).L, An = 4xF9
            if rom[i+1] == 0xF9 and op1 in (0x41,0x43,0x45,0x47,0x49,0x4B,0x4D,0x4F):
                an = (op1 - 0x41) // 2
                t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
                s = max(0, i-2); e = min(len(rom), i+10)
                ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
                print(f'  LEA (${t:08X}).L, A{an} @ ${i:06X}: {ctx}')

# Search for LEA to FF0000 base
print()
print('=== LEA/MOVEA to $FF0000 base area (E0FF encoding) ===')
for i in range(len(rom) - 5):
    if rom[i+2] == 0xE0 and rom[i+3] == 0xFF and rom[i+4] == 0x00:
        base = rom[i+5]
        op1 = rom[i]
        if rom[i+1] == 0xF9 and op1 in (0x41,0x43,0x45,0x47,0x49,0x4B,0x4D,0x4F):
            an = (op1 - 0x41) // 2
            t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
            s = max(0, i-2); e = min(len(rom), i+10)
            ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
            print(f'  LEA (${t:08X}).L, A{an} @ ${i:06X}: {ctx}')

# Also check MOVEA
for i in range(len(rom) - 5):
    op = (rom[i]<<8)|rom[i+1]
    if op in (0x207C, 0x227C, 0x247C, 0x267C, 0x287C, 0x2A7C, 0x2C7C, 0x2E7C):
        if rom[i+2] == 0xE0 and rom[i+3] == 0xFF:
            t = (rom[i+2]<<24)|(rom[i+3]<<16)|(rom[i+4]<<8)|rom[i+5]
            an = (op - 0x207C) // 0x200
            s = max(0, i-2); e = min(len(rom), i+10)
            ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
            print(f'  MOVEA.L #${t:08X}, A{an} @ ${i:06X}: {ctx}')
