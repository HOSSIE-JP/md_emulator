#!/usr/bin/env python3
"""Diagnose VDP state during Puyo Puyo gameplay for S/H and sprite issues."""
import urllib.request, json

BASE = "http://localhost:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

def show_vdp_regs():
    state = get("/cpu/state")
    vdp = state.get("vdp", {})
    regs = vdp.get("registers", [])
    if len(regs) >= 0x20:
        r0c = regs[0x0C]
        sh_mode = (r0c & 0x08) != 0
        h40 = (r0c & 0x81) != 0
        print(f"  Reg 0x0C = 0x{r0c:02X}  H40={h40}  S/H={sh_mode}")
        r00 = regs[0x00]
        r01 = regs[0x01]
        print(f"  Reg 0x00 = 0x{r00:02X}  LeftBlank={(r00>>5)&1}  HInt={(r00>>4)&1}")
        print(f"  Reg 0x01 = 0x{r01:02X}  Display={(r01>>6)&1}  VInt={(r01>>5)&1}  DMA={(r01>>4)&1}")
        print(f"  Reg 0x05 = 0x{regs[5]:02X}  (SAT)")
        print(f"  Reg 0x10 = 0x{regs[0x10]:02X}  (scroll size)")
        print(f"  Reg 0x11 = 0x{regs[0x11]:02X}  Reg 0x12 = 0x{regs[0x12]:02X}  (window)")
    status = vdp.get("status", 0)
    print(f"  Status = 0x{status:04X}  Collision={(status>>5)&1}  Overflow={(status>>6)&1}")
    return regs

def show_sprites():
    sprites = get("/vdp/sprites")
    sp_list = sprites if isinstance(sprites, list) else sprites.get("sprites", [])
    print(f"  Total sprites in link list: {len(sp_list)}")
    for s in sp_list[:15]:
        pri = "P" if s.get("priority") else "."
        hf = "H" if s.get("hflip") else "."
        vf = "V" if s.get("vflip") else "."
        pal = s.get("palette", 0)
        print(f"    #{s['index']:2d} x={s['x']:4d} y={s['y']:4d} {s['width']}x{s['height']} tile=0x{s['tile']:03X} pal={pal} {pri}{hf}{vf} link={s['link']}")
    if len(sp_list) > 15:
        print(f"    ... ({len(sp_list) - 15} more)")
    # Count sprites with/without priority
    pri_count = sum(1 for s in sp_list if s.get("priority"))
    nopri_count = len(sp_list) - pri_count
    print(f"  Priority: {pri_count} with, {nopri_count} without")

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Title screen
print("=== Title screen (100 frames) ===")
post("/emulator/step", {"frames": 100})
regs = show_vdp_regs()
show_sprites()

# Press Start
print("\n=== After Start (50 frames) ===")
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
post("/emulator/step", {"frames": 45})
regs = show_vdp_regs()
show_sprites()

# Advance through menus to get to gameplay
# Select 1P mode (press Start a few more times)
print("\n=== Pressing Start again (menu) ===")
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
post("/emulator/step", {"frames": 60})
regs = show_vdp_regs()

# Keep pressing Start to advance
for i in range(5):
    post("/input/controller", {"player": 1, "buttons": 128})
    post("/emulator/step", {"frames": 5})
    post("/input/controller", {"player": 1, "buttons": 0})
    post("/emulator/step", {"frames": 100})

print(f"\n=== Dialogue/Game scene ===")
regs = show_vdp_regs()
show_sprites()

# One more set of Start presses to get into actual gameplay
for i in range(3):
    post("/input/controller", {"player": 1, "buttons": 128})
    post("/emulator/step", {"frames": 5})
    post("/input/controller", {"player": 1, "buttons": 0})
    post("/emulator/step", {"frames": 120})

print(f"\n=== Gameplay ===")
regs = show_vdp_regs()
show_sprites()
