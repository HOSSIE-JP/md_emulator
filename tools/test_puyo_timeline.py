"""Check SAT at different frame counts to see if game populates it properly"""
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

# Reset and reload
print("Resetting and loading ROM...")
api("POST", "/api/v1/emulator/reset", {})
api("POST", "/api/v1/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

check_frames = [60, 120, 180, 300, 600, 900, 1200, 1500, 1800]
current = 0

for target in check_frames:
    delta = target - current
    for _ in range(delta):
        api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
    current = target
    
    # Check SAT
    r = api("GET", "/api/v1/vdp/registers")
    regs = r["registers"]
    sat_addr = (regs[5] & 0x7F) << 9
    
    r_vram = api("GET", f"/api/v1/vdp/vram?addr={sat_addr}&len=640")
    sat_data = r_vram.get("data", [])
    
    # Count non-zero entries
    valid_sprites = 0
    link = 0
    chain_len = 0
    for _ in range(80):
        base = link * 8
        if base + 7 >= len(sat_data):
            break
        entry = sat_data[base:base+8]
        y_pos = ((entry[0] << 8) | entry[1]) & 0x3FF
        next_link = entry[3] & 0x7F
        attr = (entry[4] << 8) | entry[5]
        x_pos = ((entry[6] << 8) | entry[7]) & 0x1FF
        
        sprite_y = y_pos - 128
        sprite_x = x_pos - 128
        
        chain_len += 1
        if -32 <= sprite_y <= 256 and -32 <= sprite_x <= 352:
            valid_sprites += 1
        
        if next_link == 0:
            break
        link = next_link
    
    # SAT first entry raw
    first_8 = ' '.join(f'{sat_data[i]:02X}' for i in range(8))
    
    # Frame analysis
    r_frame = api("GET", "/api/v1/video/frame")
    pixels = r_frame["pixels_argb"]
    unique = len(set(pixels))
    nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
    
    # Get colors
    r_col = api("GET", "/api/v1/vdp/colors")
    nz_cram = sum(1 for c in r_col.get("colors_argb", []) if (c & 0xFFFFFF) != 0)
    
    # CPU state
    r_cpu = api("GET", "/api/v1/cpu/state")
    m68k = r_cpu["cpu"]["m68k"]
    
    print(f"Frame {target:5d}: PC=0x{m68k['pc']:06X} SAT@0x{sat_addr:04X} "
          f"chain={chain_len} visible={valid_sprites} "
          f"colors={unique} nonblack={nb}/71680 cram_nz={nz_cram} "
          f"first=[{first_8}]")
