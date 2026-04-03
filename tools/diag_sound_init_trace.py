#!/usr/bin/env python3
"""Trace M68K execution around $8300 (sound init) to find why bit 3 of $FF0066 is never set."""
import requests, sys

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def step(n=1):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n})
    r.raise_for_status()
    return r.json()

def get_trace():
    r = requests.get(f"{BASE}/cpu/trace")
    r.raise_for_status()
    return r.json()

def get_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()["cpu"]["m68k"]

def main():
    load_rom()
    
    print("Searching for M68K execution near $8300-$8400 (sound init function)")
    print("=" * 80)
    
    for frame in range(1, 301):
        step(1)
        
        # Get trace ring
        trace_data = get_trace()
        trace_ring = trace_data.get("trace_ring", [])
        
        # Check for PCs in the $8300-$8500 range
        sound_traces = [t for t in trace_ring if 0x8300 <= t["pc"] <= 0x8500]
        
        # Also check for PCs near $83DC (TST.B D2)  
        tst_traces = [t for t in trace_ring if 0x83D0 <= t["pc"] <= 0x83F0]
        
        if sound_traces or frame in [1, 10, 15, 20, 25, 30, 35, 40, 50]:
            # Read $FF0066 word
            mem66 = get_mem(0xFF0066, 2)
            val66 = (mem66[0] << 8) | mem66[1]
            
            cpu = get_cpu()
            pc = cpu["pc"]
            
            if sound_traces:
                print(f"\nFrame {frame}: {len(sound_traces)} instructions in $8300-$8500, PC={pc:#06x}, $FF0066={val66:#06x}")
                for t in sound_traces[:10]:
                    print(f"  PC=${t['pc']:06X}: {t.get('mnemonic', '???')}")
                if tst_traces:
                    print(f"  *** TST traces near $83DC: {len(tst_traces)}")
                    for t in tst_traces:
                        print(f"    PC=${t['pc']:06X}: {t.get('mnemonic', '???')}")
            else:
                print(f"Frame {frame:3d}: PC={pc:#06x}, $FF0066={val66:#06x} (no $8300 traces)")
    
    # Final state
    mem66 = get_mem(0xFF0066, 2)
    val66 = (mem66[0] << 8) | mem66[1]
    print(f"\nFinal: $FF0066 = {val66:#06x}")
    print(f"  bit 1 = {(val66 >> 1) & 1} (scene transition)")
    print(f"  bit 2 = {(val66 >> 2) & 1}")
    print(f"  bit 3 = {(val66 >> 3) & 1} (sound enable)")

if __name__ == "__main__":
    main()
