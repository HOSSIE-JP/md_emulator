#!/usr/bin/env python3
"""Disassemble M68K routine at $D5B0 (GEMS sound update from VBlank)."""
import json, urllib.request, struct

API = "http://localhost:8080/api/v1"

def fetch_mem(addr, length):
    url = f"{API}/cpu/memory?addr={addr}&len={length}"
    with urllib.request.urlopen(url) as r:
        return bytes(json.load(r)["data"])

def r16(d, o):
    return struct.unpack_from(">H", d, o)[0]

def r32(d, o):
    return struct.unpack_from(">I", d, o)[0]

def s8(v):
    return v - 256 if v >= 128 else v

def s16(v):
    return v - 65536 if v >= 32768 else v

SIZE_NAMES = {0: "B", 1: "W", 2: "L"}
AREG = lambda n: "SP" if n == 7 else f"A{n}"
DREG = lambda n: f"D{n}"

def reglist(mask, reverse=False):
    """MOVEM register list decode."""
    regs = []
    if reverse:
        # Pre-decrement: bit 0=A7, bit 7=A0, bit 8=D7, bit 15=D0
        for i in range(8):
            if mask & (1 << i): regs.append(AREG(7 - i))
        for i in range(8):
            if mask & (1 << (8 + i)): regs.append(DREG(7 - i))
    else:
        for i in range(8):
            if mask & (1 << i): regs.append(DREG(i))
        for i in range(8):
            if mask & (1 << (8 + i)): regs.append(AREG(i))
    return "/".join(regs)

def ea_decode(d, off, mode, reg, size="W", pc=0):
    """Decode EA, return (string, extra_bytes)."""
    if mode == 0: return (DREG(reg), 0)
    if mode == 1: return (AREG(reg), 0)
    if mode == 2: return (f"({AREG(reg)})", 0)
    if mode == 3: return (f"({AREG(reg)})+", 0)
    if mode == 4: return (f"-({AREG(reg)})", 0)
    if mode == 5:
        disp = s16(r16(d, off))
        if disp >= 0:
            return (f"(${disp:04X},{AREG(reg)})", 2)
        return (f"(-${-disp:04X},{AREG(reg)})", 2)
    if mode == 6:
        ext = r16(d, off)
        idx_reg = AREG((ext >> 12) & 7) if ext & 0x8000 else DREG((ext >> 12) & 7)
        idx_size = ".L" if ext & 0x0800 else ".W"
        disp8 = s8(ext & 0xFF)
        return (f"({disp8},{AREG(reg)},{idx_reg}{idx_size})", 2)
    if mode == 7:
        if reg == 0:
            addr = r16(d, off)
            if addr >= 0x8000:
                addr = addr | 0xFFFF0000
            return (f"(${addr & 0xFFFFFFFF:08X}).W", 2)
        if reg == 1:
            addr = r32(d, off)
            return (f"(${addr:08X}).L", 4)
        if reg == 2:
            disp = s16(r16(d, off))
            target = pc + disp
            return (f"(${target:06X},PC)", 2)
        if reg == 3:
            ext = r16(d, off)
            idx_reg = AREG((ext >> 12) & 7) if ext & 0x8000 else DREG((ext >> 12) & 7)
            idx_size = ".L" if ext & 0x0800 else ".W"
            disp8 = s8(ext & 0xFF)
            return (f"({disp8},PC,{idx_reg}{idx_size})", 2)
        if reg == 4:
            if size == "B":
                v = r16(d, off)
                return (f"#${v & 0xFF:02X}", 2)
            elif size == "L":
                v = r32(d, off)
                return (f"#${v:08X}", 4)
            else:
                v = r16(d, off)
                return (f"#${v:04X}", 2)
    return (f"??ea({mode},{reg})", 0)

