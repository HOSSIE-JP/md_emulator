#!/usr/bin/env python3
"""Find VINT enable/disable routines and SGDK SYS_enableInts pattern."""

rom_path = "frontend/roms/北へPM 鮎.bin"
with open(rom_path, "rb") as f:
    rom = f.read()

def read16(addr):
    return (rom[addr] << 8) | rom[addr+1]

# SGDK VDP reg1 cache is at 0xFFA831 (24-bit) = E0FFA831 (32-bit)
# Pattern to search: MOVE.B ($E0FFA831), D0 = bytes 10 39 E0 FF A8 31
CACHE_READ = bytes([0x10, 0x39, 0xE0, 0xFF, 0xA8, 0x31])
# MOVE.B D0, ($E0FFA831) = bytes 13 C0 E0 FF A8 31
CACHE_WRITE = bytes([0x13, 0xC0, 0xE0, 0xFF, 0xA8, 0x31])

print("=== References to VDP reg1 cache (0xFFA831) ===")
for pattern, desc in [(CACHE_READ, "READ"), (CACHE_WRITE, "WRITE")]:
    for i in range(len(rom) - len(pattern)):
        if rom[i:i+len(pattern)] == pattern:
            # Show context (20 bytes before and 20 after)
            start = max(0, i - 20)
            end = min(len(rom), i + len(pattern) + 20)
            ctx_before = " ".join(f"{rom[j]:02X}" for j in range(start, i))
            ctx_at = " ".join(f"{rom[j]:02X}" for j in range(i, i + len(pattern)))
            ctx_after = " ".join(f"{rom[j]:02X}" for j in range(i + len(pattern), end))
            print(f"\n  {desc} at 0x{i:06X}:")
            print(f"    Before: {ctx_before}")
            print(f"    Instr:  {ctx_at}")
            print(f"    After:  {ctx_after}")
            
            # Decode surrounding for key patterns
            # Check for ORI.B #$20 (0000 0020) = set VINT
            # Check for ANDI.B #$DF (0200 FFDF) = clear VINT
            for j in range(max(0, i-10), min(len(rom)-3, i+20), 2):
                w = read16(j)
                if w == 0x0000:
                    w2 = read16(j+2)
                    if (w2 & 0xFF) == 0x20:
                        print(f"    ** ORI.B #$20, D0 at 0x{j:06X} (SET VINT!)")
                if w == 0x0200:
                    w2 = read16(j+2)
                    if (w2 & 0xFF) == 0xDF:
                        print(f"    ** ANDI.B #$DF, D0 at 0x{j:06X} (CLEAR VINT!)")

# Also search for ANDI.B #$DF pattern anywhere (VDP VINT disable)
print("\n=== All ANDI.B #$DF (VINT clear) patterns ===")
andi_df = bytes([0x02, 0x00, 0xFF, 0xDF])  # ANDI.B #$DF, D0
for i in range(len(rom) - len(andi_df)):
    if rom[i:i+len(andi_df)] == andi_df:
        print(f"  ANDI.B #$DF at 0x{i:06X}")

# Search for ORI.B #$20 pattern (VDP VINT enable) 
print("\n=== All ORI.B #$20, D0 patterns ===")
ori_20 = bytes([0x00, 0x00, 0x00, 0x20])  # ORI.B #$20, D0
for i in range(len(rom) - len(ori_20)):
    if rom[i:i+len(ori_20)] == ori_20:
        # Check if it looks like code (not just data)
        if i < 0x20000:  # Only show in SGDK code area
            ctx = " ".join(f"{rom[j]:02X}" for j in range(max(0,i-8), min(len(rom), i+12)))
            print(f"  ORI.B #$20 at 0x{i:06X}: {ctx}")

# Also check for BSET #5 patterns (another way to set bit 5)
# BSET #imm, Dn = 08C0 + reg, imm = 0005
print("\n=== BSET #5, D0 patterns (another VINT enable method) ===")
bset5 = bytes([0x08, 0xC0, 0x00, 0x05])  # BSET #5, D0
for i in range(len(rom) - len(bset5)):
    if rom[i:i+len(bset5)] == bset5:
        if i < 0x20000:
            ctx = " ".join(f"{rom[j]:02X}" for j in range(max(0,i-8), min(len(rom), i+12)))
            print(f"  BSET #5, D0 at 0x{i:06X}: {ctx}")
