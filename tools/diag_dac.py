#!/usr/bin/env python3
"""Check DAC rendering debug counters."""
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

# Run 120 frames
for _ in range(120):
    post("/emulator/step", {"frames": 1})

# Press Start
post("/input/controller", {"player": 1, "buttons": BTN_START})
for _ in range(10):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0})

# Run 300 more frames
for _ in range(300):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print(f"Frame: {apu['vdp_frame']}")
print(f"YM write total: {apu['ym_write_total']}")
print(f"DAC enabled: {apu['dac_enabled']}")
print(f"DAC data: {apu['dac_data']}")
print()
print(f"debug_fm_ticks: {apu.get('debug_fm_ticks', 'N/A')}")
print(f"debug_fm_nonzero: {apu.get('debug_fm_nonzero', 'N/A')}")
print(f"debug_dac_samples: {apu.get('debug_dac_samples', 'N/A')}")
print(f"debug_dac_nonzero: {apu.get('debug_dac_nonzero', 'N/A')}")
print()

# Check audio buffer
audio = get("/audio/samples")
samples = audio.get("samples", [])
nonzero = sum(1 for s in samples if abs(s) > 0.0001)
if samples:
    max_val = max(abs(s) for s in samples)
else:
    max_val = 0
print(f"Audio samples: {len(samples)}, nonzero: {nonzero}, max: {max_val:.6f}")
print()

# Check channel 5 panning (DAC channel)
channels = apu.get("channels", [])
if len(channels) > 5:
    ch5 = channels[5]
    print(f"Channel 5 (DAC): pan_left={ch5['pan_left']} pan_right={ch5['pan_right']}")
    print(f"  fnum={ch5['fnum']} block={ch5['block']} algo={ch5['algorithm']}")
