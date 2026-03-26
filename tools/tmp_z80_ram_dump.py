#!/usr/bin/env python3
"""Dump Z80 RAM to check if driver is properly loaded."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def dump_z80_ram(label):
    # Read Z80 RAM via M68K bus address $A00000 = 10485760, 512 bytes
    mem = api(f"/cpu/memory?addr=10485760&len=512")
    ram = mem.get("data", [])
    
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    z80_sp = apu.get("z80_sp", 0xFFFF)
    iff1 = apu.get("iff1", False)
    
    print(f"\n--- {label} ---")
    print(f"Z80 PC=0x{z80_pc:04X}, SP=0x{z80_sp:04X}, iff1={iff1}")
    
    if len(ram) < 128:
        print(f"Only got {len(ram)} bytes")
        return ram
    
    # Show key areas
    for start in [0x00, 0x30, 0x100]:
        end = min(start + 32, len(ram))
        hexdump = " ".join(f"{ram[i]:02X}" for i in range(start, end))
        print(f"  ${start:04X}: {hexdump}")
    
    # Check if $0038 area looks like code
    isr_bytes = ram[0x38:0x48]
    print(f"  ISR@$0038: {' '.join(f'{b:02X}' for b in isr_bytes)}")
    
    # Non-zero byte count
    nz = sum(1 for b in ram if b != 0)
    print(f"  Non-zero bytes: {nz}/{len(ram)}")
    
    return ram

def main():
    print("Loading ROM...")
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    dump_z80_ram("After ROM load (frame 0)")
    
    # Step 1 frame
    api("/emulator/step", "POST", {"cycles": 896040})
    dump_z80_ram("Frame 1")
    
    api("/emulator/step", "POST", {"cycles": 896040})
    dump_z80_ram("Frame 2")
    
    api("/emulator/step", "POST", {"cycles": 896040 * 3})
    dump_z80_ram("Frame 5")
    
    api("/emulator/step", "POST", {"cycles": 896040 * 5})
    dump_z80_ram("Frame 10")

if __name__ == "__main__":
    main()
