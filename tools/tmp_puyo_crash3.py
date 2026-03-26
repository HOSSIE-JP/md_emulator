#!/usr/bin/env python3
"""Get full Z80 trace at crash frame 301."""
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

    # Step to frame 300 (just before crash)
    for f in range(300):
        api("/emulator/step", "POST", {"cycles": 896040})

    apu = api("/apu/state")
    print(f"Frame 300: Z80 PC=0x{apu.get('z80_pc',0):04X}")
    
    # Get pre-crash trace
    trace_ring = apu.get("z80_trace_ring", [])
    print(f"\n=== TRACE AT FRAME 300 (Z80 still at 0x{apu.get('z80_pc',0):04X}) ===")
    print(f"Trace ring size: {len(trace_ring)}")
    for i, entry in enumerate(trace_ring[:100]):
        print(f"  {i:3d}: {entry}")

    # Now step one more frame to trigger crash
    api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    print(f"\nFrame 301: Z80 PC=0x{z80_pc:04X}")
    
    trace_ring = apu.get("z80_trace_ring", [])
    print(f"\n=== TRACE AT FRAME 301 ===")
    # Find all non-NOP entries
    non_nops = [(i, e) for i, e in enumerate(trace_ring) if "Nop" not in e]
    nop_count = len(trace_ring) - len(non_nops)
    print(f"Total entries: {len(trace_ring)}, NOPs: {nop_count}, Non-NOPs: {len(non_nops)}")
    for i, entry in non_nops[:100]:
        print(f"  {i:4d}: {entry}")

if __name__ == "__main__":
    main()
