"""Check Window plane settings during demo gameplay"""
import urllib.request, json

BASE = "http://127.0.0.1:8117/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    d = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=d,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

# Reset to demo gameplay
post("/emulator/reset")
post("/emulator/step", {"frames": 3000})

# Check window plane registers
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")

r03 = rdata[0x03]
r11 = rdata[0x11]
r12 = rdata[0x12]
win_addr = (r03 & 0x3E) << 10
win_h_pos = r11
win_v_pos = r12
win_right = (win_h_pos & 0x80) != 0
win_h_cell = (win_h_pos & 0x1F) * 2  # 2-cell units
win_down = (win_v_pos & 0x80) != 0
win_v_cell = win_v_pos & 0x1F

print(f"Window register $11 (win_h): 0x{r11:02X} = right={win_right}, h_cell={win_h_cell}")
print(f"Window register $12 (win_v): 0x{r12:02X} = down={win_down}, v_cell={win_v_cell}")
print(f"Window nametable addr: 0x{win_addr:04X}")

# Is window active?
if win_h_cell == 0 and win_v_cell == 0:
    print("Window: INACTIVE (h_cell=0, v_cell=0)")
else:
    print("Window: ACTIVE")
    
# Read the window nametable
# Window stride = 64 for H40
win_stride = 64  # cells per row 
win_size = win_stride * 32 * 2  # max 32 rows
vram = get(f"/vdp/vram?addr={win_addr}&len={min(win_size, 4096)}")
wdata = vram.get("data") or vram.get("vram")
print(f"\nWindow nametable at 0x{win_addr:04X} (first 10 rows):")
for row in range(min(10, len(wdata) // (win_stride * 2))):
    tiles = []
    for col in range(min(10, win_stride)):
        off = (row * win_stride + col) * 2
        if off + 1 < len(wdata):
            entry = (wdata[off] << 8) | wdata[off+1]
            tiles.append(f"{entry:04X}")
    print(f"  row {row:2d}: {' '.join(tiles)}")

# Also check: with the current window settings, which scanlines does it cover?
print(f"\nWindow covers:")
if win_v_cell == 0 and not win_down:
    print("  Full screen (v_cell=0, down=false = covers ALL lines)")
elif win_v_cell == 0 and win_down:
    print("  No lines (v_cell=0, down=true)")
elif win_down:
    print(f"  Lines from y_cell={win_v_cell} ({win_v_cell*8} px) downwards")
else:
    print(f"  Lines from top to y_cell={win_v_cell-1} (first {win_v_cell*8} px)")

if win_h_cell == 0:
    if not win_right:
        print("  Full width (h_cell=0, right=false)")
    else:
        print("  No width (h_cell=0, right=true)")
elif win_right:
    print(f"  Right side from x_cell={win_h_cell} ({win_h_cell*8} px)")
else:
    print(f"  Left side from x=0 to x_cell={win_h_cell-1} ({win_h_cell*8} px)")
