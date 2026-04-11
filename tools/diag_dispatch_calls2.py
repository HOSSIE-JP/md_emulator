#!/usr/bin/env python3
"""Search ROM for PC-relative JSR/BSR calls to $8BBC and $8DFC."""

ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

rom_len = len(rom)

# --- JSR (d16,PC) = 4E BA xxxx to $8BBC ---
print("=== JSR (d16,PC) to $8BBC ===")
target = 0x8BBC
for addr in range(0, min(rom_len - 3, 0x100000), 2):
    if rom[addr] == 0x4E and rom[addr + 1] == 0xBA:
        disp_addr = addr + 2
        disp = (rom[disp_addr] << 8) | rom[disp_addr + 1]
        if disp >= 0x8000:
            disp -= 0x10000
        dest = disp_addr + disp
        if dest == target:
            start = max(0, addr - 16)
            end = min(rom_len, addr + 20)
            h = ' '.join('%02X' % rom[start + i] for i in range(end - start))
            print(f"  JSR @ ${addr:06X} -> ${dest:06X}: {h}")
            # Decode preceding stack setup (look back for PEA/CLR instructions)
            pre_start = max(0, addr - 32)
            pre = ' '.join('%02X' % rom[pre_start + i] for i in range(addr - pre_start))
            print(f"    Setup (${pre_start:06X}): {pre}")

# --- JSR (d16,PC) = 4E BA xxxx to $8DFC ---
print("\n=== JSR (d16,PC) to $8DFC ===")
target2 = 0x8DFC
for addr in range(0, min(rom_len - 3, 0x100000), 2):
    if rom[addr] == 0x4E and rom[addr + 1] == 0xBA:
        disp_addr = addr + 2
        disp = (rom[disp_addr] << 8) | rom[disp_addr + 1]
        if disp >= 0x8000:
            disp -= 0x10000
        dest = disp_addr + disp
        if dest == target2:
            start = max(0, addr - 16)
            end = min(rom_len, addr + 20)
            h = ' '.join('%02X' % rom[start + i] for i in range(end - start))
            print(f"  JSR @ ${addr:06X} -> ${dest:06X}: {h}")

# --- Disassemble $8DFC function ---
print("\n=== Disassembly of $8DFC-$8E80 ===")
for a in range(0x8DFC, min(0x8EA0, rom_len), 2):
    h = '%02X %02X' % (rom[a], rom[a + 1])
    print(f"  ${a:06X}: {h}", end='')
    w = (rom[a] << 8) | rom[a + 1]
    # Simple decode
    if w == 0x4E75:
        print("  ; RTS")
    elif w == 0x4E71:
        print("  ; NOP")
    elif rom[a] == 0x4E and rom[a + 1] == 0xBA:
        if a + 3 < rom_len:
            d16 = (rom[a + 2] << 8) | rom[a + 3]
            if d16 >= 0x8000:
                d16 -= 0x10000
            dest = (a + 2) + d16
            print(f"  ; JSR ${dest:06X}")
        else:
            print()
    elif w == 0x42A7:
        print("  ; CLR.L -(SP)")
    elif w == 0x4878:
        if a + 3 < rom_len:
            imm = (rom[a + 2] << 8) | rom[a + 3]
            print(f"  ; PEA (${imm:04X}).W  [push {imm}]")
        else:
            print()
    elif w & 0xFFF8 == 0x48E7:
        print("  ; MOVEM.L regs,-(SP)")
    elif w & 0xFFF8 == 0x4CDF:
        print("  ; MOVEM.L (SP)+,regs")
    else:
        print()

# --- Script engine jump table decode ---
print("\n=== Script engine jump table at $B670 ===")
table_base = 0xB670  # Offset base for JMP
for i in range(19):
    off_addr = 0xB670 + i * 2
    off_val = (rom[off_addr] << 8) | rom[off_addr + 1]
    target = table_base + off_val
    print(f"  Entry {i:2d} (${off_addr:06X}): offset=${off_val:04X} -> ${target:06X}")

# --- Decode entry 18 ($B696) which likely calls dispatch ---
print("\n=== Entry 18 handler at $B696 ===")
for a in range(0xB696, min(0xB6C0, rom_len), 2):
    h = '%02X %02X' % (rom[a], rom[a + 1])
    w = (rom[a] << 8) | rom[a + 1]
    extra = ''
    if w == 0x42A7:
        extra = '  ; CLR.L -(SP) [push 0]'
    elif w == 0x4878:
        if a + 3 < rom_len:
            imm = (rom[a + 2] << 8) | rom[a + 3]
            extra = f'  ; PEA (${imm:04X}).W [push {imm}]'
    elif rom[a] == 0x4E and rom[a + 1] == 0xBA:
        if a + 3 < rom_len:
            d16 = (rom[a + 2] << 8) | rom[a + 3]
            if d16 >= 0x8000:
                d16 -= 0x10000
            dest = (a + 2) + d16
            extra = f'  ; JSR ${dest:06X}'
    print(f"  ${a:06X}: {h}{extra}")

# --- What does dispatch($8BBC) do with step 0 vs step 5? ---
# Read the handler jump table inside dispatch
print("\n=== Dispatch $8BBC internal jump table ===")
# $8BF8: 30 3B 08 06 = MOVE.W (6,PC,D0.W),D0
# $8BFC: 4E FB 00 02 = JMP (2,PC,D0.W)
# Table at $8BFE+2 = $8C00? No, let's recalc
# MOVE.W at $8BF8, ext word at $8BFA: 08 06, PC=$8BFA, EA=$8BFA+6+D0 = $8C00+D0
# JMP at $8BFC, ext word at $8BFE: 00 02, PC=$8BFE, target=$8BFE+2+D0 = $8C00+D0
# Table at $8C00
for i in range(6):
    off_addr = 0x8C00 + i * 2
    if off_addr + 1 < rom_len:
        off_val = (rom[off_addr] << 8) | rom[off_addr + 1]
        target = 0x8C00 + off_val
        print(f"  Step {i}: offset=${off_val:04X} -> ${target:06X}")
