#!/usr/bin/env python3
"""Test: press Start button to advance game and check if music commands appear."""
import urllib.request, json, time

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

# Run some frames to let game init
for _ in range(120):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print(f"Before Start: frame={apu['vdp_frame']} ym_total={apu['ym_write_total']} z80_pc=0x{apu['z80_pc']:04X}")

# Get M68K state 
cpu = get("/cpu/state")
m68k = cpu.get("cpu", {}).get("m68k", {})
print(f"  M68K PC=0x{m68k['pc']:06X} SR=0x{m68k.get('sr',0):04X}")

# Read ROM at M68K PC to see what instruction is there
pc = m68k['pc']
mem = get(f"/cpu/memory?addr={pc}&len=16")
rom_bytes = mem.get("data", [])
hex_str = " ".join(f"{b:02X}" for b in rom_bytes[:16])
print(f"  Code at PC: {hex_str}")

# Now inject Start button press
# Controller_1, bit mapping: start=0x80 typically
post("/input/controller", {"player": 1, "buttons": {"start": True}})

# Run 10 frames with Start held
for _ in range(10):
    post("/emulator/step", {"frames": 1})

# Release Start
post("/input/controller", {"player": 1, "buttons": {}})

# Run 120 more frames
for _ in range(120):
    post("/emulator/step", {"frames": 1})

apu2 = get("/apu/state")
print(f"\nAfter Start press: frame={apu2['vdp_frame']} ym_total={apu2['ym_write_total']} z80_pc=0x{apu2['z80_pc']:04X}")

cpu2 = get("/cpu/state")
m68k2 = cpu2.get("cpu", {}).get("m68k", {})
print(f"  M68K PC=0x{m68k2['pc']:06X}")

# Check if new register types were written
h0 = apu2.get("ym_histogram_port0_nonzero", [])
h1 = apu2.get("ym_histogram_port1_nonzero", [])
print(f"\n  Port 0 histogram ({len(h0)} unique regs):")
for h in h0:
    print(f"    {h}")
print(f"  Port 1 histogram ({len(h1)} unique regs):")
for h in h1:
    print(f"    {h}")

# Check Z80 command area
mem_1f = get(f"/cpu/memory?addr={0xA01F00}&len=64")
data = mem_1f.get("data", [])
if len(data) >= 0x20 + 16:
    cmd = " ".join(f"{data[0x20+i]:02X}" for i in range(16))
    print(f"\n  Z80 RAM 0x1F20: {cmd}")
