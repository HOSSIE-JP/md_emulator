#!/usr/bin/env python3
"""Trace M68K PC + VDP reg1 at every frame to find crash point."""
import requests

API = "http://localhost:8080/api/v1"

r = requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {r.status_code}")
requests.post(f"{API}/emulator/reset")

FRAME_CYCLES = 128056
prev_reg1 = 0
prev_pc = 0
changes = []

for frame in range(200):
    if frame > 0:
        requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    
    cr = requests.get(f"{API}/cpu/state")
    cpu = cr.json()
    pc = cpu.get("pc", -1)
    sr = cpu.get("sr", 0)
    
    vr = requests.get(f"{API}/vdp/registers")
    regs = vr.json() if isinstance(vr.json(), list) else vr.json().get("registers", [])
    reg1 = regs[1] if len(regs) > 1 else -1
    
    # Report significant changes
    if reg1 != prev_reg1 or pc != prev_pc or frame < 3 or frame % 25 == 0:
        if reg1 != prev_reg1 or (pc == 0 and prev_pc != 0) or frame < 3 or frame % 25 == 0:
            stopped = cpu.get("stopped", False)
            cycles = cpu.get("cycles", 0)
            d0 = cpu.get("data_regs", [0])[0] if "data_regs" in cpu else 0
            a7 = cpu.get("addr_regs", [0]*8)[7] if "addr_regs" in cpu else 0
            print(f"F{frame:4d}: PC=0x{pc:08X} SR=0x{sr:04X} reg1=0x{reg1:02X} "
                  f"stopped={stopped} cyc={cycles} A7=0x{a7:08X}")
            if reg1 != prev_reg1:
                print(f"        ** reg1 CHANGED 0x{prev_reg1:02X} -> 0x{reg1:02X}")
            if pc == 0 and prev_pc != 0:
                print(f"        ** PC WENT TO ZERO! (was 0x{prev_pc:08X})")
    
    prev_reg1 = reg1
    prev_pc = pc

# Also check exception vectors
print("\n--- Exception Vectors from ROM ---")
for i in range(0, 0x100, 4):
    try:
        r = requests.get(f"{API}/cpu/memory", params={"address": i, "length": 4})
        data = r.json()
        if isinstance(data, list) and len(data) == 4:
            vec = (data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]
            names = {0:"SSP", 4:"Entry", 8:"BusErr", 0xC:"AddrErr", 0x10:"Illegal", 
                     0x14:"DivZero", 0x18:"CHK", 0x1C:"TRAPV", 0x20:"Priv",
                     0x24:"Trace", 0x28:"LineA", 0x2C:"LineF",
                     0x60:"Spurious", 0x64:"IRQ1", 0x68:"IRQ2/ExtInt", 0x6C:"IRQ3",
                     0x70:"IRQ4/HInt", 0x74:"IRQ5", 0x78:"IRQ6/VInt", 0x7C:"IRQ7"}
            name = names.get(i, "")
            if name or vec != 0:
                print(f"  [{i:03X}] {name:12s}: 0x{vec:08X}")
    except:
        pass
