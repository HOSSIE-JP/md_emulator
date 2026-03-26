#!/usr/bin/env python3
"""Verify Puyo Puyo BGM improvement with fixed FM synthesis."""
import urllib.request
import json
import time

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    # Load ROM
    print("Loading Puyo Puyo ROM...")
    r = api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    print(f"  Load: {r}")

    # Advance to frame 420+ where BGM starts
    print("\nAdvancing to frame 420...")
    for f in range(420):
        api("/emulator/step", "POST", {"cycles": 896040})

    # Get APU state at frame 420
    apu = api("/apu/state")
    if "error" in apu:
        print(f"  APU error: {apu}")
        return
    
    channels = apu.get("channels", [])
    print(f"\n=== APU State at Frame 420 ===")
    for i, ch in enumerate(channels):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        algo = ch.get("algorithm", 0)
        fb = ch.get("feedback", 0)
        key_on_ops = sum(1 for op in ch.get("operators", []) if op.get("key_on", False))
        att_vals = [op.get("attenuation", 1023) for op in ch.get("operators", [])]
        phases = [op.get("env_phase", "?") for op in ch.get("operators", [])]
        print(f"  CH{i+1}: fnum={fnum:4d} block={block} algo={algo} fb={fb} keys={key_on_ops}/4 att={att_vals} phases={phases}")

    # Now collect some audio samples and analyze quality
    print("\n=== Audio Quality Check (5 frames) ===")
    for test_frame in range(5):
        api("/emulator/step", "POST", {"cycles": 896040})
        samples_resp = api("/audio/samples?count=800")
        samples = samples_resp.get("samples", [])
        if not samples:
            print(f"  Frame {420+test_frame+1}: No samples!")
            continue
        
        # Analyze sample statistics
        nonzero = sum(1 for s in samples if s != 0)
        if samples:
            abs_vals = [abs(s) for s in samples]
            max_val = max(abs_vals)
            avg_val = sum(abs_vals) / len(abs_vals)
            # Count zero-crossing rate (indicator of frequency content)
            zero_crossings = 0
            for j in range(1, len(samples)):
                if (samples[j] > 0 and samples[j-1] <= 0) or (samples[j] < 0 and samples[j-1] >= 0):
                    zero_crossings += 1
            # Check for clipping
            clipped = sum(1 for s in samples if abs(s) > 0.95)
            print(f"  Frame {420+test_frame+1}: samples={len(samples)} nz={nonzero}/{len(samples)} "
                  f"max={max_val:.4f} avg={avg_val:.4f} zero_cross={zero_crossings} clipped={clipped}")
        
    # Check Z80 command byte to verify BGM is playing
    z80_ram = api("/cpu/memory?addr=0&len=40&type=z80")
    cmd_byte = z80_ram.get("data", [0]*0x28)[0x27] if len(z80_ram.get("data", [])) > 0x27 else 0
    print(f"\n  Z80 cmd byte ($0027): 0x{cmd_byte:02X}")
    
    # Run 60 more frames and check channel activity is sustained
    print("\n=== Extended playback test (60 frames) ===")
    total_nz = 0
    total_samples = 0
    for f in range(60):
        api("/emulator/step", "POST", {"cycles": 896040})
        samples_resp = api("/audio/samples?count=800")
        samples = samples_resp.get("samples", [])
        total_samples += len(samples)
        total_nz += sum(1 for s in samples if s != 0)
    
    print(f"  Total samples: {total_samples}, non-zero: {total_nz}")
    if total_samples > 0:
        print(f"  Non-zero ratio: {total_nz/total_samples:.1%}")
    
    # Final APU state
    apu2 = api("/apu/state")
    channels2 = apu2.get("channels", [])
    print(f"\n=== APU State at Frame ~545 ===")
    for i, ch in enumerate(channels2):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        key_on_ops = sum(1 for op in ch.get("operators", []) if op.get("key_on", False))
        att_vals = [op.get("attenuation", 1023) for op in ch.get("operators", [])]
        phases = [op.get("env_phase", "?") for op in ch.get("operators", [])]
        print(f"  CH{i+1}: fnum={fnum:4d} block={block} keys={key_on_ops}/4 att={att_vals} phases={phases}")

    print("\nDone!")

if __name__ == "__main__":
    main()
