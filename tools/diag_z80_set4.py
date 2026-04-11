#!/usr/bin/env python3
"""Z80 RAM内のSET/RES bit 4操作検索 + コマンド処理フロー($033D/$038E)の詳細解析"""
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

def read_z80(start, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={0xA00000 + start + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def read_mem(addr, length):
    data = api_get(f"/cpu/memory?addr={addr}&len={length}")
    return data.get("data", [])

def main():
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 50})

    z80 = read_z80(0, 0x2000)

    # === Search for all SET bit, (HL) instructions (CB C6..CB FE) ===
    print("=== Z80 RAM: 全SET bit操作 on (HL) ===")
    for i in range(len(z80) - 1):
        if z80[i] == 0xCB:
            op2 = z80[i+1]
            ot = (op2 >> 6) & 3
            bit = (op2 >> 3) & 7
            reg = op2 & 7
            rn = ["B","C","D","E","H","L","(HL)","A"][reg]
            if ot == 3 and reg == 6:  # SET bit, (HL)
                # Find nearest LD HL, nn before this
                hl_target = None
                for j in range(i-1, max(i-30, -1), -1):
                    if z80[j] == 0x21 and j+2 < len(z80):
                        hl_target = z80[j+1] | (z80[j+2] << 8)
                        break
                target_str = f" [HL=${hl_target:04X}]" if hl_target is not None else ""
                print(f"  ${i:04X}: SET {bit}, (HL){target_str}")

    # === Search for SET 4 on ANY register ===
    print("\n=== Z80 RAM: SET 4 操作 (全レジスタ) ===")
    for i in range(len(z80) - 1):
        if z80[i] == 0xCB:
            op2 = z80[i+1]
            ot = (op2 >> 6) & 3
            bit = (op2 >> 3) & 7
            reg = op2 & 7
            rn = ["B","C","D","E","H","L","(HL)","A"][reg]
            if ot == 3 and bit == 4:
                print(f"  ${i:04X}: SET 4, {rn}")

    # === Search for OR $10 / OR #$10 on A (sets bit 4) ===
    print("\n=== Z80 RAM: OR/SET bit 4 on A (F6 10 = OR $10) ===")
    for i in range(len(z80) - 1):
        if z80[i] == 0xF6 and z80[i+1] == 0x10:
            print(f"  ${i:04X}: OR $10")

    # === Disassemble $033D-$0400 (main loop + command dispatch) ===
    print("\n=== Z80 Main Loop $033D-$03A0 ===")
    for i in range(0x033D, min(0x03A0, len(z80))):
        b = z80[i]
        extra = ""
        if i + 2 < len(z80):
            if b == 0xCD: extra = f" → CALL ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC3: extra = f" → JP ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x21: extra = f" → LD HL, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x3A: extra = f" → LD A, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0x32: extra = f" → LD (${ z80[i+1] | (z80[i+2] << 8):04X}), A"
            elif b == 0x22: extra = f" → LD (${z80[i+1] | (z80[i+2] << 8):04X}), HL"
            elif b == 0x2A: extra = f" → LD HL, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0xCA: extra = f" → JP Z, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC2: extra = f" → JP NZ, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xDA: extra = f" → JP C, ${z80[i+1] | (z80[i+2] << 8):04X}"
        if i + 1 < len(z80):
            if b == 0x20: 
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR NZ, ${i+2+off:04X}"
            elif b == 0x28:
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR Z, ${i+2+off:04X}"
            elif b == 0x18:
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR ${i+2+off:04X}"
            elif b == 0xCB:
                op2 = z80[i+1]
                ot = (op2 >> 6) & 3
                bit = (op2 >> 3) & 7
                reg = op2 & 7
                rn = ["B","C","D","E","H","L","(HL)","A"][reg]
                if ot == 0: extra = f" → RLC/RL/RRC/RR/SLA/SRA/? {rn}"
                elif ot == 1: extra = f" → BIT {bit}, {rn}"
                elif ot == 2: extra = f" → RES {bit}, {rn}"
                elif ot == 3: extra = f" → SET {bit}, {rn}"
        if b == 0xCF: extra = " → RST $08"
        elif b == 0xC9: extra = " → RET"
        elif b == 0xFB: extra = " → EI"
        elif b == 0xF3: extra = " → DI"
        elif b == 0xAF: extra = " → XOR A"
        print(f"  ${i:04X}: {b:02X}{extra}")

    # === Disassemble $038E-$03F0 (command processing branch) ===
    print("\n=== Z80 Command Dispatch $038E-$0420 ===")
    for i in range(0x038E, min(0x0420, len(z80))):
        b = z80[i]
        extra = ""
        if i + 2 < len(z80):
            if b == 0xCD: extra = f" → CALL ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC3: extra = f" → JP ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x21: extra = f" → LD HL, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x3A: extra = f" → LD A, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0x32: extra = f" → LD (${z80[i+1] | (z80[i+2] << 8):04X}), A"
            elif b == 0xCA: extra = f" → JP Z, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC2: extra = f" → JP NZ, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xDA: extra = f" → JP C, ${z80[i+1] | (z80[i+2] << 8):04X}"
        if i + 1 < len(z80):
            if b == 0x20:
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR NZ, ${i+2+off:04X}"
            elif b == 0x28:
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR Z, ${i+2+off:04X}"
            elif b == 0x18:
                off = z80[i+1]
                if off >= 0x80: off -= 256
                extra = f" → JR ${i+2+off:04X}"
            elif b == 0xCB:
                op2 = z80[i+1]
                ot = (op2 >> 6) & 3
                bit = (op2 >> 3) & 7
                reg = op2 & 7
                rn = ["B","C","D","E","H","L","(HL)","A"][reg]
                if ot == 1: extra = f" → BIT {bit}, {rn}"
                elif ot == 2: extra = f" → RES {bit}, {rn}"
                elif ot == 3: extra = f" → SET {bit}, {rn}"
        if b == 0xCF: extra = " → RST $08"
        elif b == 0xC9: extra = " → RET"
        elif b == 0xFB: extra = " → EI"
        elif b == 0xF3: extra = " → DI"
        elif b == 0xAF: extra = " → XOR A"
        print(f"  ${i:04X}: {b:02X}{extra}")

    # === Check $09D0-$09E0 ===
    print("\n=== Z80 $09C0-$09E0 ($09D5 LD ($0102), A コンテキスト) ===")
    for i in range(0x09C0, min(0x09E0, len(z80))):
        b = z80[i]
        extra = ""
        if i + 2 < len(z80):
            if b == 0xCD: extra = f" → CALL ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC3: extra = f" → JP ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x21: extra = f" → LD HL, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x3A: extra = f" → LD A, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0x32: extra = f" → LD (${z80[i+1] | (z80[i+2] << 8):04X}), A"
        if i + 1 < len(z80):
            if b == 0xCB:
                op2 = z80[i+1]
                ot = (op2 >> 6) & 3
                bit = (op2 >> 3) & 7
                reg = op2 & 7
                rn = ["B","C","D","E","H","L","(HL)","A"][reg]
                if ot == 1: extra = f" → BIT {bit}, {rn}"
                elif ot == 2: extra = f" → RES {bit}, {rn}"
                elif ot == 3: extra = f" → SET {bit}, {rn}"
        if b == 0xCF: extra = " → RST $08"
        elif b == 0xC9: extra = " → RET"
        elif b == 0xFB: extra = " → EI"
        elif b == 0xF3: extra = " → DI"
        elif b == 0xAF: extra = " → XOR A"
        print(f"  ${i:04X}: {b:02X}{extra}")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
