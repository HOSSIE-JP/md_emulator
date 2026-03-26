#!/usr/bin/env python3
"""Dump Z80 RAM at various points to understand flag lifecycle."""
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

# Monitor Z80 RAM low area (flags) and key addresses every frame
prev_state = None

for frame in range(1, 200):
    post("/emulator/step", {"frames": 1})
    
    # Read Z80 RAM 0x0020-0x0030
    z80_mem = get(f"/cpu/memory?addr={0xA00020}&len=16")
    z80_data = tuple(z80_mem.get("data", [0]*16))
    
    if z80_data != prev_state:
        z80_hex = " ".join(f"{b:02X}" for b in z80_data)
        apu = get("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        ym_wr = apu.get("ym_write_total", 0)
        print(f"Frame {frame:3d}: Z80[0x20-0x2F]={z80_hex} Z80_PC=0x{z80_pc:04X} ym_wr={ym_wr}")
        prev_state = z80_data
