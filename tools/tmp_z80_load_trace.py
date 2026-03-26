#!/usr/bin/env python3
"""Trace M68K Z80 RAM writes to verify driver loading."""
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

def main():
    print("Loading ROM...")
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    # Get ROM header
    rom = api("/cpu/memory?addr=0&len=512")
    rom_data = rom.get("data", [])
    
    # Initial SP and PC
    init_sp = (rom_data[0] << 24) | (rom_data[1] << 16) | (rom_data[2] << 8) | rom_data[3]
    init_pc = (rom_data[4] << 24) | (rom_data[5] << 16) | (rom_data[6] << 8) | rom_data[7]
    print(f"Initial SP=0x{init_sp:08X}, PC=0x{init_pc:08X}")
    
    # Check bus request state
    apu = api("/apu/state")
    print(f"Z80 bus_requested={apu.get('z80_bus_requested', '?')}, z80_reset={apu.get('z80_reset', '?')}")
    
    # Read Z80 write count from apu state
    z80_writes = apu.get("z80_m68k_write_count", 0)
    print(f"Z80 M68K write count: {z80_writes}")
    
    # Step small amounts and check when Z80 RAM gets populated
    for step in range(20):
        api("/emulator/step", "POST", {"cycles": 50000})
        
        # Check Z80 RAM first few bytes
        mem = api("/cpu/memory?addr=10485760&len=64")
        ram = mem.get("data", [])
        
        apu = api("/apu/state")
        z80_pc = apu.get("z80_pc", 0)
        z80_writes = apu.get("z80_m68k_write_count", 0)
        z80_reset = apu.get("z80_reset", "?")
        z80_bus_req = apu.get("z80_bus_requested", "?")
        
        nz = sum(1 for b in ram if b != 0)
        first_nz = next((i for i, b in enumerate(ram) if b != 0), -1)
        
        print(f"Step {step+1}: Z80 PC=0x{z80_pc:04X}, writes={z80_writes}, "
              f"reset={z80_reset}, busreq={z80_bus_req}, "
              f"nz_bytes={nz}, first@{first_nz}")
        if nz > 0:
            print(f"  RAM[0:16]: {' '.join(f'{b:02X}' for b in ram[:16])}")
            print(f"  RAM[56:64]: {' '.join(f'{b:02X}' for b in ram[56:64])}")
        
        if nz > 10:
            # Enough data loaded, check the full picture
            mem2 = api("/cpu/memory?addr=10485760&len=512")
            ram2 = mem2.get("data", [])
            nz2 = sum(1 for b in ram2 if b != 0)
            print(f"\n  Full 512 bytes: {nz2} non-zero")
            
            # Show $0000-$0040
            for off in range(0, 0x40, 16):
                hexdump = " ".join(f"{ram2[i]:02X}" for i in range(off, off+16))
                print(f"  ${off:04X}: {hexdump}")
            break

if __name__ == "__main__":
    main()
