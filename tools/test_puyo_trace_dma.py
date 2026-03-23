"""Check conditional flag for SAT DMA and trace DMA execution"""
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

# Check at several frame counts
for target_frame in [100, 300, 500, 600, 700, 900]:
    frames_per_step = 100
    for _ in range(frames_per_step):
        api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
    
    # Check conditional flags
    r_flag = api("GET", f"/api/v1/cpu/memory?addr={0xFF1834}&len=2")
    flag = r_flag.get("data", [])
    flag_val = (flag[0] << 8) | flag[1]
    
    r_cnt = api("GET", f"/api/v1/cpu/memory?addr={0xFF0DE4}&len=2")
    cnt = r_cnt.get("data", [])
    cnt_val = (cnt[0] << 8) | cnt[1]
    
    # Check VDP reg 1 shadow
    r_reg = api("GET", f"/api/v1/cpu/memory?addr={0xFF0A23}&len=1")
    reg1 = r_reg.get("data", [0])[0]
    
    # Check SAT buffer
    r_sat = api("GET", f"/api/v1/cpu/memory?addr={0xFF0E86}&len=16")
    sat_buf = r_sat.get("data", [])
    sat_hex = ' '.join(f'{b:02X}' for b in sat_buf[:16])
    
    # Check VRAM SAT
    r_vram = api("GET", f"/api/v1/vdp/vram?addr={0xBC00}&len=16")
    vram_sat = r_vram.get("data", [])
    vram_hex = ' '.join(f'{b:02X}' for b in vram_sat[:16])
    
    # Frame info
    r_frame = api("GET", "/api/v1/video/frame")
    pixels = r_frame["pixels_argb"]
    nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
    
    print(f"Frame ~{target_frame}: $FF1834={flag_val:04X} $FF0DE4(cnt)={cnt_val:04X} "
          f"reg1_shadow=0x{reg1:02X} nonblack={nb}")
    print(f"  RAM SAT: {sat_hex}")
    print(f"  VRAM SAT: {vram_hex}")
