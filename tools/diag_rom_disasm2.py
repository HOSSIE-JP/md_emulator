#!/usr/bin/env python3
"""Disassemble the branch target $7C3C and surrounding areas to trace the sound init call chain."""
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

def disasm_words(data, base_addr):
    """Print raw word-level data with basic opcode identification."""
    i = 0
    while i < len(data) - 1:
        addr = base_addr + i
        word = (data[i] << 8) | data[i+1]
        
        # Get next words for context
        w2 = (data[i+2] << 8) | data[i+3] if i+3 < len(data) else 0
        w3 = (data[i+4] << 8) | data[i+5] if i+5 < len(data) else 0
        w4 = (data[i+6] << 8) | data[i+7] if i+7 < len(data) else 0
        
        note = ""
        extra = 0
        
        if word == 0x4E75: note = "RTS"
        elif word == 0x4E73: note = "RTE"
        elif word == 0x4E71: note = "NOP"
        
        # MOVEM
        elif (word & 0xFE00) == 0x4C00 or (word & 0xFE00) == 0x4800:
            note = "MOVEM"
        
        # MOVE.W (xxx).L, Dn — 3039, 3239, 3439, 3639
        elif (word & 0xF1FF) == 0x3039:
            dn = (word >> 9) & 7
            a = (w2 << 16) | w3
            note = f"MOVE.W (${a:08X}).L, D{dn}"
            extra = 4
        
        # MOVE.W Dn, (xxx).L — 33Cn
        elif (word & 0xFFF8) == 0x33C0:
            dn = word & 7
            a = (w2 << 16) | w3
            note = f"MOVE.W D{dn}, (${a:08X}).L"
            extra = 4
        
        # MOVE.L (xxx).L, An — 2079, 2279, etc.  
        elif (word & 0xF1FF) == 0x2079:
            an = (word >> 9) & 7
            a = (w2 << 16) | w3
            note = f"MOVEA.L (${a:08X}).L, A{an}"
            extra = 4
        
        # JSR (An)
        elif (word & 0xFFF8) == 0x4E90:
            an = word & 7
            note = f"JSR (A{an})"
        
        # JSR (xxx).L
        elif word == 0x4EB9:
            a = (w2 << 16) | w3
            note = f"JSR ${a:08X}"
            extra = 4
        
        # JSR (d16,PC)
        elif (word & 0xFFC0) == 0x4E80 and (word & 0x3F) == 0x3A:
            disp = w2
            if disp >= 0x8000: disp -= 0x10000
            target = addr + 2 + disp
            note = f"JSR (PC, ${disp:04X}) → ${target:06X}"
            extra = 2
        
        # BSR.W
        elif (word >> 8) == 0x61 and (word & 0xFF) == 0x00:
            disp = w2
            if disp >= 0x8000: disp -= 0x10000
            target = addr + 2 + disp
            note = f"BSR.W ${target:06X}"
            extra = 2
        
        # BSR.B
        elif (word >> 8) == 0x61:
            disp = word & 0xFF
            if disp >= 0x80: disp -= 0x100
            note = f"BSR.B ${addr+2+disp:06X}"
        
        # Bcc
        elif (word >> 12) == 0x6:
            cond = (word >> 8) & 0xF
            cond_names = ['BRA','BSR','BHI','BLS','BCC','BCS','BNE','BEQ',
                         'BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE']
            disp = word & 0xFF
            if disp == 0:
                disp = w2
                if disp >= 0x8000: disp -= 0x10000
                note = f"{cond_names[cond]}.W ${addr+2+disp:06X}"
                extra = 2
            else:
                if disp >= 0x80: disp -= 0x100
                note = f"{cond_names[cond]}.B ${addr+2+disp:06X}"
        
        # BTST #imm, Dn or (xxx)
        elif (word & 0xFFC0) == 0x0800:
            ea_mode = (word >> 3) & 7
            ea_reg = word & 7
            bit = w2 & 0xFF
            if ea_mode == 0:
                note = f"BTST #{bit}, D{ea_reg}"
                extra = 2
            elif ea_mode == 7 and ea_reg == 1:
                a = (w3 << 16) | w4 if i+7 < len(data) else 0
                note = f"BTST #{bit}, (${w3:04X}).W"
                extra = 4
        
        # BTST #imm, (xxx).L 
        elif word == 0x0839:
            bit = w2 & 0xFF
            a = (w3 << 16) | w4
            note = f"BTST #{bit}, (${a:08X}).L"
            extra = 6
        
        # TST.B/W/L
        elif (word & 0xFF00) == 0x4A00:
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            ea_mode = (word >> 3) & 7
            ea_reg = word & 7
            if ea_mode == 0:
                note = f"TST.{sn} D{ea_reg}"
            else:
                note = f"TST.{sn}"
        
        # ORI
        elif (word & 0xFF00) == 0x0000 and (word & 0xC0) != 0:
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            ea_mode = (word >> 3) & 7
            ea_reg = word & 7
            if ea_mode == 0:
                note = f"ORI.{sn} #${w2:04X}, D{ea_reg}"
                extra = 2
        
        # ADDQ
        elif (word & 0xF100) == 0x5000:
            data_val = (word >> 9) & 7
            if data_val == 0: data_val = 8
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            note = f"ADDQ.{sn} #{data_val}"
        
        # SUBQ
        elif (word & 0xF100) == 0x5100:
            data_val = (word >> 9) & 7
            if data_val == 0: data_val = 8
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            note = f"SUBQ.{sn} #{data_val}"
        
        # PEA
        elif (word & 0xFFC0) == 0x4840:
            note = "PEA"
        
        # CLR
        elif (word & 0xFF00) == 0x4200:
            size = (word >> 6) & 3
            sn = ['B','W','L'][size] if size < 3 else '?'
            note = f"CLR.{sn}"
        
        # MOVEQ
        elif (word & 0xF100) == 0x7000:
            dn = (word >> 9) & 7
            imm = word & 0xFF
            if imm >= 0x80: imm -= 0x100
            note = f"MOVEQ #{imm}, D{dn}"
        
        if extra > 0:
            hex_bytes = ' '.join(f'{data[i+j]:02X}' for j in range(min(2+extra, len(data)-i)))
            print(f"  ${addr:06X}: {hex_bytes:<20s} {note}")
            i += 2 + extra
        else:
            print(f"  ${addr:06X}: {word:04X}                 {note}")
            i += 2

def main():
    load_rom()
    
    areas = [
        (0x7C3C, 200, "Branch target $7C3C (bit 2 handler)"),
        (0x7B66, 24, "Branch target $7B66 (bit 0 handler)"),
        (0x7B7E, 40, "Branch target $7B7E (bit 4 handler)"),
        (0x7B12, 80, "Branch target $7B12 (bit 5 handler)"),
        (0x7DCC, 80, "Branch target $7DCC"),
        (0x7D74, 40, "Branch target $7D74"),
        (0x7A5E, 100, "Main loop ($7A5E) re-disasm"),
    ]
    
    for addr, size, label in areas:
        data = get_mem(addr, size)
        print(f"\n{'='*70}")
        print(f"{label}")
        print(f"{'='*70}")
        disasm_words(data, addr)

if __name__ == "__main__":
    main()
