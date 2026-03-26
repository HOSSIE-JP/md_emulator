"""Deep audio diagnostic: load Puyo Puyo, run frames, inspect YM2612 state and audio output."""
import requests
import json
import math
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

def dump_ym_regs(bus_mem, base, label):
    """Read YM2612 registers from work RAM dump (not direct - use memory API)"""
    pass

print("=== Loading Puyo Puyo ROM ===")
resp = api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print(f"Load: {resp}")
api_post("/emulator/reset")

# Run enough frames to get into the game with music
print("\n=== Running 300 frames to reach music ===")
api_post("/emulator/step", {"frames": 300})

# Now read the YM2612 registers via memory bus reads
print("\n=== YM2612 Register Dump ===")

# Read YM2612 registers from emulator memory
# The APU state is not directly exposed via API, so let's read what we can
# First, check if there's an APU state endpoint
try:
    state = api_get("/apu/state")
    print("APU state endpoint found!")
    print(json.dumps(state, indent=2)[:3000])
except requests.exceptions.HTTPError as e:
    print(f"No /apu/state endpoint: {e}")

# Read I/O area to check Z80/YM2612 communication
# 0xA00000 = Z80 RAM, look for sound driver data
print("\n=== Z80 RAM (first 256 bytes) ===")
mem = api_get("/cpu/memory?addr=10485760&len=256")  # 0xA00000
z80_bytes = mem.get("data", [])
print(f"Z80 RAM dump (first 64): {z80_bytes[:64]}")

# Get CPU trace to see what registers the game is writing
print("\n=== CPU Trace (last entries) ===")
trace = api_get("/cpu/trace")
traces = trace.get("traces", [])
if traces:
    # Look for YM2612 writes (addresses 0xA04000-0xA04003)
    ym_writes = [t for t in traces if 'addr' in str(t) and 'A040' in str(t).upper()]
    print(f"Total trace entries: {len(traces)}")
    print(f"YM2612 writes in trace: {len(ym_writes)}")
    # Show last 10 trace entries
    for t in traces[-10:]:
        print(f"  {t}")

# Run more frames and collect audio
print("\n=== Running 60 more frames and collecting audio ===")
api_post("/emulator/step", {"frames": 60})
audio = api_get("/audio/samples?frames=4000")
samples = audio.get("samples", [])
print(f"Total audio samples: {len(samples)}")

if samples:
    nonzero = sum(1 for s in samples if abs(s) > 0.001)
    min_s = min(samples)
    max_s = max(samples)
    print(f"Non-zero samples: {nonzero}/{len(samples)} ({100.0*nonzero/len(samples):.1f}%)")
    print(f"Range: [{min_s:.6f}, {max_s:.6f}]")
    
    # RMS per chunk
    chunk_size = 800  # ~one frame worth of samples
    print(f"\nRMS per {chunk_size}-sample chunk:")
    for i in range(0, min(len(samples), 8000), chunk_size):
        chunk = samples[i:i+chunk_size]
        if chunk:
            rms = math.sqrt(sum(s*s for s in chunk) / len(chunk))
            bar = "#" * int(min(rms * 100, 60))
            print(f"  [{i//chunk_size:3d}] RMS={rms:.6f} {bar}")
    
    # Check for FM vs PSG contribution
    # L/R patterns: FM is stereo, PSG has fixed pan
    left_samples = samples[0::2]
    right_samples = samples[1::2]
    if left_samples and right_samples:
        l_rms = math.sqrt(sum(s*s for s in left_samples) / len(left_samples))
        r_rms = math.sqrt(sum(s*s for s in right_samples) / len(right_samples))
        print(f"\nLeft RMS:  {l_rms:.6f}")
        print(f"Right RMS: {r_rms:.6f}")
        
        # Check first 100 sample values
        print(f"\nFirst 20 stereo pairs:")
        for i in range(min(20, len(left_samples))):
            print(f"  [{i:3d}] L={left_samples[i]:+.6f}  R={right_samples[i]:+.6f}")

    # Verdict
    avg_abs = sum(abs(s) for s in samples) / len(samples) if samples else 0
    if avg_abs < 0.0001:
        print("\n>>> VERDICT: COMPLETELY SILENT")
    elif avg_abs < 0.001:
        print("\n>>> VERDICT: Nearly silent (very low amplitude)")
    elif nonzero < len(samples) * 0.1:
        print("\n>>> VERDICT: Mostly silent with occasional output")
    else:
        print(f"\n>>> VERDICT: Audio present (avg abs: {avg_abs:.6f})")
else:
    print("No audio samples!")

# Step one more frame and check audio buffer timing
print("\n=== Single frame audio check ===")
api_post("/emulator/step", {"frames": 1})
audio2 = api_get("/audio/samples?frames=800")
s2 = audio2.get("samples", [])
print(f"Samples after 1 frame: {len(s2)}")
if s2:
    nonz = sum(1 for s in s2 if abs(s) > 0.001)
    print(f"Non-zero: {nonz}/{len(s2)}")
