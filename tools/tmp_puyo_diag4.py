#!/usr/bin/env python3
"""Diagnose freq latching: check histogram, register values, latch state."""
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

    # Check at frame 10 (init phase)
    for f in range(10):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    print("=== Frame 10 ===")
    print("ym_write_total:", apu.get("ym_write_total"))
    print("P0 freq regs:", apu.get("regs_port0_freq"))
    print("P1 freq regs:", apu.get("regs_port1_freq"))
    print("P0 histogram:", apu.get("ym_histogram_port0_nonzero"))
    print("P1 histogram:", apu.get("ym_histogram_port1_nonzero"))

    # Check at frame 100
    for f in range(90):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    print("\n=== Frame 100 ===")
    print("ym_write_total:", apu.get("ym_write_total"))
    print("P0 freq regs:", apu.get("regs_port0_freq"))
    print("P1 freq regs:", apu.get("regs_port1_freq"))
    print("P0 histogram:", apu.get("ym_histogram_port0_nonzero"))
    print("P1 histogram:", apu.get("ym_histogram_port1_nonzero"))

    # Check at frame 420
    for f in range(320):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    print("\n=== Frame 420 ===")
    print("ym_write_total:", apu.get("ym_write_total"))
    print("P0 freq regs:", apu.get("regs_port0_freq"))
    print("P1 freq regs:", apu.get("regs_port1_freq"))
    print("P0 histogram:", apu.get("ym_histogram_port0_nonzero"))
    print("P1 histogram:", apu.get("ym_histogram_port1_nonzero"))
    
    # Show channel details 
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        ops = ch.get("operators", [])
        keys = [op.get("key_on") for op in ops]
        atts = [op.get("attenuation") for op in ops]
        envs = [op.get("env_phase", "?")[:3] for op in ops]
        print(f"  CH{i+1}: fnum={ch.get('fnum',0):4d} block={ch.get('block',0)} algo={ch.get('algorithm',0)} "
              f"keys={keys} atts={atts} envs={envs}")

    print(f"\nZ80 PC: {apu.get('z80_pc')}")
    print(f"Z80 bus_req: {apu.get('z80_bus_requested')}, reset: {apu.get('z80_reset')}")
    print(f"Z80 halted: {apu.get('z80_halted')}, iff1: {apu.get('z80_iff1')}")
    
    # Check Z80 RAM at $0027 (command byte)
    mem = api("/cpu/memory", "POST", {"address": 0, "length": 8192, "source": "z80"})
    if "data" in mem:
        z80_ram = mem["data"]
        print(f"Z80 RAM[0027]={z80_ram[0x27]:02X}" if len(z80_ram) > 0x27 else "Z80 RAM too short")
        # Show a hex dump of Z80 RAM around command area
        print(f"Z80 RAM[0020..0030]: {' '.join(f'{z80_ram[i]:02X}' for i in range(0x20, min(0x30, len(z80_ram))))}")

if __name__ == "__main__":
    main()
