#!/usr/bin/env python3
"""Test: Check if Z80 command register clears after fix, and check audio."""
import json
import urllib.request
import os

BASE = "http://127.0.0.1:8089"

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_memory(addr, length):
    return api("GET", f"/api/v1/cpu/memory?addr={addr}&len={length}")

# Load ROM
abs_path = os.path.abspath("roms/puyo.bin")
api("POST", "/api/v1/emulator/load-rom-path", {"path": abs_path})
print("ROM loaded")

# Run frames and check Z80 state
for frame in range(1, 11):
    api("POST", "/api/v1/emulator/step", {"frames": 1})
    z80 = get_memory(0xA00020, 16)
    val27 = z80['data'][7]  # offset 7 = 0x27
    val24 = z80['data'][4]  # offset 4 = 0x24
    val26 = z80['data'][6]  # offset 6 = 0x26
    status = "0x27_CLEARED" if val27 == 0 else f"0x27=0x{val27:02X}"
    print(f"Frame {frame:2d}: [24]={val24:02X} [26]={val26:02X} [27]={val27:02X} {status}")

# Run more frames with Start button pressed
print("\nPressing START...")
api("POST", "/api/v1/input/controller", {"player": 1, "buttons": 128})

for frame in range(11, 211):
    api("POST", "/api/v1/emulator/step", {"frames": 1})
    if frame % 20 == 0:
        z80 = get_memory(0xA00020, 16)
        val27 = z80['data'][7]
        print(f"Frame {frame:3d}: [27]={val27:02X}")

# Check audio samples
audio = api("GET", "/api/v1/audio/samples")
samples = audio.get("samples", [])
nonzero = sum(1 for s in samples if s != 0 and s != 0x8000 and s != -32768)
print(f"\nAudio: {len(samples)} samples, {nonzero} non-zero")

# Check APU state
apu = api("GET", "/api/v1/apu/state")
if "ym2612" in apu:
    ym = apu["ym2612"]
    print(f"YM2612 write_count: {ym.get('write_count', '?')}")
    print(f"YM2612 nonzero FM: {ym.get('nonzero_fm_samples', '?')}")
    print(f"YM2612 nonzero DAC: {ym.get('nonzero_dac_samples', '?')}")
