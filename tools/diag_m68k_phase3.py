#!/usr/bin/env python3
"""M68K Phase 3ハンドラ解析: $85C0-$8640 ROM領域のディスアセンブル"""
import requests

API = "http://localhost:8080/api/v1"

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={addr + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def disasm_m68k_simple(data, base):
    """Very basic M68K disassembler for common patterns"""
    i = 0
    lines = []
    while i < len(data) - 1:
        addr = base + i
        w = (data[i] << 8) | data[i+1]

        # MOVE.B ($A0xxxx).L, Dn  →  1C39/1439/etc
        if (w >> 8) in (0x14, 0x16, 0x18, 0x1A, 0x1C, 0x1E) and data[i+1] == 0x39:
            if i + 5 < len(data):
                a = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
                dreg = (w >> 9) & 7
                lines.append(f"${addr:06X}: MOVE.B (${a:08X}).L, D{dreg}")
                i += 6; continue

        # MOVE.B #imm, ($A0xxxx).L  →  13FC
        if w == 0x13FC and i + 7 < len(data):
            imm = data[i+3]  # byte immediate at i+2..i+3
            a = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            lines.append(f"${addr:06X}: MOVE.B #${imm:02X}, (${a:08X}).L")
            i += 8; continue

        # MOVE.B Dn, ($A0xxxx).L  →  13C0..13C7
        if (w & 0xFFF8) == 0x13C0 and i + 5 < len(data):
            sreg = w & 7
            a = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
            lines.append(f"${addr:06X}: MOVE.B D{sreg}, (${a:08X}).L")
            i += 6; continue

        # MOVE.W #imm, ($A11100)  →  33FC
        if w == 0x33FC and i + 7 < len(data):
            imm = (data[i+2] << 8) | data[i+3]
            a = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            lines.append(f"${addr:06X}: MOVE.W #${imm:04X}, (${a:08X}).L")
            i += 8; continue

        # BTST #bit, ($A11100)  →  0839
        if w == 0x0839 and i + 7 < len(data):
            bit = data[i+3]
            a = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            lines.append(f"${addr:06X}: BTST #{bit}, (${a:08X}).L")
            i += 8; continue

        # BNE.B offset
        if (w >> 8) == 0x66:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            target = addr + 2 + off
            lines.append(f"${addr:06X}: BNE.B ${target:06X}")
            i += 2; continue

        # BEQ.B offset
        if (w >> 8) == 0x67:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            target = addr + 2 + off
            lines.append(f"${addr:06X}: BEQ.B ${target:06X}")
            i += 2; continue

        # BRA.B offset
        if (w >> 8) == 0x60:
            off = w & 0xFF
            if off == 0:
                if i + 3 < len(data):
                    off = (data[i+2] << 8) | data[i+3]
                    if off >= 0x8000: off -= 0x10000
                    target = addr + 2 + off
                    lines.append(f"${addr:06X}: BRA.W ${target:06X}")
                    i += 4; continue
            else:
                if off >= 0x80: off -= 256
                target = addr + 2 + off
                lines.append(f"${addr:06X}: BRA.B ${target:06X}")
                i += 2; continue

        # JSR (abs).L  →  4EB9
        if w == 0x4EB9 and i + 5 < len(data):
            a = (data[i+2] << 24) | (data[i+3] << 16) | (data[i+4] << 8) | data[i+5]
            lines.append(f"${addr:06X}: JSR ${a:08X}")
            i += 6; continue

        # RTS  →  4E75
        if w == 0x4E75:
            lines.append(f"${addr:06X}: RTS")
            i += 2; continue

        # MOVE.W #imm, (abs).L  →  33FC
        # Already handled above

        # MOVEQ #imm, Dn  →  7000..7FFF
        if (w >> 12) == 7:
            dreg = (w >> 9) & 7
            imm = w & 0xFF
            if imm >= 0x80: imm -= 256
            lines.append(f"${addr:06X}: MOVEQ #{imm}, D{dreg}")
            i += 2; continue

        # TST.B Dn or TST.W Dn
        if (w & 0xFFF8) == 0x4A00:
            lines.append(f"${addr:06X}: TST.B D{w & 7}")
            i += 2; continue

        # Default: show raw word
        lines.append(f"${addr:06X}: DC.W ${w:04X}")
        i += 2

    return lines

def main():
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 1})

    # === Read M68K ROM around the $A00102 read locations ===
    print("=== M68K Phase handler regions (with $A00102 reads) ===")

    regions = [
        (0x8340, 0xC0, "Handler 1 ($836C/$83C8)"),
        (0x85A0, 0xC0, "Handler 2 ($85CE/$862A)"),
        (0x8770, 0xC0, "Handler 3 ($8796/$87F2)"),
        (0x8920, 0xC0, "Handler 4 ($893E/$899A)"),
        (0x8AC0, 0xC0, "Handler 5 ($8AEA/$8B46)"),
        (0x8D80, 0xC0, "Handler 6 ($8DA0/$8E30)"),
    ]

    for start, length, label in regions:
        print(f"\n--- {label} ---")
        data = read_mem(start, length)
        lines = disasm_m68k_simple(data, start)
        for line in lines:
            mark = ""
            if "A00102" in line: mark = " <<<<<"
            elif "A00100" in line: mark = " <<<"
            elif "A11100" in line: mark = " <--bus"
            elif "A11200" in line: mark = " <--reset"
            elif "A00161" in line: mark = " <<161"
            print(f"  {line}{mark}")

    # === Also check the dispatch table mechanism ===
    print("\n\n=== M68K dispatch at $7A5E area: how Phase 3 handler is selected ===")
    # Read main loop dispatch
    data_7a = read_mem(0x7A00, 0x100)
    lines_7a = disasm_m68k_simple(data_7a, 0x7A00)
    for line in lines_7a[:40]:
        print(f"  {line}")

    # === Also read $7C00-$7C50 to understand bit2 handler entry ===
    print("\n=== $7C00-$7C60 (bit 2 handler entry) ===")
    data_7c = read_mem(0x7C00, 0x60)
    lines_7c = disasm_m68k_simple(data_7c, 0x7C00)
    for line in lines_7c:
        print(f"  {line}")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
