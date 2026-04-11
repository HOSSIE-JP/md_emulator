#!/usr/bin/env python3
"""Disassemble M68K code at $6C8E and $6CEC from the emulator API."""
import json
import urllib.request
import struct

BASE = "http://127.0.0.1:8080/api/v1/cpu/memory"

def fetch(addr, length):
    url = f"{BASE}?addr={addr}&len={length}"
    with urllib.request.urlopen(url) as resp:
        d = json.loads(resp.read())
    return bytes(d["data"])

def r16(data, pos):
    if pos + 1 < len(data):
        return (data[pos] << 8) | data[pos + 1]
    return 0

def r32(data, pos):
    if pos + 3 < len(data):
        return struct.unpack_from(">I", data, pos)[0]
    return 0

def s8(v):
    return v - 256 if v >= 128 else v

def s16(v):
    return v - 65536 if v >= 32768 else v

def disasm(data, base_addr, max_bytes=None):
    """Disassemble M68K code. Returns list of (addr, raw_bytes, mnemonic)."""
    results = []
    pos = 0
    limit = len(data) - 1 if max_bytes is None else min(max_bytes, len(data) - 1)

    while pos < limit:
        addr = base_addr + pos
        sp = pos
        w = r16(data, pos)
        pos += 2
        inst = None

        # ---- MOVE.B #imm, (xxx).L ---- 13FC
        if w == 0x13FC:
            imm = r16(data, pos) & 0xFF; pos += 2
            dst = r32(data, pos); pos += 4
            inst = f"MOVE.B  #${imm:02X}, (${dst:08X}).L"

        # ---- MOVE.W #imm, (xxx).L ---- 33FC
        elif w == 0x33FC:
            imm = r16(data, pos); pos += 2
            dst = r32(data, pos); pos += 4
            inst = f"MOVE.W  #${imm:04X}, (${dst:08X}).L"

        # ---- MOVE.W (xxx).L, (xxx).L ---- 33F9
        elif w == 0x33F9:
            src = r32(data, pos); pos += 4
            dst = r32(data, pos); pos += 4
            inst = f"MOVE.W  (${src:08X}).L, (${dst:08X}).L"

        # ---- MOVE.W (xxx).L, Dn ---- 3039, 3239, 3439, 3639
        elif w & 0xF1FF == 0x3039:
            dn = (w >> 9) & 7
            src = r32(data, pos); pos += 4
            inst = f"MOVE.W  (${src:08X}).L, D{dn}"

        # ---- MOVE.W Dn, (xxx).L ---- 33C0-33C7
        elif w & 0xFFF8 == 0x33C0:
            dn = w & 7
            dst = r32(data, pos); pos += 4
            inst = f"MOVE.W  D{dn}, (${dst:08X}).L"

        # ---- MOVE.L #imm, (xxx).L ---- 23FC
        elif w == 0x23FC:
            imm = r32(data, pos); pos += 4
            dst = r32(data, pos); pos += 4
            inst = f"MOVE.L  #${imm:08X}, (${dst:08X}).L"

        # ---- MOVEQ #imm, Dn ---- 70xx-7Exx (even)
        elif (w >> 12) == 7 and not (w & 0x100):
            dn = (w >> 9) & 7
            imm = w & 0xFF
            inst = f"MOVEQ   #${imm:02X}, D{dn}"

        # ---- LEA (xxx).L, An ---- x1F9
        elif w & 0xF1FF == 0x41F9:
            an = (w >> 9) & 7
            ea = r32(data, pos); pos += 4
            inst = f"LEA     (${ea:08X}).L, A{an}"

        # ---- LEA d16(An), Am ---- x1E8+src
        elif w & 0xF1F8 == 0x41E8:
            am = (w >> 9) & 7
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"LEA     ${d16 & 0xFFFF:04X}(A{an}), A{am}"

        # ---- MOVEA.L #imm, An ---- x07C
        elif w & 0xF1FF == 0x207C:
            an = (w >> 9) & 7
            imm = r32(data, pos); pos += 4
            inst = f"MOVEA.L #${imm:08X}, A{an}"

        # ---- MOVEA.L (xxx).L, An ---- x079
        elif w & 0xF1FF == 0x2079:
            an = (w >> 9) & 7
            src = r32(data, pos); pos += 4
            inst = f"MOVEA.L (${src:08X}).L, A{an}"

        # ---- MOVEA.L d16(An), Am ---- x068+src
        elif w & 0xF1F8 == 0x2068:
            am = (w >> 9) & 7
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"MOVEA.L ${d16 & 0xFFFF:04X}(A{an}), A{am}"

        # ---- MOVEA.W d16(An), Am ---- 3x68+src
        elif w & 0xF1F8 == 0x3068:
            am = (w >> 9) & 7
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"MOVEA.W ${d16 & 0xFFFF:04X}(A{an}), A{am}"

        # ---- MOVE.W d16(An), Dm ---- 3x2A etc
        elif w & 0xF1C0 == 0x3028:
            dm = (w >> 9) & 7
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"MOVE.W  ${d16 & 0xFFFF:04X}(A{an}), D{dm}"

        # ---- MOVE.W (An), Dn ---- 3x10+src
        elif w & 0xF1F8 == 0x3010:
            dn = (w >> 9) & 7
            an = w & 7
            inst = f"MOVE.W  (A{an}), D{dn}"

        # ---- MOVE.W Dn, Dm ---- 3x00+src
        elif w & 0xF1F8 == 0x3000 and (w & 0xF000) == 0x3000:
            dm = (w >> 9) & 7
            dn = w & 7
            inst = f"MOVE.W  D{dn}, D{dm}"

        # ---- MOVE.L Dn, -(SP) ---- 2F0x
        elif w & 0xFFF8 == 0x2F00:
            dn = w & 7
            inst = f"MOVE.L  D{dn}, -(SP)"

        # ---- MOVE.L An, -(SP) ---- 2F08+
        elif w & 0xFFF8 == 0x2F08:
            an = w & 7
            inst = f"MOVE.L  A{an}, -(SP)"

        # ---- MOVEA.L (SP)+, An ---- 2x5F
        elif w & 0xF1FF == 0x205F:
            an = (w >> 9) & 7
            inst = f"MOVEA.L (SP)+, A{an}"

        # ---- MOVE.L (SP)+, Dn ---- 2x1F
        elif w & 0xF1FF == 0x201F:
            dn = (w >> 9) & 7
            inst = f"MOVE.L  (SP)+, D{dn}"

        # ---- PEA (xxx).W ---- 4878
        elif w == 0x4878:
            val = r16(data, pos); pos += 2
            inst = f"PEA     (${val:04X}).W"

        # ---- PEA (xxx).L ---- 4879
        elif w == 0x4879:
            val = r32(data, pos); pos += 4
            inst = f"PEA     (${val:08X}).L"

        # ---- CLR.L -(SP) ---- 42A7
        elif w == 0x42A7:
            inst = "CLR.L   -(SP)"

        # ---- CLR.W -(SP) ---- 4267
        elif w == 0x4267:
            inst = "CLR.W   -(SP)"

        # ---- JSR (xxx).L ---- 4EB9
        elif w == 0x4EB9:
            target = r32(data, pos); pos += 4
            inst = f"JSR     (${target:08X}).L"

        # ---- JSR d16(PC) ---- 4EBA
        elif w == 0x4EBA:
            d16 = s16(r16(data, pos)); pos += 2
            target = addr + 2 + d16
            inst = f"JSR     ${target:06X}(PC)"

        # ---- BSR.W ---- 6100
        elif w == 0x6100:
            d16 = s16(r16(data, pos)); pos += 2
            target = addr + 2 + d16
            inst = f"BSR.W   ${target:06X}"

        # ---- BSR.B ---- 61xx
        elif (w >> 8) == 0x61 and (w & 0xFF):
            d8 = s8(w & 0xFF)
            target = addr + 2 + d8
            inst = f"BSR.B   ${target:06X}"

        # ---- BRA.W ---- 6000
        elif w == 0x6000:
            d16 = s16(r16(data, pos)); pos += 2
            target = addr + 2 + d16
            inst = f"BRA.W   ${target:06X}"

        # ---- BRA.B ---- 60xx
        elif (w >> 8) == 0x60 and (w & 0xFF):
            d8 = s8(w & 0xFF)
            target = addr + 2 + d8
            inst = f"BRA.B   ${target:06X}"

        # ---- Bcc.W ---- 6x00
        elif (w & 0xF0FF) == 0x6000 and (w & 0x0F00):
            cc = (w >> 8) & 0xF
            d16 = s16(r16(data, pos)); pos += 2
            target = addr + 2 + d16
            cc_names = {2:"HI",3:"LS",4:"CC",5:"CS",6:"NE",7:"EQ",
                        8:"VC",9:"VS",10:"PL",11:"MI",12:"GE",13:"LT",14:"GT",15:"LE"}
            cn = cc_names.get(cc, f"cc{cc}")
            inst = f"B{cn}.W  ${target:06X}"

        # ---- Bcc.B ---- 6xxx
        elif (w >> 12) == 0x6 and (w & 0xFF):
            cc = (w >> 8) & 0xF
            d8 = s8(w & 0xFF)
            target = addr + 2 + d8
            cc_names = {2:"HI",3:"LS",4:"CC",5:"CS",6:"NE",7:"EQ",
                        8:"VC",9:"VS",10:"PL",11:"MI",12:"GE",13:"LT",14:"GT",15:"LE"}
            cn = cc_names.get(cc, f"cc{cc}")
            inst = f"B{cn}.B  ${target:06X}"

        # ---- RTS ---- 4E75
        elif w == 0x4E75:
            inst = "RTS"

        # ---- RTE ---- 4E73
        elif w == 0x4E73:
            inst = "RTE"

        # ---- NOP ---- 4E71
        elif w == 0x4E71:
            inst = "NOP"

        # ---- ADDQ.W #n, Dn ---- 5n40+reg
        elif w & 0xF1C0 == 0x5040 and (w & 0x38) == 0:
            n = (w >> 9) & 7; n = n if n else 8
            dn = w & 7
            inst = f"ADDQ.W  #{n}, D{dn}"

        # ---- ADDQ.L #n, An ---- 5n48+reg (includes SP)
        elif w & 0xF1F8 == 0x5048:
            n = (w >> 9) & 7; n = n if n else 8
            an = w & 7
            nm = "SP" if an == 7 else f"A{an}"
            inst = f"ADDQ.L  #{n}, {nm}"

        # ---- SUBQ.W #n, Dn ---- 5n40+reg (bit8=1)
        elif w & 0xF1C0 == 0x5140 and (w & 0x38) == 0:
            n = (w >> 9) & 7; n = n if n else 8
            dn = w & 7
            inst = f"SUBQ.W  #{n}, D{dn}"

        # ---- SUBQ.L #n, An ---- 5n48+reg (bit8=1)
        elif w & 0xF1F8 == 0x5148:
            n = (w >> 9) & 7; n = n if n else 8
            an = w & 7
            nm = "SP" if an == 7 else f"A{an}"
            inst = f"SUBQ.L  #{n}, {nm}"

        # ---- ADDQ/SUBQ to other EA ----
        elif w & 0xF100 == 0x5000 and (w & 0xC0) != 0xC0:
            n = (w >> 9) & 7; n = n if n else 8
            sz = (w >> 6) & 3
            sub = (w >> 8) & 1
            op = "SUBQ" if sub else "ADDQ"
            szc = [".B", ".W", ".L"][sz]
            mode = (w >> 3) & 7
            reg = w & 7
            if mode == 0:
                inst = f"{op}{szc}  #{n}, D{reg}"
            elif mode == 1:
                nm = "SP" if reg == 7 else f"A{reg}"
                inst = f"{op}.L  #{n}, {nm}"
            else:
                inst = f"{op}{szc}  #{n}, ea({mode},{reg})"

        # ---- TST.W (xxx).L ---- 4A79
        elif w == 0x4A79:
            ea = r32(data, pos); pos += 4
            inst = f"TST.W   (${ea:08X}).L"

        # ---- TST.W Dn ---- 4A40-4A47
        elif w & 0xFFF8 == 0x4A40:
            dn = w & 7
            inst = f"TST.W   D{dn}"

        # ---- TST.B Dn ---- 4A00-4A07
        elif w & 0xFFF8 == 0x4A00:
            dn = w & 7
            inst = f"TST.B   D{dn}"

        # ---- TST.L Dn ---- 4A80
        elif w & 0xFFF8 == 0x4A80:
            dn = w & 7
            inst = f"TST.L   D{dn}"

        # ---- BTST #n, (xxx).L ---- 0839
        elif w == 0x0839:
            bit = r16(data, pos) & 0xFF; pos += 2
            ea = r32(data, pos); pos += 4
            inst = f"BTST    #{bit}, (${ea:08X}).L"

        # ---- BTST #n, Dn ---- 0800+reg
        elif w & 0xFFF8 == 0x0800:
            dn = w & 7
            bit = r16(data, pos); pos += 2
            inst = f"BTST    #{bit}, D{dn}"

        # ---- BTST Dn, Dm ---- 0x00+
        elif w & 0xF1F8 == 0x0100:
            dn = (w >> 9) & 7
            dm = w & 7
            inst = f"BTST    D{dn}, D{dm}"

        # ---- BSET #n, (xxx).L ---- 08F9
        elif w == 0x08F9:
            bit = r16(data, pos) & 0xFF; pos += 2
            ea = r32(data, pos); pos += 4
            inst = f"BSET    #{bit}, (${ea:08X}).L"

        # ---- BCLR #n, (xxx).L ---- 08B9
        elif w == 0x08B9:
            bit = r16(data, pos) & 0xFF; pos += 2
            ea = r32(data, pos); pos += 4
            inst = f"BCLR    #{bit}, (${ea:08X}).L"

        # ---- ORI.W #imm, (xxx).L ---- 0079
        elif w == 0x0079:
            imm = r16(data, pos); pos += 2
            dst = r32(data, pos); pos += 4
            inst = f"ORI.W   #${imm:04X}, (${dst:08X}).L"

        # ---- ORI.B #imm, (xxx).L ---- 0039
        elif w == 0x0039:
            imm = r16(data, pos) & 0xFF; pos += 2
            dst = r32(data, pos); pos += 4
            inst = f"ORI.B   #${imm:02X}, (${dst:08X}).L"

        # ---- CMPI.W #imm, Dn ---- 0C40+reg
        elif w & 0xFFF8 == 0x0C40:
            dn = w & 7
            imm = r16(data, pos); pos += 2
            inst = f"CMPI.W  #${imm:04X}, D{dn}"

        # ---- CMPI.B #imm, Dn ---- 0C00+reg
        elif w & 0xFFF8 == 0x0C00:
            dn = w & 7
            imm = r16(data, pos) & 0xFF; pos += 2
            inst = f"CMPI.B  #${imm:02X}, D{dn}"

        # ---- ANDI.W #imm, Dn ---- 0240+reg
        elif w & 0xFFF8 == 0x0240:
            dn = w & 7
            imm = r16(data, pos); pos += 2
            inst = f"ANDI.W  #${imm:04X}, D{dn}"

        # ---- ANDI.L #imm, Dn ---- 0280+reg
        elif w & 0xFFF8 == 0x0280:
            dn = w & 7
            imm = r32(data, pos); pos += 4
            inst = f"ANDI.L  #${imm:08X}, D{dn}"

        # ---- CMPA.W #imm, An ---- BxFC
        elif w & 0xF1FF == 0xB0FC:
            an = (w >> 9) & 7
            imm = r16(data, pos); pos += 2
            inst = f"CMPA.W  #${imm:04X}, A{an}"

        # ---- MOVEM.L regs, -(SP) ---- 48E7
        elif w == 0x48E7:
            mask = r16(data, pos); pos += 2
            regs = []
            for i in range(8):
                if mask & (1 << (15 - i)):
                    regs.append(f"D{i}")
            for i in range(8):
                if mask & (1 << (7 - i)):
                    regs.append(f"A{i}")
            inst = f"MOVEM.L {'/'.join(regs)}, -(SP)"

        # ---- MOVEM.L (SP)+, regs ---- 4CDF
        elif w == 0x4CDF:
            mask = r16(data, pos); pos += 2
            regs = []
            for i in range(8):
                if mask & (1 << i):
                    regs.append(f"D{i}")
            for i in range(8):
                if mask & (1 << (8 + i)):
                    regs.append(f"A{i}")
            inst = f"MOVEM.L (SP)+, {'/'.join(regs)}"

        # ---- MOVE.B #imm, (A0) ---- 10BC (size .B with dest=(A0))
        # Actually 10BC = MOVE.B #xx, (A0) format
        elif w == 0x10BC:
            imm = r16(data, pos); pos += 2
            # High byte is the value (only low byte of extension word matters for .B)
            inst = f"MOVE.B  #${(imm >> 8) & 0xFF:02X}, (A0)"
            # Actually for MOVE.B #imm, the imm is sign-extended from low byte of word
            # The encoding: 10BC XXYY where YY (or the whole word low byte) is the imm
            # Let me reconsider: for 10BC, dest is (A0), size is byte
            # The immediate word: low 8 bits are the value
            inst = f"MOVE.B  #${imm & 0xFF:02X}, (A0)"

        # ---- MOVE.W #imm, (An) ---- 34BC (dest=(A2))
        elif w & 0xF1FF == 0x30BC:
            an_map = {0x30BC: 0, 0x32BC: 1, 0x34BC: 2, 0x36BC: 3, 0x38BC: 4, 0x3ABC: 5, 0x3CBC: 6, 0x3EBC: 7}
            an = (w >> 9) & 7
            imm = r16(data, pos); pos += 2
            inst = f"MOVE.W  #${imm:04X}, (A{an})"

        # ---- MOVE.W Dm, (An) ---- 3x80+
        elif w & 0xF1F8 == 0x3080:
            an = (w >> 9) & 7
            dm = w & 7
            inst = f"MOVE.W  D{dm}, (A{an})"

        # ---- MOVE.L D2, (A2) ---- 2482
        elif w & 0xF1F8 == 0x2080:
            an = (w >> 9) & 7
            dm = w & 7
            inst = f"MOVE.L  D{dm}, (A{an})"

        # ---- MOVE.W Dm, d16(An) ---- 3540 etc
        elif w & 0xF1C0 == 0x3140:
            an = (w >> 9) & 7
            dm = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"MOVE.W  D{dm}, ${d16 & 0xFFFF:04X}(A{an})"

        # ---- ADD.W Dn, Dm ---- Dx40+src
        elif w & 0xF1C0 == 0xD040 and (w & 0x38) == 0:
            dm = (w >> 9) & 7
            dn = w & 7
            inst = f"ADD.W   D{dn}, D{dm}"

        # ---- SUB.L An, Dn ---- 9x88+src
        elif w & 0xF1F8 == 0x9088:
            dn = (w >> 9) & 7
            an = w & 7
            inst = f"SUB.L   A{an}, D{dn}"

        # ---- DBF Dn, target ---- 51C8+reg
        elif w & 0xFFF8 == 0x51C8:
            dn = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            target = addr + 2 + d16
            inst = f"DBF     D{dn}, ${target:06X}"

        # ---- CLR.B d16(An) ---- 4228+an
        elif w & 0xFFF8 == 0x4228:
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"CLR.B   ${d16 & 0xFFFF:04X}(A{an})"

        # ---- CLR.W Dn ---- 4240+reg
        elif w & 0xFFF8 == 0x4240:
            dn = w & 7
            inst = f"CLR.W   D{dn}"

        # ---- CLR.L Dn ---- 4280+reg
        elif w & 0xFFF8 == 0x4280:
            dn = w & 7
            inst = f"CLR.L   D{dn}"

        # ---- EXT.W Dn ---- 4880+reg
        elif w & 0xFFF8 == 0x4880:
            dn = w & 7
            inst = f"EXT.W   D{dn}"

        # ---- EXT.L Dn ---- 48C0+reg
        elif w & 0xFFF8 == 0x48C0:
            dn = w & 7
            inst = f"EXT.L   D{dn}"

        # ---- SWAP Dn ---- 4840+reg
        elif w & 0xFFF8 == 0x4840:
            dn = w & 7
            inst = f"SWAP    D{dn}"

        # ---- MOVE.B (An)+, Dm or similar ---- 1x18+src
        elif w & 0xF1F8 == 0x1018:
            dm = (w >> 9) & 7
            an = w & 7
            inst = f"MOVE.B  (A{an})+, D{dm}"

        # ---- MOVE.B d8(An,Xn), ... or d16(PC) ----

        # ---- General MOVE.B #imm to d16(An) ---- 117C etc
        elif w & 0xF1C0 == 0x1100 and (w & 0x38) == 0x38 and (w & 7) == 4:
            # MOVE.B #imm, ... but check the pattern
            pass

        # ---- BTST #n, d16(An) ---- 0828+src
        elif w & 0xFFF8 == 0x0828:
            an = w & 7
            bit = r16(data, pos) & 0xFF; pos += 2
            d16 = s16(r16(data, pos)); pos += 2
            # Hmm, 0828 is BTST #n, d8(An,Xn)? Let me check
            # Actually 0828 is not standard. Let me just use raw.
            pos -= 4  # rewind
            inst = None

        # ---- MOVE.B d16(An), Dm ---- various
        elif w & 0xF1C0 == 0x1028:
            dm = (w >> 9) & 7
            an = w & 7
            d16 = s16(r16(data, pos)); pos += 2
            inst = f"MOVE.B  ${d16 & 0xFFFF:04X}(A{an}), D{dm}"

        # ---- Generic fallback ----
        if inst is None:
            raw = " ".join(f"{data[sp+j]:02X}" for j in range(min(2, len(data) - sp)))
            inst = f"DC.W    ${w:04X}"

        raw_bytes = " ".join(f"{data[sp+j]:02X}" for j in range(pos - sp))
        results.append((addr, raw_bytes, inst))

        # If RTS found, mark it
        if inst == "RTS":
            results.append((None, "", ""))  # separator

    return results


