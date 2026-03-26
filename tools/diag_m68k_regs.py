#!/usr/bin/env python3
"""Deep M68K diagnostic: registers, stack, and code at key points."""
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

for target_frame in [1, 5, 30, 60, 120, 300, 600]:
    while True:
        apu = get("/apu/state")
        if apu.get("vdp_frame", 0) >= target_frame:
            break
        post("/emulator/step", {"frames": 1})
    
    cpu = get("/cpu/state")
    m = cpu.get("cpu", {}).get("m68k", {})
    pc = m.get("pc", 0)
    sr = m.get("sr", 0)
    
    # Read code at PC
    mem = get(f"/cpu/memory?addr={pc}&len=20")
    code = " ".join(f"{b:02X}" for b in mem.get("data", [])[:20])
    
    # D registers
    dregs = [m.get(f"d{i}", 0) for i in range(8)]
    aregs = [m.get(f"a{i}", 0) for i in range(8)]
    
    print(f"Frame {target_frame:3d}: PC=0x{pc:06X} SR=0x{sr:04X}")
    print(f"  D: {' '.join(f'{d:08X}' for d in dregs)}")
    print(f"  A: {' '.join(f'{a:08X}' for a in aregs)}")
    print(f"  Code: {code}")
    
    # If in busy-wait, check what A0 points to
    if pc == 0x000334:
        a0 = aregs[0]
        mem2 = get(f"/cpu/memory?addr={a0}&len=4")
        val = mem2.get("data", [0, 0, 0, 0])
        word = (val[0] << 8) | val[1]
        print(f"  (A0)=0x{a0:06X} -> word=0x{word:04X}, D0=0x{dregs[0]:08X}")
    print()
