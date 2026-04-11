#!/usr/bin/env python3
"""Read ROM at $B200-$B300 and $D4E0-$D520 to understand init and JMP write."""
import requests

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def get_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def main():
    load_rom()
    
    for addr, size, label in [
        (0xB200, 128, "$B200 area (init code)"),
        (0xD4C0, 80, "$D4C0 area (DMA init loop)"),
        (0x0200, 20, "Exception vectors $200 (entry point)"),
    ]:
        data = get_mem(addr, size)
        print(f"\n{'='*60}")
        print(label)
        print(f"{'='*60}")
        for i in range(0, len(data) - 1, 2):
            a = addr + i
            w = (data[i] << 8) | data[i+1]
            note = ""
            if w == 0x4E75: note = "RTS"
            elif w == 0x4E73: note = "RTE"
            elif w == 0x23FC and i + 9 < len(data):
                val = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                dst = (data[i+6]<<24)|(data[i+7]<<16)|(data[i+8]<<8)|data[i+9]
                note = f"MOVE.L #${val:08X}, (${dst:08X}).L"
            elif w == 0x33FC and i + 7 < len(data):
                val = (data[i+2]<<8)|data[i+3]
                dst = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                note = f"MOVE.W #${val:04X}, (${dst:08X}).L"
            elif w == 0x4EB9 and i + 5 < len(data):
                t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                note = f"JSR ${t:08X}"
            elif (w >> 12) == 6:
                cn = ['BRA','BSR','BHI','BLS','BCC','BCS','BNE','BEQ',
                      'BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE'][(w>>8)&0xF]
                d = w & 0xFF
                if d == 0 and i + 3 < len(data):
                    d = (data[i+2]<<8)|data[i+3]
                    if d >= 0x8000: d -= 0x10000
                    note = f"{cn}.W ${a+2+d:06X}"
                elif d != 0:
                    if d >= 0x80: d -= 0x100
                    note = f"{cn}.B ${a+2+d:06X}"
            print(f"  ${a:06X}: {w:04X}  {note}")

    # Check entry point
    print("\n\nEntry point (reset vector at offset 4):")
    data = get_mem(0, 8)
    sp = (data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]
    pc = (data[4]<<24)|(data[5]<<16)|(data[6]<<8)|data[7]
    print(f"  Initial SP: ${sp:08X}")
    print(f"  Initial PC: ${pc:08X}")
    
    # Read the init code 
    print(f"\nInit code at ${pc:06X}:")
    data = get_mem(pc, 100)
    for i in range(0, min(len(data) - 1, 100), 2):
        a = pc + i
        w = (data[i] << 8) | data[i+1]
        note = ""
        if w == 0x4EB9 and i + 5 < len(data):
            t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            note = f"JSR ${t:08X}"
        elif (w >> 12) == 6:
            cn = ['BRA','BSR','BHI','BLS','BCC','BCS','BNE','BEQ',
                  'BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE'][(w>>8)&0xF]
            d = w & 0xFF
            if d == 0 and i + 3 < len(data):
                d = (data[i+2]<<8)|data[i+3]
                if d >= 0x8000: d -= 0x10000
                note = f"{cn}.W ${a+2+d:06X}"
            elif d != 0:
                if d >= 0x80: d -= 0x100
                note = f"{cn}.B ${a+2+d:06X}"
        print(f"  ${a:06X}: {w:04X}  {note}")

if __name__ == "__main__":
    main()