def annotate(inst, addr):
    """Add comments for known addresses."""
    comments = []
    if "E0FFA820" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("dispatch counter")
    if "E0FF0062" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("dispatch return value")
    if "E0FF0064" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("dispatch mode flag")
    if "E0FF0066" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("*** FF0066 flags ***")
    if "E0FF0067" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("*** FF0067 flags ***")
    if "E0FF0116" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("GEMS command count")
    if "E0FF0198" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("GEMS command table ptr")
    if "E0FF019A" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("GEMS command table ptr+2")
    if "E0FF030B" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("sound/GEMS flag")
    if "E0FF0313" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("sound active flag")
    if "E0FF0318" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("sound channel table")
    if "E0FF030E" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("sound param")
    if "E0FF0310" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("sound param ptr")
    if "E0FF0628" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("channel table base ptr")
    if "00A11100" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("Z80 bus request")
    if "00A11200" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("Z80 reset")
    if "00C00011" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("VDP ctrl port")
    if "00C00004" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("VDP ctrl port")
    if "0001C372" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("ROM data pointer")
    if "00A00000" in inst.replace("$", "").replace(" ", "").upper():
        comments.append("Z80 RAM base")
    return "; ".join(comments)


print("=" * 80)
print("DISASSEMBLY OF $6C8E (initialization function called by dispatch(0,0))")
print("Called from $8C92: BSR $6C8E")
print("=" * 80)

