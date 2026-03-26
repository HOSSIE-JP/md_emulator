#!/usr/bin/env python3
"""Check Z80 queue, YM2612 state, and audio after running."""
import urllib.request, json, struct

BASE = "http://localhost:8091/api/v1"

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Z80 command queue
z80 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
d = bytes(z80["data"])
print("=== Z80 Command Queue ===")
print("Slots [0x00..0x07]:", " ".join(f"{b:02X}" for b in d[0:8]))
print("Param1 [0x08..0x0F]:", " ".join(f"{b:02X}" for b in d[8:16]))
print("Param2 [0x10..0x17]:", " ".join(f"{b:02X}" for b in d[16:24]))
print(f"  [0x20]={d[0x20]:02X} [0x21]={d[0x21]:02X} [0x22]={d[0x22]:02X} [0x23]={d[0x23]:02X}")
print(f"  [0x24]={d[0x24]:02X} [0x25]={d[0x25]:02X} [0x26]={d[0x26]:02X} [0x27]={d[0x27]:02X}")

# Check CPU state
cpu = get("/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"\nM68K PC=${m68k['pc']:06X} SR=${m68k['sr']:04X}")
print(f"Z80 PC=${cpu['cpu']['z80_pc']:04X}")

# Check APU state
apu = get("/apu/state")
print("\n=== APU State ===")
if "ym2612" in apu:
    ym = apu["ym2612"]
    for k, v in sorted(ym.items()):
        if isinstance(v, (int, float, str, bool)):
            print(f"  {k}: {v}")
        elif isinstance(v, list) and len(v) <= 20:
            print(f"  {k}: {v}")
        elif isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
if "psg" in apu:
    print(f"  PSG: {apu['psg']}")

# Check audio samples
samples = get("/audio/samples")
print("\n=== Audio ===")
sk = list(samples.keys())
print(f"  Keys: {sk}")
if "samples" in samples:
    sdata = samples["samples"]
    if isinstance(sdata, list):
        nonzero = sum(1 for s in sdata if s != 0)
        print(f"  {nonzero}/{len(sdata)} non-zero samples")
        if nonzero > 0:
            first_nz = next(i for i, s in enumerate(sdata) if s != 0)
            print(f"  First non-zero at index {first_nz}: {sdata[first_nz]}")
elif "left" in samples:
    left = samples["left"]
    right = samples["right"]
    nz_l = sum(1 for s in left if s != 0)
    nz_r = sum(1 for s in right if s != 0)
    print(f"  Left: {nz_l}/{len(left)} non-zero, Right: {nz_r}/{len(right)} non-zero")
elif "data" in samples:
    raw = bytes(samples["data"])
    nonzero = sum(1 for i in range(0, len(raw), 2) if struct.unpack_from("<h", raw, i)[0] != 0)
    print(f"  {nonzero}/{len(raw)//2} non-zero samples")
else:
    print(f"  Unknown format, first 5 items: {dict(list(samples.items())[:5])}")
