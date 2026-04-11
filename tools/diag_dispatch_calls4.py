#!/usr/bin/env python3
"""Decode all step handler sub-functions to understand what each does."""

ROM_PATH = 'frontend/roms/北へPM 鮎.bin'

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

rom_len = len(rom)

# Each step handler calls a sub-function via JSR (PC-relative)
# Let me extract the target of each JSR
step_handlers = {
    5: (0x8C10, 0x8C16),  # JSR at $8C16
    1: (0x8C2A, 0x8C30),  # JSR at $8C30
    3: (0x8C40, 0x8C46),  # JSR at $8C46
    4: (0x8C56, 0x8C5E),  # JSR at $8C5E -> $8292
    2: (0x8C6C, 0x8C72),  # JSR at $8C72
    0: (0x8C92, 0x8C92),  # JSR at $8C92
}

print("=== Step handler sub-function targets ===")
for step in range(6):
    handler_start, jsr_addr = step_handlers[step]
    if rom[jsr_addr] == 0x4E and rom[jsr_addr + 1] == 0xBA:
        d16 = (rom[jsr_addr + 2] << 8) | rom[jsr_addr + 3]
        if d16 >= 0x8000:
            d16 -= 0x10000
        target = (jsr_addr + 2) + d16
        print(f"  Step {step}: handler at ${handler_start:06X}, JSR @ ${jsr_addr:06X} -> ${target:06X}")
    else:
        print(f"  Step {step}: handler at ${handler_start:06X}, opcode at ${jsr_addr:06X} = {rom[jsr_addr]:02X}{rom[jsr_addr+1]:02X}")

# Special case handlers
print("\n=== Special case: current_step==5, calls $4E9E ===")
for a in range(0x4E9E, min(0x4EE0, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

print("\n=== Special case: current_step==4, calls $4E86 ===")
for a in range(0x4E86, min(0x4EC0, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Main function containing dispatch(0,0) and dispatch(5,1)
# Let me find the start of the function at $8CFC
print("\n=== Function containing dispatch(0,0) at $8CFC ===")
# Look for MOVEM or LINK before $8CFC
# Check from $8C9C onward
for a in range(0x8C9C, 0x8D10, 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Read $6CEA - what does the common init function do?
print("\n=== $6CEA (common init, called by step 0 handler and before step transition) ===")
for a in range(0x6CEA, min(0x6D30, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Read $8538 - step 5 handler function
print("\n=== $8538 (step 5 sub-function) ===")
for a in range(0x8538, min(0x85A0, rom_len), 16):
    h = ' '.join('%02X' % rom[a + i] for i in range(min(16, rom_len - a)))
    print(f"  ${a:06X}: {h}")

# Find what CALLS the function at $8CFC
# The function seems to start around $8C9C
# Look for all JSR/BSR to $8C9C or nearby
print("\n=== Who calls the init function (around $8C9C-$8CFC)? ===")
# Search for JSR (PC-rel) to addresses $8C9C-$8D00
for func_target in [0x8C9C, 0x8CA0, 0x8CB0, 0x8CC0, 0x8CD0, 0x8CE0]:
    for addr in range(0, min(rom_len - 3, 0x100000), 2):
        if rom[addr] == 0x4E and rom[addr + 1] == 0xBA:
            d16 = (rom[addr + 2] << 8) | rom[addr + 3]
            if d16 >= 0x8000:
                d16 -= 0x10000
            dest = (addr + 2) + d16
            if dest == func_target:
                print(f"  JSR @ ${addr:06X} -> ${dest:06X}")

# Also search for JSR $8CD0 specifically (looks like function start based on MOVE.B #0 pattern)
for func_target in range(0x8C9C, 0x8D00, 2):
    found = False
    for addr in range(0, min(rom_len - 3, 0x100000), 2):
        if rom[addr] == 0x4E and rom[addr + 1] == 0xBA:
            d16 = (rom[addr + 2] << 8) | rom[addr + 3]
            if d16 >= 0x8000:
                d16 -= 0x10000
            dest = (addr + 2) + d16
            if dest == func_target:
                if not found:
                    found = True
                print(f"  JSR @ ${addr:06X} -> ${func_target:06X}")
