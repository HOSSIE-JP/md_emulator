#!/usr/bin/env python3
"""Disassemble ROM around $8660 to understand who sets $FF019C = $0161,
and around $84D0 to understand $FF019C = $0111.
Also search for calls to $8600-$8700 range."""
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
    
    # Disassemble around $8660 and $84D0
    for addr, size, label in [
        (0x8480, 160, "$8480 area (around $84DC where $0111 set)"),
        (0x8600, 160, "$8600 area (around $866C where $0161 set)"),
        (0x8CF0, 40, "$8CF0 area (clear $FF019C)"),
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
            elif (w & 0xFFF8) == 0x4EC0: note = f"JMP (A{w&7})"
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
            print(f"  ${a:06X}: {w:04X}  {note}")
    
    # Search for calls to $8600-$8700 range
    print(f"\n{'='*60}")
    print("Searching for JSR/BSR to $8600-$8700 range...")
    print(f"{'='*60}")
    
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 5):
            w = (data[i] << 8) | data[i+1]
            # JSR (xxx).L = 4EB9
            if w == 0x4EB9 and i + 5 < len(data):
                t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                if 0x8600 <= t <= 0x8700:
                    print(f"  ${chunk_start+i:06X}: JSR ${t:08X}")
            # BSR.W = 6100 xxxx
            if w == 0x6100 and i + 3 < len(data):
                d = (data[i+2]<<8)|data[i+3]
                if d >= 0x8000: d -= 0x10000
                t = chunk_start + i + 2 + d
                if 0x8600 <= t <= 0x8700:
                    print(f"  ${chunk_start+i:06X}: BSR.W ${t:06X}")
            # 4EBA (JSR PC-relative)
            if w == 0x4EBA and i + 3 < len(data):
                d = (data[i+2]<<8)|data[i+3]
                if d >= 0x8000: d -= 0x10000
                t = chunk_start + i + 2 + d
                if 0x8600 <= t <= 0x8700:
                    print(f"  ${chunk_start+i:06X}: JSR (PC) → ${t:06X}")
    
    # Also search for pointer value 00008660-00008700
    print(f"\n  Pointer search (00 00 86 xx in ROM):")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 3):
            if data[i] == 0x00 and data[i+1] == 0x00 and data[i+2] == 0x86:
                if 0x00 <= data[i+3] <= 0xFF:
                    val = (data[i+2]<<8)|data[i+3]
                    if 0x8600 <= val <= 0x8700:
                        print(f"  ${chunk_start+i:06X}: 00 00 {data[i+2]:02X} {data[i+3]:02X}  (pointer to ${val:04X})")
    
    # Search for calls to $8480-$8500 range  
    print(f"\n  Searching for calls to $8480-$8500:")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 5):
            w = (data[i] << 8) | data[i+1]
            if w == 0x4EB9 and i + 5 < len(data):
                t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                if 0x8480 <= t <= 0x8700:
                    print(f"  ${chunk_start+i:06X}: JSR ${t:08X}")

if __name__ == "__main__":
    main()
