#!/usr/bin/env python3
"""Load ROM, run 1000 frames, then search ROM for VDP reg1 patterns."""
import requests
import sys

BASE = "http://localhost:8080/api/v1"

# Load ROM and run 1000 frames first
rom_path = "frontend/roms/北へPM 鮎.bin"
print(f"Loading ROM: {rom_path}")
requests.post(f"{BASE}/emulator/load-rom-path", json={"path": rom_path}, timeout=10)

for batch in [200, 300, 500]:
    print(f"  stepping {batch}...")
    requests.post(f"{BASE}/emulator/step", json={"frames": batch}, timeout=300)

# Now check VDP state
r = requests.get(f"{BASE}/vdp/registers", timeout=10)
regs = r.json().get("registers", [])
print(f"\nVDP Reg1: 0x{regs[1]:02X} (VINT={bool(regs[1]&0x20)}, DISP={bool(regs[1]&0x40)}, DMA={bool(regs[1]&0x10)})")

# Get CPU state
r2 = requests.get(f"{BASE}/cpu/state", timeout=10)
cpu = r2.json()["cpu"]["m68k"]
print(f"M68K PC: 0x{cpu['pc']:06X} SR: 0x{cpu['sr']:04X} stopped={cpu['stopped']}")

# Read first 64KB of ROM
rom_r = requests.get(f"{BASE}/cpu/memory", params={"address": "0", "length": "65536"}, timeout=30)
rom = bytes(rom_r.json().get("data", []))

# Entry point
ep = (rom[4]<<24)|(rom[5]<<16)|(rom[6]<<8)|rom[7]
print(f"Entry point: 0x{ep:08X}")

# Search for all VDP reg1 writes (0x81xx where xx varies)
reg1_writes = {}
for i in range(0, len(rom)-1, 2):
    w = (rom[i]<<8)|rom[i+1]
    if (w & 0xFF00) == 0x8100:
        val = w & 0xFF
        if val not in reg1_writes:
            reg1_writes[val] = []
        reg1_writes[val].append(i)

print(f"\nAll VDP reg1 write values found in ROM:")
for val in sorted(reg1_writes.keys()):
    positions = reg1_writes[val]
    vint = "VINT" if val & 0x20 else "    "
    disp = "DISP" if val & 0x40 else "    "
    print(f"  0x81{val:02X} (0x{val:02X} {vint} {disp}): {len(positions)} occurrences at {[hex(p) for p in positions[:10]]}")

# Check what the M68K is doing - read code around current PC
r3 = requests.get(f"{BASE}/cpu/memory", params={"address": str(cpu["pc"]), "length": "64"}, timeout=10)
code = r3.json().get("data", [])
code_hex = " ".join(f"{code[j]:02X}" for j in range(min(32, len(code))))
print(f"\nCode at PC 0x{cpu['pc']:06X}: {code_hex}")

# Check APU brief state
r4 = requests.get(f"{BASE}/apu/state", timeout=10)
apu = r4.json()
print(f"\nAPU: VINT delivered={apu.get('vint_delivered')} vdp_frame={apu.get('vdp_frame')}")
print(f"     ym_write_total={apu.get('ym_write_total')} dac_enabled={apu.get('dac_enabled')}")
