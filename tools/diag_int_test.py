#!/usr/bin/env python3
"""Test audio after Z80 interrupt fix."""
import urllib.request, json

BASE = "http://localhost:8093/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Run 10 frames for init
post("/emulator/step", {"frames": 10})

# Check Z80 command queue
z80 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d = bytes(z80["data"])
print(f"After 10 frames:")
print(f"  Z80 [0x22]={d[0x22]:02X} [0x24]={d[0x24]:02X} [0x25]={d[0x25]:02X} [0x27]={d[0x27]:02X}")
print(f"  Slots: {' '.join(f'{b:02X}' for b in d[0:8])}")

# Check audio
samples = get("/audio/samples") 
sdata = samples["samples"]
nonzero = sum(1 for s in sdata if s != 0)
total = len(sdata)
print(f"  Audio: {nonzero}/{total} non-zero samples")

# Run 200 more frames (title screen)
post("/emulator/step", {"frames": 200})
z80_2 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d2 = bytes(z80_2["data"])
print(f"\nAfter 210 frames:")
print(f"  Z80 [0x22]={d2[0x22]:02X} [0x24]={d2[0x24]:02X} [0x25]={d2[0x25]:02X} [0x27]={d2[0x27]:02X}")
samples2 = get("/audio/samples")
sdata2 = samples2["samples"]
nonzero2 = sum(1 for s in sdata2 if s != 0)
print(f"  Audio: {nonzero2}/{len(sdata2)} non-zero samples")
if nonzero2 > 0:
    nz_vals = [s for s in sdata2 if s != 0]
    print(f"  Sample range: min={min(nz_vals)}, max={max(nz_vals)}")
    print(f"  First 20 non-zero: {nz_vals[:20]}")

# Press Start
print("\nPressing Start...")
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
post("/emulator/step", {"frames": 200})

z80_3 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d3 = bytes(z80_3["data"])
print(f"\nAfter Start + 200 frames:")
print(f"  Z80 [0x22]={d3[0x22]:02X} [0x24]={d3[0x24]:02X} [0x25]={d3[0x25]:02X} [0x27]={d3[0x27]:02X}")
samples3 = get("/audio/samples")
sdata3 = samples3["samples"]
nonzero3 = sum(1 for s in sdata3 if s != 0)
print(f"  Audio: {nonzero3}/{len(sdata3)} non-zero samples")
if nonzero3 > 0:
    nz_vals3 = [s for s in sdata3 if s != 0]
    print(f"  Sample range: min={min(nz_vals3)}, max={max(nz_vals3)}")

# Check CPU state
cpu = get("/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"\n  M68K PC=${m68k['pc']:06X} SR=${m68k['sr']:04X}")
print(f"  Z80 PC=${cpu['cpu']['z80_pc']:04X}")

# Check APU for YM2612 activity
apu = get("/apu/state")
if "ym2612" in apu:
    ym = apu["ym2612"]
    for k in ["write_count", "total_writes", "channels"]:
        if k in ym:
            v = ym[k]
            if isinstance(v, (int, float)):
                print(f"  YM2612 {k}: {v}")

print("\nDone.")
