#!/usr/bin/env python3
"""Find callers of VDP reg1 write function at 0x9282 and trace D0 source."""
import struct

rom_path = "frontend/roms/北へPM 鮎.bin"
with open(rom_path, "rb") as f:
    rom = f.read()

def read16(addr):
    return (rom[addr] << 8) | rom[addr+1]

def read32(addr):
    return (rom[addr]<<24) | (rom[addr+1]<<16) | (rom[addr+2]<<8) | rom[addr+3]

TARGET = 0x9282

# Search for JSR $00009282 (4EB9 0000 9282)
print(f"=== Searching for calls to 0x{TARGET:06X} ===")

jsr_pattern = bytes([0x4E, 0xB9, 0x00, 0x00, TARGET >> 8, TARGET & 0xFF])
for i in range(0, len(rom) - len(jsr_pattern)):
    if rom[i:i+len(jsr_pattern)] == jsr_pattern:
        print(f"  JSR at 0x{i:06X}")
        # Show context
        start = max(0, i - 16)
        ctx = " ".join(f"{rom[j]:02X}" for j in range(start, min(len(rom), i + 12)))
        print(f"    Context: {ctx}")

# Search for BSR.W to 0x9282
for i in range(0, len(rom) - 4, 2):
    w = read16(i)
    if w == 0x6100:  # BSR.W
        disp = read16(i + 2)
        if disp >= 0x8000:
            disp -= 0x10000
        target = (i + 2 + disp) & 0xFFFFFF
        if target == TARGET:
            print(f"  BSR.W at 0x{i:06X} (displacement {disp})")
            start = max(0, i - 20)
            end = min(len(rom), i + 16)
            for addr in range(start, end, 2):
                w2 = read16(addr)
                marker = " <-- BSR" if addr == i else ""
                print(f"    0x{addr:06X}: {w2:04X}{marker}")

# Also search for BSR.S to 0x9282 (8-bit displacement)
for i in range(0, len(rom), 2):
    w = read16(i)
    if (w & 0xFF00) == 0x6100 and (w & 0xFF) != 0:  # BSR.S
        disp = w & 0xFF
        if disp >= 0x80:
            disp -= 0x100
        target = (i + 2 + disp) & 0xFFFFFF
        if target == TARGET:
            print(f"  BSR.S at 0x{i:06X} (displacement {disp})")
            start = max(0, i - 20)
            end = min(len(rom), i + 8)
            for addr in range(start, end, 2):
                w2 = read16(addr)
                marker = " <-- BSR.S" if addr == i else ""
                print(f"    0x{addr:06X}: {w2:04X}{marker}")

# Also search for JMP to 0x9282
jmp_pattern = bytes([0x4E, 0xF9, 0x00, 0x00, TARGET >> 8, TARGET & 0xFF])
for i in range(0, len(rom) - len(jmp_pattern)):
    if rom[i:i+len(jmp_pattern)] == jmp_pattern:
        print(f"  JMP at 0x{i:06X}")

# Also check if there's a BRA to 0x9282
for i in range(0, len(rom) - 4, 2):
    w = read16(i)
    if w == 0x6000:  # BRA.W
        disp = read16(i + 2)
        if disp >= 0x8000:
            disp -= 0x10000
        target = (i + 2 + disp) & 0xFFFFFF
        if target == TARGET:
            print(f"  BRA.W at 0x{i:06X}")
    elif (w & 0xFF00) == 0x6000 and (w & 0xFF) != 0:  # BRA.S
        disp = w & 0xFF
        if disp >= 0x80:
            disp -= 0x100
        target = (i + 2 + disp) & 0xFFFFFF
        if target == TARGET:
            print(f"  BRA.S at 0x{i:06X}")

# Also check for inline fall-through: is there a function just before 0x9282?
print(f"\n=== Code before 0x{TARGET:06X} ===")
for i in range(max(0, TARGET - 40), TARGET + 4, 2):
    w = read16(i)
    s = f"  0x{i:06X}: {w:04X}"
    if w == 0x4E75: s += " RTS"
    elif w == 0x4E71: s += " NOP"
    print(s)

# Now check the code right before the call site for how D0 gets 0x54
# The scan showed at frame 126, SL176: D0=0x8154 at PC=0x92A0
# Before 0x9282, D0 must have been set to something with lower byte = 0x54
# Let's check what's 0x92A0 backward context shows
# We need to understand: what calls the function at 0x9282 with D0=0x54?

# Also, let me check if the function at 0x928A (the MOVE that does the write) could be entered
# independently from 0x9282 (i.e., entry at 0x928A)
print(f"\n=== Looking for calls to 0x928A (VDP write instruction) ===")
TARGET2 = 0x928A
jsr_pattern2 = bytes([0x4E, 0xB9, 0x00, 0x00, TARGET2 >> 8, TARGET2 & 0xFF])
for i in range(0, len(rom) - len(jsr_pattern2)):
    if rom[i:i+len(jsr_pattern2)] == jsr_pattern2:
        print(f"  JSR at 0x{i:06X}")
