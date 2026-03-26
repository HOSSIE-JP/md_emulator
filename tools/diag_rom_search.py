#!/usr/bin/env python3
"""Search ROM for M68K references to Z80 command address 0xA00027."""
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

# Read the first 512KB of ROM
rom_data = []
for offset in range(0, 0x80000, 0x4000):
    mem = get(f"/cpu/memory?addr={offset}&len=16384")
    rom_data.extend(mem.get("data", []))

print(f"ROM size: {len(rom_data)} bytes")

# Search for patterns
patterns = [
    ("00A00027 (long addr)", bytes([0x00, 0xA0, 0x00, 0x27])),
    ("00A0002x (near 0x27)", bytes([0x00, 0xA0, 0x00, 0x2])),
    ("A1 1100 (Z80 bus req)", bytes([0x00, 0xA1, 0x11, 0x00])),
    ("A1 1200 (Z80 reset)", bytes([0x00, 0xA1, 0x12, 0x00])),
]

for name, pattern in patterns:
    matches = []
    for i in range(len(rom_data) - len(pattern) + 1):
        if rom_data[i:i+len(pattern)] == list(pattern):
            matches.append(i)
    if matches:
        print(f"\n{name}: {len(matches)} matches")
        for m in matches[:20]:  # Show first 20
            ctx_start = max(0, m - 4)
            ctx = " ".join(f"{rom_data[ctx_start+j]:02X}" for j in range(min(12, len(rom_data) - ctx_start)))
            print(f"  0x{m:06X}: ...{ctx}")

# Also check: what Z80 RAM area does M68K write to during init?
# Search for writes to 0xA00000 area more broadly
print("\n\n=== Z80 RAM area references ===")
for check_addr_byte in [0x20, 0x25, 0x26, 0x27, 0x28]:
    pattern = bytes([0x00, 0xA0, 0x00, check_addr_byte])
    matches = []
    for i in range(len(rom_data) - 4):
        if rom_data[i:i+4] == list(pattern):
            matches.append(i)
    if matches:
        print(f"  Ref to 0xA000{check_addr_byte:02X}: {len(matches)} at {', '.join(f'0x{m:06X}' for m in matches[:10])}")
