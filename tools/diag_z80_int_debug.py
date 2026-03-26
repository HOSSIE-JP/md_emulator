#!/usr/bin/env python3
"""Comprehensive Z80 interrupt and YM write debugging."""
import urllib.request, json

BASE = "http://localhost:8094/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

def get_key_state():
    apu = get("/apu/state")
    return {
        "write_log_len": apu.get("ym_write_log_len", 0),
        "z80_pc": apu.get("z80_pc", 0),
        "z80_halted": apu.get("z80_halted", False),
        "z80_iff1": apu.get("z80_iff1", "?"),
        "z80_int_pending": apu.get("z80_int_pending", "?"),
        "z80_bank": apu.get("z80_bank_68k_addr", "?"),
        "vint_delivered": apu.get("vint_delivered", 0),
        "vdp_frame": apu.get("vdp_frame", 0),
        "fm_nonzero": apu.get("debug_fm_nonzero", 0),
    }

# Fresh load
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Step 1: Initial state
state = get_key_state()
print(f"\nAfter load (0 frames):")
for k, v in state.items():
    print(f"  {k}: {v}")

# Step 2: Run 5 frames
post("/emulator/step", {"frames": 5})
s1 = get_key_state()
print(f"\nAfter 5 frames:")
for k, v in s1.items():
    marker = " ***CHANGED***" if v != state.get(k) else ""
    print(f"  {k}: {v}{marker}")

# Step 3: Run 100 more frames (title screen fully up)
post("/emulator/step", {"frames": 100})
s2 = get_key_state()
print(f"\nAfter 105 frames:")
for k, v in s2.items():
    marker = " ***CHANGED***" if v != s1.get(k) else ""
    print(f"  {k}: {v}{marker}")

# Check the Z80 queue state before Start
z80q = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d = bytes(z80q["data"])
print(f"\n  Z80 queue [0-7]: {' '.join(f'{d[i]:02X}' for i in range(8))}")
print(f"  Z80 [0x22]={d[0x22]:02X} [0x24]={d[0x24]:02X} [0x25]={d[0x25]:02X} [0x27]={d[0x27]:02X}")

# Check YM write log state  
apu = get("/apu/state")
wlog = apu.get("ym_write_log_first100", [])
print(f"\n  YM write log length: {apu.get('ym_write_log_len', 0)}")
if len(wlog) > 34:
    print(f"  NEW writes after init (34+):")
    for i, entry in enumerate(wlog[34:]):
        print(f"    #{34+i}: {entry}")

# Step 4: Press Start
print("\n=== Pressing Start ===")
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})

s3 = get_key_state()
print(f"\nAfter Start + 5 frames:")
for k, v in s3.items():
    marker = " ***CHANGED***" if v != s2.get(k) else ""
    print(f"  {k}: {v}{marker}")

# Check queue immediately after Start
z80q2 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d2 = bytes(z80q2["data"])
print(f"  Z80 queue [0-7]: {' '.join(f'{d2[i]:02X}' for i in range(8))}")
print(f"  Z80 [0x22]={d2[0x22]:02X} [0x24]={d2[0x24]:02X} [0x25]={d2[0x25]:02X} [0x27]={d2[0x27]:02X}")

# Step 5: Run 50 more frames after Start
post("/emulator/step", {"frames": 50})
s4 = get_key_state()
print(f"\nAfter Start + 55 frames:")
for k, v in s4.items():
    marker = " ***CHANGED***" if v != s3.get(k) else ""
    print(f"  {k}: {v}{marker}")

# Step 6: Run 200 more frames  
post("/emulator/step", {"frames": 200})
s5 = get_key_state()
print(f"\nAfter Start + 255 frames:")
for k, v in s5.items():
    marker = " ***CHANGED***" if v != s4.get(k) else ""
    print(f"  {k}: {v}{marker}")

# Final: check full write log
apu_final = get("/apu/state")
wlog_final = apu_final.get("ym_write_log_first100", [])
log_len_final = apu_final.get("ym_write_log_len", 0)
print(f"\nFinal YM write log: {log_len_final} entries")
if log_len_final > 34:
    print("  NEW writes beyond init:")
    for i, entry in enumerate(wlog_final[34:min(50, len(wlog_final))]):
        print(f"    #{34+i}: {entry}")

# Check audio
samples = get("/audio/samples")
sdata = samples["samples"]
nonzero = sum(1 for s in sdata if s != 0)
print(f"\nAudio: {nonzero}/{len(sdata)} non-zero samples")

# Check M68K work RAM
gems = get("/cpu/memory", {"addr": 0xFF012C, "len": 16})
gd = bytes(gems["data"])
print(f"M68K work RAM $FF012C-$FF013B: {' '.join(f'{b:02X}' for b in gd)}")

# Read around bank area for Z80
z80_bank = get("/cpu/memory", {"addr": 0xA01F00, "len": 128})
bd = bytes(z80_bank["data"])
nonzero_bank = [(0x1F00+i, bd[i]) for i in range(len(bd)) if bd[i] != 0]
if nonzero_bank:
    print(f"\nZ80 work area $1F00-$1F7F (non-zero):")
    for addr, val in nonzero_bank[:30]:
        print(f"  ${addr:04X}: ${val:02X}")

print("\nDone.")
