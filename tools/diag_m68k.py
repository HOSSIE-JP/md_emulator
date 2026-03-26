#!/usr/bin/env python3
"""Check M68K state and Z80 communication area."""  
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

for nframes in [10, 60, 120, 360]:
    prev = get("/cpu/state")
    prev_pc = prev.get("m68k", {}).get("pc", 0)
    
    # Run to target
    while True:
        apu = get("/apu/state")
        current_cycles = apu['z80_total_cycles']
        # Use a rough estimate: 60 frames = ~60*127856 = 7.7M m68k cycles = 3.85M z80 cycles
        if current_cycles >= nframes * 63000:  # rough z80 cycles per frame
            break
        post("/emulator/step", {"frames": 1})
    
    cpu = get("/cpu/state")
    apu = get("/apu/state")
    m68k = cpu.get("m68k", {})
    
    print(f"\n=== After ~{nframes} frames ===")
    print(f"  M68K PC=0x{m68k.get('pc', 0):06X} SR=0x{m68k.get('sr', 0):04X}")
    print(f"  M68K D0=0x{m68k.get('d', [0])[0]:08X} A0=0x{m68k.get('a', [0])[0]:08X}")
    print(f"  Z80 PC={apu['z80_pc']} cycles={apu['z80_total_cycles']} halted={apu['z80_halted']}")
    print(f"  ym_writes={apu['ym_write_total']} z80_reset={apu['z80_reset']} bus_req={apu['z80_bus_requested']}")
    
    # Check Z80 communication area (0x1F00-0x1FFF)
    comm_area = get(f"/cpu/memory?addr={0xA01F00}&len=64")
    comm_data = comm_area.get("data", [])
    print(f"  Z80 comm [0x1F00..0x1F3F]: {' '.join(f'{b:02X}' for b in comm_data[:64])}")
    
    # Also specifically check 0x1F20 area (GEMS channel data?)
    area_1f20 = get(f"/cpu/memory?addr={0xA01F20}&len=32")
    data_1f20 = area_1f20.get("data", [])
    print(f"  Z80 RAM [0x1F20..0x1F3F]: {' '.join(f'{b:02X}' for b in data_1f20[:32])}")

print("\n=== DONE ===")
