#!/usr/bin/env python3
"""Disassemble key areas of the ROM to trace why $8300 (sound init) is never called.
Focus on the main loop and the addresses where M68K spends time."""
import requests, sys

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def get_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def hexdump(data, base_addr):
    """Print hexdump with address."""
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        print(f"  ${base_addr+i:06X}: {hex_str}")

def disasm_simple(data, base_addr):
    """Very basic M68K disassembly - just show words for analysis."""
    i = 0
    while i < len(data) - 1:
        word = (data[i] << 8) | data[i+1]
        addr = base_addr + i
        # Identify common patterns
        note = ""
        if word == 0x4E75:
            note = "RTS"
        elif word == 0x4E73:
            note = "RTE"
        elif word == 0x4E71:
            note = "NOP"
        elif (word >> 8) == 0x61:
            # BSR.B
            disp = word & 0xFF
            if disp == 0 and i+3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                note = f"BSR.W ${addr+2+disp:06X}"
                i += 4
                print(f"  ${addr:06X}: {word:04X} {data[i-2]:02X}{data[i-1]:02X}  {note}")
                continue
            else:
                if disp >= 0x80: disp -= 0x100
                note = f"BSR.B ${addr+2+disp:06X}"
        elif (word & 0xFF00) == 0x4E00 and (word & 0xF0) == 0x80:
            # JSR
            mode = (word >> 3) & 7
            reg = word & 7
            if mode == 7 and reg == 1 and i+5 < len(data):
                target = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                note = f"JSR ${target:08X}"
                i += 6
                print(f"  ${addr:06X}: {word:04X} ...    {note}")
                continue
            elif mode == 7 and reg == 0 and i+3 < len(data):
                target = (data[i+2] << 8) | data[i+3]
                if target >= 0x8000: target = target | 0xFFFF0000
                note = f"JSR ${target & 0xFFFFFF:06X}"
                i += 4
                print(f"  ${addr:06X}: {word:04X} {data[i-2]:02X}{data[i-1]:02X}  {note}")
                continue
        elif (word >> 8) == 0x4A:
            # TST
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            note = f"TST.{sn}"
        elif word == 0x0079 or word == 0x0039:
            # ORI.W or ORI.B to absolute long
            if i + 7 < len(data):
                imm = (data[i+2] << 8) | data[i+3]
                target = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
                sn = 'W' if word == 0x0079 else 'B'
                note = f"ORI.{sn} #${imm:04X},${target:08X}"
                i += 8
                print(f"  ${addr:06X}: {word:04X} ...    {note}")
                continue
        elif (word >> 12) == 0x6:
            # Bcc
            cond = (word >> 8) & 0xF
            cond_names = ['BRA','BSR','BHI','BLS','BCC','BCS','BNE','BEQ',
                         'BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE']
            disp = word & 0xFF
            if disp == 0 and i+3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                note = f"{cond_names[cond]}.W ${addr+2+disp:06X}"
                i += 4
                print(f"  ${addr:06X}: {word:04X} {data[i-2]:02X}{data[i-1]:02X}  {note}")
                continue
            elif disp != 0:
                if disp >= 0x80: disp -= 0x100
                note = f"{cond_names[cond]}.B ${addr+2+disp:06X}"
        elif (word & 0xFFC0) == 0x4EC0:
            note = "JMP"
        
        print(f"  ${addr:06X}: {word:04X}        {note}")
        i += 2

def main():
    load_rom()
    
    # Read key ROM areas
    areas = [
        (0x7A5E, 128, "Main loop ($7A5E)"),
        (0x7980, 80, "VBlank poll area ($7980)"),
        (0x8300, 256, "Sound init function ($8300)"),
        (0x83D0, 64, "TST.B D2 / BGE area ($83D0)"),
        (0x6500, 80, "Code at $6500 (frequent PC)"),
        (0x05A0, 48, "Code at $05A0"),
        (0x50D0, 32, "Code at $50D0"),
        (0x02A0, 96, "VBlank handler ($02A0)"),
    ]
    
    for addr, size, label in areas:
        data = get_mem(addr, size)
        print(f"\n{'='*60}")
        print(f"{label}")
        print(f"{'='*60}")
        disasm_simple(data, addr)
    
    # Search ROM for references to $8300 (JSR/BSR targets)
    print(f"\n{'='*60}")
    print(f"Searching ROM for JSR/BSR to $8300...")
    print(f"{'='*60}")
    
    # Read larger ROM area and search for $8300 reference
    # $8300 as absolute long would appear as 00 00 83 00 
    # As BSR.W displacement from various locations
    for chunk_start in range(0x0000, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(0, len(data) - 5):
            # Check for absolute long address 0x00008300
            if i + 3 < len(data):
                long_val = (data[i] << 24) | (data[i+1] << 16) | (data[i+2] << 8) | data[i+3]
                if long_val == 0x00008300:
                    # Check previous word for JSR/JMP
                    if i >= 2:
                        prev_word = (data[i-2] << 8) | data[i-1]
                        if prev_word in [0x4EB9, 0x4EF9]:
                            print(f"  ${chunk_start+i-2:06X}: JSR/JMP $00008300")
    
    # Also search for BSR.W to $8300
    for chunk_start in range(0x7000, 0x9000, 0x1000):
        data = get_mem(chunk_start, 0x1000)
        for i in range(0, len(data) - 3):
            word = (data[i] << 8) | data[i+1]
            if (word >> 8) == 0x61 and (word & 0xFF) == 0x00:
                # BSR.W
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                target = chunk_start + i + 2 + disp
                if 0x8300 <= target <= 0x8310:
                    print(f"  ${chunk_start+i:06X}: BSR.W ${target:06X}")

if __name__ == "__main__":
    main()
