#!/usr/bin/env python3
"""Test: press Start to advance game, check for music commands."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

BTN_START = 0x80

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 120 frames for init
for _ in range(120):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
h0_before = len(apu.get("ym_histogram_port0_nonzero", []))
print(f"Before Start: frame={apu['vdp_frame']} ym_total={apu['ym_write_total']} hist0_regs={h0_before}")

# Press Start for 10 frames
post("/input/controller", {"player": 1, "buttons": BTN_START})
for _ in range(10):
    post("/emulator/step", {"frames": 1})

# Release Start, run 120 frames
post("/input/controller", {"player": 1, "buttons": 0})
for _ in range(120):
    post("/emulator/step", {"frames": 1})

apu2 = get("/apu/state")
print(f"After Start+wait: frame={apu2['vdp_frame']} ym_total={apu2['ym_write_total']}")
h0 = apu2.get("ym_histogram_port0_nonzero", [])
h1 = apu2.get("ym_histogram_port1_nonzero", [])
print(f"  Port 0 unique regs: {len(h0)}")
for h in h0:
    print(f"    {h}")
print(f"  Port 1 unique regs: {len(h1)}")
for h in h1:
    print(f"    {h}")

# Try another Start press
post("/input/controller", {"player": 1, "buttons": BTN_START})
for _ in range(10):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0})
for _ in range(300):
    post("/emulator/step", {"frames": 1})

apu3 = get("/apu/state")
print(f"\nAfter 2nd Start+wait: frame={apu3['vdp_frame']} ym_total={apu3['ym_write_total']}")
h0 = apu3.get("ym_histogram_port0_nonzero", [])
h1 = apu3.get("ym_histogram_port1_nonzero", [])
print(f"  Port 0 unique regs: {len(h0)}")
for h in h0:
    print(f"    {h}")
print(f"  Port 1 unique regs: {len(h1)}")
for h in h1:
    print(f"    {h}")

# Check Z80 command area
mem_1f = get(f"/cpu/memory?addr={0xA01F00}&len=64")
data = mem_1f.get("data", [])
cmd_hex = " ".join(f"{data[i]:02X}" for i in range(min(64, len(data))))
print(f"\n  Z80 RAM 0x1F00: {cmd_hex}")
