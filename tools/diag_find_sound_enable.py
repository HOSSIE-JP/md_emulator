"""Find what code sets bit 3 of $FF0067 (sound enable flag)"""
ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

with open(ROM_PATH, "rb") as f:
    rom = f.read()

# Search for references to $E0FF0067 (full address)
target = bytes([0xE0, 0xFF, 0x00, 0x67])
print("=== References to $E0FF0067 ===")
for i in range(len(rom) - 4):
    if rom[i:i+4] == target:
        ctx_start = max(0, i - 6)
        ctx_end = min(len(rom), i + 12)
        ctx = rom[ctx_start:ctx_end]
        print(f"  ${i:06X}: ...{ctx.hex(' ')}...")

# Also search for $FF0067 references (mirrored address, fewer search bytes = more results)
# Use the pattern 0xFF0067 = FF 00 67
# But we need to be more specific: 00FF0067 
target2 = bytes([0x00, 0xFF, 0x00, 0x67])
print("\n=== References to $00FF0067 ===")
for i in range(len(rom) - 4):
    if rom[i:i+4] == target2:
        ctx_start = max(0, i - 4)
        ctx_end = min(len(rom), i + 8)
        ctx = rom[ctx_start:ctx_end]
        print(f"  ${i:06X}: ...{ctx.hex(' ')}...")

# The VBlank handler uses $E0FF0067. Let me also check for nearby addresses
# $FF0064 (VBlank flag), $FF0042 (counter)
print("\n=== References to $E0FF0064 ===")
target3 = bytes([0xE0, 0xFF, 0x00, 0x64])
count = 0
for i in range(len(rom) - 4):
    if rom[i:i+4] == target3:
        count += 1
        if count <= 10:
            ctx_start = max(0, i - 4)
            ctx_end = min(len(rom), i + 8)
            ctx = rom[ctx_start:ctx_end]
            print(f"  ${i:06X}: ...{ctx.hex(' ')}...")
print(f"  Total: {count}")

# More importantly: what SETS bit 3? Look for BSET #3, xxx
# BSET #imm, <ea>.l = 08F9 0003 <address>
# BSET #imm, <ea>.l = 08F9 then mask 0003 then addr E0FF0067
bset_pattern = bytes([0x08, 0xF9, 0x00, 0x03, 0xE0, 0xFF, 0x00, 0x67])
print(f"\n=== BSET #3, ($E0FF0067) ===")
for i in range(len(rom) - len(bset_pattern)):
    if rom[i:i+len(bset_pattern)] == bset_pattern:
        print(f"  Found at ${i:06X}")

# ORI.B #$08, ($E0FF0067).l = 0039 0008 E0FF0067
ori_pattern = bytes([0x00, 0x39, 0x00, 0x08, 0xE0, 0xFF, 0x00, 0x67])
print(f"\n=== ORI.B #$08, ($E0FF0067) ===")
for i in range(len(rom) - len(ori_pattern)):
    if rom[i:i+len(ori_pattern)] == ori_pattern:
        print(f"  Found at ${i:06X}")

# MOVE.B #xx, ($E0FF0067).l = 13FC xx E0FF0067
# Search for: 13FC followed by any byte, then E0FF0067
print(f"\n=== MOVE.B #imm, ($E0FF0067) ===")
for i in range(len(rom) - 8):
    if rom[i] == 0x13 and rom[i+1] == 0xFC and rom[i+4:i+8] == target:
        imm = rom[i+2:i+4]
        print(f"  Found at ${i:06X}: MOVE.B #${imm[1]:02X}, ($E0FF0067)")

# Let's look at what calls the sound init routine
# The game's init should set $FF0067 bit 3 when sound is ready
# Let me find the code that first writes to $FF0067

# Also look at the return address $1C326
print(f"\n=== Code at return address $1C326 ===")
for o in range(0, 96, 16):
    data = rom[0x1C326+o:0x1C326+o+16]
    print(f"  ${0x1C326+o:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Look at $1C300-1C340 for context (the calling function)
print(f"\n=== Calling function around $1C300 ===")
for o in range(0, 128, 16):
    data = rom[0x1C2C0+o:0x1C2C0+o+16]
    print(f"  ${0x1C2C0+o:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Search for who sets $FF004C (frame counter) or how the game tracks time
# Also let's check: Is the game stuck because frame_ctr stays at 94?
# The VBlank handler sets $FF004C. If VINT is disabled, counter stops.
# But what READS $FF004C?
target_4c = bytes([0xE0, 0xFF, 0x00, 0x4C])
print(f"\n=== References to $E0FF004C (frame counter) ===")
count = 0
for i in range(len(rom) - 4):
    if rom[i:i+4] == target_4c:
        count += 1
        if count <= 15:
            ctx_start = max(0, i - 4)
            ctx_end = min(len(rom), i + 8)
            ctx = rom[ctx_start:ctx_end]
            print(f"  ${i:06X}: ...{ctx.hex(' ')}...")
print(f"  Total: {count}")