def disasm(d, base, length):
    """Disassemble M68K code."""
    results = []
    off = 0
    while off < length and off < len(d) - 1:
        pc = base + off
        w = r16(d, off)
        consumed = 2
        mnem = None

        # === Decode instruction ===
        op_hi4 = (w >> 12) & 0xF
        
        # 0000 - ORI/ANDI/SUBI/ADDI/BTST/BSET/BCLR/BCHG/CMPI/EORI
        if op_hi4 == 0:
            if (w & 0xFF00) == 0x0000 and (w & 0x00C0) != 0x00C0:
                # ORI
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                if sz == "B":
                    imm = r16(d, off+2) & 0xFF
                    imm_s = f"#${imm:02X}"
                    consumed = 4
                elif sz == "L":
                    imm = r32(d, off+2)
                    imm_s = f"#${imm:08X}"
                    consumed = 6
                else:
                    imm = r16(d, off+2)
                    imm_s = f"#${imm:04X}"
                    consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
                consumed += ea_bytes
                mnem = f"ORI.{sz}   {imm_s},{ea_s}"
            elif (w & 0xFF00) == 0x0200 and (w & 0x00C0) != 0x00C0:
                # ANDI
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                if sz == "B":
                    imm = r16(d, off+2) & 0xFF
                    imm_s = f"#${imm:02X}"
                    consumed = 4
                elif sz == "L":
                    imm = r32(d, off+2)
                    imm_s = f"#${imm:08X}"
                    consumed = 6
                else:
                    imm = r16(d, off+2)
                    imm_s = f"#${imm:04X}"
                    consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
                consumed += ea_bytes
                mnem = f"ANDI.{sz}  {imm_s},{ea_s}"
            elif (w & 0xFF00) == 0x0400 and (w & 0x00C0) != 0x00C0:
                # SUBI
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                if sz == "B":
                    imm = r16(d, off+2) & 0xFF
                    imm_s = f"#${imm:02X}"
                    consumed = 4
                elif sz == "L":
                    imm = r32(d, off+2)
                    imm_s = f"#${imm:08X}"
                    consumed = 6
                else:
                    imm = r16(d, off+2)
                    imm_s = f"#${imm:04X}"
                    consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
                consumed += ea_bytes
                mnem = f"SUBI.{sz}  {imm_s},{ea_s}"
            elif (w & 0xFF00) == 0x0600 and (w & 0x00C0) != 0x00C0:
                # ADDI
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                if sz == "B":
                    imm = r16(d, off+2) & 0xFF
                    imm_s = f"#${imm:02X}"
                    consumed = 4
                elif sz == "L":
                    imm = r32(d, off+2)
                    imm_s = f"#${imm:08X}"
                    consumed = 6
                else:
                    imm = r16(d, off+2)
                    imm_s = f"#${imm:04X}"
                    consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
                consumed += ea_bytes
                mnem = f"ADDI.{sz}  {imm_s},{ea_s}"
            elif (w & 0xFF00) == 0x0C00 and (w & 0x00C0) != 0x00C0:
                # CMPI
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                if sz == "B":
                    imm = r16(d, off+2) & 0xFF
                    imm_s = f"#${imm:02X}"
                    consumed = 4
                elif sz == "L":
                    imm = r32(d, off+2)
                    imm_s = f"#${imm:08X}"
                    consumed = 6
                else:
                    imm = r16(d, off+2)
                    imm_s = f"#${imm:04X}"
                    consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
                consumed += ea_bytes
                mnem = f"CMPI.{sz}  {imm_s},{ea_s}"
            elif (w & 0xFFC0) == 0x0800:
                # BTST #imm,<ea>
                bit = r16(d, off+2)
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, "B", pc+consumed)
                consumed += ea_bytes
                mnem = f"BTST    #{bit},{ea_s}"
            elif (w & 0xFFC0) == 0x08C0:
                # BSET #imm,<ea>
                bit = r16(d, off+2)
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, "B", pc+consumed)
                consumed += ea_bytes
                mnem = f"BSET    #{bit},{ea_s}"
            elif (w & 0xFFC0) == 0x0880:
                # BCLR #imm,<ea>
                bit = r16(d, off+2)
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, "B", pc+consumed)
                consumed += ea_bytes
                mnem = f"BCLR    #{bit},{ea_s}"
            elif (w & 0xFFC0) == 0x0840:
                # BCHG #imm,<ea>
                bit = r16(d, off+2)
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, "B", pc+consumed)
                consumed += ea_bytes
                mnem = f"BCHG    #{bit},{ea_s}"
            elif (w & 0xF1C0) == 0x0100:
                # BTST Dn,<ea>
                dn = (w >> 9) & 7
                dst_mode = (w >> 3) & 7
                dst_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, dst_mode, dst_reg, "B", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"BTST    {DREG(dn)},{ea_s}"

        # MOVE/MOVEA
        elif op_hi4 in (1, 2, 3):
            sz_map = {1: "B", 3: "W", 2: "L"}
            sz = sz_map[op_hi4]
            dst_reg = (w >> 9) & 7
            dst_mode = (w >> 6) & 7
            src_mode = (w >> 3) & 7
            src_reg = w & 7
            src_s, src_bytes = ea_decode(d, off+2, src_mode, src_reg, sz, pc+2)
            consumed = 2 + src_bytes
            dst_s, dst_bytes = ea_decode(d, off+consumed, dst_mode, dst_reg, sz, pc+consumed)
            consumed += dst_bytes
            if dst_mode == 1:
                mnem = f"MOVEA.{sz} {src_s},{AREG(dst_reg)}"
            else:
                mnem = f"MOVE.{sz}  {src_s},{dst_s}"

        # 0100 - misc (LEA, CLR, TST, NEG, NOT, JSR, JMP, PEA, MOVEM, etc.)
        elif op_hi4 == 4:
            if (w & 0xFF00) == 0x4200:
                # CLR
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"CLR.{sz}   {ea_s}"
            elif (w & 0xFF00) == 0x4400:
                # NEG
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"NEG.{sz}   {ea_s}"
            elif (w & 0xFF00) == 0x4600:
                # NOT
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"NOT.{sz}   {ea_s}"
            elif (w & 0xFF00) == 0x4A00:
                # TST
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"TST.{sz}   {ea_s}"
            elif (w & 0xFFF8) == 0x4840:
                # SWAP Dn
                mnem = f"SWAP    {DREG(w & 7)}"
            elif (w & 0xFFF8) == 0x4880:
                # EXT.W Dn
                mnem = f"EXT.W   {DREG(w & 7)}"
            elif (w & 0xFFF8) == 0x48C0:
                # EXT.L Dn
                mnem = f"EXT.L   {DREG(w & 7)}"
            elif (w & 0xFFC0) == 0x4840 and ((w >> 3) & 7) != 0:
                # PEA
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "L", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"PEA     {ea_s}"
            elif (w & 0xFFC0) == 0x4E80:
                # JSR
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "L", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"JSR     {ea_s}"
            elif (w & 0xFFC0) == 0x4EC0:
                # JMP
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "L", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"JMP     {ea_s}"
            elif w == 0x4E75:
                mnem = "RTS"
            elif w == 0x4E71:
                mnem = "NOP"
            elif w == 0x4E73:
                mnem = "RTE"
            elif w == 0x4E77:
                mnem = "RTR"
            elif (w & 0xFFF0) == 0x4E60:
                # MOVE USP
                if w & 8:
                    mnem = f"MOVE    USP,{AREG(w & 7)}"
                else:
                    mnem = f"MOVE    {AREG(w & 7)},USP"
            elif (w & 0xFFF8) == 0x4E50:
                # LINK
                disp = s16(r16(d, off+2))
                consumed = 4
                mnem = f"LINK    {AREG(w & 7)},#${disp & 0xFFFF:04X}"
            elif (w & 0xFFF8) == 0x4E58:
                # UNLK
                mnem = f"UNLK    {AREG(w & 7)}"
            elif (w & 0xFB80) == 0x4880:
                # MOVEM
                direction = (w >> 10) & 1  # 0=reg-to-mem, 1=mem-to-reg
                sz = "L" if w & 0x0040 else "W"
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                mask = r16(d, off+2)
                consumed = 4
                ea_s, ea_bytes = ea_decode(d, off+consumed, ea_mode, ea_reg, sz, pc+consumed)
                consumed += ea_bytes
                reverse = (ea_mode == 4)
                rl = reglist(mask, reverse)
                if direction == 0:
                    mnem = f"MOVEM.{sz} {rl},{ea_s}"
                else:
                    mnem = f"MOVEM.{sz} {ea_s},{rl}"
            elif (w & 0xF1C0) == 0x41C0:
                # LEA
                an = (w >> 9) & 7
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "L", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"LEA     {ea_s},{AREG(an)}"
            elif w == 0x46FC:
                # MOVE #imm,SR
                imm = r16(d, off+2)
                consumed = 4
                mnem = f"MOVE    #${imm:04X},SR"
            elif (w & 0xFFC0) == 0x46C0:
                # MOVE <ea>,SR
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"MOVE    {ea_s},SR"
            elif (w & 0xFFC0) == 0x44C0:
                # MOVE <ea>,CCR
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"MOVE    {ea_s},CCR"

        # ADDQ/SUBQ/Scc/DBcc
        elif op_hi4 == 5:
            if (w & 0x00C0) == 0x00C0:
                # Scc or DBcc
                cond = (w >> 8) & 0xF
                if (w & 0x00F8) == 0x00C8:
                    # DBcc
                    dn = w & 7
                    disp = s16(r16(d, off+2))
                    consumed = 4
                    target = pc + 2 + disp
                    cc_names = ["T","F","HI","LS","CC","CS","NE","EQ",
                                "VC","VS","PL","MI","GE","LT","GT","LE"]
                    mnem = f"DB{cc_names[cond]}    {DREG(dn)},$%06X" % target
                else:
                    # Scc
                    ea_mode = (w >> 3) & 7
                    ea_reg = w & 7
                    ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "B", pc+2)
                    consumed = 2 + ea_bytes
                    cc_names = ["T","F","HI","LS","CC","CS","NE","EQ",
                                "VC","VS","PL","MI","GE","LT","GT","LE"]
                    mnem = f"S{cc_names[cond]}     {ea_s}"
            else:
                # ADDQ/SUBQ
                data3 = (w >> 9) & 7
                if data3 == 0: data3 = 8
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                if w & 0x0100:
                    mnem = f"SUBQ.{sz}  #{data3},{ea_s}"
                else:
                    mnem = f"ADDQ.{sz}  #{data3},{ea_s}"

        # Bcc/BRA/BSR
        elif op_hi4 == 6:
            cond = (w >> 8) & 0xF
            disp8 = w & 0xFF
            if disp8 == 0:
                disp = s16(r16(d, off+2))
                consumed = 4
                target = pc + 2 + disp
            elif disp8 == 0xFF:
                disp = struct.unpack_from(">i", d, off+2)[0]
                consumed = 6
                target = pc + 2 + disp
            else:
                disp = s8(disp8)
                target = pc + 2 + disp
            cc_names = ["BRA","BSR","BHI","BLS","BCC","BCS","BNE","BEQ",
                        "BVC","BVS","BPL","BMI","BGE","BLT","BGT","BLE"]
            sz_s = ".S" if consumed == 2 else (".W" if consumed == 4 else ".L")
            mnem = f"{cc_names[cond]}{sz_s}   ${target:06X}"

        # MOVEQ
        elif op_hi4 == 7:
            if not (w & 0x0100):
                dn = (w >> 9) & 7
                imm = s8(w & 0xFF)
                mnem = f"MOVEQ   #{imm},{DREG(dn)}"

        # OR/DIV/SBCD
        elif op_hi4 == 8:
            if (w & 0x01C0) == 0x00C0:
                # DIVU
                dn = (w >> 9) & 7
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"DIVU.W  {ea_s},{DREG(dn)}"
            elif (w & 0x01C0) == 0x01C0:
                # DIVS
                dn = (w >> 9) & 7
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"DIVS.W  {ea_s},{DREG(dn)}"
            else:
                # OR
                dn = (w >> 9) & 7
                direction = (w >> 8) & 1
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                if direction:
                    mnem = f"OR.{sz}    {DREG(dn)},{ea_s}"
                else:
                    mnem = f"OR.{sz}    {ea_s},{DREG(dn)}"

        # SUB/SUBA/SUBX
        elif op_hi4 == 9:
            if (w & 0x00C0) == 0x00C0:
                # SUBA
                an = (w >> 9) & 7
                sz = "L" if w & 0x0100 else "W"
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"SUBA.{sz}  {ea_s},{AREG(an)}"
            else:
                dn = (w >> 9) & 7
                direction = (w >> 8) & 1
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                if direction:
                    mnem = f"SUB.{sz}   {DREG(dn)},{ea_s}"
                else:
                    mnem = f"SUB.{sz}   {ea_s},{DREG(dn)}"

        # CMP/CMPA/EOR
        elif op_hi4 == 0xB:
            if (w & 0x00C0) == 0x00C0:
                # CMPA
                an = (w >> 9) & 7
                sz = "L" if w & 0x0100 else "W"
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"CMPA.{sz}  {ea_s},{AREG(an)}"
            elif w & 0x0100:
                # EOR or CMPM
                if (w & 0x0038) == 0x0008:
                    # CMPM
                    sz_bits = (w >> 6) & 3
                    sz = SIZE_NAMES.get(sz_bits, "?")
                    ax = (w >> 9) & 7
                    ay = w & 7
                    mnem = f"CMPM.{sz}  ({AREG(ay)})+,({AREG(ax)})+"
                else:
                    dn = (w >> 9) & 7
                    sz_bits = (w >> 6) & 3
                    sz = SIZE_NAMES.get(sz_bits, "?")
                    ea_mode = (w >> 3) & 7
                    ea_reg = w & 7
                    ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                    consumed = 2 + ea_bytes
                    mnem = f"EOR.{sz}   {DREG(dn)},{ea_s}"
            else:
                # CMP
                dn = (w >> 9) & 7
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"CMP.{sz}   {ea_s},{DREG(dn)}"

        # AND/MUL/ABCD/EXG
        elif op_hi4 == 0xC:
            if (w & 0x01C0) == 0x00C0:
                # MULU
                dn = (w >> 9) & 7
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"MULU.W  {ea_s},{DREG(dn)}"
            elif (w & 0x01C0) == 0x01C0:
                # MULS
                dn = (w >> 9) & 7
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"MULS.W  {ea_s},{DREG(dn)}"
            elif (w & 0xF1F8) == 0xC140:
                # EXG Dn,Dn
                rx = (w >> 9) & 7
                ry = w & 7
                mnem = f"EXG     {DREG(rx)},{DREG(ry)}"
            elif (w & 0xF1F8) == 0xC148:
                # EXG An,An
                rx = (w >> 9) & 7
                ry = w & 7
                mnem = f"EXG     {AREG(rx)},{AREG(ry)}"
            elif (w & 0xF1F8) == 0xC188:
                # EXG Dn,An
                rx = (w >> 9) & 7
                ry = w & 7
                mnem = f"EXG     {DREG(rx)},{AREG(ry)}"
            else:
                dn = (w >> 9) & 7
                direction = (w >> 8) & 1
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                if direction:
                    mnem = f"AND.{sz}   {DREG(dn)},{ea_s}"
                else:
                    mnem = f"AND.{sz}   {ea_s},{DREG(dn)}"

        # ADD/ADDA/ADDX
        elif op_hi4 == 0xD:
            if (w & 0x00C0) == 0x00C0:
                # ADDA
                an = (w >> 9) & 7
                sz = "L" if w & 0x0100 else "W"
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                mnem = f"ADDA.{sz}  {ea_s},{AREG(an)}"
            else:
                dn = (w >> 9) & 7
                direction = (w >> 8) & 1
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, sz, pc+2)
                consumed = 2 + ea_bytes
                if direction:
                    mnem = f"ADD.{sz}   {DREG(dn)},{ea_s}"
                else:
                    mnem = f"ADD.{sz}   {ea_s},{DREG(dn)}"

        # Shift/Rotate
        elif op_hi4 == 0xE:
            if (w & 0x00C0) == 0x00C0:
                # Memory shift
                direction = "L" if w & 0x0100 else "R"
                kind = (w >> 9) & 3
                kind_names = ["AS", "LS", "ROX", "RO"]
                ea_mode = (w >> 3) & 7
                ea_reg = w & 7
                ea_s, ea_bytes = ea_decode(d, off+2, ea_mode, ea_reg, "W", pc+2)
                consumed = 2 + ea_bytes
                mnem = f"{kind_names[kind]}{direction}.W  {ea_s}"
            else:
                direction = "L" if w & 0x0100 else "R"
                sz_bits = (w >> 6) & 3
                sz = SIZE_NAMES.get(sz_bits, "?")
                kind = (w >> 3) & 3
                kind_names = ["AS", "LS", "ROX", "RO"]
                dn = w & 7
                if w & 0x0020:
                    cnt = DREG((w >> 9) & 7)
                else:
                    cnt = (w >> 9) & 7
                    if cnt == 0: cnt = 8
                    cnt = f"#{cnt}"
                mnem = f"{kind_names[kind]}{direction}.{sz}  {cnt},{DREG(dn)}"

        # LEA via 4xxx already covered
        # LINK/UNLK already covered

        if mnem is None:
            mnem = f"DC.W    ${w:04X}"

        raw_bytes = " ".join(f"{d[off+i]:02X}" for i in range(min(consumed, len(d)-off)))
        results.append((pc, raw_bytes, mnem))
        off += consumed

    return results

