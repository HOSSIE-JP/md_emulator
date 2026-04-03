#!/usr/bin/env python3
"""Search ROM for code that could set bit 1 of word at $FF0066."""

with open("frontend/roms/\u5317\u3078PM \u9b8e.bin", "rb") as f:
    rom = f.read()

# Find ALL references to E0FF0066 in the ROM and decode what they do
refs = []
target = b"\xE0\xFF\x00\x66"
offset = 0
while True:
    idx = rom.find(target, offset)
    if idx == -1:
        break
    refs.append(idx)
    offset = idx + 1

print(f"Found {len(refs)} references to $E0FF0066")
print()

for ref_pos in refs:
    # The address constant appears at ref_pos. The instruction starts earlier.
    # Need to look back to find the opcode
    start = max(0, ref_pos - 12)
    end = min(len(rom), ref_pos + 8)
    ctx = rom[start:end]
    hex_str = " ".join("%02X" % b for b in ctx)
    
    # Check if this is a WRITE instruction (MOVE.W to this address)
    # Common patterns:
    # 33C0 E0FF0066 = MOVE.W D0, ($FF0066)
    # 33C2 E0FF0066 = MOVE.W D2, ($FF0066)
    # 33FC xxxx E0FF0066 = MOVE.W #imm, ($FF0066)
    # 0079 xxxx E0FF0066 = ORI.W #imm, ($FF0066)
    # Also could be reads: 3039 E0FF0066 = MOVE.W ($FF0066), D0
    
    is_write = False
    desc = "?"
    
    # Check 2 bytes before the address constant
    if ref_pos >= 2:
        pre2 = rom[ref_pos-2:ref_pos]
        if pre2 == b"\x33\xC0":
            desc = "MOVE.W D0, ($FF0066) -- WRITE"
            is_write = True
        elif pre2 == b"\x33\xC2":
            desc = "MOVE.W D2, ($FF0066) -- WRITE"
            is_write = True
    
    # Check 4 bytes before for ORI/MOVE.W #imm
    if ref_pos >= 4:
        pre4 = rom[ref_pos-4:ref_pos]
        if pre4[:2] == b"\x33\xFC":
            imm = (pre4[2] << 8) | pre4[3]
            desc = "MOVE.W #$%04X, ($FF0066) -- WRITE imm" % imm
            is_write = True
        elif pre4[:2] == b"\x00\x79":
            imm = (pre4[2] << 8) | pre4[3]
            desc = "ORI.W #$%04X, ($FF0066) -- WRITE ORI" % imm
            is_write = True
        elif pre4[:2] == b"\x02\x79":
            imm = (pre4[2] << 8) | pre4[3]
            desc = "ANDI.W #$%04X, ($FF0066) -- WRITE ANDI" % imm
            is_write = True
    
    # Check for reads: 3039 E0FF0066 or 3439
    if ref_pos >= 2:
        pre2 = rom[ref_pos-2:ref_pos]
        if pre2 == b"\x30\x39":
            desc = "MOVE.W ($FF0066), D0 -- READ"
        elif pre2 == b"\x34\x39":
            desc = "MOVE.W ($FF0066), D2 -- READ"
        elif pre2 == b"\x32\x39":
            desc = "MOVE.W ($FF0066), D1 -- READ"
    
    # Check for BTST/BSET/BCLR on byte FF0067
    if ref_pos >= 4:
        pre4 = rom[ref_pos-4:ref_pos]
        if pre4[:2] == b"\x08\x39":
            bit = pre4[3]
            desc = "BTST #%d, ($FF0066) -- READ test" % bit
        elif pre4[:2] == b"\x08\xF9":
            bit = pre4[3]
            desc = "BSET #%d, ($FF0066) -- WRITE set" % bit
            is_write = True
    
    addr_of_ref = ref_pos  # This is the address of E0FF0066 in ROM
    # The instruction that contains this reference
    instr_addr = ref_pos - 6 if ref_pos >= 6 else 0
    
    marker = " *** WRITE ***" if is_write else ""
    print("  ROM offset $%06X: %s%s" % (ref_pos, desc, marker))
    print("    Context: %s" % hex_str)
    print()


# Also check E0FF0067 for byte operations
print("\n=== References to E0FF0067 ===")
target67 = b"\xE0\xFF\x00\x67"
offset = 0
while True:
    idx = rom.find(target67, offset)
    if idx == -1:
        break
    start = max(0, idx - 8)
    end = min(len(rom), idx + 8)
    hex_str = " ".join("%02X" % b for b in rom[start:end])
    
    desc = "?"
    if idx >= 4:
        pre4 = rom[idx-4:idx]
        if pre4[:2] == b"\x08\x39":
            bit = pre4[3]
            desc = "BTST #%d, ($FF0067)" % bit
        elif pre4[:2] == b"\x08\xF9":
            bit = pre4[3]
            desc = "BSET #%d, ($FF0067) -- WRITE"
        elif pre4[:2] == b"\x08\xB9":
            bit = pre4[3]
            desc = "BCLR #%d, ($FF0067) -- WRITE"
    if idx >= 2:
        pre2 = rom[idx-2:idx]
        if pre2 == b"\x13\xC0":
            desc = "MOVE.B D0, ($FF0067) -- WRITE"
        elif pre2 == b"\x10\x39":
            desc = "MOVE.B ($FF0067), D0 -- READ"
    
    print("  ROM offset $%06X: %s" % (idx, desc))
    print("    Context: %s" % hex_str)
    print()
