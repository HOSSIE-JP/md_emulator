#!/usr/bin/env python3
"""Check GEMS binary in ROM and Z80 startup sequence."""
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

# Read GEMS binary from ROM at 0x7E000
# First 64 bytes
rom_gems = get(f"/cpu/memory?addr={0x7E000}&len=64")
data = rom_gems.get("data", [])
print("GEMS binary in ROM (0x7E000):")
for i in range(0, min(64, len(data)), 16):
    hex_str = " ".join(f"{data[i+j]:02X}" for j in range(min(16, len(data)-i)))
    print(f"  {0x7E000+i:06X} (Z80 off {i:04X}): {hex_str}")

# Specifically check the flag bytes that should map to Z80 0x0020-0x002F
print(f"\nGEMS binary at Z80 offset 0x20-0x2F:")
flags = data[0x20:0x30]
flag_hex = " ".join(f"{b:02X}" for b in flags)
print(f"  {flag_hex}")
print(f"  0x24 = 0x{flags[4]:02X}, 0x26 = 0x{flags[6]:02X}, 0x27 = 0x{flags[7]:02X}")

# Now run the emulator and check Z80 RAM state very early
print("\n--- After ROM load, before stepping ---")
z80_ram = get(f"/cpu/memory?addr={0xA00000}&len=64")
z80_data = z80_ram.get("data", [])
z80_hex = " ".join(f"{z80_data[i]:02X}" for i in range(min(48, len(z80_data))))
print(f"  Z80 RAM: {z80_hex}")

# Step 1 frame
post("/emulator/step", {"frames": 1})
z80_ram2 = get(f"/cpu/memory?addr={0xA00000}&len=64")
z80_data2 = z80_ram2.get("data", [])
z80_hex2 = " ".join(f"{z80_data2[i]:02X}" for i in range(min(48, len(z80_data2))))
apu = get("/apu/state")
print(f"\n--- After 1 frame ---")
print(f"  Z80 RAM: {z80_hex2}")
print(f"  Z80 PC=0x{apu['z80_pc']:04X} halted={apu['z80_halted']}")

# Step 1 more
post("/emulator/step", {"frames": 1})
z80_ram3 = get(f"/cpu/memory?addr={0xA00000}&len=64")  
z80_data3 = z80_ram3.get("data", [])
apu3 = get("/apu/state")
print(f"\n--- After 2 frames ---")
z80_hex3 = " ".join(f"{z80_data3[i]:02X}" for i in range(min(48, len(z80_data3))))
print(f"  Z80 RAM: {z80_hex3}")
print(f"  Z80 PC=0x{apu3['z80_pc']:04X} cycles={apu3.get('z80_total_cycles',0)}")

# Check: what code is the Z80 actually executing?
# Read Z80 RAM at the PC location
z80_pc = apu3['z80_pc']
pc_mem = get(f"/cpu/memory?addr={0xA00000 + z80_pc}&len=16")
pc_data = pc_mem.get("data", [])
pc_hex = " ".join(f"{b:02X}" for b in pc_data[:16])
print(f"  Code at Z80 PC: {pc_hex}")
