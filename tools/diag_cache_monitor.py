#!/usr/bin/env python3
"""Monitor SGDK VDP register cache at RAM 0xFFA83C to find when VINT bit gets cleared."""
import requests

API = "http://localhost:8080/api/v1"

r = requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {r.status_code}")
requests.post(f"{API}/emulator/reset")

FRAME_CYCLES = 128056
# SGDK VDP register cache: reg1 is at offset 1 from the base
# From trace: reads from 0xE0FFA83C (24-bit: 0x00FFA83C)
CACHE_ADDR = 0x00FFA83C
# Also check base of register cache (reg0)
CACHE_BASE = 0x00FFA83B  # reg[0]

prev_cache = None
prev_reg1 = 0

for frame in range(135):
    if frame > 0:
        requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    
    # Read VDP registers
    vr = requests.get(f"{API}/vdp/registers")
    regs = vr.json()["registers"]
    reg1 = regs[1]
    
    # Read SGDK cache from RAM (read 32 bytes around the cache)
    try:
        r = requests.get(f"{API}/cpu/memory", params={"address": CACHE_BASE - 5, "length": 48})
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            mem = data["data"]
        elif isinstance(data, list):
            mem = data
        else:
            mem = []
        cache_reg1 = mem[6] if len(mem) > 6 else -1  # offset 6 = addr+6 = 0xFFA83C
    except:
        cache_reg1 = -1
        mem = []
    
    changed = (reg1 != prev_reg1) or (cache_reg1 != prev_cache)
    if changed or frame < 20 or frame % 25 == 0:
        cc = requests.get(f"{API}/cpu/state").json()["cpu"]["m68k"]
        pc = cc["pc"]
        
        print(f"F{frame:4d}: VDP_reg1=0x{reg1:02X} cache=0x{cache_reg1:02X} PC=0x{pc:06X}", end="")
        if reg1 != prev_reg1:
            print(f"  [VDP CHANGED 0x{prev_reg1:02X}->0x{reg1:02X}]", end="")
        if cache_reg1 != prev_cache:
            if prev_cache is not None:
                print(f"  [CACHE CHANGED 0x{prev_cache:02X}->0x{cache_reg1:02X}]", end="")
        
        # Show surrounding cache bytes
        if len(mem) >= 20:
            hex_str = " ".join(f"{b:02X}" for b in mem[:20])
            print(f"\n       Cache area: {hex_str}", end="")
        print()
        
        prev_reg1 = reg1
        prev_cache = cache_reg1

# Detailed trace around frame 126
print("\n=== Detailed trace frame 125 (scanline-by-scanline) ===")
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

for i in range(125):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Now step scanline by scanline through frame 126
prev_c = None
for sl in range(262):
    requests.post(f"{API}/emulator/step", json={"cycles": 488})
    
    try:
        r = requests.get(f"{API}/cpu/memory", params={"address": CACHE_ADDR, "length": 1})
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            c = data["data"][0]
        elif isinstance(data, list):
            c = data[0]
        else:
            c = -1
    except:
        c = -1
    
    vr = requests.get(f"{API}/vdp/registers")
    reg1 = vr.json()["registers"][1]
    
    if c != prev_c or reg1 != prev_reg1:
        cc = requests.get(f"{API}/cpu/state").json()["cpu"]["m68k"]
        print(f"  SL{sl:3d}: cache=0x{c:02X} VDP_reg1=0x{reg1:02X} PC=0x{cc['pc']:06X} D0=0x{cc['d'][0]:08X}")
        prev_c = c
        prev_reg1 = reg1
