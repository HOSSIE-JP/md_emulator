#!/usr/bin/env python3
"""Efficient Z80 crash investigation."""
import urllib.request
import json
import sys

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def main():
    print("Loading ROM...")
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    # Step quickly to frame 270
    print("Stepping to frame 270...")
    api("/emulator/step", "POST", {"cycles": 896040 * 270})
    
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    print(f"Frame 270: Z80 PC=0x{z80_pc:04X}")
    
    # Step one frame at a time to find crash  
    for f in range(271, 320):
        api("/emulator/step", "POST", {"cycles": 896040})
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        
        if z80_pc >= 0x2000:
            print(f"Frame {f}: Z80 PC=0x{z80_pc:04X} - OUT OF NORMAL RANGE")
            
            # Get the trace ring
            trace_ring = apu.get("z80_trace_ring", [])
            print(f"Trace ring: {len(trace_ring)} entries")
            
            # Find the last idle loop entry (newest first in trace)
            last_idle = None
            for i, entry in enumerate(trace_ring):
                if "$116" in entry and ("Rrca" in entry or "JpCond" in entry or "LdR8" in entry or "Or" in entry or "Jr" in entry):
                    last_idle = i
                    break
            
            if last_idle is not None:
                print(f"\nLast idle loop entry at index {last_idle}")
                # Show the transition (entries before and after, newest-first)
                start_show = max(0, last_idle - 10)
                end_show = min(len(trace_ring), last_idle + 80)
                for i in range(start_show, end_show):
                    print(f"  {i:5d}: {trace_ring[i]}")
            else:
                print("No idle loop entries found!")
                # Show newest entries
                for i in range(min(50, len(trace_ring))):
                    print(f"  {i:5d}: {trace_ring[i]}")
                # Show oldest entries
                print("  ...")
                for i in range(max(0, len(trace_ring)-50), len(trace_ring)):
                    print(f"  {i:5d}: {trace_ring[i]}")
            
            break
        elif f % 10 == 0:
            print(f"Frame {f}: Z80 PC=0x{z80_pc:04X} (OK)")

if __name__ == "__main__":
    main()