# ---- Main ----
print("Fetching 512 bytes from $D5B0...")
rom = fetch_mem(0xD5B0, 512)

print(f"\n{'='*80}")
print(f"M68K Disassembly: $D5B0-$D7AF (GEMS Sound Update Routine)")
print(f"{'='*80}\n")

lines = disasm(rom, 0xD5B0, 512)

# Annotate known addresses
def annotate(mnem):
    notes = []
    if "E0FF0116" in mnem or "($E0FF0116)" in mnem:
        notes.append("GEMS: pending command count")
    if "E0FF0198" in mnem or "($E0FF0198)" in mnem:
        notes.append("GEMS: command table base/ptr")
    if "E0FF019A" in mnem or "($E0FF019A)" in mnem:
        notes.append("GEMS: command table offset")
    if "00A11100" in mnem:
        notes.append("Z80 bus request register")
    if "00A11200" in mnem:
        notes.append("Z80 reset register")
    if "00005204" in mnem or "000052B4" in mnem:
        notes.append("GEMS: Z80 bus request subroutine?")
    if "$A00" in mnem or "$00A0" in mnem:
        notes.append("Z80 address space")
    if "A01C" in mnem:
        notes.append("GEMS command buffer area")
    if "E0FF00" in mnem:
        notes.append("Work RAM ($FF00xx)")
    if "E0FF01" in mnem:
        notes.append("Work RAM ($FF01xx)")
    if notes:
        return "  ; " + " | ".join(notes)
    return ""

