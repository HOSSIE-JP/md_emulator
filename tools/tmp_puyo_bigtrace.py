#!/usr/bin/env python3
"""Capture Z80 crash transition with large trace ring (32K entries)."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

def main():
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})

    # Step to frame 295 (crash is between 250-301)
    # From earlier test: frame 250 PC=0x2FB1, frame 301 PC=0x4B27 CRASH
    # Let's step to 295 with full frames, then get trace
    for f in range(295):
        api("/emulator/step", "POST", {"cycles": 896040})
    
    # Step one more frame
    api("/emulator/step", "POST", {"cycles": 896040})
    
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    print(f"Frame 296: Z80 PC=0x{z80_pc:04X}")
    
    trace_ring = apu.get("z80_trace_ring", [])
    print(f"Trace ring size: {len(trace_ring)}")
    
    # Search for the transition from idle loop to crash
    # Idle loop entries have PC in $116F-$1176
    # Also look for INT handler entries ($0038)
    idle_entries = []
    int_entries = []
    first_bad = None
    
    for i, entry in enumerate(trace_ring):
        if "$116" in entry or "$117" in entry:
            idle_entries.append(i)
        if "$0038" in entry or "INT" in entry:
            int_entries.append(i)
        if first_bad is None and any(x in entry for x in ["$1FE", "$1FF", "$200", "$201", "$202", "$203", "$204", "$205"]):
            pass  # These could be sequential crash execution
    
    if idle_entries:
        # Found idle loop entries! Show the transition
        last_idle = idle_entries[0]  # newest idle entry (entries are newest-first)
        print(f"\nLast idle loop at index {last_idle}")
        print("=== Transition from idle to crash ===")
        # Show from a few entries before the transition to a few after
        for i in range(last_idle + 5, max(0, last_idle - 50), -1):
            if i < len(trace_ring):
                marker = "  "
                entry = trace_ring[i]
                if "$116" in entry or "$117" in entry:
                    marker = ">>IDLE "
                elif "INT" in entry or "$0038" in entry:
                    marker = ">>INT  "
                print(f"  {marker}{i:5d}: {entry}")
    else:
        print("\nNo idle loop entries found even with 32K trace ring!")
        # Show the OLDEST entries (closest to the transition)
        print("Oldest 100 entries:")
        for i in range(max(0, len(trace_ring)-100), len(trace_ring)):
            print(f"  {i:5d}: {trace_ring[i]}")
    
    if int_entries:
        print(f"\nINT handler entries found at indices: {int_entries[:20]}")
        # Show context around first INT entry
        for idx in int_entries[:3]:
            print(f"  Context around INT at index {idx}:")
            for i in range(idx + 3, max(0, idx - 10), -1):
                if i < len(trace_ring):
                    print(f"    {i:5d}: {trace_ring[i]}")
    else:
        print("\nNo INT handler entries found!")

if __name__ == "__main__":
    main()
