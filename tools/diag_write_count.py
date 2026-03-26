#!/usr/bin/env python3
"""Diagnostic: Check Z80 M68K write counter after each frame."""
import json
import urllib.request
import sys

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

# 1. Load ROM
rom_path = "roms/puyo.bin"
with open(rom_path, "rb") as f:
    rom_data = list(f.read())
print(f"ROM size: {len(rom_data)} bytes ({len(rom_data):#x})")
print(f"ROM[0x7E020:0x7E030] = {[f'{b:02X}' for b in rom_data[0x7E020:0x7E030]]}")

import os
abs_path = os.path.abspath(rom_path)
api("POST", "/api/v1/emulator/load-rom-path", {"path": abs_path})
print("ROM loaded")

# 2. Check Z80 RAM before any frames
z80 = get_memory(0xA00020, 16)
print(f"Before frames: Z80 RAM[0x20:0x30] = {[f'{b:02X}' for b in z80['data']]}")

# 3. Run frames one at a time, checking Z80 RAM after each
for frame in range(1, 11):
    api("POST", "/api/v1/emulator/step", {"frames": 1})
    z80 = get_memory(0xA00020, 16)
    print(f"Frame {frame:2d}: Z80 RAM[0x20:0x30] = {[f'{b:02X}' for b in z80['data']]}")

# 4. Also check the very beginning of Z80 RAM (first 16 bytes)
z80_start = get_memory(0xA00000, 16)
print(f"Z80 RAM[0x00:0x10] = {[f'{b:02X}' for b in z80_start['data']]}")

# Compare with ROM
print(f"ROM [0x7E000:0x7E010] = {[f'{b:02X}' for b in rom_data[0x7E000:0x7E010]]}")

print("\nDone. Check server stderr for [FRAME] z80_m68k_write_count logs.")

# 5. Verify ROM consistency: check actual ROM bytes at copy loop and Z80 binary addresses
print("\n=== ROM verification ===")
rom_at_copy = get_memory(0x007252, 24)  # copy code
print(f"ROM @ $7252 (copy code): {[f'{b:02X}' for b in rom_at_copy['data']]}")

# Verify GEMS source bytes vs what the copy loop should write 
for offset in [0x000, 0x004, 0x010, 0x400, 0x800, 0xC00, 0x1000, 0x1F00]:
    rom_val = rom_data[0x7E000 + offset]
    z80_mem = get_memory(0xA00000 + offset, 1)
    z80_val = z80_mem['data'][0]
    match = "OK" if rom_val == z80_val else "MISMATCH"
    print(f"  Offset {offset:#06x}: ROM[{0x7E000+offset:#06x}]={rom_val:02X}, Z80[{offset:#06x}]={z80_val:02X} {match}")

# 6. Check M68K CPU state and trace ring
cpu = api("GET", "/api/v1/cpu/state")
cpu_data = cpu.get('cpu', {})
d = cpu_data.get('d', [0]*8)
a = cpu_data.get('a', [0]*8)
pc = cpu_data.get('pc', 0)
print(f"\nM68K state: PC={pc:#010x}")
print(f"  D: {[f'{v:#010x}' for v in d]}")
print(f"  A: {[f'{v:#010x}' for v in a]}")

trace = api("GET", "/api/v1/cpu/trace")
ring = trace.get('trace_ring', [])
if ring:
    print(f"\nLast 10 M68K instructions (of {len(ring)} in ring):")
    for t in ring[-10:]:
        print(f"  PC={t['pc']:#08x} op={t['opcode']:#06x} cyc={t['cycles']} {t['mnemonic']}")