for pc, raw, mnem in lines:
    ann = annotate(mnem + " " + raw)
    print(f"${pc:06X}: {raw:<24s} {mnem}{ann}")

# Summary
print(f"\n{'='*80}")
print("ANALYSIS SUMMARY")
print(f"{'='*80}")

z80_writes = []
z80_reads = []
ram_accesses = []
jsrs = []

for pc, raw, mnem in lines:
    full = mnem + " " + raw
    if "A0" in full and ("00A0" in full or "$A0" in full):
        if "MOVE" in mnem and mnem.index("MOVE") == 0:
            # Check destination
            parts = mnem.split(",")
            if len(parts) == 2:
                dst = parts[1].strip()
                if "A0" in dst or "A1" in dst:
                    pass  # Loading address
                else:
                    z80_writes.append((pc, mnem))
    if "JSR" in mnem or "BSR" in mnem:
        jsrs.append((pc, mnem))
    if "E0FF" in full or "FF00" in full or "FF01" in full:
        ram_accesses.append((pc, mnem))

print(f"\nSubroutine calls (JSR/BSR):")
for pc, m in jsrs:
    print(f"  ${pc:06X}: {m}")

print(f"\nWork RAM accesses ($FFxxxx):")
for pc, m in ram_accesses:
    print(f"  ${pc:06X}: {m}")
