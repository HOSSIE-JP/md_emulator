"""Force-enable sound by setting $FF0067 bit3 AND VDP VINT"""
import urllib.request, json, time

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def read_mem(addr, length):
    r = api("GET", f"/cpu/memory?addr={addr}&len={length}")
    return r.get("data") or r.get("memory", [])

def write_mem(addr, data):
    return api("POST", "/cpu/memory", {"addr": addr, "data": data})

def safe_int(v):
    return int(v, 16) if isinstance(v, str) else int(v)

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Fresh load
time.sleep(2)
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("ROM loaded")

# Step to frame 200 (game running)
api("POST", "/emulator/step", {"frames": 200})

# Check original state
flag = read_mem(0xFF0067, 1)[0]
vdp = api("GET", "/vdp/registers")
regs = vdp["registers"]
reg1 = regs[1] if isinstance(regs, list) else regs.get("1", 0)
print(f"Before: $FF0067=0x{flag:02X}, VDP Reg1=0x{reg1:02X}")

# Force sound enable
write_mem(0xFF0067, [flag | 0x08])  # set bit 3

# Force VINT enable via VDP register API
api("POST", "/vdp/registers", {"reg": 1, "value": reg1 | 0x20})

# Verify
flag2 = read_mem(0xFF0067, 1)[0]
vdp2 = api("GET", "/vdp/registers")
regs2 = vdp2["registers"]
reg1b = regs2[1] if isinstance(regs2, list) else regs2.get("1", 0)
print(f"After:  $FF0067=0x{flag2:02X} (bit3={'SET' if flag2&8 else 'clr'}), VDP Reg1=0x{reg1b:02X} (VINT={'ON' if reg1b&0x20 else 'OFF'})")

# Step 500 more frames
api("POST", "/emulator/step", {"frames": 500})

# Check sound state
apu = api("GET", "/apu/state")
bank = safe_int(apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", "0")))
bank_max = safe_int(apu.get("z80_bank_max_value", "0"))
z80_writes = safe_int(apu.get("z80_m68k_write_count", "0"))
ym_hist = apu.get("ym_write_histogram", {})
non_timer = {k: v for k, v in ym_hist.items() if k not in ("27", "2A", "2B")} if ym_hist else {}

print(f"\nF700: bank=0x{bank:06X} max=0x{bank_max:06X} z80w={z80_writes}")
print(f"  YM non-timer regs: {len(non_timer)}")
if non_timer:
    top_regs = sorted(non_timer.items(), key=lambda x: int(x[1]) if isinstance(x[1], (int, str)) else 0, reverse=True)[:15]
    print(f"  Top FM regs: {dict(top_regs)}")

flag3 = read_mem(0xFF0067, 1)[0]
fc = read_mem(0xFF004C, 4)
fc_val = (fc[0]<<24)|(fc[1]<<16)|(fc[2]<<8)|fc[3]
print(f"  $FF0067=0x{flag3:02X}, frame_ctr={fc_val}")

cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"  PC=0x{m68k['pc']:06X}")

banked = apu.get("z80_banked_read_log", [])
print(f"  Z80 banked reads: {len(banked)}")

# Step another 500 
api("POST", "/emulator/step", {"frames": 500})
apu2 = api("GET", "/apu/state")
bank2 = safe_int(apu2.get("z80_bank_68k_addr", apu2.get("bank_68k_addr", "0")))
bank_max2 = safe_int(apu2.get("z80_bank_max_value", "0"))
ym_hist2 = apu2.get("ym_write_histogram", {})
non_timer2 = {k: v for k, v in ym_hist2.items() if k not in ("27", "2A", "2B")} if ym_hist2 else {}
print(f"\nF1200: bank=0x{bank2:06X} max=0x{bank_max2:06X}")
print(f"  YM non-timer regs: {len(non_timer2)}")
if non_timer2:
    top_regs2 = sorted(non_timer2.items(), key=lambda x: int(x[1]) if isinstance(x[1], (int, str)) else 0, reverse=True)[:15]
    print(f"  Top FM regs: {dict(top_regs2)}")

flag4 = read_mem(0xFF0067, 1)[0]
fc2 = read_mem(0xFF004C, 4)
fc_val2 = (fc2[0]<<24)|(fc2[1]<<16)|(fc2[2]<<8)|fc2[3]
print(f"  $FF0067=0x{flag4:02X}, frame_ctr={fc_val2}")
banked2 = apu2.get("z80_banked_read_log", [])
print(f"  Z80 banked reads: {len(banked2)}")
