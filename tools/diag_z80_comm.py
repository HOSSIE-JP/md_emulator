#!/usr/bin/env python3
"""Check M68K→Z80 command communication area and M68K bus writes."""
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

# Run frames progressively and check command area
for target_frame in [1, 5, 10, 30, 60, 120, 300, 600]:
    while True:
        apu = get("/apu/state")
        current_frame = apu.get("vdp_frame", 0)
        if current_frame >= target_frame:
            break
        post("/emulator/step", {"frames": 1})
    
    # Read Z80 RAM communication area (typically 0x1F00-0x1FFF)
    mem_1f00 = get(f"/memory?address={0xA01F00}&length=64")
    mem_data = mem_1f00.get("data", [])
    
    # Also read around the GEMS command area more broadly
    mem_1e00 = get(f"/memory?address={0xA01E00}&length=32")
    mem_1e_data = mem_1e00.get("data", [])
    
    m68k_pc = get("/cpu/state").get("cpu", {}).get("m68k", {}).get("pc", 0)
    z80_pc = apu.get("z80_pc", 0)
    ym_writes = apu.get("ym_write_total", 0)
    
    # Show first 32 bytes of the GEMS command area
    cmd_hex = " ".join(f"{b:02X}" for b in mem_data[:32])
    print(f"Frame {target_frame:3d}: M68K=0x{m68k_pc:06X} Z80=0x{z80_pc:04X} ym_wr={ym_writes:6d}")
    print(f"  Z80 RAM 0x1F00: {cmd_hex}")
    # Show 0x1F20 area specifically (GEMS command byte)
    if len(mem_data) >= 0x20 + 8:
        cmd_area = " ".join(f"{mem_data[0x20+i]:02X}" for i in range(8))
        print(f"  Z80 RAM 0x1F20: {cmd_area}")
    
    # Also check 0x1E00 area
    cmd_hex2 = " ".join(f"{b:02X}" for b in mem_1e_data[:32])
    print(f"  Z80 RAM 0x1E00: {cmd_hex2}")
    print()
