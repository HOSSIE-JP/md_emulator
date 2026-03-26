#!/usr/bin/env python3
"""Capture Z80 trace right before crash with 32K ring + dump Z80 RAM."""
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

    # Step to just before the crash
    for f in range(250):
        api("/emulator/step", "POST", {"cycles": 896040})

    # Now step one frame at a time
    for f in range(251, 310):
        api("/emulator/step", "POST", {"cycles": 896040})
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        
        # Check if Z80 is no longer in the idle loop range
        if z80_pc >= 0x2000 or z80_pc < 0x1000:
            if z80_pc >= 0x4000:
                print(f"Frame {f}: Z80 PC=0x{z80_pc:04X} CRASH!")
            else:
                in_mirror = z80_pc >= 0x2000
                real_addr = z80_pc & 0x1FFF if in_mirror else z80_pc
                print(f"Frame {f}: Z80 PC=0x{z80_pc:04X} (real=0x{real_addr:04X})")
            
            trace_ring = apu.get("z80_trace_ring", [])
            print(f"Trace ring: {len(trace_ring)} entries")
            
            # Search for the LAST time the Z80 was in normal operation
            # Idle loop: $116F-$1176
            # Also look for: CALL/RET/JP instructions that might have gone wrong
            last_idle_idx = None
            last_int_idx = None
            interesting = []
            
            for i, entry in enumerate(trace_ring):
                # Check for idle loop  
                if any(f"${addr:04X}" in entry for addr in range(0x116F, 0x1177)):
                    if last_idle_idx is None:
                        last_idle_idx = i
                # Check for INT
                if "INT" in entry or "$0038" in entry:
                    if last_int_idx is None:
                        last_int_idx = i
                    interesting.append((i, "INT", entry))
                # Check for RET, RETI, CALL, JP
                if any(x in entry for x in ["Ret", "Call", "Jp(", "Jr("]):
                    if len(interesting) < 200:
                        interesting.append((i, "FLOW", entry))
            
            if last_idle_idx is not None:
                print(f"\nLast idle entry at index {last_idle_idx}")
                # Show 30 entries around the transition
                start = max(0, last_idle_idx - 5)
                end = min(len(trace_ring), last_idle_idx + 50)
                print(f"Trace around transition (indices {start}-{end}):")
                for i in range(start, end):
                    marker = "  "
                    if any(f"${addr:04X}" in trace_ring[i] for addr in range(0x116F, 0x1177)):
                        marker = ">>"
                    elif "INT" in trace_ring[i]:
                        marker = "!!"
                    print(f"  {marker}{i:5d}: {trace_ring[i]}")
            
            if last_int_idx is not None:
                print(f"\nFirst INT at index {last_int_idx}")
                start = max(0, last_int_idx - 3)
                end = min(len(trace_ring), last_int_idx + 20)
                for i in range(start, end):
                    print(f"  {i:5d}: {trace_ring[i]}")
            
            # Show interesting flow entries  
            if interesting:
                print(f"\nInteresting flow entries (first 30):")
                for idx, kind, entry in interesting[:30]:
                    print(f"  [{kind}] {idx:5d}: {entry}")
            
            break

if __name__ == "__main__":
    main()
