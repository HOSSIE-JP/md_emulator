#!/usr/bin/env python3
"""Disassemble M68K sound driver code around Z80 RAM references."""
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

# Read ROM around the sound driver functions (0x007200-0x007500)
addresses = [
    (0x007200, 0x300, "Sound driver area"),
    (0x0005D0, 0x040, "Z80 bus release area"),
    (0x009E60, 0x040, "Second 0xA00026 ref"),
]

for start, length, name in addresses:
    mem = get(f"/cpu/memory?addr={start}&len={length}")
    data = mem.get("data", [])
    
    print(f"\n=== {name} (0x{start:06X}) ===")
    for i in range(0, min(len(data), length), 16):
        addr = start + i
        hex_str = " ".join(f"{data[i+j]:02X}" for j in range(min(16, len(data)-i)))
        ascii_str = "".join(chr(data[i+j]) if 0x20 <= data[i+j] < 0x7F else "." for j in range(min(16, len(data)-i)))
        print(f"  {addr:06X}: {hex_str:48s}  {ascii_str}")
