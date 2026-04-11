#!/usr/bin/env python3
"""Detailed analysis of dispatch $8BBC function and its call sites."""

ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

rom_len = len(rom)

# Corrected dispatch jump table
print("=== Dispatch $8BBC internal jump table (corrected) ===")
# Table base at $8C04 (after MOVE.W (6,PC,D0.W),D0 and JMP (2,PC,D0.W))
table_base = 0x8C04
for step in range(6):
    off_addr = table_base + step * 2
    off_val = (rom[off_addr] << 8) | rom[off_addr + 1]
    target = table_base + off_val
    print(f"  Step {step}: table[{step}]=${off_val:04X} -> handler at ${target:06X}")

# Read dispatch function fully: $8BBC-$8CA0
print("\n=== Full dispatch function $8BBC-$8CA0 ===")
for a in range(0x8BBC, min(0x8CA0, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Read the step handlers
handlers = {
    0: 0x8C92,
    1: 0x8C2A,
    2: 0x8C6C,
    3: 0x8C40,
    4: 0x8C56,
    5: 0x8C10,
}

for step, addr in sorted(handlers.items()):
    print(f"\n=== Step {step} handler at ${addr:06X} ===")
    end = min(addr + 48, rom_len)
    for a in range(addr, end, 16):
        h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
        print(f"  ${a:06X}: {h}")

# Special branches: when current_step == 4 ($8C8A) or current_step == 5 ($8C82)
print("\n=== Special case: current_step==5 -> $8C82 ===")
for a in range(0x8C82, min(0x8C92, rom_len), 2):
    h = '%02X %02X' % (rom[a], rom[a + 1])
    w = (rom[a] << 8) | rom[a + 1]
    extra = ''
    if rom[a] == 0x4E and rom[a + 1] == 0xBA:
        d16 = (rom[a + 2] << 8) | rom[a + 3]
        if d16 >= 0x8000:
            d16 -= 0x10000
        dest = (a + 2) + d16
        extra = f'  ; JSR ${dest:06X}'
    elif w == 0x4E75:
        extra = '  ; RTS'
    print(f"  ${a:06X}: {h}{extra}")

print("\n=== Special case: current_step==4 -> $8C8A ===")
for a in range(0x8C8A, min(0x8C9A, rom_len), 2):
    h = '%02X %02X' % (rom[a], rom[a + 1])
    w = (rom[a] << 8) | rom[a + 1]
    extra = ''
    if rom[a] == 0x4E and rom[a + 1] == 0xBA:
        d16 = (rom[a + 2] << 8) | rom[a + 3]
        if d16 >= 0x8000:
            d16 -= 0x10000
        dest = (a + 2) + d16
        extra = f'  ; JSR ${dest:06X}'
    elif w == 0x4E75:
        extra = '  ; RTS'
    elif w == 0x6000 or (rom[a] == 0x60 and rom[a+1] != 0x00):
        if rom[a+1] == 0x00:
            d16 = (rom[a + 2] << 8) | rom[a + 3]
            if d16 >= 0x8000:
                d16 -= 0x10000
            dest = (a + 2) + d16
            extra = f'  ; BRA.W ${dest:06X}'
        else:
            disp = rom[a+1] if rom[a+1] < 0x80 else rom[a+1] - 0x100
            dest = a + 2 + disp
            extra = f'  ; BRA.B ${dest:06X}'
    print(f"  ${a:06X}: {h}{extra}")

# Read all 6 call sites with context to understand who calls them
print("\n=== Call site 1: $8CFC (dispatch(0,0)) ===")
print("  Context before (what function is this in?):")
for a in range(0x8CD0, 0x8D10, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

print("\n=== Call site 2: $8D0C (dispatch(5,1)) ===")
print("  What happens AFTER dispatch(5,1) returns:")
for a in range(0x8D10, 0x8D40, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

print("\n=== Call site 3: $8D92 (dispatch(5,1)) ===")
print("  Context:")
for a in range(0x8D70, 0x8DA0, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

print("\n=== Call site 4: $8E22 (inside $8DFC, dispatch(5,1)) ===")
print("  Already shown above")

print("\n=== Call site 5: $B386 (dispatch(5,1)) ===")
for a in range(0xB360, 0xB3B0, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

print("\n=== Call site 6: $CE44 (dispatch(5,1)) ===")
for a in range(0xCE20, 0xCE70, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Does any code write step 4 to $FF01A0?
print("\n=== Search for writes of value 4 to $FF01A0 ===")
# MOVE.W #4, ($FF01A0) = 33FC 0004 E0FF 01A0
pat4 = bytes([0x33, 0xFC, 0x00, 0x04, 0xE0, 0xFF, 0x01, 0xA0])
offset = 0
while True:
    idx = rom.find(pat4, offset)
    if idx == -1:
        break
    ctx = ' '.join('%02X' % rom[max(0,idx-4):min(rom_len,idx+12)])
    print(f"  MOVE.W #4,($FF01A0) @ ${idx:06X}")
    offset = idx + 1

# Also check MOVE.W D?,($FF01A0) = 33C? E0FF 01A0
for reg in range(8):
    pat = bytes([0x33, 0xC0 + reg, 0xE0, 0xFF, 0x01, 0xA0])
    offset = 0
    while True:
        idx = rom.find(pat, offset)
        if idx == -1:
            break
        ctx_start = max(0, idx - 8)
        ctx_end = min(rom_len, idx + 12)
        ctx = ' '.join('%02X' % rom[ctx_start + i] for i in range(ctx_end - ctx_start))
        print(f"  MOVE.W D{reg},($FF01A0) @ ${idx:06X}: {ctx}")
        offset = idx + 1

# Step 4 handler -> does it call $8292?
print("\n=== Step 4 handler code at $8C56 (detailed) ===")
for a in range(0x8C56, min(0x8C70, rom_len), 2):
    h = '%02X %02X' % (rom[a], rom[a + 1])
    w = (rom[a] << 8) | rom[a + 1]
    extra = ''
    if rom[a] == 0x4E and rom[a + 1] == 0xBA:
        d16 = (rom[a + 2] << 8) | rom[a + 3]
        if d16 >= 0x8000:
            d16 -= 0x10000
        dest = (a + 2) + d16
        extra = f'  ; JSR ${dest:06X}'
    elif rom[a] == 0x4E and rom[a + 1] == 0xB9:
        dest = (rom[a+2]<<24)|(rom[a+3]<<16)|(rom[a+4]<<8)|rom[a+5]
        extra = f'  ; JSR ${dest:06X}'
    elif w == 0x4E75:
        extra = '  ; RTS'
    print(f"  ${a:06X}: {h}{extra}")
