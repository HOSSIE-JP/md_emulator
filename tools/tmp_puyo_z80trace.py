#!/usr/bin/env python3
"""Check Z80 trace ring to understand why Z80 crashed."""
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

    # Step to frame 420 (BGM should be playing)
    for f in range(420):
        api("/emulator/step", "POST", {"cycles": 896040})

    apu = api("/apu/state")
    print(f"Z80 PC: 0x{apu.get('z80_pc', 0):04X}")
    print(f"Z80 halted: {apu.get('z80_halted')}")
    print(f"Z80 iff1: {apu.get('z80_iff1')}")
    print(f"Z80 total_cycles: {apu.get('z80_total_cycles')}")
    print(f"Z80 bus_req: {apu.get('z80_bus_requested')}")
    print(f"Z80 reset: {apu.get('z80_reset')}")
    
    # Z80 trace ring (last executed instructions)
    trace_ring = apu.get("z80_trace_ring", [])
    print(f"\nZ80 trace ring ({len(trace_ring)} entries, newest first):")
    for i, entry in enumerate(trace_ring[:64]):
        print(f"  {i:3d}: {entry}")

if __name__ == "__main__":
    main()
