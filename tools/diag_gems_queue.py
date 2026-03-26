#!/usr/bin/env python3
"""Monitor GEMS command queue: M68K pending at 0xFF012C and Z80 slot counter."""
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

BTN_START = 0x80

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

prev_cmd = None
prev_slot = None

for frame in range(1, 901):
    post("/emulator/step", {"frames": 1})
    
    # Press start at frame 120 and 250
    if frame == 120 or frame == 250:
        post("/input/controller", {"player": 1, "buttons": BTN_START})
    if frame == 130 or frame == 260:
        post("/input/controller", {"player": 1, "buttons": 0})
    
    # Check M68K work RAM command pending bytes 
    cmd_mem = get(f"/cpu/memory?addr={0xFF012C}&len=4")
    cmd_data = cmd_mem.get("data", [0, 0, 0, 0])
    
    # Check Z80 RAM slot counter (0xA00022) and first bytes
    z80_mem = get(f"/cpu/memory?addr={0xA00020}&len=16")
    z80_data = z80_mem.get("data", [0]*16)
    
    # Z80 slot counter at offset 2 (addr 0x0022)
    slot_counter = z80_data[2]  # addr 0x0022
    
    # Only print when something changes
    cmd_tuple = tuple(cmd_data)
    if cmd_tuple != prev_cmd or slot_counter != prev_slot:
        z80_hex = " ".join(f"{b:02X}" for b in z80_data)
        print(f"Frame {frame:4d}: cmd_pending=[{cmd_data[0]:02X} {cmd_data[1]:02X} {cmd_data[2]:02X} {cmd_data[3]:02X}] "
              f"slot={slot_counter} z80[0x20-0x2F]={z80_hex}")
        prev_cmd = cmd_tuple
        prev_slot = slot_counter
    
    # Also periodically print status
    if frame in [1, 60, 120, 130, 200, 250, 260, 400, 600, 900]:
        cpu = get("/cpu/state")
        m = cpu.get("cpu", {}).get("m68k", {})
        apu = get("/apu/state")
        # Check work RAM flag at 0xFF0134
        flag_mem = get(f"/cpu/memory?addr={0xFF0134}&len=2")
        flag = (flag_mem.get("data", [0,0])[0] << 8) | flag_mem.get("data", [0,0])[1]
        # Also check 0xFFFCAC 
        fcac_mem = get(f"/cpu/memory?addr={0xFFFCAC}&len=1")
        fcac = fcac_mem.get("data", [0])[0]
        z80_hex = " ".join(f"{b:02X}" for b in z80_data)
        print(f"  STATUS frame={frame}: M68K_PC=0x{m['pc']:06X} ym_wr={apu.get('ym_write_total',0)} "
              f"flag0134={flag:04X} fcac={fcac:02X}")
