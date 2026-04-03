#!/usr/bin/env python3
"""Disassemble $7DF6, $7DD2, and search for $8300 references more thoroughly."""
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
    
    # Read and dump key areas
    areas = [
        (0x7DF6, 256, "$7DF6 (sound command handler when $FF019C != 0)"),
        (0x7DD2, 40, "$7DD2 (bus granted path)"),
        (0x7F0C, 80, "$7F0C (bit 0 of $FF019F set)"),
        (0x7E90, 80, "$7E90 (BLS target)"),
        (0x78B4, 80, "$78B4 (called near start of main loop)"),
    ]
    
    for addr, size, label in areas:
        data = get_mem(addr, size)
        print(f"\n{'='*70}")
        print(f"{label}")
        print(f"{'='*70}")
        i = 0
        while i < len(data) - 1:
            a = addr + i
            w = (data[i] << 8) | data[i+1]
            
            # Try to identify key patterns
            extra_hex = ""
            note = ""
            skip = 2
            
            # JSR (xxx).L
            if w == 0x4EB9 and i + 5 < len(data):
                target = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                note = f"JSR ${target:08X}"
                extra_hex = f"{data[i+2]:02X}{data[i+3]:02X} {data[i+4]:02X}{data[i+5]:02X}"
                skip = 6
            # JSR (d16,PC)
            elif w == 0x4EBA and i + 3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                target = a + 2 + disp
                note = f"JSR (PC) → ${target:06X}"
                extra_hex = f"{data[i+2]:02X}{data[i+3]:02X}"
                skip = 4
            # BSR.W
            elif (w >> 8) == 0x61 and (w & 0xFF) == 0x00 and i + 3 < len(data):
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                target = a + 2 + disp
                note = f"BSR.W ${target:06X}"
                extra_hex = f"{data[i+2]:02X}{data[i+3]:02X}"
                skip = 4
            # BSR.B
            elif (w >> 8) == 0x61:
                disp = w & 0xFF
                if disp >= 0x80: disp -= 0x100
                note = f"BSR.B ${a+2+disp:06X}"
            # RTS
            elif w == 0x4E75:
                note = "RTS"
            # RTE
            elif w == 0x4E73:
                note = "RTE"
            # JSR (An)
            elif (w & 0xFFF8) == 0x4E90:
                note = f"JSR (A{w & 7})"
            # JMP (An)
            elif (w & 0xFFF8) == 0x4EC0:
                note = f"JMP (A{w & 7})"
            # Bcc
            elif (w >> 12) == 0x6:
                cond = (w >> 8) & 0xF
                cn = ['BRA','BSR','BHI','BLS','BCC','BCS','BNE','BEQ',
                      'BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE'][cond]
                disp = w & 0xFF
                if disp == 0 and i + 3 < len(data):
                    disp = (data[i+2] << 8) | data[i+3]
                    if disp >= 0x8000: disp -= 0x10000
                    note = f"{cn}.W ${a+2+disp:06X}"
                    extra_hex = f"{data[i+2]:02X}{data[i+3]:02X}"
                    skip = 4
                elif disp != 0:
                    if disp >= 0x80: disp -= 0x100
                    note = f"{cn}.B ${a+2+disp:06X}"
            # MOVE.W (xxx).L, Dn
            elif (w & 0xF1FF) == 0x3039 and i + 5 < len(data):
                dn = (w >> 9) & 7
                ea = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                note = f"MOVE.W (${ea:08X}).L, D{dn}"
                skip = 6
            # MOVE.W Dn, (xxx).L
            elif (w & 0xFFF8) == 0x33C0 and i + 5 < len(data):
                dn = w & 7
                ea = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                note = f"MOVE.W D{dn}, (${ea:08X}).L"
                skip = 6
            # MOVE.W #imm, (xxx).L
            elif w == 0x33FC and i + 7 < len(data):
                imm = (data[i+2] << 8) | data[i+3]
                ea = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
                note = f"MOVE.W #${imm:04X}, (${ea:08X}).L"
                skip = 8
            # MOVEA.L (xxx).L, An
            elif (w & 0xF1FF) == 0x2079 and i + 5 < len(data):
                an = (w >> 9) & 7
                ea = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                note = f"MOVEA.L (${ea:08X}).L, A{an}"
                skip = 6
            
            hex_str = ' '.join(f'{data[i+j]:02X}' for j in range(min(skip, len(data)-i)))
            print(f"  ${a:06X}: {hex_str:<16s} {note}")
            i += skip
    
    # Search for $8300 as a pointer in ROM (could be in a jump table)
    print(f"\n{'='*70}")
    print(f"Searching for $8300 as a pointer value in ROM...")
    print(f"{'='*70}")
    
    # $8300 could appear as: 00 00 83 00 (long) or 83 00 (word, sign-extended)
    for chunk_start in range(0x0000, 0x20000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(0, len(data) - 3):
            # Check for 00 00 83 00 (absolute long $00008300)
            if data[i] == 0x00 and data[i+1] == 0x00 and data[i+2] == 0x83 and data[i+3] == 0x00:
                print(f"  ${chunk_start+i:06X}: 00 00 83 00  (long pointer to $8300)")
            # Check for 00 83 00 (possible misaligned)
            if i > 0 and data[i] == 0x00 and data[i+1] == 0x83 and data[i+2] == 0x00:
                # Check context
                w_before = data[i-1]
                print(f"  ${chunk_start+i:06X}: {w_before:02X} 00 83 00  (possible ref)")
    
    # Also check for PC-relative calls: JSR (d16,PC) where PC+d16 = $8300
    # 4EBA xxxx where (caller_addr + 2 + xxxx) = $8300
    print(f"\n  PC-relative (4EBA) calls that would reach $8300:")
    for chunk_start in range(0x6000, 0xA000, 0x2000):
        data = get_mem(chunk_start, 0x2000)
        for i in range(0, len(data) - 3):
            w = (data[i] << 8) | data[i+1]
            if w == 0x4EBA:
                disp = (data[i+2] << 8) | data[i+3]
                if disp >= 0x8000: disp -= 0x10000
                target = chunk_start + i + 2 + disp
                if 0x8300 <= target <= 0x830F:
                    print(f"  ${chunk_start+i:06X}: 4EBA {data[i+2]:02X}{data[i+3]:02X}  JSR (PC) → ${target:06X}")

if __name__ == "__main__":
    main()
