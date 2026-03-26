#!/usr/bin/env python3
"""Deeper audio test: run more frames, check M68K sound state, YM writes."""
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

# Load and run
abs_path = os.path.abspath("roms/puyo.bin")
api("POST", "/api/v1/emulator/load-rom-path", {"path": abs_path})

# Run 60 frames (1 second), then start pressing buttons
api("POST", "/api/v1/emulator/step", {"frames": 60})
print("After 60 frames (title screen):")
z80 = get_memory(0xA00020, 16)
print(f"  Z80 comm: {[f'{b:02X}' for b in z80['data']]}")

# Check work RAM for sound-related data
wram = get_memory(0xFF0120, 32)
print(f"  Work RAM $FF0120-$FF013F: {[f'{b:02X}' for b in wram['data']]}")

# Try pressing Start
api("POST", "/api/v1/input/controller", {"player": 1, "buttons": 128})
api("POST", "/api/v1/emulator/step", {"frames": 5})
api("POST", "/api/v1/input/controller", {"player": 1, "buttons": 0})
api("POST", "/api/v1/emulator/step", {"frames": 60})

print("\nAfter 125 frames (Start pressed):")
z80 = get_memory(0xA00020, 16)
print(f"  Z80 comm: {[f'{b:02X}' for b in z80['data']]}")
wram = get_memory(0xFF0120, 32)
print(f"  Work RAM $FF0120-$FF013F: {[f'{b:02X}' for b in wram['data']]}")

# Press Start again
api("POST", "/api/v1/input/controller", {"player": 1, "buttons": 128})
api("POST", "/api/v1/emulator/step", {"frames": 5})
api("POST", "/api/v1/input/controller", {"player": 1, "buttons": 0})
api("POST", "/api/v1/emulator/step", {"frames": 120})

print("\nAfter 250 frames (Start pressed twice):")
z80 = get_memory(0xA00020, 16)
print(f"  Z80 comm: {[f'{b:02X}' for b in z80['data']]}")
wram = get_memory(0xFF0120, 32)
print(f"  Work RAM $FF0120-$FF013F: {[f'{b:02X}' for b in wram['data']]}")

# Run 300 more frames for gameplay 
api("POST", "/api/v1/emulator/step", {"frames": 300})

# Check audio
audio = api("GET", "/api/v1/audio/samples")
samples = audio.get("samples", [])
nonzero = sum(1 for s in samples if s != 0 and s != 0x8000 and s != -32768)
print(f"\nAudio after 550 frames: {len(samples)} samples, {nonzero} non-zero")

apu = api("GET", "/api/v1/apu/state")
if isinstance(apu, dict):
    for k, v in apu.items():
        if isinstance(v, dict):
            print(f"  {k}: write_count={v.get('write_count','?')}, nonzero_fm={v.get('nonzero_fm_samples','?')}, nonzero_dac={v.get('nonzero_dac_samples','?')}")

# Final Z80 comm check
z80 = get_memory(0xA00020, 16)
print(f"\nFinal Z80 comm: {[f'{b:02X}' for b in z80['data']]}")
