#!/usr/bin/env python3
"""Check buffer latency after Start press."""
import urllib.request, json

BASE = "http://localhost:8080/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())

def get_audio():
    raw = urllib.request.urlopen(f"{BASE}/audio/samples").read()
    return json.loads(raw).get("samples", [])

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Title screen
post("/emulator/step", {"frames": 100})
get_audio()  # drain

# Press Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})

# Check audio latency frame by frame after Start
for i in range(20):
    post("/emulator/step", {"frames": 10})
    apu = get("/apu/state")
    samples = get_audio()
    nz = sum(1 for s in samples if abs(s) > 0.001)
    buflen = apu.get("audio_buffer_len", 0)
    fm_nz = apu.get("debug_output_nonzero", 0)
    print(f"  +{(i+1)*10:3d}f: buf={buflen:6d} fm_nz={fm_nz:6d} got={len(samples):4d} nz={nz}")
