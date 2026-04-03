"""Test if SRAM enables game progression and sound"""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def read_mem(addr, length):
    r = api("GET", f"/cpu/memory?addr={addr}&len={length}")
    return r.get("data") or r.get("memory", [])

def safe_int(v):
    return int(v, 16) if isinstance(v, str) else int(v)

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Load ROM fresh
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("ROM loaded with SRAM support")

# Run 1500 frames and check sound state at intervals
checkpoints = [100, 200, 500, 800, 1000, 1200, 1500]
for target in checkpoints:
    prev = 0 if target == checkpoints[0] else checkpoints[checkpoints.index(target)-1]
    frames_to_step = target - prev
    
    # Press START at frame 800
    if target == 800:
        api("POST", "/input/controller", {"player": 1, "buttons": 0x0080})
    
    api("POST", "/emulator/step", {"frames": frames_to_step})
    
    if target == 850 or target == 800:
        api("POST", "/input/controller", {"player": 1, "buttons": 0})
    
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    apu = api("GET", "/apu/state")
    
    bank = safe_int(apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", "0")))
    bank_writes = safe_int(apu.get("z80_bank_write_count", "0"))
    bank_max = safe_int(apu.get("z80_bank_max_value", "0"))
    z80_writes = safe_int(apu.get("z80_m68k_write_count", "0"))
    
    # Check YM2612 write activity
    ym_hist = apu.get("ym_write_histogram", {})
    non_timer_regs = {k: v for k, v in ym_hist.items() if k not in ("27", "2A", "2B")} if ym_hist else {}
    
    print(f"F{target:4d}: PC=${m68k['pc']:06X} bank=0x{bank:06X} "
          f"bw={bank_writes} bmax=0x{bank_max:06X} z80w={z80_writes} "
          f"ym_nonTimer={len(non_timer_regs)}")

# Release START
api("POST", "/input/controller", {"player": 1, "buttons": 0})

# Do extended run to 3000 frames
print("\n--- Extended run ---")
api("POST", "/emulator/step", {"frames": 500})
for target in [2000, 2500, 3000]:
    api("POST", "/emulator/step", {"frames": 500})
    apu = api("GET", "/apu/state")
    bank = safe_int(apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", "0")))
    bank_max = safe_int(apu.get("z80_bank_max_value", "0"))
    bank_writes = safe_int(apu.get("z80_bank_write_count", "0"))
    z80_writes = safe_int(apu.get("z80_m68k_write_count", "0"))
    
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    
    ym_hist = apu.get("ym_write_histogram", {})
    non_timer = {k: v for k, v in ym_hist.items() if k not in ("27", "2A", "2B")} if ym_hist else {}
    
    print(f"F{target:4d}: PC=${m68k['pc']:06X} bank=0x{bank:06X} "
          f"bw={bank_writes} bmax=0x{bank_max:06X} z80w={z80_writes} "
          f"ym_nonTimer={len(non_timer)}")
    
    if non_timer:
        print(f"  FM regs: {dict(list(non_timer.items())[:10])}")

# Check Z80 bank write log
bank_log = apu.get("z80_bank_write_log", [])
if bank_log:
    print(f"\nBank write log (last 20): {bank_log[-20:]}")
else:
    print(f"\nBank write log: empty")

# Check Z80 RAM for communication changes
z80_1fa = read_mem(0xA001FA, 2)
z80_100 = read_mem(0xA00100, 16)
print(f"\nZ80 $1FA={z80_1fa}")
print(f"Z80 $100-$10F={[f'{b:02X}' for b in z80_100]}")

# Check banked read log
banked = apu.get("z80_banked_read_log", [])
print(f"Z80 banked reads: {len(banked)}")
if banked:
    print(f"  First 5: {banked[:5]}")
