#!/usr/bin/env python3
"""Search ROM for VDP register 1 write patterns and check M68K state."""
import requests

BASE = "http://localhost:8080/api/v1"

# Read entry point
r = requests.get(f"{BASE}/cpu/memory", params={"address": "0x4", "length": "4"}, timeout=10)
entry = r.json().get("data", [0,0,0,0])
ep = (entry[0]<<24) | (entry[1]<<16) | (entry[2]<<8) | entry[3]
print(f"Entry point: 0x{ep:08X}")

# Read first 64KB of ROM to search for VDP register patterns
rom_r = requests.get(f"{BASE}/cpu/memory", params={"address": "0", "length": "65536"}, timeout=30)
rom = bytes(rom_r.json().get("data", []))
print(f"ROM size for search: {len(rom)}")

# Search for VDP register 1 write patterns
pos8174 = []  # reg1=0x74 (VINT ON, display ON, DMA ON)
pos8154 = []  # reg1=0x54 (VINT OFF, display ON, DMA ON)
for i in range(0, len(rom)-1, 2):
    w = (rom[i] << 8) | rom[i+1]
    if w == 0x8174:
        pos8174.append(i)
    if w == 0x8154:
        pos8154.append(i)

print(f"\n0x8174 (reg1=0x74 VINT ON) found at: {[hex(p) for p in pos8174[:30]]}")
print(f"0x8154 (reg1=0x54 VINT OFF) found at: {[hex(p) for p in pos8154[:30]]}")

# Show context around 0x8174 occurrences
for pos in pos8174[:5]:
    start = max(0, pos - 8)
    end = min(len(rom), pos + 16)
    ctx = " ".join(f"{rom[j]:02X}" for j in range(start, end))
    print(f"  Context at 0x{pos:06X}: {ctx}")

# Check current M68K state
r3 = requests.get(f"{BASE}/cpu/state", timeout=10)
cpu = r3.json()["cpu"]["m68k"]
print(f"\nM68K PC: 0x{cpu['pc']:06X}")
print(f"M68K SR: 0x{cpu['sr']:04X} (IPL mask={(cpu['sr']>>8)&7})")
print(f"M68K D: {[hex(x) for x in cpu['d']]}")
print(f"M68K A: {[hex(x) for x in cpu['a']]}")
print(f"M68K stopped: {cpu['stopped']}")
print(f"M68K total_cycles: {cpu['total_cycles']}")

# Check code at current PC
r4 = requests.get(f"{BASE}/cpu/memory", params={"address": str(cpu["pc"]), "length": "32"}, timeout=10)
code = r4.json().get("data", [])
code_hex = " ".join(f"{b:02X}" for b in code[:32])
print(f"Code at PC: {code_hex}")

# Check M68K trace ring (last executed instructions)
r5 = requests.get(f"{BASE}/cpu/trace", timeout=10)
traces = r5.json()
if isinstance(traces, list):
    n = min(20, len(traces))
    print(f"\nLast {n} M68K traces:")
    for t in traces[-n:]:
        if isinstance(t, dict):
            print(f"  PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t['mnemonic']} cyc={t['cycles']}")
elif isinstance(traces, dict) and "traces" in traces:
    tlist = traces["traces"]
    n = min(20, len(tlist))
    print(f"\nLast {n} M68K traces:")
    for t in tlist[-n:]:
        if isinstance(t, dict):
            print(f"  PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t['mnemonic']} cyc={t['cycles']}")
else:
    print(f"Trace format: {type(traces)}, keys: {traces.keys() if isinstance(traces,dict) else 'N/A'}")
