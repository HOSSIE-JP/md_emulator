#!/usr/bin/env python3
"""Check M68K boot code and Z80 driver loading."""
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
    
    # Read ROM around entry point $200 and search for Z80 bus request writes
    rom_data = api("/cpu/memory?addr=512&len=512")["data"]  # $200-$3FF
    
    print(f"Entry point code at $200:")
    for off in range(0, min(128, len(rom_data)), 16):
        addr = 0x200 + off
        hexdump = " ".join(f"{rom_data[i]:02X}" for i in range(off, min(off+16, len(rom_data))))
        print(f"  ${addr:04X}: {hexdump}")
    
    # Search for Z80 init pattern: writes to $A11100 or $A11200
    # Pattern: A1 11 (bus request) or A1 12 (reset)
    rom_full = api("/cpu/memory?addr=0&len=32768")["data"]
    
    print(f"\nSearching for Z80 control register writes (A11100/A11200)...")
    for i in range(len(rom_full) - 3):
        # Look for address $00A11100 or $00A11200 in big-endian
        if rom_full[i] == 0x00 and rom_full[i+1] == 0xA1:
            if rom_full[i+2] == 0x11 and rom_full[i+3] == 0x00:
                print(f"  Found $00A11100 ref at ROM offset ${i:04X}")
            elif rom_full[i+2] == 0x12 and rom_full[i+3] == 0x00:
                print(f"  Found $00A11200 ref at ROM offset ${i:04X}")
        # Also search for short encoding: A1 11 00 or A1 12 00
        if rom_full[i] == 0xA1 and rom_full[i+1] == 0x11:
            if rom_full[i+2] == 0x00:
                print(f"  Found $A11100 ref at ROM offset ${i:04X}")
            elif rom_full[i+2] == 0x01:
                print(f"  Found $A11101 ref at ROM offset ${i:04X}")
        if rom_full[i] == 0xA1 and rom_full[i+1] == 0x12:
            if rom_full[i+2] == 0x00:
                print(f"  Found $A11200 ref at ROM offset ${i:04X}")
    
    # Search for writes to Z80 space $A00000
    print(f"\nSearching for Z80 RAM writes ($A00000 pattern)...")
    for i in range(len(rom_full) - 3):
        if rom_full[i] == 0x00 and rom_full[i+1] == 0xA0 and rom_full[i+2] == 0x00 and rom_full[i+3] == 0x00:
            context = " ".join(f"{rom_full[j]:02X}" for j in range(max(0,i-8), min(len(rom_full), i+8)))
            print(f"  Found $00A00000 at ROM ${i:04X}: {context}")
        # Short form
        if rom_full[i] == 0xA0 and rom_full[i+1] == 0x00 and rom_full[i+2] == 0x00:
            if i > 0 and rom_full[i-1] not in [0xA0]:
                context = " ".join(f"{rom_full[j]:02X}" for j in range(max(0,i-4), min(len(rom_full), i+8)))
                print(f"  Found $A00000 at ROM ${i:04X}: ...{context}")

if __name__ == "__main__":
    main()
