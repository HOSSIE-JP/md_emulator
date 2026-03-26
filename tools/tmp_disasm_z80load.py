#!/usr/bin/env python3
"""Disassemble the Z80 driver loading code in Puyo Puyo ROM."""
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
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    # Read ROM around Z80 init areas
    for addr_label, base in [
        ("$0280 (early init)", 0x280),
        ("$0570 (bus req area)", 0x570),
        ("$7190 (driver load 1)", 0x7190),
        ("$7250 (driver load 2)", 0x7250),
        ("$7280 (post load)", 0x7280),
    ]:
        rom = api(f"/cpu/memory?addr={base}&len=128")["data"]
        print(f"\n=== ROM at {addr_label} ===")
        for off in range(0, len(rom), 16):
            addr = base + off
            hexdump = " ".join(f"{rom[i]:02X}" for i in range(off, min(off+16, len(rom))))
            # Try basic ASCII
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in rom[off:min(off+16, len(rom))])
            print(f"  ${addr:04X}: {hexdump:48s} {ascii_str}")
    
    # Also read the Z80 driver source data at $076C00
    src = api(f"/cpu/memory?addr=486400&len=64")["data"]  # 486400 = 0x76C00
    print(f"\n=== Z80 driver source at $076C00 ===")
    for off in range(0, len(src), 16):
        addr = 0x76C00 + off
        hexdump = " ".join(f"{src[i]:02X}" for i in range(off, min(off+16, len(src))))
        print(f"  ${addr:05X}: {hexdump}")
    
    # Also $07E000
    src2 = api(f"/cpu/memory?addr=516096&len=64")["data"]  # 516096 = 0x7E000
    print(f"\n=== Z80 driver source at $07E000 ===")
    for off in range(0, len(src2), 16):
        addr = 0x7E000 + off
        hexdump = " ".join(f"{src2[i]:02X}" for i in range(off, min(off+16, len(src2))))
        print(f"  ${addr:05X}: {hexdump}")

if __name__ == "__main__":
    main()
