#!/usr/bin/env python3
"""Test audio by properly draining stale samples first."""
import urllib.request, json

BASE = "http://localhost:8094/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Fresh load
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Run to title screen  
post("/emulator/step", {"frames": 100})
print("Title screen reached (100 frames)")

# Drain ALL accumulated audio (title silence)
for _ in range(50):
    get("/audio/samples")
print("Stale audio drained")

# Press Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
print("Start pressed")

# Run 100 frames to let music start
post("/emulator/step", {"frames": 100})
print("Ran 100 frames after Start")

# Now check fresh audio samples
samples = get("/audio/samples")
sdata = samples["samples"]
nonzero = sum(1 for s in sdata if s != 0)
total = len(sdata)
print(f"\nFresh audio: {nonzero}/{total} non-zero samples")

if nonzero > 0:
    nz = [s for s in sdata if s != 0]
    print(f"  Min: {min(nz):.6f}, Max: {max(nz):.6f}")
    print(f"  First 10 non-zero: {[f'{v:.4f}' for v in nz[:10]]}")
    # Show sample distribution
    abs_vals = [abs(s) for s in nz]
    print(f"  Avg absolute: {sum(abs_vals)/len(abs_vals):.6f}")
    # Show waveform snippet (first 40 samples)
    print(f"  Waveform (first 40):")
    for i in range(0, min(40, total), 2):
        l = sdata[i]
        r = sdata[i+1] if i+1 < total else 0
        bar_l = '#' * int(abs(l) * 50) if l != 0 else ''
        bar_r = '#' * int(abs(r) * 50) if r != 0 else ''
        print(f"    L:{l:+.4f} {bar_l}  R:{r:+.4f} {bar_r}")
else:
    print("  Still silent - checking buffer state...")
    apu = get("/apu/state")
    print(f"  audio_buffer_len: {apu.get('audio_buffer_len', 0)}")
    print(f"  fm_nonzero: {apu.get('debug_fm_nonzero', 0)}")
    print(f"  write_log_len: {apu.get('ym_write_log_len', 0)}")
    # Try getting MORE samples to clear old ones
    for batch in range(10):
        samples2 = get("/audio/samples")
        sdata2 = samples2["samples"]
        nz2 = sum(1 for s in sdata2 if s != 0)
        if nz2 > 0:
            print(f"  Batch {batch+1}: {nz2}/{len(sdata2)} non-zero!")
            nz_vals = [s for s in sdata2 if s != 0]
            print(f"    Range: {min(nz_vals):.6f} to {max(nz_vals):.6f}")
            break
        else:
            print(f"  Batch {batch+1}: still 0 ({len(sdata2)} samples)")

print("\nDone!")
