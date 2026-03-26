#!/usr/bin/env python3
"""Dump raw YM2612 register state."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
for i in range(120):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print(f"ym_write_total: {apu.get('ym_write_total')}")
print(f"dac_enabled: {apu.get('dac_enabled')}")
print(f"regs_port0_key (0x28): 0x{apu.get('regs_port0_key', 0):02X}")
print(f"regs_port0_22 (LFO): 0x{apu.get('regs_port0_22', 0):02X}")
print(f"regs_port0_2a (DAC): 0x{apu.get('regs_port0_2a', 0):02X}")
print(f"regs_port0_2b (DAC en): 0x{apu.get('regs_port0_2b', 0):02X}")
print(f"\nFrequency regs port0 (0xA0-A6): {apu.get('regs_port0_freq')}")
print(f"Frequency regs port1 (0xA0-A6): {apu.get('regs_port1_freq')}")
print(f"Algorithm regs port0 (0xB0-B2): {apu.get('regs_port0_algo')}")
print(f"Algorithm regs port1 (0xB0-B2): {apu.get('regs_port1_algo')}")
print(f"Pan regs port0 (0xB4-B6): {apu.get('regs_port0_b4_b6')}")
print(f"Pan regs port1 (0xB4-B6): {apu.get('regs_port1_b4_b6')}")
print(f"TL regs port0 (0x40-4F): {apu.get('regs_port0_tl')}")
print(f"TL regs port1 (0x40-4F): {apu.get('regs_port1_tl')}")

# Check Z80 state
print(f"\nZ80 PC: 0x{apu.get('z80_pc', 0):04X}")
print(f"Z80 halted: {apu.get('z80_halted')}")
print(f"Z80 total_cycles: {apu.get('z80_total_cycles')}")
print(f"Z80 bus requested: {apu.get('z80_bus_requested')}")
print(f"Z80 reset: {apu.get('z80_reset')}")
print(f"YM write queue pending: {apu.get('ym_write_queue_len')}")
