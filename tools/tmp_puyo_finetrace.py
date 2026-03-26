#!/usr/bin/env python3
"""Fine-grained Z80 trace to catch crash transition."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def main():
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})

    # Step to frame 295 quickly
    for f in range(295):
        api("/emulator/step", "POST", {"cycles": 896040})

    # Now step in smaller increments (~1/20 of a frame = ~45000 cycles)
    STEP = 45000
    step_count = 0
    prev_pc = None
    for i in range(200):
        api("/emulator/step", "POST", {"cycles": STEP})
        step_count += 1
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        iff1 = apu.get("z80_iff1", False)
        halted = apu.get("z80_halted", False)
        status = "OK" if z80_pc < 0x2000 else "MIRROR" if z80_pc < 0x4000 else "CRASH"
        
        # Only print when status changes or every 5 steps
        if z80_pc != prev_pc or status != "OK":
            frame_est = 295 + (step_count * STEP) / 896040
            print(f"Step {step_count:3d} (~frame {frame_est:.1f}): Z80 PC=0x{z80_pc:04X} iff1={iff1} halted={halted} [{status}]")
        
        if status == "MIRROR" or status == "CRASH":
            # Show Z80 trace ring  
            trace_ring = apu.get("z80_trace_ring", [])
            # Find the transition point in the trace
            idle_found = False
            crash_start = None
            for j, entry in enumerate(trace_ring):
                # Idle loop is at $116F-$1176
                if "$116" in entry or "$117" in entry:
                    if not idle_found:
                        idle_found = True
                        crash_start = j
                        print(f"\n  === Transition at trace index {j} ===")
                        # Show surrounding entries
                        for k in range(max(0, j-3), min(len(trace_ring), j+20)):
                            print(f"  {k:4d}: {trace_ring[k]}")
                        break
            
            if not idle_found:
                # The crash happened too long ago, show all unique entries
                print(f"\n  === No idle loop entries found in trace ring ===")
                print(f"  First 20 entries (newest):")
                for j in range(min(20, len(trace_ring))):
                    print(f"  {j:4d}: {trace_ring[j]}")
                print(f"  Last 20 entries (oldest):")
                for j in range(max(0, len(trace_ring)-20), len(trace_ring)):
                    print(f"  {j:4d}: {trace_ring[j]}")
            break
        prev_pc = z80_pc

if __name__ == "__main__":
    main()
