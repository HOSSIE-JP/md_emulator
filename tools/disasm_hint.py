"""Disassemble the HInt handler at 0x6AC."""
import urllib.request, json

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Read the HInt handler code
handler_addr = 0x6AC
code = api_get(f"/cpu/memory?addr={handler_addr}&len=256")["data"]

# Simple 68000 disassembler for the handler
# The handler bytes: 00 7C 07 00 = ORI.W #$0700, SR
# Then: 4A 39 00 FF 01 3A = TST.B $FF013A
# etc.
# Let me just print bytes and basic decode
print(f"HInt handler at 0x{handler_addr:06X}:")
print(f"Bytes: {' '.join(f'{b:02X}' for b in code[:128])}")
print()

# Manual decode of the key parts:
# 0x6AC: 007C 0700 -> ORI #$0700, SR  (mask all interrupts)
# 0x6B0: 4A39 00FF013A -> TST.B $FF013A (test a RAM flag)
# 0x6B6: 6700 004E -> BEQ.W $0706  (if zero, skip to $0706)
# 0x6BA: 48E7 0080 -> MOVEM.L A0, -(SP)  (save A0)
# 0x6BE: 23FC 40000010 00C00004 -> MOVE.L #$40000010, $C00004 (VDP command write)
# Wait, that's interesting - $40000010 is a VDP control word
# $4000 = Address 0x0000 in VRAM write mode, but with $0010 it might be different

# Let me decode VDP command: 
# First word: 0x4000 -> CD1,CD0=01 (VRAM write), A13-A0=0x0000
# Second word: 0x0010 -> CD4,CD3,CD2=000, A16,A15,A14=000
# So it's VRAM write at address 0x0000

# Actually for Puyo Puyo this might be writing to the hscroll table
# Let me check: $40000010 is the VDP auto-increment setup

# 0x6C6: 2079 00FF013C -> MOVEA.L ($FF013C).L, A0  (load pointer from RAM)
# 0x6CC: 33D0 00C00000 -> MOVE.W (A0), $C00000  (write to VDP data port)
# 0x6D2: 5479 00FF013E -> ADDQ.W #2, ($FF013E).L (increment something)
# 0x6D8: 5379 00FF0140 -> SUBQ.W #1, ($FF0140).L (decrement counter)
# 0x6DE: 6600 0020 -> BNE.W $0700 (if not zero, branch)

# So the handler:
# 1. Masks interrupts
# 2. Tests $FF013A (a flag byte)
# 3. If flag is set: sets VDP address register, writes hscroll data from a table pointer
# 4. Increments pointer, decrements counter

# Now the VDP command at 0x6BE: 23FC 40000010 00C00004
# This writes the LONG $40000010 to $C00004 (VDP control)
# First write: 0x4000 -> sets up first half
# Second write: 0x0010 -> completes the command
# Full command: bits from both words:
# CD[5:0] = 000001 (bits: CD1CD0 from first=01, CD5CD4CD3CD2 from second=0000)
# So code=1 = VRAM write
# Address: A[15:0] from first word = 0x4000 bits [13:0] = 0x0000
# + A[16:14] from second = 0
# So VRAM write address = 0x0000? That doesn't seem right for hscroll...

# Let me be more careful with the VDP command decode:
# First word = 0x4000 = 0100 0000 0000 0000
# CD1= bit 7 of first byte = 0
# CD0= bit 6 of first byte = 1
# A13..A0 = 00 0000 0000 0000 = 0x0000
# Actually no: CD1CD0 = bits 15,14 of first word = 01
# A13..A0 = bits 13..0 of first word = 0x0000

