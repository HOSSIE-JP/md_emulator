#!/usr/bin/env python3
"""Quick Z80 crash test with old code - use cpu state endpoint."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})

    for f in range(1, 420):
        api("/emulator/step", "POST", {"cycles": 896040})
        if f % 50 == 0 or (f >= 295 and f <= 310):
            cpu = api("/cpu/state")
            z80_pc = cpu.get("z80_pc", cpu.get("z80", {}).get("pc", 0))
            if z80_pc == 0:
                # Try to find it in the response
                if "z80" in cpu:
                    z80_pc = cpu["z80"].get("pc", 0)
                elif "z80_pc" in cpu:
                    z80_pc = cpu["z80_pc"]
            status = "OK" if z80_pc < 0x4000 else "CRASH"
            print(f"Frame {f:3d}: Z80 PC=0x{z80_pc:04X} [{status}]")
            if z80_pc >= 0x4000:
                break
    
    # Get audio samples at frame 420
    audio = api("/audio/samples", "POST", {"frames": 1600})
    if "data" in audio:
        samples = audio["data"]
        max_val = max(abs(s) for s in samples) if samples else 0
        nonzero = sum(1 for s in samples if abs(s) > 0.001)
        print(f"\nAudio: {len(samples)} samples, max={max_val:.4f}, nonzero={nonzero}")
    elif "error" in audio:
        print(f"Audio error: {audio['error']}")

if __name__ == "__main__":
    main()
