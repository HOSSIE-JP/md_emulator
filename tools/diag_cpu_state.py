#!/usr/bin/env python3
"""Check M68K CPU state and VDP registers for interrupt delivery issues."""
import requests
import json

BASE = "http://localhost:8080/api/v1"

r = requests.get(f"{BASE}/cpu/state", timeout=10)
cpu = r.json()
m = cpu.get("m68k", {})
print("M68K PC:", hex(m.get("pc", 0)))
print("M68K SP:", hex(m.get("a", [0]*8)[7]))
print("M68K SR:", hex(m.get("sr", 0)))
ipl = (m.get("sr", 0) >> 8) & 7
print(f"M68K SR IPL mask: {ipl}")
print("M68K pending_ipl:", m.get("pending_ipl", 0))
print("M68K D regs:", [hex(x) for x in m.get("d", [])])
print("M68K A regs:", [hex(x) for x in m.get("a", [])])
print("Z80 PC:", hex(cpu.get("z80_pc", 0)))

r2 = requests.get(f"{BASE}/vdp/registers", timeout=10)
vdp_regs = r2.json()
regs = vdp_regs.get("registers", [])
if len(regs) > 1:
    print(f"VDP Reg1: 0x{regs[1]:02X} (VINT enable: {bool(regs[1] & 0x20)}, display enable: {bool(regs[1] & 0x40)})")
if len(regs) > 0:
    print(f"VDP Reg0: 0x{regs[0]:02X} (HINT enable: {bool(regs[0] & 0x10)})")

r3 = requests.get(f"{BASE}/cpu/trace", timeout=10)
traces = r3.json()
if traces:
    n = min(30, len(traces))
    print(f"\nLast {n} M68K traces:")
    for t in traces[-n:]:
        print(f"  PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t['mnemonic']} cycles={t['cycles']}")
else:
    print("No M68K traces available")

# Also check memory at VINT vector (0x78) and key addresses
r4 = requests.get(f"{BASE}/cpu/memory", params={"address": "0x78", "length": "4"}, timeout=10)
mem = r4.json()
vint_vec = mem.get("data", [0,0,0,0])
vint_addr = (vint_vec[0] << 24) | (vint_vec[1] << 16) | (vint_vec[2] << 8) | vint_vec[3]
print(f"\nVINT vector (0x78): 0x{vint_addr:08X}")

r5 = requests.get(f"{BASE}/cpu/memory", params={"address": "0x70", "length": "4"}, timeout=10)
mem5 = r5.json()
hint_vec = mem5.get("data", [0,0,0,0])
hint_addr = (hint_vec[0] << 24) | (hint_vec[1] << 16) | (hint_vec[2] << 8) | hint_vec[3]
print(f"HINT vector (0x70): 0x{hint_addr:08X}")
