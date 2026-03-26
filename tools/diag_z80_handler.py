#!/usr/bin/env python3
"""Diagnostic: Read and analyze Z80 handler code + M68K VBlank handler."""
import json
import urllib.request
import os
import struct

BASE = "http://127.0.0.1:8088"

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_memory(addr, length):
    return api("GET", f"/api/v1/cpu/memory?addr={addr}&len={length}")

# Load ROM file
with open("roms/puyo.bin", "rb") as f:
    rom = f.read()

# 1. Read Z80 RAM around main loop and handler addresses
print("=== Z80 Main Loop ($116F-$1190) ===")
z80_loop = get_memory(0xA0116F, 48)['data']
for i in range(0, len(z80_loop), 16):
    addr = 0x116F + i
    hex_str = ' '.join(f'{b:02X}' for b in z80_loop[i:i+16])
    print(f"  ${addr:04X}: {hex_str}")

print("\n=== Z80 Handler $1197 (cmd 1/2) ===")
z80_h1 = get_memory(0xA01197, 80)['data']
for i in range(0, len(z80_h1), 16):
    addr = 0x1197 + i
    hex_str = ' '.join(f'{b:02X}' for b in z80_h1[i:i+16])
    print(f"  ${addr:04X}: {hex_str}")

print("\n=== Z80 Handler $1226 (cmd 0/3) ===")
z80_h2 = get_memory(0xA01226, 96)['data']
for i in range(0, len(z80_h2), 16):
    addr = 0x1226 + i
    hex_str = ' '.join(f'{b:02X}' for b in z80_h2[i:i+16])
    print(f"  ${addr:04X}: {hex_str}")

# 2. Search ROM for references to $A00027
print("\n=== ROM references to $A00027 ===")
target = bytes([0x00, 0xA0, 0x00, 0x27])
for i in range(len(rom) - 4):
    if rom[i:i+4] == target:
        # Show surrounding context
        ctx_start = max(0, i-4)
        ctx = rom[ctx_start:i+8]
        print(f"  ROM offset ${i:06X}: ...{' '.join(f'{b:02X}' for b in ctx)}...")

# Also search for the pattern with just $A00027 (might be split)
# Actually search for writes: MOVE.B to $A00027
# Pattern: 13FC xx00 00A0 0027 (MOVE.B #xx,$A00027.L)
# Or: 4239 00A0 0027 (CLR.B $A00027.L)  
print("\n=== Searching for CLR.B $A00027.L (4239 00A0 0027) ===")
clr_pattern = bytes([0x42, 0x39, 0x00, 0xA0, 0x00, 0x27])
for i in range(len(rom) - 6):
    if rom[i:i+6] == clr_pattern:
        print(f"  Found at ROM ${i:06X}")

print("\n=== Searching for MOVE.B #0,$A00027.L (13FC 0000 00A0 0027) ===")
mov_pattern = bytes([0x13, 0xFC, 0x00, 0x00, 0x00, 0xA0, 0x00, 0x27])
for i in range(len(rom) - 8):
    if rom[i:i+8] == mov_pattern:
        print(f"  Found at ROM ${i:06X}")

# 3. Find VBlank vector
vblank_addr = struct.unpack('>I', rom[0x78:0x7C])[0]
print(f"\n=== VBlank vector: ${vblank_addr:08X} ===")

# Read the VBlank handler
vblank_code = get_memory(vblank_addr, 64)['data']
print(f"VBlank handler code:")
for i in range(0, len(vblank_code), 16):
    addr = vblank_addr + i
    hex_str = ' '.join(f'{b:02X}' for b in vblank_code[i:i+16])
    print(f"  ${addr:06X}: {hex_str}")

# 4. Check the Z80 jump table at $118F
print("\n=== Z80 Jump Table at $118F ===")
z80_jt = get_memory(0xA0118F, 16)['data']
for i in range(0, len(z80_jt), 2):
    addr_val = z80_jt[i] | (z80_jt[i+1] << 8)  # Z80 is little-endian
    print(f"  Entry {i//2}: ${addr_val:04X}")
