#!/usr/bin/env python3
"""Check audio quality: DC offset, noise floor, waveform shape."""
import urllib.request, json, struct, math

BASE = "http://localhost:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

def get_audio():
    raw = urllib.request.urlopen(f"{BASE}/audio/samples").read()
    data = json.loads(raw)
    return data.get("samples", [])

def analyze(label, samples):
    if not samples:
        print(f"  {label}: no samples"); return
    n = len(samples)
    # Split L/R
    left = [samples[i] for i in range(0, n, 2)]
    right = [samples[i] for i in range(1, n, 2)]
    for ch, data in [("L", left), ("R", right)]:
        mn, mx = min(data), max(data)
        avg = sum(data) / len(data)
        rms = math.sqrt(sum(s*s for s in data) / len(data))
        nz = sum(1 for s in data if abs(s) > 0.001)
        print(f"  {label} {ch}: min={mn:.4f} max={mx:.4f} avg={avg:.4f} rms={rms:.4f} nonzero={nz}/{len(data)}")

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
get_audio()  # drain any stale

# Before any frames
samples = get_audio()
analyze("Pre-frame", samples)

# Run 10 frames
post("/emulator/step", {"frames": 10})
samples = get_audio()
analyze("10 frames", samples)

# Run 90 more (title screen, no music expected)
post("/emulator/step", {"frames": 90})
samples = get_audio()
analyze("100 frames (title)", samples)

# Press Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})

# Music frames
post("/emulator/step", {"frames": 50})
samples = get_audio()
analyze("Start+55 (music)", samples)

post("/emulator/step", {"frames": 100})
samples = get_audio()
analyze("Start+155 (music)", samples)

# First 20 sample values
if samples:
    print(f"\n  First 20 values: {[f'{s:.5f}' for s in samples[:20]]}")
