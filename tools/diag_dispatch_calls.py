#!/usr/bin/env python3
"""Search ROM for all references to dispatch function at $8BBC."""
import struct

ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

rom_len = len(rom)
print(f"ROM size: {rom_len} bytes (0x{rom_len:06X})")

# --- Task 1: JSR $8BBC (4EB9 00008BBC) ---
print("\n=== JSR $8BBC (4E B9 00 00 8B BC) ===")
pattern_jsr = bytes([0x4E, 0xB9, 0x00, 0x00, 0x8B, 0xBC])
offset = 0
jsr_sites = []
while True:
    idx = rom.find(pattern_jsr, offset)
    if idx == -1:
        break
    jsr_sites.append(idx)
    start = max(0, idx - 12)
    end = min(rom_len, idx + 18)
    ctx = ' '.join('%02X' % rom[start + i] for i in range(end - start))
    print(f"  ${idx:06X}: {ctx}")
    # Show 16 bytes before for stack setup (arguments)
    pre_start = max(0, idx - 24)
    pre = ' '.join('%02X' % rom[pre_start + i] for i in range(idx - pre_start))
    print(f"    args setup (${pre_start:06X}-${idx-1:06X}): {pre}")
    offset = idx + 1

print(f"\n  Total JSR $8BBC calls: {len(jsr_sites)}")

# --- BSR to $8BBC ---
print("\n=== BSR to $8BBC ===")
bsr_sites = []
for addr in range(0, min(rom_len, 0x100000), 2):
    if rom[addr] != 0x61:
        continue
    b = rom[addr + 1]
    if b == 0x00:
        # BSR.W
        if addr + 3 < rom_len:
            disp = (rom[addr + 2] << 8) | rom[addr + 3]
            if disp >= 0x8000:
                disp -= 0x10000
            target = addr + 2 + disp
            if target == 0x8BBC:
                bsr_sites.append(addr)
                start = max(0, addr - 8)
                end = min(rom_len, addr + 12)
                ctx = ' '.join('%02X' % rom[start + i] for i in range(end - start))
                print(f"  BSR.W @ ${addr:06X} -> ${target:06X}: {ctx}")
    elif b != 0xFF:
        disp = b if b < 0x80 else b - 0x100
        target = addr + 2 + disp
        if target == 0x8BBC:
            bsr_sites.append(addr)
            start = max(0, addr - 8)
            end = min(rom_len, addr + 12)
            ctx = ' '.join('%02X' % rom[start + i] for i in range(end - start))
            print(f"  BSR.B @ ${addr:06X} -> ${target:06X}: {ctx}")

print(f"  Total BSR $8BBC calls: {len(bsr_sites)}")

# --- Task 2: Read $B600-$B700 (script engine) ---
print("\n=== Script engine $B600-$B700 ===")
for a in range(0xB600, min(0xB700, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# --- Task 2b: Read $B700-$B800 ---
print("\n=== Script engine $B700-$B800 ===")
for a in range(0xB700, min(0xB800, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# --- Task 3: Read $8DFC-$8E7C ---
print("\n=== $8DFC-$8E7C (called from script engine) ===")
for a in range(0x8DFC, min(0x8E7C, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# --- Task 4: Does $8DFC reference $8BBC? ---
print("\n=== Searching $8D00-$8F00 for $8BBC references ===")
region = rom[0x8D00:0x8F00]
pat = bytes([0x00, 0x00, 0x8B, 0xBC])
off = 0
while True:
    idx = region.find(pat, off)
    if idx == -1:
        break
    abs_addr = 0x8D00 + idx
    start = max(0, idx - 4)
    end = min(len(region), idx + 8)
    ctx = ' '.join('%02X' % region[start + i] for i in range(end - start))
    print(f"  ${abs_addr:06X}: {ctx}")
    off = idx + 1

# Also check for BSR from $8DFC region to $8BBC
for addr in range(0x8D00, 0x8F00, 2):
    if rom[addr] == 0x61:
        b = rom[addr + 1]
        if b == 0x00 and addr + 3 < rom_len:
            disp = (rom[addr + 2] << 8) | rom[addr + 3]
            if disp >= 0x8000:
                disp -= 0x10000
            target = addr + 2 + disp
            if target == 0x8BBC:
                print(f"  BSR.W from ${addr:06X} -> $8BBC")
        elif b != 0x00 and b != 0xFF:
            disp = b if b < 0x80 else b - 0x100
            target = addr + 2 + disp
            if target == 0x8BBC:
                print(f"  BSR.B from ${addr:06X} -> $8BBC")

# --- Task 5: What happens after dispatch calls return ---
# Show code after each JSR $8BBC site
print("\n=== Code AFTER each JSR $8BBC (return continuation) ===")
for site in jsr_sites:
    after = site + 6  # JSR abs.L is 6 bytes
    end = min(rom_len, after + 32)
    h = ' '.join('%02X' % rom[after + i] for i in range(end - after))
    print(f"  After ${site:06X} (continues at ${after:06X}): {h}")

# --- Read dispatch function itself $8BBC-$8C40 ---
print("\n=== Dispatch function $8BBC-$8C40 ===")
for a in range(0x8BBC, min(0x8C40, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# --- Also check $8200-$82A0 area (handler 4 at $8292) ---
print("\n=== Handler area $8250-$82D0 ===")
for a in range(0x8250, min(0x82D0, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")
