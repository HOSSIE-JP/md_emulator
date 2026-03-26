#!/usr/bin/env python3
"""Diagnostic: Investigate the Z80 copy loop source address mismatch."""
import json
import urllib.request
import os

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

# Load ROM
rom_path = "roms/puyo.bin"
with open(rom_path, "rb") as f:
    rom_data = f.read()

print(f"ROM size: {len(rom_data)} bytes")

# Compare ROM data at the two source addresses
print("\n=== ROM $076C00 (actual source used by copy loop) ===")
print(f"Bytes 0-15: {[f'{rom_data[0x076C00+i]:02X}' for i in range(16)]}")
print(f"Bytes 16-31: {[f'{rom_data[0x076C00+i]:02X}' for i in range(16, 32)]}")

print("\n=== ROM $07E000 (expected GEMS binary) ===")
print(f"Bytes 0-15: {[f'{rom_data[0x07E000+i]:02X}' for i in range(16)]}")
print(f"Bytes 16-31: {[f'{rom_data[0x07E000+i]:02X}' for i in range(16, 32)]}")

# Check non-zero regions in $076C00 data
nonzero_count = 0
for i in range(0x2000):
    if rom_data[0x076C00 + i] != 0:
        nonzero_count += 1
print(f"\nROM $076C00: {nonzero_count}/{0x2000} non-zero bytes")

nonzero_count2 = 0
for i in range(0x2000):
    if rom_data[0x07E000 + i] != 0:
        nonzero_count2 += 1
print(f"ROM $07E000: {nonzero_count2}/{0x2000} non-zero bytes")

# Check if they're the same data
same = rom_data[0x076C00:0x076C00+0x2000] == rom_data[0x07E000:0x07E000+0x2000]
print(f"Same data? {same}")

# Check the M68K code at $71B0-$71D0 (around the copy loop at $71C0)
print("\n=== M68K code around $71B0 (before copy loop) ===")
for addr in range(0x71A0, 0x71D0, 2):
    hi = rom_data[addr]
    lo = rom_data[addr + 1]
    word = (hi << 8) | lo
    print(f"  ${addr:06X}: {word:04X}", end="")
    if word == 0x12D8:
        print("  <-- MOVE.B (A0)+,(A1)+", end="")
    elif word == 0x41F9:
        long_val = (rom_data[addr+2] << 24) | (rom_data[addr+3] << 16) | (rom_data[addr+4] << 8) | rom_data[addr+5]
        print(f"  <-- LEA ${long_val:08X},A0", end="")
    elif word == 0x43F9:
        long_val = (rom_data[addr+2] << 24) | (rom_data[addr+3] << 16) | (rom_data[addr+4] << 8) | rom_data[addr+5]
        print(f"  <-- LEA ${long_val:08X},A1", end="")
    elif (word & 0xFFF8) == 0x51C8:
        disp = (rom_data[addr+2] << 8) | rom_data[addr+3]
        if disp > 0x7FFF:
            disp -= 0x10000
        print(f"  <-- DBRA D{word & 7},${addr+2+disp:06X}", end="")
    elif word == 0x303C:
        imm = (rom_data[addr+2] << 8) | rom_data[addr+3]
        print(f"  <-- MOVE.W #${imm:04X},D0", end="")
    print()

# Also check the code at $7252 (the OTHER copy loop)
print("\n=== M68K code at $7252 (other copy loop) ===")
for addr in range(0x7248, 0x7270, 2):
    hi = rom_data[addr]
    lo = rom_data[addr + 1]
    word = (hi << 8) | lo
    print(f"  ${addr:06X}: {word:04X}", end="")
    if word == 0x12D8:
        print("  <-- MOVE.B (A0)+,(A1)+", end="")
    elif word == 0x41F9:
        long_val = (rom_data[addr+2] << 24) | (rom_data[addr+3] << 16) | (rom_data[addr+4] << 8) | rom_data[addr+5]
        print(f"  <-- LEA ${long_val:08X},A0", end="")
    elif word == 0x43F9:
        long_val = (rom_data[addr+2] << 24) | (rom_data[addr+3] << 16) | (rom_data[addr+4] << 8) | rom_data[addr+5]
        print(f"  <-- LEA ${long_val:08X},A1", end="")
    elif (word & 0xFFF8) == 0x51C8:
        disp = (rom_data[addr+2] << 8) | rom_data[addr+3]
        if disp > 0x7FFF:
            disp -= 0x10000
        print(f"  <-- DBRA D{word & 7},${addr+2+disp:06X}", end="")
    elif word == 0x303C:
        imm = (rom_data[addr+2] << 8) | rom_data[addr+3]
        print(f"  <-- MOVE.W #${imm:04X},D0", end="")
    print()

# Check Z80 RAM at offset $114A (where the Z80 jumps to)
print("\n=== Z80 RAM around entry point $114A ===")
z80_data = get_memory(0xA00000 + 0x114A, 32)
print(f"Z80 RAM[$114A:$116A] = {[f'{b:02X}' for b in z80_data['data']]}")

# And the ROM equivalent for that offset
print(f"ROM[$076C00+$114A=$077D4A:] = {[f'{rom_data[0x077D4A+i]:02X}' for i in range(32)]}")
print(f"ROM[$07E000+$114A=$07F14A:] = {[f'{rom_data[0x07F14A+i]:02X}' for i in range(32)]}")
