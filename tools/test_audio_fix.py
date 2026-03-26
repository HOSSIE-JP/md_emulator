"""Test audio output after EG counter shift / SSG-EG fixes."""
import requests
import json
import struct
import sys

BASE = "http://127.0.0.1:8080/api/v1"

def api_get(path):
    r = requests.get(f"{BASE}{path}")
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{BASE}{path}", json=data or {})
    r.raise_for_status()
    return r.json()

# 1. Load Puyo Puyo ROM
print("=== Loading ROM ===")
resp = api_post("/emulator/load-rom-path", {"path": "roms/s_a_t_d.smd"})
print(f"Load: {resp}")

# 2. Reset
api_post("/emulator/reset")

# 3. Run 300 frames (about 5 seconds) to get past the title screen into music
print("\n=== Running 300 frames ===")
api_post("/emulator/step", {"frames": 300})

# 4. Get audio samples (run additional frames to collect audio)
print("\n=== Collecting audio samples ===")
api_post("/emulator/step", {"frames": 60})
audio = api_get("/audio/samples?frames=4000")
samples = audio.get("samples", [])
print(f"Sample rate: {audio.get('sample_rate')}")
print(f"Channels: {audio.get('channels')}")
print(f"Total samples: {len(samples)}")

if samples:
    # Analyze audio
    import math
    
    # Check for silence
    nonzero = sum(1 for s in samples if s != 0)
    print(f"\nNon-zero samples: {nonzero} / {len(samples)} ({100*nonzero/len(samples):.1f}%)")
    
    # Check amplitude range
    min_s = min(samples)
    max_s = max(samples)
    print(f"Min sample: {min_s}")
    print(f"Max sample: {max_s}")
    
    # Check for clipping (excessive noise would show many max/min values)
    clipped = sum(1 for s in samples if abs(s) > 30000)
    print(f"Clipped samples (|s|>30000): {clipped}")
    
    # Calculate RMS in chunks to check for music-like variation
    chunk_size = 1000
    rms_values = []
    for i in range(0, min(len(samples), 20000), chunk_size):
        chunk = samples[i:i+chunk_size]
        if chunk:
            rms = math.sqrt(sum(s*s for s in chunk) / len(chunk))
            rms_values.append(rms)
    
    print(f"\nRMS per {chunk_size}-sample chunk (first {len(rms_values)} chunks):")
    for i, rms in enumerate(rms_values):
        bar = "#" * int(rms / 500)
        print(f"  [{i:3d}] RMS={rms:8.1f} {bar}")
    
    # Check if there's variety in amplitude (music) vs constant (noise/silence)
    if rms_values:
        avg_rms = sum(rms_values) / len(rms_values)
        rms_std = math.sqrt(sum((r - avg_rms)**2 for r in rms_values) / len(rms_values))
        print(f"\nAvg RMS: {avg_rms:.1f}")
        print(f"RMS StdDev: {rms_std:.1f}")
        
        if avg_rms < 100:
            print("\n>>> VERDICT: Audio is mostly SILENT")
        elif rms_std < avg_rms * 0.1:
            print("\n>>> VERDICT: Audio may be NOISE (constant amplitude)")
        else:
            print("\n>>> VERDICT: Audio has VARIATION (likely music!)")
else:
    print("No samples returned!")

# 5. Check YM2612 register state
print("\n=== APU State ===")
try:
    apu = api_get("/apu/state")
    if "error" not in apu:
        print(json.dumps(apu, indent=2)[:2000])
    else:
        print(f"APU state error: {apu}")
except Exception as e:
    print(f"Could not get APU state: {e}")
