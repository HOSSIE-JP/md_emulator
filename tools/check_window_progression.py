"""Check window plane registers at different frames"""
import urllib.request, json

BASE = "http://127.0.0.1:8118/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    d = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=d,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

# Reset and check at various stages
post("/emulator/reset")

for target_frame in [100, 500, 900, 1800, 2100, 3000]:
    current = 0
    post("/emulator/reset")
    post("/emulator/step", {"frames": target_frame})
    
    regs = get("/vdp/registers")
    rdata = regs.get("registers") or regs.get("data")
    r11 = rdata[0x11]
    r12 = rdata[0x12]
    r01 = rdata[0x01]
    display_en = (r01 & 0x40) != 0
    
    print(f"Frame {target_frame:5d}: R$11=0x{r11:02X} R$12=0x{r12:02X} display={'ON' if display_en else 'OFF'}")
    
    win_right = (r11 & 0x80) != 0
    win_h_cell = (r11 & 0x1F) * 2
    win_down = (r12 & 0x80) != 0
    win_v_cell = r12 & 0x1F
    print(f"         win_right={win_right}, win_h_cell={win_h_cell}, win_down={win_down}, win_v_cell={win_v_cell}")
    
    # Get frame to check if display is working
    fdata = get("/video/frame")
    pixels = fdata["pixels_argb"]
    non_black = sum(1 for p in pixels if (p & 0x00FFFFFF) != 0)
    total = len(pixels)
    print(f"         non-black pixels: {non_black}/{total} ({non_black*100//total}%)")