# Second word = 0x0010 = 0000 0000 0001 0000
# CD3CD2 = bits 5,4 = 01 ??? Let me recheck
# In the standard VDP protocol:
# 1st word bits: CD1 CD0 A13 A12 A11 A10 A9 A8 A7 A6 A5 A4 A3 A2 A1 A0
# 2nd word bits: 0   0   0   0   0   0   0   0   CD5 CD4 CD3 CD2 0  0  A15 A14
# 
# So first word 0x4000:
# CD1=0 CD0=1 A13..A0=0x0000 -> address=0x0000
# Second word 0x0010:
# CD5..CD2 from bits 7..4 = 0001 
# A15..A14 from bits 1..0 = 00
# Full code = CD5..CD0 = 000101 ??? 
# Wait, standard encoding:
# 2nd word bits 7-4 = CD5 CD4 0 CD3 CD2 (some docs differ)
# Actually the standard is:
# 2nd word: 0 0 0 0 0 0 0 0 | CD5 CD4 _ CD3 CD2 _ A15 A14
# bits 7:4 of low byte = 0001
# So CD5=0, CD4=0, then bit5 is unused, CD3=0, CD2=1
# No wait, let me use the standard Sega layout:
# 
# Control word format (two writes):
# First write: xxAA AAAA AAAA AAAA (first 2 bits = CD1,CD0; rest = A13..A0)
# Second write: 0000 0000 xxxx xxAA (bits 7-4 of low byte = CD5,CD4,CD3,CD2; bits 1-0 = A15,A14)
# 
# For 0x0010:
# Byte 0 = 0x00, Byte 1 = 0x10
# bits 7-4 of byte 1 = 0001 -> CD5=0 CD4=0 CD3=0 CD2=1
# bits 1-0 of byte 1 = 00 -> A15=0, A14=0
# 
# So full CD = CD5..CD0 = 00 0001 = 0x01 -> VRAM write
# Full addr = A15..A0 = 0x0000
# 
# But the hscroll table is at 0xB800! So this isn't writing to the hscroll table.
# Unless... the handler writes via DMA, or the VDP address is different

# Actually, wait. Let me re-read the handler more carefully.
# Let me just look at what VRAM address is being targeted.
# 
# The VDP auto-increment is set by R15 = 0x02 (increment by 2 each write).
# The command 0x40000010 sets up a VRAM write at address 0x0000.
# This writes the color/tile data to VRAM address 0, which is tile data area.
# That doesn't make sense for hscroll.
#
# UNLESS the handler doesn't write hscroll at all!
# Maybe the HInt handler updates CRAM (colors) instead, for color cycling effects.
# Or maybe the VDP command is different.
#
# Let me re-parse: 23FC writes a LONG to an address.
# 23FC 40000010 00C00004 means:
# MOVE.L #$40000010, ($C00004).L
# This is writing 0x40000010 to VDP control port ($C00004)
#
# But VDP control writes are 16-bit. A 32-bit write to the control port
# is treated as TWO 16-bit writes: first 0x4000, then 0x0010.
# This is the standard two-write sequence to set up access.

# Actually wait - when the 68K does a MOVE.L to the VDP control port,
# it writes the high word first, then the low word.
# So it's: write16($C00004, 0x4000); write16($C00004, 0x0010)
# This means:
# 1st control write: 0x4000 - this is captured as pending command
# 2nd control write: 0x0010 - completes the full address/code setup
# Result: VRAM write at address 0x0000 
#
# Hmm. Let me check another possibility. Maybe 0xFF013A is 0 (the flag), 
# so the handler actually jumps to 0x0706 (the BEQ branch).
# In that case, the "main" hscroll write path is skipped.

# Let me read the flag byte from RAM
flag = api_get("/cpu/memory?addr=16711994&len=1")  # 0xFF013A = 16711994
print(f"RAM $FF013A = {flag['data'][0]}")

# And let me read the branch target at 0x0706
code2 = api_get(f"/cpu/memory?addr=0x0706&len=128")["data"]
print(f"\nCode at 0x0706:")
print(f"Bytes: {' '.join(f'{b:02X}' for b in code2[:64])}")

# Also read the handler's other path
# After the BEQ, what does the "skip" path do?
# 0x6B6: 6700 004E -> BEQ.W to 0x6B6+4+0x4E = 0x706
# At 0x706, the handler continues...

# Let me also step to title screen and check the flag
api_post("/emulator/step", {"frames": 900})
flag2 = api_get("/cpu/memory?addr=16711994&len=8")
print(f"\nAt title screen:")
print(f"RAM $FF013A = {flag2['data'][0]}")
for i in range(8):
    print(f"  $FF{0x013A+i:04X} = 0x{flag2['data'][i]:02X} ({flag2['data'][i]})")
