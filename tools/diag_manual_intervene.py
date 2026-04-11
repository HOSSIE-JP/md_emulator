#!/usr/bin/env python3
"""Manual intervention test: clear $FF019C after frame 40 to see if game progresses.
Also try setting bit 3 of $FF0066 manually."""
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

def write_mem(addr, data):
    r = requests.post(f"{BASE}/cpu/memory", json={"addr": addr, "data": data})
    r.raise_for_status()
    return r.json()

def read_word(addr):
    d = get_mem(addr, 2)
    return (d[0] << 8) | d[1]

def read_long(addr):
    d = get_mem(addr, 4)
    return (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()["cpu"]["m68k"]

def get_vdp():
    r = requests.get(f"{BASE}/vdp/registers")
    r.raise_for_status()
    data = r.json()
    # Could be a list of register values or a dict
    if isinstance(data, list):
        return {"registers_list": data}
    return data

def main():
    load_rom()
    
    # Step to frame 45 to let Z80 init complete and sound cmd be set
    print("Stepping to frame 45...")
    step(45)
    
    print(f"Before intervention:")
    print(f"  $FF019C = ${read_word(0xFF019C):04X}")
    print(f"  $FF0066 = ${read_word(0xFF0066):04X}")
    print(f"  $FF0306 = ${read_long(0xFF0306):08X}")
    print(f"  $FF005E = ${read_long(0xFF005E):08X}")
    cpu = get_cpu()
    print(f"  M68K PC = ${cpu['pc']:06X}")
    vdp = get_vdp()
    regs = vdp.get('registers_list', vdp.get('registers', []))
    r1 = regs[1] if isinstance(regs, list) and len(regs) > 1 else 0
    print(f"  VDP R1 = ${r1:02X} (VINT_EN = {(r1 >> 5) & 1})")
    
    # Intervention 1: Clear $FF019C (remove sound command)
    print("\n=== Intervention: Clear $FF019C ===")
    write_mem(0xFF019C, [0x00, 0x00])
    
    # Intervention 2: Set bit 3 of $FF0066 (sound ready flag)
    ff0066 = read_word(0xFF0066)
    new_val = ff0066 | 0x0008  # set bit 3
    write_mem(0xFF0066, [(new_val >> 8) & 0xFF, new_val & 0xFF])
    
    # Intervention 3: Set bit 1 of $FF0066 (scene transition flag) 
    new_val = new_val | 0x0002  # set bit 1
    write_mem(0xFF0066, [(new_val >> 8) & 0xFF, new_val & 0xFF])
    
    print(f"After intervention:")
    print(f"  $FF019C = ${read_word(0xFF019C):04X}")
    print(f"  $FF0066 = ${read_word(0xFF0066):04X}")
    
    # Now step and see what happens
    print("\nStepping with intervention...")
    for frame in range(46, 300):
        step(1)
        
        ff019c = read_word(0xFF019C)
        ff0066 = read_word(0xFF0066)
        ff0306 = read_long(0xFF0306)
        ff005e = read_long(0xFF005E)
        cpu = get_cpu()
        pc = cpu['pc']
        
        # Re-apply intervention every frame if needed
        if ff019c != 0:
            write_mem(0xFF019C, [0x00, 0x00])
            
        # Keep bit 3 set
        if (ff0066 & 0x0008) == 0:
            ff0066 |= 0x0008
            write_mem(0xFF0066, [(ff0066 >> 8) & 0xFF, ff0066 & 0xFF])
        
        # Keep bit 1 set  
        if (ff0066 & 0x0002) == 0:
            ff0066 |= 0x0002
            write_mem(0xFF0066, [(ff0066 >> 8) & 0xFF, ff0066 & 0xFF])
        
        if frame in [46, 47, 48, 50, 60, 75, 100, 125, 150, 200, 250] or ff0306 != 0x4E1A or ff005e != 0x1C2E:
            vdp = get_vdp()
            regs = vdp.get('registers_list', vdp.get('registers', []))
            r1 = regs[1] if isinstance(regs, list) and len(regs) > 1 else 0
            print(f"  F{frame:4d}: PC=${pc:06X} FF019C=${ff019c:04X} FF0066=${ff0066:04X} "
                  f"FF0306=${ff0306:08X} FF005E=${ff005e:08X} R1=${r1:02X}")

    print(f"\nFinal state at frame 300:")
    print(f"  $FF019C = ${read_word(0xFF019C):04X}")
    print(f"  $FF0066 = ${read_word(0xFF0066):04X}")
    print(f"  $FF0306 = ${read_long(0xFF0306):08X}")
    print(f"  $FF005E = ${read_long(0xFF005E):08X}")
    cpu = get_cpu()
    print(f"  M68K PC = ${cpu['pc']:06X}")
    vdp = get_vdp()
    regs = vdp.get('registers_list', vdp.get('registers', []))
    r1 = regs[1] if isinstance(regs, list) and len(regs) > 1 else 0
    print(f"  VDP R1 = ${r1:02X} (VINT_EN = {(r1 >> 5) & 1})")

if __name__ == "__main__":
    main()
