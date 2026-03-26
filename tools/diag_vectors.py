#!/usr/bin/env python3
"""Check ROM vector table to see SP/PC setup."""
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

# Read ROM vector table (first 256 bytes)
mem = get("/cpu/memory?addr=0&len=256")
data = mem.get("data", [])

# Initial SSP (address 0x000000, 4 bytes big-endian)
ssp = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
# Initial PC (address 0x000004, 4 bytes big-endian)
initial_pc = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
# VBlank vector (address 0x000078, level 6)
vblank_vec = (data[0x78] << 24) | (data[0x79] << 16) | (data[0x7A] << 8) | data[0x7B]

print(f"Initial SSP: 0x{ssp:08X}")
print(f"Initial PC:  0x{initial_pc:08X}")
print(f"VBlank vec:  0x{vblank_vec:08X}")
print(f"First 16 bytes: {' '.join(f'{b:02X}' for b in data[:16])}")

# Now check M68K state before any stepping
cpu = get("/cpu/state")
m = cpu.get("cpu", {}).get("m68k", {})
print(f"\nM68K PC=0x{m['pc']:06X} SR=0x{m.get('sr',0):04X}")
dregs = [m.get(f"d{i}", m.get("d", [0]*8)[i] if isinstance(m.get("d"), list) else 0) for i in range(8)]
aregs = [m.get(f"a{i}", m.get("a", [0]*8)[i] if isinstance(m.get("a"), list) else 0) for i in range(8)]
print(f"D: {dregs}")
print(f"A: {aregs}")

# Check if d/a are arrays or individual fields
print(f"\nRaw M68K state keys: {list(m.keys())}")
print(f"D field type: {type(m.get('d'))}")
if isinstance(m.get('d'), list):
    print(f"D values: {m['d']}")
if isinstance(m.get('a'), list):
    print(f"A values: {m['a']}")
