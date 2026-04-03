#!/usr/bin/env python3
"""Check M68K state and Z80 reset issue."""
import requests, json, sys

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Load ROM and run a few frames
api("post", "/emulator/load-rom-path", json={"path": "roms/s_a_t_d.smd"})
api("post", "/emulator/step", json={"frames": 5})

# Get M68K state
cpu = api("get", "/cpu/state")
m68k_data = cpu.get("cpu", {}).get("cpu", {}).get("m68k", {})
print("=== M68K State ===")
for k in ["pc", "sr", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7",
          "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "ssp", "usp"]:
    v = m68k_data.get(k, 0)
    if isinstance(v, int):
        print(f"  {k}: 0x{v:08X}")

# Read ROM entry point
entry_mem = api("get", "/cpu/memory?address=0x000004&length=4")
entry_data = entry_mem.get("data", [])
entry_pc = (entry_data[0] << 24) | (entry_data[1] << 16) | (entry_data[2] << 8) | entry_data[3]
print(f"\nROM entry point: 0x{entry_pc:08X}")

# VBlank vector
vbl_mem = api("get", "/cpu/memory?address=0x000078&length=4")
vbl_data = vbl_mem.get("data", [])
vbl_addr = (vbl_data[0] << 24) | (vbl_data[1] << 16) | (vbl_data[2] << 8) | vbl_data[3]
print(f"VBlank vector: 0x{vbl_addr:08X}")

# Read ROM around PC
pc = m68k_data.get("pc", 0)
start = max(0, (pc & ~0xF) - 0x20)
mem = api("get", f"/cpu/memory?address={start}&length=128")
data = mem.get("data", [])
print(f"\n=== ROM around PC=0x{pc:06X} ===")
for i in range(0, len(data), 16):
    addr = start + i
    hexstr = " ".join(f"{b:02X}" for b in data[i:i+16])
    marker = " <-- PC" if addr <= pc < addr + 16 else ""
    print(f"  ${addr:06X}: {hexstr}{marker}")

# M68K trace ring
trace = cpu.get("cpu", {}).get("m68k_trace_ring", [])
print(f"\n=== M68K Trace Ring (last 30 entries) ===")
for entry in trace[-30:]:
    epc = entry.get("pc", 0)
    mn = entry.get("mnemonic", "")
    ops = entry.get("operands", "")
    print(f"  ${epc:06X}: {mn:<12s} {ops}")

# Step more frames
api("post", "/emulator/step", json={"frames": 195})
cpu2 = api("get", "/cpu/state")
m68k2 = cpu2.get("cpu", {}).get("cpu", {}).get("m68k", {})
pc2 = m68k2.get("pc", 0)
sr2 = m68k2.get("sr", 0)
print(f"\n=== After 200 total frames ===")
print(f"  PC = 0x{pc2:06X}, SR = 0x{sr2:04X}")

# Check Z80 write count
apu = api("get", "/apu/state")
print(f"  Z80 reset = {apu.get('z80_reset')}")
print(f"  Z80 bus req = {apu.get('z80_bus_requested')}")
print(f"  Z80 m68k writes = {apu.get('z80_m68k_write_count', 'N/A')}")

# Search ROM for writes to $A11200 pattern (move.w #xxxx, $A11200)
# Pattern: 33FC xxxx 00A1 1200
print(f"\n=== Searching ROM for $A11200 write patterns ===")
rom_mem = api("get", f"/cpu/memory?address=0x000000&length=4096")
rom = rom_mem.get("data", [])
for i in range(len(rom) - 7):
    # MOVE.W #imm, (abs).L = 33FC xxxx addr_hi addr_lo
    if rom[i] == 0x33 and rom[i+1] == 0xFC:
        # Check if destination is $00A11200
        if (i + 8 <= len(rom) and
            rom[i+4] == 0x00 and rom[i+5] == 0xA1 and
            rom[i+6] == 0x12 and rom[i+7] == 0x00):
            imm = (rom[i+2] << 8) | rom[i+3]
            print(f"  ${i:06X}: MOVE.W #${imm:04X}, ($A11200).L")
    # MOVE.W #imm, (abs).W with address encoding in next 2 bytes
    # Also check for short absolute
