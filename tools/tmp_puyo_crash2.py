#!/usr/bin/env python3
"""Narrow down exact Z80 crash frame and capture trace."""
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

    # Quick step to frame 300 (known OK)
    for f in range(300):
        api("/emulator/step", "POST", {"cycles": 896040})
    
    apu = api("/apu/state")
    print(f"Frame 300: Z80 PC=0x{apu.get('z80_pc',0):04X}")
    
    # Step one frame at a time from 300 to 350
    for f in range(301, 360):
        api("/emulator/step", "POST", {"cycles": 896040})
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        if z80_pc >= 0x4000:
            print(f"\n=== Z80 CRASH at frame {f} ===")
            print(f"Z80 PC=0x{z80_pc:04X}")
            print(f"Z80 iff1={apu.get('z80_iff1')}")
            print(f"Z80 halted={apu.get('z80_halted')}")
            
            # Show Z80 trace ring (all entries, newest first)
            trace_ring = apu.get("z80_trace_ring", [])
            print(f"\nZ80 trace ring ({len(trace_ring)} entries):")
            # Find first non-NOP entries (these are from before the crash)
            nop_count = 0
            for i, entry in enumerate(trace_ring):
                if "Nop" in entry:
                    nop_count += 1
                else:
                    if nop_count > 0:
                        print(f"  ... {nop_count} NOPs from crashed execution ...")
                    print(f"  {i:4d}: {entry}")
                    if i - nop_count > 100:  # Show enough context
                        break
            break
        elif f % 10 == 0:
            print(f"Frame {f}: Z80 PC=0x{z80_pc:04X} (OK)")

if __name__ == "__main__":
    main()
