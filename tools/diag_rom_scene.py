#!/usr/bin/env python3
"""Check $1C2E (VBlank scene controller), $92D8 (scene transition), 
and search for code that sets bit 1 of $FF0066/$FF0067."""
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
        (0x1C2E, 40, "$1C2E (VBlank scene controller = $FF005E)"),
        (0x92D8, 120, "$92D8 (scene transition processor)"),
        (0x5280, 120, "$5280 (before bit 2 set at $5314)"),
        (0x4E5C, 50, "$4E5C-$4EA6 (scene function area)"),
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
            elif (w & 0xF1FF) == 0x3039 and i + 5 < len(data):
                dn = (w >> 9) & 7
                ea = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                note = f"MOVE.W (${ea:08X}).L, D{dn}"
            elif (w & 0xFFF8) == 0x33C0 and i + 5 < len(data):
                dn = w & 7
                ea = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
                note = f"MOVE.W D{dn}, (${ea:08X}).L"
            elif w == 0x33FC and i + 7 < len(data):
                imm = (data[i+2]<<8)|data[i+3]
                ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                note = f"MOVE.W #${imm:04X}, (${ea:08X}).L"
            elif w == 0x0079 and i + 7 < len(data):
                imm = (data[i+2]<<8)|data[i+3]
                ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                note = f"ORI.W #${imm:04X}, (${ea:08X}).L"
            elif w == 0x0279 and i + 7 < len(data):
                imm = (data[i+2]<<8)|data[i+3]
                ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                note = f"ANDI.W #${imm:04X}, (${ea:08X}).L"
            print(f"  ${a:06X}: {w:04X}  {note}")
    
    # Search for ORI.W instructions that set bits in $FF0066
    # ORI.W #xxxx, D0 followed by MOVE.W D0, ($FF0066)
    # Or ORI.W #xxxx, ($FF0066) directly (0079 xxxx E0FF 0066)
    print(f"\n{'='*60}")
    print("Searching for ORI.W #xxx, ($FF0066):")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 7):
            if data[i] == 0x00 and data[i+1] == 0x79:
                imm = (data[i+2]<<8)|data[i+3]
                ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                if ea == 0xE0FF0066 or (ea & 0x00FFFFFF) == 0xFF0066:
                    print(f"  ${chunk_start+i:06X}: ORI.W #${imm:04X}, ($FF0066)")
    
    # Also search: ORI.W #$0002 pattern to find bit 1 setting
    # 0040 0002 = ORI.W #$0002, D0  
    # 0079 0002 = ORI.W #$0002, (xxx)
    print(f"\nSearching for ORI.W #$0002 (bit 1 set) near $FF0066:")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 3):
            # ORI.W #$0002, D0
            if data[i] == 0x00 and data[i+1] == 0x40 and data[i+2] == 0x00 and data[i+3] == 0x02:
                # Check if followed by MOVE.W D0, ($FF0066) within next 8 bytes
                for j in range(i+4, min(i+20, len(data)-5)):
                    if data[j] == 0x33 and data[j+1] == 0xC0 and data[j+2] == 0xE0 and data[j+3] == 0xFF and data[j+4] == 0x00 and data[j+5] == 0x66:
                        print(f"  ${chunk_start+i:06X}: ORI.W #$0002, D0 ... MOVE.W D0, ($FF0066) at ${chunk_start+j:06X}")
                        break
    
    # Search for BSET #1 instructions targeting $FF0067
    # 08F9 = BSET #imm, (xxx).L  
    print(f"\nSearching for BSET instructions on $FF0066/$FF0067:")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 7):
            if data[i] == 0x08 and data[i+1] == 0xF9:
                bit = (data[i+2]<<8)|data[i+3]
                ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
                if (ea & 0x00FFFFFF) in [0xFF0066, 0xFF0067]:
                    print(f"  ${chunk_start+i:06X}: BSET #{bit&0xff}, (${ea:08X}).L")

    # Check what $92D8 sets - does it set bit 1?
    print(f"\n{'='*60}")
    print("Checking if $92D8 sets bit 1 of $FF0066 (it should RE-ENABLE scene processing)")

if __name__ == "__main__":
    main()
