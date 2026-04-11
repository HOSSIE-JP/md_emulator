#!/usr/bin/env python3
"""VBlankハンドラの解析と$FF0064/$FFA820のランタイム監視"""
import requests, struct, sys

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def step(n=1):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n})
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def read_word(addr):
    d = read_mem(addr, 2)
    return (d[0] << 8) | d[1]

def read_long(addr):
    d = read_mem(addr, 4)
    return (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()

def get_trace():
    r = requests.get(f"{BASE}/cpu/trace")
    r.raise_for_status()
    return r.json()

def dump_rom(addr, length):
    """ROMバイト列を16bit word単位でダンプ"""
    data = read_mem(addr, length)
    words = []
    for i in range(0, len(data) - 1, 2):
        w = (data[i] << 8) | data[i+1]
        words.append(w)
    return data, words

def disasm_simple(addr, data):
    """簡易逆アセンブル（主要命令のみ）"""
    lines = []
    i = 0
    while i < len(data) - 1:
        w = (data[i] << 8) | data[i+1]
        a = addr + i
        
        # MOVE.W #imm, (abs).L
        if w == 0x33FC and i + 8 <= len(data):
            imm = (data[i+2] << 8) | data[i+3]
            dst = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            lines.append(f"  ${a:06X}: MOVE.W #${imm:04X}, (${dst:08X})")
            i += 8; continue
        
        # MOVE.W (abs).L, Dn
        if (w & 0xF1FF) == 0x3039:
            dn = (w >> 9) & 7
            if i + 6 <= len(data):
                src = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: MOVE.W (${src:08X}), D{dn}")
                i += 6; continue
        
        # MOVE.W Dn, (abs).L
        if (w & 0xFFF8) == 0x33C0:
            dn = w & 7
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: MOVE.W D{dn}, (${dst:08X})")
                i += 6; continue
        
        # BTST #n, Dn
        if (w & 0xFFF8) == 0x0800:
            dn = w & 7
            if i + 4 <= len(data):
                bit = (data[i+2] << 8) | data[i+3]
                lines.append(f"  ${a:06X}: BTST #{bit}, D{dn}")
                i += 4; continue
        
        # BSET #n, Dn / (An) etc
        if (w & 0xFFC0) == 0x08C0:
            mode = (w >> 3) & 7
            reg = w & 7
            if i + 4 <= len(data):
                bit = (data[i+2] << 8) | data[i+3]
                if mode == 0:
                    lines.append(f"  ${a:06X}: BSET #{bit}, D{reg}")
                    i += 4; continue
                elif mode == 7 and reg == 1 and i + 8 <= len(data):
                    dst = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
                    lines.append(f"  ${a:06X}: BSET #{bit}, (${dst:08X})")
                    i += 8; continue
        
        # BCLR #n
        if (w & 0xFFC0) == 0x0880:
            mode = (w >> 3) & 7
            reg = w & 7
            if i + 4 <= len(data):
                bit = (data[i+2] << 8) | data[i+3]
                if mode == 0:
                    lines.append(f"  ${a:06X}: BCLR #{bit}, D{reg}")
                    i += 4; continue
        
        # ORI.W #imm, Dn
        if (w & 0xFFF8) == 0x0040:
            dn = w & 7
            if i + 4 <= len(data):
                imm = (data[i+2] << 8) | data[i+3]
                lines.append(f"  ${a:06X}: ORI.W #${imm:04X}, D{dn}")
                i += 4; continue
        
        # ANDI.W #imm, Dn
        if (w & 0xFFF8) == 0x0240:
            dn = w & 7
            if i + 4 <= len(data):
                imm = (data[i+2] << 8) | data[i+3]
                lines.append(f"  ${a:06X}: ANDI.W #${imm:04X}, D{dn}")
                i += 4; continue
        
        # CLR.W (abs).L
        if w == 0x4279:
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: CLR.W (${dst:08X})")
                i += 6; continue
        
        # CLR.L (abs).L
        if w == 0x42B9:
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: CLR.L (${dst:08X})")
                i += 6; continue
        
        # TST.W Dn
        if (w & 0xFFF8) == 0x4A40:
            dn = w & 7
            lines.append(f"  ${a:06X}: TST.W D{dn}")
            i += 2; continue
        
        # TST.B Dn
        if (w & 0xFFF8) == 0x4A00:
            dn = w & 7
            lines.append(f"  ${a:06X}: TST.B D{dn}")
            i += 2; continue
        
        # Bcc.B (byte displacement)
        cc_names = {0:"BRA",1:"BSR",2:"BHI",3:"BLS",4:"BCC",5:"BCS",6:"BNE",7:"BEQ",
                    8:"BVC",9:"BVS",10:"BPL",11:"BMI",12:"BGE",13:"BLT",14:"BGT",15:"BLE"}
        cc = (w >> 8) & 0xF
        disp = w & 0xFF
        if cc in cc_names and disp != 0 and disp != 0xFF:
            if disp >= 0x80: disp -= 0x100
            target = a + 2 + disp
            lines.append(f"  ${a:06X}: {cc_names[cc]}.B ${target:06X}")
            i += 2; continue
        
        # Bcc.W (word displacement)
        if cc in cc_names and disp == 0:
            if i + 4 <= len(data):
                disp16 = (data[i+2] << 8) | data[i+3]
                if disp16 >= 0x8000: disp16 -= 0x10000
                target = a + 2 + disp16
                lines.append(f"  ${a:06X}: {cc_names[cc]}.W ${target:06X}")
                i += 4; continue
        
        # JSR (abs).L
        if w == 0x4EB9:
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: JSR ${dst:08X}")
                i += 6; continue
        
        # JSR (PC)+d16
        if w == 0x4EBA:
            if i + 4 <= len(data):
                d16 = (data[i+2] << 8) | data[i+3]
                if d16 >= 0x8000: d16 -= 0x10000
                target = a + 2 + d16
                lines.append(f"  ${a:06X}: JSR (PC) → ${target:08X}")
                i += 4; continue
        
        # JMP (abs).L
        if w == 0x4EF9:
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: JMP ${dst:08X}")
                i += 6; continue
        
        # RTS
        if w == 0x4E75:
            lines.append(f"  ${a:06X}: RTS")
            i += 2; continue
        
        # RTE
        if w == 0x4E73:
            lines.append(f"  ${a:06X}: RTE")
            i += 2; continue
        
        # MOVEM.L regs, -(SP)
        if w == 0x48E7:
            if i + 4 <= len(data):
                mask = (data[i+2] << 8) | data[i+3]
                lines.append(f"  ${a:06X}: MOVEM.L regs, -(SP) mask=${mask:04X}")
                i += 4; continue
        
        # MOVEM.L (SP)+, regs
        if w == 0x4CDF:
            if i + 4 <= len(data):
                mask = (data[i+2] << 8) | data[i+3]
                lines.append(f"  ${a:06X}: MOVEM.L (SP)+, regs mask=${mask:04X}")
                i += 4; continue
        
        # MOVEQ
        if (w >> 8) == 0x70 or (w & 0xF100) == 0x7000:
            dn = (w >> 9) & 7
            imm = w & 0xFF
            if imm >= 0x80: imm -= 0x100
            lines.append(f"  ${a:06X}: MOVEQ #{imm}, D{dn}")
            i += 2; continue
        
        # ADDQ.W #n, An/Dn
        if (w & 0xF1C0) == 0x5040:
            n = (w >> 9) & 7
            if n == 0: n = 8
            mode = (w >> 3) & 7
            reg = w & 7
            if mode == 0:
                lines.append(f"  ${a:06X}: ADDQ.W #{n}, D{reg}")
            elif mode == 1:
                lines.append(f"  ${a:06X}: ADDQ.W #{n}, A{reg}")
            else:
                lines.append(f"  ${a:06X}: ADDQ.W #{n}, ea({mode},{reg})")
            i += 2; continue
        
        # ADDQ.L #n, An/Dn
        if (w & 0xF1C0) == 0x5080:
            n = (w >> 9) & 7
            if n == 0: n = 8
            mode = (w >> 3) & 7
            reg = w & 7
            if mode == 0:
                lines.append(f"  ${a:06X}: ADDQ.L #{n}, D{reg}")
            elif mode == 1:
                lines.append(f"  ${a:06X}: ADDQ.L #{n}, A{reg}")
            else:
                lines.append(f"  ${a:06X}: ADDQ.L #{n}, ea({mode},{reg})")
            i += 2; continue
        
        # SUBQ.W #n
        if (w & 0xF1C0) == 0x5140:
            n = (w >> 9) & 7
            if n == 0: n = 8
            mode = (w >> 3) & 7
            reg = w & 7
            if mode == 0:
                lines.append(f"  ${a:06X}: SUBQ.W #{n}, D{reg}")
            else:
                lines.append(f"  ${a:06X}: SUBQ.W #{n}, ea({mode},{reg})")
            i += 2; continue
        
        # MOVE.B D0, (abs).L
        if w == 0x13C0:
            if i + 6 <= len(data):
                dst = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: MOVE.B D0, (${dst:08X})")
                i += 6; continue
        
        # MOVE.B (abs).L, Dn
        if (w & 0xF1FF) == 0x1039:
            dn = (w >> 9) & 7
            if i + 6 <= len(data):
                src = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                lines.append(f"  ${a:06X}: MOVE.B (${src:08X}), D{dn}")
                i += 6; continue
        
        # NOP
        if w == 0x4E71:
            lines.append(f"  ${a:06X}: NOP")
            i += 2; continue
        
        # SWAP
        if (w & 0xFFF8) == 0x4840:
            dn = w & 7
            lines.append(f"  ${a:06X}: SWAP D{dn}")
            i += 2; continue
        
        # PEA
        if (w & 0xFFC0) == 0x4840 and ((w >> 3) & 7) != 0:
            # PEA (xxx).W
            mode = (w >> 3) & 7
            reg = w & 7
            if mode == 7 and reg == 0:
                if i + 4 <= len(data):
                    val = (data[i+2] << 8) | data[i+3]
                    lines.append(f"  ${a:06X}: PEA (${val:04X}).W")
                    i += 4; continue
            elif mode == 7 and reg == 1:
                if i + 6 <= len(data):
                    val = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                    lines.append(f"  ${a:06X}: PEA (${val:08X}).L")
                    i += 6; continue
        
        # Default: raw word
        lines.append(f"  ${a:06X}: ${w:04X}")
        i += 2
    
    return lines

# ================================================================
print("=" * 60)
print("1. VBlankベクタの読み取り")
print("=" * 60)
load_rom()

# Level 6 (VBlank) interrupt vector at ROM $000078
vblank_vector = read_long(0x000078)
print(f"Level 6 VBlank vector: ${vblank_vector:08X}")

# Level 4 (HBlank) interrupt vector at ROM $000070
hblank_vector = read_long(0x000070)
print(f"Level 4 HBlank vector: ${hblank_vector:08X}")

# Also check level 2
level2_vector = read_long(0x000068)
print(f"Level 2 vector: ${level2_vector:08X}")

print()
print("=" * 60)
print(f"2. VBlankハンドラのディスアセンブル (${vblank_vector:06X})")
print("=" * 60)
vb_data, _ = dump_rom(vblank_vector, 256)
vb_lines = disasm_simple(vblank_vector, vb_data)
for line in vb_lines:
    print(line)

print()
print("=" * 60)
print("3. メインループ bit 0 ハンドラの確認")  
print("   (bit 0 = VBlank処理?)")
print("=" * 60)
# Disassemble main loop around $7A5E-$7C40
ml_data, _ = dump_rom(0x7A5E, 0x200)
ml_lines = disasm_simple(0x7A5E, ml_data)
for line in ml_lines[:80]:  # 最初の80行
    print(line)

print()
print("=" * 60)
print("4. ディスパッチ関数 $048C")
print("=" * 60)
disp_data, _ = dump_rom(0x048C, 64)
disp_lines = disasm_simple(0x048C, disp_data)
for line in disp_lines:
    print(line)

print()
print("=" * 60)
print("5. $04A4 関数 (カウンタ設定?)")
print("=" * 60)
f04a4_data, _ = dump_rom(0x04A4, 64)
f04a4_lines = disasm_simple(0x04A4, f04a4_data)
for line in f04a4_lines:
    print(line)

print()
print("=" * 60)
print("6. $8630 (counter=0 ディスパッチターゲット)")
print("=" * 60)
t8630_data, _ = dump_rom(0x8630, 64)
t8630_lines = disasm_simple(0x8630, t8630_data)
for line in t8630_lines:
    print(line)

print()
print("=" * 60)
print("7. $8588 (delay loop exit)")
print("=" * 60)
t8588_data, _ = dump_rom(0x8588, 48)
t8588_lines = disasm_simple(0x8588, t8588_data)
for line in t8588_lines:
    print(line)

print()
print("=" * 60)
print("8. ランタイム監視 (50フレーム)")
print("=" * 60)
print(f"{'Frame':>5} {'PC':>8} {'FF0062':>8} {'FF0064':>8} {'FF0066':>8} {'FF019C':>8} {'FFA820':>8}")
for frame in range(50):
    step(1)
    cpu = get_cpu()
    pc = cpu.get("pc", 0)
    ff0062 = read_word(0xFF0062)
    ff0064 = read_word(0xFF0064)
    ff0066 = read_word(0xFF0066)
    ff019c = read_word(0xFF019C)
    ffa820 = read_word(0xFFA820)
    print(f"{frame:5d} {pc:08X} {ff0062:08X} {ff0064:08X} {ff0066:08X} {ff019c:08X} {ffa820:08X}")

print()
print("=" * 60)
print("9. トレースリング確認 ($82xx-$86xx PC)")
print("=" * 60)
trace = get_trace()
ring = trace.get("trace_ring", [])
for entry in ring:
    pc_val = entry.get("pc", 0)
    if 0x8200 <= pc_val <= 0x8700:
        print(f"  PC=${pc_val:08X}")
    if 0x0480 <= pc_val <= 0x04C0:
        print(f"  PC=${pc_val:08X} (dispatch?)")

# Check if any trace entries are in the VBlank handler range
vb_entries = [e for e in ring if vblank_vector <= e.get("pc", 0) < vblank_vector + 256]
if vb_entries:
    print(f"  VBlankハンドラ内のトレースエントリ: {len(vb_entries)} 件")
    for e in vb_entries[:5]:
        print(f"    PC=${e.get('pc',0):08X}")
else:
    print("  VBlankハンドラ内のトレースエントリ: なし")

print("\n完了")
