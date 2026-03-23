"""Check per-line hscroll table at the transition point"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

def api_get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# Reset and step to title screen with HInt
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

regs = api_get("/vdp/registers")["registers"]
hint_en = (regs[0] >> 4) & 1
hscroll_mode = regs[0xB] & 3
hscroll_addr = (regs[0xD] & 0x3F) << 10
print(f"HInt enabled: {hint_en}, HScroll mode: {hscroll_mode}, HScroll addr: 0x{hscroll_addr:04X}")

if hscroll_mode == 3:
    # Per-line hscroll: 4 bytes per line (2 for A, 2 for B), 224 lines
    vram = bytes(api_get(f"/vdp/vram?addr={hscroll_addr}&len=896")["data"])
    print(f"\nPer-line hscroll table (first 30 lines):")
    for line in range(30):
        offset = line * 4
        if offset + 3 < len(vram):
            hs_a = (vram[offset] << 8) | vram[offset + 1]
            hs_b = (vram[offset + 2] << 8) | vram[offset + 3]
            hs_a_signed = hs_a if hs_a < 0x8000 else hs_a - 0x10000
            hs_b_signed = hs_b if hs_b < 0x8000 else hs_b - 0x10000
            print(f"  line {line:3d}: A={hs_a_signed:5d} B={hs_b_signed:5d}")
    
    print(f"\nLines 100-120:")
    for line in range(100, 120):
        offset = line * 4
        if offset + 3 < len(vram):
            hs_a = (vram[offset] << 8) | vram[offset + 1]
            hs_b = (vram[offset + 2] << 8) | vram[offset + 3]
            hs_a_signed = hs_a if hs_a < 0x8000 else hs_a - 0x10000
            hs_b_signed = hs_b if hs_b < 0x8000 else hs_b - 0x10000
            print(f"  line {line:3d}: A={hs_a_signed:5d} B={hs_b_signed:5d}")

    # Check if HInt is actually modifying CRAM/scroll during rendering
    # In the title screen, Puyo uses HInt to update the CRAM mid-frame
    # for the "gradient" effect on the title
    print(f"\nHInt counter (R0xA): {regs[0xA]}")
