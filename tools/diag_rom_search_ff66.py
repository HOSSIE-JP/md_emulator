#!/usr/bin/env python3
"""Search ROM for all instructions that reference $FF0066 (or $E0FF0066).
Also check $19C2, $4E1A and what they do."""
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
    
    # Search entire ROM for E0FF0066 pattern (bytes: E0 FF 00 66)
    print("Searching ROM for references to $E0FF0066 (E0 FF 00 66):")
    print("=" * 60)
    
    for chunk_start in range(0, 0x3A0000, 0x10000):
        try:
            data = get_mem(chunk_start, min(0x10000, 0x3A0000 - chunk_start))
        except:
            break
        for i in range(len(data) - 3):
            if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x00 and data[i+3] == 0x66:
                addr = chunk_start + i
                # Show context (4 bytes before and after)
                start = max(0, i - 8)
                end = min(len(data), i + 8)
                ctx = data[start:end]
                ctx_hex = ' '.join(f'{b:02X}' for b in ctx)
                print(f"  ${addr:06X}: ... {ctx_hex} ...")
    
    # Also search for FF0066 as word (FF 00 66) - might be sign-extended word address
    print("\nSearching for $FF0066 as word reference (00 66 after FF 00):")
    # Searching for E0FF followed by 0066 is the same as above.
    # Also check if any instruction uses (xxx).W addressing for $0066
    
    # Disassemble key functions
    for addr, size, label in [
        (0x19C2, 200, "$19C2 (Z80 program loader?)"),
        (0x4E1A, 200, "$4E1A (scene function)"),
        (0x7D02, 30, "$7D02 (after counter check)"),
    ]:
        data = get_mem(addr, size)
        print(f"\n{'='*60}")
        print(f"{label}")
        print(f"{'='*60}")
        for i in range(0, min(len(data)-1, size), 2):
            a = addr + i
            w = (data[i] << 8) | data[i+1]
            # Basic identification
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
            print(f"  ${a:06X}: {w:04X}  {note}")

if __name__ == "__main__":
    main()
