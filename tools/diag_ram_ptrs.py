#!/usr/bin/env python3
"""Check RAM pointers ($FF0306, $FF005E) and disassemble $7F5C, $7F92.
Also trace if M68K PC ever enters $8300-$8500 by adding a counter."""
import requests

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def step(n=1):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n})
    r.raise_for_status()

def get_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def read_long(addr):
    d = get_mem(addr, 4)
    return (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]

def read_word(addr):
    d = get_mem(addr, 2)
    return (d[0] << 8) | d[1]

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()["cpu"]["m68k"]

def main():
    load_rom()
    
    # First: disassemble $7F5C and $7F92
    for addr, size, label in [
        (0x7F5C, 60, "$7F5C (counter=0 first time path)"),
        (0x7F92, 60, "$7F92 (bus already granted in $7DF6)"),
        (0x83FA, 80, "$83FA (after ORI.W path in $8300)"),  
        (0x048C, 40, "$048C (called from $8300 via A2)"),
        (0x04A4, 40, "$04A4 (loaded into A3 in $8300)"),
    ]:
        data = get_mem(addr, size)
        print(f"\n{'='*60}")
        print(f"{label}")
        print(f"{'='*60}")
        for i in range(0, len(data) - 1, 2):
            a = addr + i
            w = (data[i] << 8) | data[i+1]
            print(f"  ${a:06X}: {w:04X}")

    # Now trace RAM state frame by frame  
    print(f"\n{'='*60}")
    print("Frame-by-frame RAM pointer tracking")
    print(f"{'='*60}")
    print(f"{'Frame':>6} {'PC':>8} {'FF0306':>10} {'FF005E':>10} {'FF0066':>8} {'FF0064':>8} {'FFA820':>8} {'FF019C':>8} {'FF019F':>8}")
    print("-" * 90)
    
    for frame in range(1, 201):
        step(1)
        
        if frame in [1, 5, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 
                      25, 30, 35, 40, 45, 50, 60, 75, 100, 125, 150, 200]:
            cpu = get_cpu()
            pc = cpu["pc"]
            
            ptr0306 = read_long(0xFF0306)
            ptr005E = read_long(0xFF005E) 
            ff0066 = read_word(0xFF0066)
            ff0064 = read_word(0xFF0064)
            ffa820 = read_word(0xFFA820)
            ff019c = read_word(0xFF019C)
            # Read byte at $FF019F
            ff019f = get_mem(0xFF019F, 1)[0]
            
            print(f"{frame:6d} {pc:#010x} {ptr0306:#010x} {ptr005E:#010x} {ff0066:#06x} {ff0064:#06x} {ffa820:#06x} {ff019c:#06x}   {ff019f:#04x}")

if __name__ == "__main__":
    main()
