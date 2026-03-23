"""Check $FF0134 flag and trace SAT update path"""
import urllib.request
import json

BASE = "http://127.0.0.1:8111"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Reset and load
api("POST", "/api/v1/emulator/reset", {})
api("POST", "/api/v1/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

for target_frame in [100, 300, 500, 600, 700]:
    for _ in range(100):
        api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
    
    # Check all relevant flags
    addrs = {
        "FF0134": 0xFF0134,
        "FF0DE4": 0xFF0DE4,
        "FF1834": 0xFF1834,
    }
    vals = {}
    for name, addr in addrs.items():
        r = api("GET", f"/api/v1/cpu/memory?addr={addr}&len=2")
        data = r.get("data", [])
        vals[name] = (data[0] << 8) | data[1]
    
    # Check VRAM SAT first 16 bytes
    r_vram = api("GET", f"/api/v1/vdp/vram?addr={0xBC00}&len=16")
    vram_sat = r_vram.get("data", [])
    vram_hex = ' '.join(f'{b:02X}' for b in vram_sat[:16])
    
    # Check RAM SAT first 16 bytes
    r_ram = api("GET", f"/api/v1/cpu/memory?addr={0xFF0E86}&len=16")
    ram_sat = r_ram.get("data", [])
    ram_hex = ' '.join(f'{b:02X}' for b in ram_sat[:16])
    
    print(f"Frame ~{target_frame}: $FF0134={vals['FF0134']:04X} "
          f"$FF0DE4={vals['FF0DE4']:04X} $FF1834={vals['FF1834']:04X}")
    print(f"  RAM  SAT[0:16]: {ram_hex}")
    print(f"  VRAM SAT[0:16]: {vram_hex}")
    
    # Check if they match
    if ram_sat[:8] == vram_sat[:8]:
        print(f"  → SAT MATCH!")
    else:
        print(f"  → SAT MISMATCH!")
