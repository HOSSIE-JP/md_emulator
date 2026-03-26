#!/usr/bin/env python3
"""Test Sonic audio."""
import urllib.request, json

BASE = "http://localhost:8080/api/v1"
def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

api("/emulator/load-rom-path", "POST", {"path": "roms/sonic.gen"})
# Step in smaller increments to avoid timeout
for i in range(10):
    api("/emulator/step", "POST", {"cycles": 896040 * 30})
apu = api("/apu/state")
z80_pc = apu.get("z80_pc", 0)
ym = apu.get("ym_write_total", 0)
channels = apu.get("channels", [])
audio = api("/audio/samples?frames=4096")
samples = audio.get("samples", [])
max_amp = max(abs(s) for s in samples) if samples else 0

print(f"Sonic at frame 300:")
print(f"  Z80 PC=0x{z80_pc:04X}, YM writes={ym}, audio max={max_amp:.4f}")
for i, ch in enumerate(channels):
    fnum = ch.get("fnum", 0)
    if fnum > 0:
        print(f"  CH{i+1}: fnum={fnum} block={ch.get('block',0)}")
nz = sum(1 for s in samples if abs(s) > 0.001)
print(f"  Audio samples: {len(samples)}, non-zero: {nz}")
