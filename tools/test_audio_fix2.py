#!/usr/bin/env python3
"""Test audio buffer fix on port 8096."""
import urllib.request, json, struct

BASE = "http://localhost:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

def get_audio():
    raw = urllib.request.urlopen(f"{BASE}/audio/samples").read()
    if len(raw) < 2:
        return []
    return struct.unpack(f"<{len(raw)//2}h", raw)

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Title screen
post("/emulator/step", {"frames": 100})
samples = get_audio()
nz = sum(1 for s in samples if s != 0)
print(f"Title: {len(samples)} samples, {nz} non-zero")

# Press Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})

# Run gameplay and check audio each batch
for batch in range(10):
    post("/emulator/step", {"frames": 20})
    samples = get_audio()
    nz = sum(1 for s in samples if s != 0)
    peak = max((abs(s) for s in samples), default=0)
    print(f"Batch {batch}: {len(samples)} samples, {nz} non-zero, peak={peak}")

# APU state
apu = get("/apu/state")
for k in ["debug_output_nonzero", "debug_output_total", "last_fm_left", "last_fm_right", "audio_buffer_len"]:
    print(f"  {k}: {apu.get(k)}")
