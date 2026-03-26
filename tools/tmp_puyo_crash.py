#!/usr/bin/env python3
"""Find when Z80 crashes by checking PC at each frame."""
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

    prev_pc = 0
    crash_frame = None
    for f in range(1, 30):
        api("/emulator/step", "POST", {"cycles": 896040})
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        iff1 = apu.get("z80_iff1", False)
        bus_req = apu.get("z80_bus_requested", False)
        z80_reset = apu.get("z80_reset", False)
        writes = apu.get("ym_write_total", 0)
        status = "OK" if z80_pc < 0x4000 else "CRASH"
        print(f"Frame {f:3d}: Z80 PC=0x{z80_pc:04X} iff1={iff1} bus={bus_req} reset={z80_reset} writes={writes} [{status}]")
        if z80_pc >= 0x4000 and crash_frame is None:
            crash_frame = f
            # Show crash trace
            trace_ring = apu.get("z80_trace_ring", [])
            print(f"\n  === CRASH at frame {f} ===")
            # Show last non-NOP instructions
            for i, entry in enumerate(trace_ring[:100]):
                if "Nop" not in entry:
                    print(f"  {i:3d}: {entry}")
            break
    
    if crash_frame is None:
        print("\nZ80 didn't crash in first 30 frames, checking through frame 420...")
        for f in range(30, 421):
            api("/emulator/step", "POST", {"cycles": 896040})
            if f % 50 == 0:
                apu = api("/apu/state")
                z80_pc = apu.get("z80_pc", 0)
                writes = apu.get("ym_write_total", 0)
                status = "OK" if z80_pc < 0x4000 else "CRASH"
                print(f"Frame {f:3d}: Z80 PC=0x{z80_pc:04X} writes={writes} [{status}]")
                if z80_pc >= 0x4000:
                    trace_ring = apu.get("z80_trace_ring", [])
                    for i, entry in enumerate(trace_ring[:100]):
                        if "Nop" not in entry:
                            print(f"  {i:3d}: {entry}")
                    break

if __name__ == "__main__":
    main()
