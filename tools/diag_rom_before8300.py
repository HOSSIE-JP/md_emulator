#!/usr/bin/env python3
"""Check code right before $8300 to see if there's a fall-through into $8300.
Also read $8690+ to see the counter=0 path in the $8600+ function."""
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
        (0x82A0, 96, "$82A0-$8300 (code before $8300)"),
        (0x8690, 120, "$8690 (counter=0 path in $8600+ function)"),
        (0x85B0, 100, "$85B0 area (targets of branches in $8600+ function: $85B2, $85D6, $85F2)"),
    ]:
        data = get_mem(addr, size)
        print(f"\n{'='*60}")
        print(f"{label}")
        print(f"{'='*60}")
        for i in range(0, len(data) - 1, 2):
            a = addr + i
            w = (data[i] << 8) | data[i+1]
            note = ""
            if w == 0x4E75: note = "RTS"
            elif w == 0x4E73: note = "RTE"
            elif (w & 0xFFF8) == 0x4E90: note = f"JSR (A{w&7})"
            elif w == 0x4EB9 and i + 5 < len(data):
                t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                note = f"JSR ${t:08X}"
            elif w == 0x4EBA and i + 3 < len(data):
                d = (data[i+2]<<8)|data[i+3]
                if d >= 0x8000: d -= 0x10000
                note = f"JSR (PC) → ${a+2+d:06X}"
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
            elif (w & 0xF100) == 0x7000:
                dn = (w >> 9) & 7
                imm = w & 0xFF
                if imm >= 0x80: imm -= 0x100
                note = f"MOVEQ #{imm}, D{dn}"
            elif w == 0x4EF9 and i + 5 < len(data):
                t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                note = f"JMP ${t:08X}"
            print(f"  ${a:06X}: {w:04X}  {note}")

if __name__ == "__main__":
    main()
