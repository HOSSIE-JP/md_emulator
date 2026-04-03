#!/usr/bin/env python3
"""Analyze the ONLY location that writes R1=0x54 (VINT OFF)."""
import requests

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})

# Read code around $E20D (R1=0x54 write)
print('=== Code around $E20D (R1=0x54 VINT OFF write) ===')
for base in range(0xE180, 0xE280, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))
    print()

# Also check R1=0x74 write at $E0CC
print('=== Code around $E0CC (R1=0x74 VINT ON write) ===')
for base in range(0xE080, 0xE100, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# And R1=0x74 write at $B563 (the other location)
print('\n=== Code around $B563 (R1=0x74 VINT ON write) ===')
for base in range(0xB540, 0xB5A0, 64):
    mem = requests.get(BASE + '/cpu/memory', params={'addr': base, 'len': 64}).json()
    data = mem['data']
    for i in range(0, len(data), 16):
        addr = base + i
        hexs = ' '.join('%02X' % b for b in data[i:i+16])
        print('$%06X: %s' % (addr, hexs))

# Now check: is $E20D inside a recognizable function? Look for RTS before it
print('\n=== Searching for function boundary before $E20D ===')
mem = requests.get(BASE + '/cpu/memory', params={'addr': 0xE100, 'len': 0x120}).json()
data = mem['data']
for i in range(len(data) - 1):
    w = (data[i] << 8) | data[i+1]
    addr = 0xE100 + i
    if w == 0x4E75:
        print('  RTS at $%06X' % addr)
    elif w == 0x4E73:
        print('  RTE at $%06X' % addr)

# Try to understand: who calls the function containing $E20D?
# Search for JSR to nearby addresses
print('\n=== Searching for references to $E1xx-$E2xx ===')
rom = requests.get(BASE + '/cpu/memory', params={'addr': 0, 'len': 0x40000}).json()
rom_data = rom['data']

# Search for JSR $00E1xx or $00E0xx patterns (4EB9 00 00 E0/E1 xx)
for prefix in [0xE0, 0xE1, 0xE2]:
    for i in range(len(rom_data) - 5):
        if (rom_data[i] == 0x4E and rom_data[i+1] == 0xB9 and 
            rom_data[i+2] == 0x00 and rom_data[i+3] == 0x00 and 
            rom_data[i+4] == prefix):
            target = (rom_data[i+2]<<24) | (rom_data[i+3]<<16) | (rom_data[i+4]<<8) | rom_data[i+5]
            addr = i
            print('  $%06X: JSR $%06X' % (addr, target))

# Also search for BSR relative calls targeting $E200 area from nearby code
# BSR.W at $E1xx or $E0xx that targets $E200+
print('\n=== Checking $E0CC and $E20D context ===')
# The scene controller at $1C2E calls ($FF005E) which is RTS
# After full VBLANK handler, it returns to main loop via RTE
# The R1 write at $E20D must be called from the scene transition code

# Check: is $E20D called indirectly via function pointer?
# Search for the address $E20D or nearby in RAM 
requests.post(BASE + '/emulator/step', json={'frames': 130})
for name, addr_check in [
    ('$FF005A (func_ptr_2)', 0xFF005A),
    ('$FF005E (func_ptr)', 0xFF005E),
    ('$FF0306 (func_ptr_3)', 0xFF0306),
    ('$FFA86C', 0xFFA86C),
]:
    mem = requests.get(BASE + '/cpu/memory', params={'addr': addr_check, 'len': 4}).json()
    v = int.from_bytes(mem['data'], 'big')
    print('  %s = $%08X' % (name, v))
