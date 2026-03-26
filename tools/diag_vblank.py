#!/usr/bin/env python3
"""Check VBlank interrupt delivery and game progression."""
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

for nframes in [1, 5, 10, 30, 60, 120, 360, 600]:
    # Step to target frame count
    while True:
        apu = get("/apu/state")
        current_frame = apu.get("vdp_frame", 0)
        if current_frame >= nframes:
            break
        post("/emulator/step", {"frames": 1})
    
    apu = get("/apu/state")
    cpu = get("/cpu/state").get("cpu", {})
    m68k = cpu.get("m68k", {})
    
    pc = m68k.get("pc", 0)
    sr = m68k.get("sr", 0)
    vint = apu.get("vint_delivered", 0)
    hint = apu.get("hint_delivered", 0)
    frame = apu.get("vdp_frame", 0)
    vint_en = apu.get("vdp_vint_enabled", False)
    hint_en = apu.get("vdp_hint_enabled", False)
    ym_writes = apu.get("ym_write_total", 0)
    reg0 = apu.get("vdp_reg0", 0)
    reg1 = apu.get("vdp_reg1", 0)
    
    print(f"Frame {frame}: PC=0x{pc:06X} SR=0x{sr:04X} | VInt={vint} HInt={hint} VInt_en={vint_en} HInt_en={hint_en} | ym_writes={ym_writes} | reg0=0x{reg0:02X} reg1=0x{reg1:02X}")

print("\n=== DONE ===")