data1 = fetch(0x6C8E, 1024)
result1 = disasm(data1, 0x6C8E, 512)

rts_count = 0
for addr, raw, inst in result1:
    if addr is None:
        print()
        rts_count += 1
        if rts_count >= 4:
            break
        continue
    comment = annotate(inst, addr)
    line = f"  ${addr:06X}: {raw:30s}  {inst}"
    if comment:
        line += f"    ; {comment}"
    print(line)

print()
print("=" * 80)
print("DISASSEMBLY OF $6CEC (dispatch main-loop handler)")
print("=" * 80)

data2 = fetch(0x6CEC, 512)
result2 = disasm(data2, 0x6CEC, 512)

rts_count = 0
for addr, raw, inst in result2:
    if addr is None:
        print()
        rts_count += 1
        if rts_count >= 3:
            break
        continue
    comment = annotate(inst, addr)
    line = f"  ${addr:06X}: {raw:30s}  {inst}"
    if comment:
        line += f"    ; {comment}"
    print(line)

# Also check the subroutine targets
print()
print("=" * 80)
print("SUBROUTINE TARGETS CALLED FROM $6C8E FUNCTION")
print("=" * 80)
for addr, raw, inst in result1:
    if addr is None:
        continue
    if "JSR" in inst or "BSR" in inst:
        print(f"  ${addr:06X}: {inst}")
