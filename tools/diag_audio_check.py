#!/usr/bin/env python3
"""Quick check: audio buffer after Z80 prefix fix."""
import urllib.request, json, struct

BASE = "http://127.0.0.1:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get_raw(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return r.read()

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 120 frames
for _ in range(120):
    post("/emulator/step", {"frames": 1})

# Get audio buffer
audio = get_raw("/audio/buffer")
n_samples = len(audio) // 4  # stereo 16-bit = 4 bytes per sample pair
print(f"Audio buffer: {len(audio)} bytes = {n_samples} sample pairs")

samples_l = []
samples_r = []
for i in range(n_samples):
    l, r = struct.unpack_from('<hh', audio, i * 4)
    samples_l.append(l)
    samples_r.append(r)

nonzero_l = sum(1 for s in samples_l if s != 0)
nonzero_r = sum(1 for s in samples_r if s != 0)
max_l = max(abs(s) for s in samples_l) if samples_l else 0
max_r = max(abs(s) for s in samples_r) if samples_r else 0

print(f"Left:  {nonzero_l}/{n_samples} nonzero, max amplitude={max_l}")
print(f"Right: {nonzero_r}/{n_samples} nonzero, max amplitude={max_r}")

# Show first few non-zero samples
found = 0
for i, (l, r) in enumerate(zip(samples_l, samples_r)):
    if l != 0 or r != 0:
        if found < 5:
            print(f"  Sample {i}: L={l} R={r}")
        found += 1

print(f"Total nonzero sample pairs: {found}")
