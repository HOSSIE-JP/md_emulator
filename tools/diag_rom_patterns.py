#!/usr/bin/env python3
"""Search ROM file directly for VDP register 1 write patterns."""
import sys

rom_path = sys.argv[1] if len(sys.argv) > 1 else "frontend/roms/北へPM 鮎.bin"
with open(rom_path, "rb") as f:
    rom = f.read()
print(f"ROM size: {len(rom)} bytes")

# Entry point
ep = (rom[4]<<24)|(rom[5]<<16)|(rom[6]<<8)|rom[7]
print(f"Entry point: 0x{ep:08X}")

# VINT vector
vint_vec = (rom[0x78]<<24)|(rom[0x79]<<16)|(rom[0x7A]<<8)|rom[0x7B]
print(f"VINT vector: 0x{vint_vec:08X}")

# Search for all VDP reg1 writes (0x81xx)
reg1_writes = {}
for i in range(0, len(rom)-1, 2):
    w = (rom[i]<<8)|rom[i+1]
    if (w & 0xFF00) == 0x8100:
        val = w & 0xFF
        if val not in reg1_writes:
            reg1_writes[val] = []
        reg1_writes[val].append(i)

print(f"\nAll VDP reg1 write values found in ROM:")
for val in sorted(reg1_writes.keys()):
    positions = reg1_writes[val]
    vint = "VINT" if val & 0x20 else "    "
    disp = "DISP" if val & 0x40 else "    "
    dma  = "DMA " if val & 0x10 else "    "
    print(f"  0x81{val:02X} (0x{val:02X} {vint} {disp} {dma}): {len(positions)} at {[hex(p) for p in positions[:10]]}")

# Context around 0x8174 (VINT ON)
for val, positions in sorted(reg1_writes.items()):
    if val & 0x20:  # VINT set
        for pos in positions[:3]:
            start = max(0, pos - 8)
            end = min(len(rom), pos + 16)
            ctx = " ".join(f"{rom[j]:02X}" for j in range(start, end))
            print(f"  Context at 0x{pos:06X} (val=0x{val:02X}): {ctx}")

# Check code around entry point
print(f"\nCode at entry point 0x{ep:06X}:")
for off in range(0, min(64, len(rom)-ep), 2):
    addr = ep + off
    w = (rom[addr]<<8)|rom[addr+1]
    print(f"  0x{addr:06X}: 0x{w:04X}", end="")
    if (w & 0xC000) == 0x8000:
        reg = (w >> 8) & 0x1F
        val = w & 0xFF
        print(f"  <- VDP reg{reg}=0x{val:02X}", end="")
    print()

# Check code near 0x7994 (where M68K is stuck)
if len(rom) > 0x7994 + 64:
    print(f"\nCode at 0x7994 (current M68K PC):")
    for off in range(0, 64, 2):
        addr = 0x7994 + off
        w = (rom[addr]<<8)|rom[addr+1]
        print(f"  0x{addr:06X}: 0x{w:04X}")
