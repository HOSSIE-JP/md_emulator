#!/usr/bin/env python3
"""Decode the main dispatch loop and search for FF019E references."""
ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

# Show broader context around the dispatch loop $8340-$8420
print('=== Main dispatch loop $8340-$8420 (raw disassembly) ===')
for a in range(0x8340, 0x8420, 2):
    h = '%02X %02X' % (rom[a], rom[a+1])
    # Quick decode of common instructions
    w = (rom[a]<<8)|rom[a+1]
    desc = ""
    if w == 0x4E75: desc = " RTS"
    elif w == 0x4E73: desc = " RTE"
    elif w == 0x4E71: desc = " NOP"
    elif w == 0x7000: desc = " MOVEQ #0, D0"
    elif (w & 0xFF00) == 0x6000: 
        disp = w & 0xFF
        if disp == 0: desc = " BRA.W"
        else:
            if disp >= 0x80: disp -= 0x100
            desc = f" BRA.S ${a+2+disp:06X}"
    elif (w & 0xFF00) == 0x6C00:
        disp = w & 0xFF
        if disp >= 0x80: disp -= 0x100
        desc = f" BGE.S ${a+2+disp:06X}"
    elif (w & 0xFF00) == 0x6600:
        disp = w & 0xFF
        if disp >= 0x80: disp -= 0x100
        if disp == 0: desc = " BNE.W"
        else: desc = f" BNE.S ${a+2+disp:06X}"
    elif (w & 0xFF00) == 0x6700:
        disp = w & 0xFF
        if disp >= 0x80: disp -= 0x100
        if disp == 0: desc = " BEQ.W"
        else: desc = f" BEQ.S ${a+2+disp:06X}"
    elif w == 0x4E92: desc = " JSR (A2)"
    elif w == 0x4E90: desc = " JSR (A0)"
    elif w == 0x4E91: desc = " JSR (A1)"
    elif w == 0x4A02: desc = " TST.B D2"
    elif w == 0x4A00: desc = " TST.B D0"
    elif w == 0x588F: desc = " ADDQ.L #4, SP"
    elif w == 0x548F: desc = " ADDQ.L #2, SP"
    elif w == 0x2F00: desc = " MOVE.L D0, -(SP)"
    elif w == 0x3039: 
        if a+5 < len(rom):
            addr = (rom[a+2]<<24)|(rom[a+3]<<16)|(rom[a+4]<<8)|rom[a+5]
            desc = f" MOVE.W (${addr:08X}).L, D0"
    elif w == 0x1439:
        if a+5 < len(rom):
            addr = (rom[a+2]<<24)|(rom[a+3]<<16)|(rom[a+4]<<8)|rom[a+5]
            desc = f" MOVE.B (${addr:08X}).L, D2"
    elif w == 0x0839:
        if a+3 < len(rom):
            bit = (rom[a+2]<<8)|rom[a+3]
            desc = f" BTST #{bit}"
    elif w == 0x33C0:
        if a+5 < len(rom):
            addr = (rom[a+2]<<24)|(rom[a+3]<<16)|(rom[a+4]<<8)|rom[a+5]
            desc = f" MOVE.W D0, (${addr:08X}).L"
    elif w == 0x33FC:
        if a+7 < len(rom):
            imm = (rom[a+2]<<8)|rom[a+3]
            addr = (rom[a+4]<<24)|(rom[a+5]<<16)|(rom[a+6]<<8)|rom[a+7]
            desc = f" MOVE.W #${imm:04X}, (${addr:08X}).L"
    elif w == 0x0040:
        if a+3 < len(rom):
            imm = (rom[a+2]<<8)|rom[a+3]
            desc = f" ORI.W #${imm:04X}, D0"
    elif w == 0x0800:
        if a+3 < len(rom):
            bit = (rom[a+2]<<8)|rom[a+3]
            desc = f" BTST #{bit}, D0"
    print(f'  ${a:06X}: {h}{desc}')

print()

# Search for ALL references to FF019E (with E0FF prefix)
print('=== References to FF019E (E0FF019E) ===')
for i in range(len(rom) - 3):
    if rom[i] == 0xE0 and rom[i+1] == 0xFF and rom[i+2] == 0x01 and rom[i+3] == 0x9E:
        s = max(0, i-8)
        e = min(len(rom), i+8)
        ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
        
        # Try to decode instruction
        decoded = "?"
        if i >= 4:
            pre = (rom[i-4]<<8)|rom[i-3]
            if pre == 0x0839: decoded = f"BTST #{rom[i-1]}"
            elif pre == 0x08F9: decoded = f"BSET #{rom[i-1]}"
            elif pre == 0x08B9: decoded = f"BCLR #{rom[i-1]}"
            elif pre == 0x0039: decoded = f"ORI.B #${rom[i-1]:02X}"
            elif pre == 0x0239: decoded = f"ANDI.B #${rom[i-1]:02X}"
        if decoded == "?" and i >= 2:
            pre = (rom[i-2]<<8)|rom[i-1]
            if pre == 0x4239: decoded = "CLR.B"
            elif pre == 0x4A39: decoded = "TST.B"
            elif pre == 0x13FC:
                imm = rom[i-1]
                decoded = f"MOVE.B #${imm:02X}"
            elif 0x13C0 <= pre <= 0x13C7:
                decoded = f"MOVE.B D{pre-0x13C0}"
        
        print(f'  ${i:06X}: {decoded}    ctx: {ctx}')

print()

# Also search for references to FF019C
print('=== References to FF019C (E0FF019C) ===')
for i in range(len(rom) - 3):
    if rom[i] == 0xE0 and rom[i+1] == 0xFF and rom[i+2] == 0x01 and rom[i+3] == 0x9C:
        s = max(0, i-8)
        e = min(len(rom), i+8)
        ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
        decoded = "?"
        if i >= 4:
            pre = (rom[i-4]<<8)|rom[i-3]
            if pre == 0x0839: decoded = f"BTST #{rom[i-1]}"
            elif pre == 0x08F9: decoded = f"BSET #{rom[i-1]}"
        if decoded == "?" and i >= 2:
            pre = (rom[i-2]<<8)|rom[i-1]
            if pre == 0x4279: decoded = "CLR.W"
            elif pre == 0x4239: decoded = "CLR.B"
        print(f'  ${i:06X}: {decoded}    ctx: {ctx}')

# Also check the Z80 communication: code reading $A00102
print()
print('=== References to Z80 RAM $A00102 ===')
for i in range(len(rom) - 3):
    if rom[i] == 0x00 and rom[i+1] == 0xA0 and rom[i+2] == 0x01 and rom[i+3] == 0x02:
        s = max(0, i-8)
        e = min(len(rom), i+8)
        ctx = ' '.join('%02X' % rom[j] for j in range(s, e))
        print(f'  ${i:06X}: ctx: {ctx}')
