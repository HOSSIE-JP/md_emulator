#!/usr/bin/env python3
"""Check audio output after Z80 prefix instruction fix."""
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

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 120 frames to generate audio
for i in range(120):
    post("/emulator/step", {"frames": 1})

# Now drain A LOT of samples (120 frames * 800 samples/frame ~= 96000 stereo frames)
data = get("/audio/samples?frames=100000")
samples = data.get("samples", [])
print(f"Audio: {len(samples)} samples (={len(samples)//2} stereo frames)")

nonzero = sum(1 for s in samples if abs(s) > 0.001)
max_amp = max(abs(s) for s in samples) if samples else 0

print(f"Nonzero (>0.001): {nonzero}/{len(samples)}")
print(f"Max amplitude: {max_amp:.6f}")

# Show first 10 non-zero samples
found = 0
for i, s in enumerate(samples):
    if abs(s) > 0.001 and found < 10:
        ch = "L" if i % 2 == 0 else "R"
        print(f"  Sample[{i}] ({ch}) = {s:.6f}")
        found += 1

print(f"\n=== {'AUDIO IS WORKING!' if nonzero > 100 else 'Still silent...'} ===")
