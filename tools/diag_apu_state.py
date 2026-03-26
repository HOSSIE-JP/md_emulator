#!/usr/bin/env python3
"""Diagnose APU state after running Puyo Puyo for some frames."""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# 1. Load ROM
print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# 2. Check initial APU state
apu0 = get("/apu/state")
print(f"\n=== INITIAL APU STATE ===")
print(f"  ym_write_total: {apu0.get('ym_write_total', 'N/A')}")
print(f"  z80_bus_requested: {apu0.get('z80_bus_requested')}")
print(f"  z80_reset: {apu0.get('z80_reset')}")

# 3. Run 10 frames
print("\nRunning 10 frames...")
for i in range(10):
    post("/emulator/step", {"frames": 1})

apu10 = get("/apu/state")
print(f"\n=== APU STATE AFTER 10 FRAMES ===")
print(f"  ym_write_total: {apu10.get('ym_write_total', 'N/A')}")
print(f"  z80_bus_requested: {apu10.get('z80_bus_requested')}")
print(f"  z80_reset: {apu10.get('z80_reset')}")
print(f"  audio_buffer_len: {apu10.get('audio_buffer_len')}")
print(f"  dac_enabled: {apu10.get('dac_enabled')}")
print(f"  eg_counter: {apu10.get('eg_counter')}")
print(f"  status: {apu10.get('status')}")
print(f"  reg27: {apu10.get('reg27')}")
print(f"  regs_port0_b4_b6: {apu10.get('regs_port0_b4_b6')}")
print(f"  regs_port1_b4_b6: {apu10.get('regs_port1_b4_b6')}")

# Print channel details
for i, ch in enumerate(apu10.get("channels", [])):
    pan = f"L={ch['pan_left']} R={ch['pan_right']}"
    freq = f"fnum={ch['fnum']} block={ch['block']}"
    alg = f"alg={ch['algorithm']} fb={ch['feedback']}"
    ops = ch.get("operators", [])
    key_info = " ".join([f"op{j}(key={o['key_on']},att={o['attenuation']},ph={o['env_phase']})" for j, o in enumerate(ops)])
    print(f"  CH{i}: {pan} {freq} {alg} {key_info}")

# 4. Run more frames (total 120)
print("\nRunning 110 more frames (total 120)...")
for i in range(110):
    post("/emulator/step", {"frames": 1})

apu120 = get("/apu/state")
print(f"\n=== APU STATE AFTER 120 FRAMES ===")
print(f"  ym_write_total: {apu120.get('ym_write_total', 'N/A')}")
print(f"  z80_bus_requested: {apu120.get('z80_bus_requested')}")
print(f"  z80_reset: {apu120.get('z80_reset')}")
print(f"  dac_enabled: {apu120.get('dac_enabled')}")
print(f"  status: {apu120.get('status')}")
print(f"  reg27: {apu120.get('reg27')}")
print(f"  regs_port0_b4_b6: {apu120.get('regs_port0_b4_b6')}")
print(f"  regs_port1_b4_b6: {apu120.get('regs_port1_b4_b6')}")
print(f"  psg_volumes: {apu120.get('psg_volumes')}")

for i, ch in enumerate(apu120.get("channels", [])):
    pan = f"L={ch['pan_left']} R={ch['pan_right']}"
    freq = f"fnum={ch['fnum']} block={ch['block']}"
    alg = f"alg={ch['algorithm']} fb={ch['feedback']}"
    ops = ch.get("operators", [])
    key_info = " ".join([f"op{j}(key={o['key_on']},att={o['attenuation']},ph={o['env_phase']})" for j, o in enumerate(ops)])
    print(f"  CH{i}: {pan} {freq} {alg} {key_info}")

# 5. Check audio samples
samples_resp = get("/audio/samples?frames=800")
samples = samples_resp.get("samples", [])
nonzero = sum(1 for s in samples if abs(s) > 1e-6)
print(f"\n=== AUDIO OUTPUT ===")
print(f"  Total samples: {len(samples)}")
print(f"  Non-zero: {nonzero}")
if nonzero > 0:
    maxval = max(abs(s) for s in samples)
    print(f"  Max amplitude: {maxval:.6f}")
    for i, s in enumerate(samples[:20]):
        print(f"    sample[{i}] = {s:.6f}")

# 6. Run 240 more frames (total 360)
print("\nRunning 240 more frames (total 360)...")
for i in range(240):
    post("/emulator/step", {"frames": 1})

apu360 = get("/apu/state")
print(f"\n=== APU STATE AFTER 360 FRAMES ===")
print(f"  ym_write_total: {apu360.get('ym_write_total', 'N/A')}")
print(f"  z80_bus_requested: {apu360.get('z80_bus_requested')}")
print(f"  z80_reset: {apu360.get('z80_reset')}")

for i, ch in enumerate(apu360.get("channels", [])):
    pan = f"L={ch['pan_left']} R={ch['pan_right']}"
    freq = f"fnum={ch['fnum']} block={ch['block']}"
    alg = f"alg={ch['algorithm']} fb={ch['feedback']}"
    ops = ch.get("operators", [])
    key_info = " ".join([f"op{j}(key={o['key_on']},att={o['attenuation']},ph={o['env_phase']})" for j, o in enumerate(ops)])
    print(f"  CH{i}: {pan} {freq} {alg} {key_info}")

samples2 = get("/audio/samples?frames=800").get("samples", [])
nonzero2 = sum(1 for s in samples2 if abs(s) > 1e-6)
print(f"\n  Audio (frame 120-360): {len(samples2)} samples, {nonzero2} non-zero")

print("\n=== DONE ===")
