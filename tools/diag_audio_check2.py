#!/usr/bin/env python3
"""Quick check: audio samples after Z80 prefix fix."""
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

# Get audio samples (which also runs 1 frame for each frame requested)
data = get("/audio/samples?frames=120")
samples = data.get("samples", [])
print(f"Audio: {len(samples)} samples, sample_rate={data.get('sample_rate')}, channels={data.get('channels')}")

nonzero = sum(1 for s in samples if s != 0)
max_amp = max(abs(s) for s in samples) if samples else 0
min_amp = min(s for s in samples) if samples else 0

print(f"Nonzero: {nonzero}/{len(samples)}")
print(f"Range: {min_amp} to {max_amp}")

# Show some non-zero values
found = 0 
for i, s in enumerate(samples):
    if s != 0 and found < 10:
        print(f"  Sample[{i}] = {s}")
        found += 1
