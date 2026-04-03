#!/usr/bin/env python3
"""Search ROM for references to $FF0067 and find who sets bits 1 and 3.
Also trace the initialization sequence to find who sets $FF019C."""
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
    
    # Search for E0FF0067
    print("References to $E0FF0067:")
    for chunk_start in range(0, 0x20000, 0x8000):
        data = get_mem(chunk_start, 0x8000)
        for i in range(len(data) - 3):
            if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x00 and data[i+3] == 0x67:
                addr = chunk_start + i
                s = max(0, i - 6)
                e = min(len(data), i + 8)
                ctx = ' '.join(f'{b:02X}' for b in data[s:e])
                print(f"  ${addr:06X}: {ctx}")
    
    # Search for E0FF019C (sound command)
    print("\nReferences to $E0FF019C:")
    for chunk_start in range(0, 0x20000, 0x8000):
        data = get_mem(chunk_start, 0x8000)
        for i in range(len(data) - 3):
            if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x01 and data[i+3] == 0x9C:
                addr = chunk_start + i
                s = max(0, i - 6)
                e = min(len(data), i + 8)
                ctx = ' '.join(f'{b:02X}' for b in data[s:e])
                print(f"  ${addr:06X}: {ctx}")
    
    # Where is $FF019C set to $0161?
    # Search for 0161 near $FF019C references
    print("\nSearching for MOVE.W #$0161 pattern (33FC 0161):")
    for chunk_start in range(0, 0x20000, 0x8000):
        data = get_mem(chunk_start, 0x8000)
        for i in range(len(data) - 3):
            if data[i] == 0x33 and data[i+1] == 0xFC and data[i+2] == 0x01 and data[i+3] == 0x61:
                addr = chunk_start + i
                e = min(len(data), i + 12)
                ctx = ' '.join(f'{b:02X}' for b in data[i:e])
                print(f"  ${addr:06X}: {ctx}")
    
    # Also search for 0161 value anywhere near $FF019C writes
    print("\nSearching for 0161 near E0FF019C writes (33C0/33C1/33Cx E0FF 019C):")
    for chunk_start in range(0, 0x20000, 0x8000):
        data = get_mem(chunk_start, 0x8000)
        for i in range(len(data) - 7):
            if (data[i] & 0xF8) == 0x33 and data[i+1] == 0xC0 | (data[i+1] & 0xF8) == 0xC0:
                if data[i+2] == 0xE0 and data[i+3] == 0xFF and data[i+4] == 0x01 and data[i+5] == 0x9C:
                    addr = chunk_start + i
                    s = max(0, i - 4)
                    e = min(len(data), i + 10)
                    ctx = ' '.join(f'{b:02X}' for b in data[s:e])
                    print(f"  ${addr:06X}: {ctx}")
    
    # Check what's at $5300 area (where bit 2 is set)
    print("\n$5300 area (bit 2 set in $FF0066):")
    data = get_mem(0x52F0, 80)
    for i in range(0, len(data) - 1, 2):
        a = 0x52F0 + i
        w = (data[i] << 8) | data[i+1]
        note = ""
        if w == 0x4E75: note = "RTS"
        elif w == 0x4EB9 and i + 5 < len(data):
            t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            note = f"JSR ${t:08X}"
        print(f"  ${a:06X}: {w:04X}  {note}")

    # Check VBlank handler disassembly ($02A0-$0300) in detail
    print("\nVBlank handler ($02A0-$02F0):")
    data = get_mem(0x02A0, 0x60)
    for i in range(0, len(data) - 1, 2):
        a = 0x02A0 + i
        w = (data[i] << 8) | data[i+1]
        note = ""
        if w == 0x4E75: note = "RTS"
        elif w == 0x4E73: note = "RTE"
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
        elif w == 0x4EB9 and i + 5 < len(data):
            t = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            note = f"JSR ${t:08X}"
        elif (w & 0xFFF8) == 0x4E90:
            note = f"JSR (A{w&7})"
        elif w == 0x0839 and i + 7 < len(data):
            bit = (data[i+2]<<8)|data[i+3]
            ea = (data[i+4]<<24)|(data[i+5]<<16)|(data[i+6]<<8)|data[i+7]
            note = f"BTST #{bit&0xff}, (${ea:08X}).L"
        print(f"  ${a:06X}: {w:04X}  {note}")

if __name__ == "__main__":
    main()
