#!/usr/bin/env python3
"""Diagnose VDP registers during Puyo Puyo gameplay."""
import urllib.request, json

BASE = "http://localhost:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

def show_regs(label):
    regs_data = get("/vdp/registers")
    regs = regs_data if isinstance(regs_data, list) else regs_data.get("registers", [])
    if len(regs) >= 0x14:
        r0c = regs[0x0C]
        sh_mode = (r0c & 0x08) != 0
        h40 = (r0c & 0x81) != 0
        r00 = regs[0x00]
        r01 = regs[0x01]
        print(f"{label}:")
        print(f"  R00=0x{r00:02X} R01=0x{r01:02X} R0C=0x{r0c:02X}  H40={h40} S/H={sh_mode}")
        print(f"  R02=0x{regs[2]:02X} R03=0x{regs[3]:02X} R04=0x{regs[4]:02X} R05=0x{regs[5]:02X}")
        print(f"  R07=0x{regs[7]:02X} (bg) R0B=0x{regs[0x0B]:02X} R10=0x{regs[0x10]:02X}")
        print(f"  R11=0x{regs[0x11]:02X} R12=0x{regs[0x12]:02X} (window)")
    else:
        print(f"{label}: regs={regs_data}")
    
    sprites_data = get("/vdp/sprites")
    sp_list = sprites_data if isinstance(sprites_data, list) else sprites_data.get("sprites", [])
    pri = sum(1 for s in sp_list if s.get("priority"))
    pal3 = sum(1 for s in sp_list if s.get("palette") == 3)
    print(f"  Sprites: {len(sp_list)} total, {pri} priority, {pal3} palette3")

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

print("--- Title ---")
post("/emulator/step", {"frames": 100})
show_regs("Title 100f")

# Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
post("/emulator/step", {"frames": 60})
show_regs("After Start")

# Navigate through menus to gameplay
for i in range(8):
    post("/input/controller", {"player": 1, "buttons": 128})
    post("/emulator/step", {"frames": 5})
    post("/input/controller", {"player": 1, "buttons": 0})
    post("/emulator/step", {"frames": 100})
    show_regs(f"Menu press {i+1}")
