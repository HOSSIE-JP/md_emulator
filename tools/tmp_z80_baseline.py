#!/usr/bin/env python3
"""Quick Z80 crash test with old code."""
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

    for f in range(1, 420):
        api("/emulator/step", "POST", {"cycles": 896040})
        if f % 50 == 0 or (f >= 295 and f <= 310):
            apu = api("/apu/state")
            z80_pc = apu.get("z80_pc", 0)
            status = "OK" if z80_pc < 0x4000 else "CRASH"
            print(f"Frame {f:3d}: Z80 PC=0x{z80_pc:04X} [{status}]")
            if z80_pc >= 0x4000:
                break

if __name__ == "__main__":
    main()
