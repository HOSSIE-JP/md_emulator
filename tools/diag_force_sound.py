"""Manually set $FF0067 bit 3 and check if sound starts playing"""
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
    r = api("POST", "/cpu/memory", {"addr": addr, "data": data})
    return r

def safe_int(v):
    return int(v, 16) if isinstance(v, str) else int(v)

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Fresh load
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("ROM loaded")

# Step to frame 200 (past init, game running normally)
api("POST", "/emulator/step", {"frames": 200})

# Check current $FF0067
flag = read_mem(0xFF0067, 1)[0]
print(f"Before: $FF0067 = 0x{flag:02X} (bit3={'SET' if flag & 8 else 'clr'})")

# Set bit 3 (OR with current value)
new_val = flag | 0x08
result = write_mem(0xFF0067, [new_val])
print(f"Write result: {result}")

# Verify
flag2 = read_mem(0xFF0067, 1)[0]
print(f"After:  $FF0067 = 0x{flag2:02X} (bit3={'SET' if flag2 & 8 else 'clr'})")

# Now also enable VINT in VDP register 1 (bit 5) so VBlank handler gets called
# Actually, let's NOT change VDP - just step and see if the game's own
# code path handles it. The VBlank handler checks this bit.
# But VINT is disabled, so the handler won't run!
# We need VINT to be enabled for the handler to call $D5B0.

# Check VDP reg 1
vdp = api("GET", "/vdp/registers")
regs = vdp.get("registers", vdp)
if isinstance(regs, list):
    reg1 = regs[1]
else:
    reg1 = regs.get("1", 0)
print(f"\nVDP Reg1 = 0x{reg1:02X} (VINT={'ON' if reg1 & 0x20 else 'OFF'})")

# VINT is off! We need to also enable it for the handler to run
# Set VDP reg 1 bit 5 via VDP control port write
# VDP register write: upper byte = 10xx_xxxx (set register), lower = data
# Reg 1: 0x81 | data → write 0x8100 | new_data  
# We need to write to VDP control port $C00004
new_reg1 = reg1 | 0x20  # enable VINT
# Write new_reg1 to VDP register 1: word = 0x8100 | new_reg1
vdp_cmd = 0x8100 | new_reg1
print(f"Setting VDP Reg1 = 0x{new_reg1:02X} (VINT ON) via VDP command 0x{vdp_cmd:04X}")
# Write to VDP control port ($C00004)
write_mem(0xC00004, [(vdp_cmd >> 8) & 0xFF, vdp_cmd & 0xFF])

# Verify VDP register changed
vdp2 = api("GET", "/vdp/registers")
regs2 = vdp2.get("registers", vdp2)
if isinstance(regs2, list):
    reg1b = regs2[1]
else:
    reg1b = regs2.get("1", 0)
print(f"VDP Reg1 after write = 0x{reg1b:02X} (VINT={'ON' if reg1b & 0x20 else 'OFF'})")

# Step 500 more frames and check sound
api("POST", "/emulator/step", {"frames": 500})

# Check APU state
apu = api("GET", "/apu/state")
bank = safe_int(apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", "0")))
bank_max = safe_int(apu.get("z80_bank_max_value", "0"))
z80_writes = safe_int(apu.get("z80_m68k_write_count", "0"))
ym_hist = apu.get("ym_write_histogram", {})
non_timer = {k: v for k, v in ym_hist.items() if k not in ("27", "2A", "2B")} if ym_hist else {}

print(f"\nF700: bank=0x{bank:06X} max=0x{bank_max:06X} z80w={z80_writes}")
print(f"  YM non-timer regs: {len(non_timer)}")
if non_timer:
    print(f"  FM regs: {dict(list(non_timer.items())[:15])}")

# Check $FF0067 - did it stay set?
flag3 = read_mem(0xFF0067, 1)[0]
print(f"  $FF0067 = 0x{flag3:02X}")

# Frame counter should be incrementing now
frame_ctr = read_mem(0xFF004C, 4)
fc = (frame_ctr[0]<<24) | (frame_ctr[1]<<16) | (frame_ctr[2]<<8) | frame_ctr[3]
print(f"  Frame counter = {fc}")

# Get CPU state
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"  PC=0x{m68k['pc']:06X}")

# Check Z80 bank
banked = apu.get("z80_banked_read_log", [])
print(f"  Z80 banked reads: {len(banked)}")
if banked:
    print(f"  First 5: {banked[:5]}")
