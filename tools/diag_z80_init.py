#!/usr/bin/env python3
"""Z80初期化コード解析 + $0102 bit 4 のセッターを特定"""
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
    print(f"Z80 RAM: {len(z80)} bytes")

    # === Z80 init code at $02B7 ===
    print("\n=== Z80 初期化コード ($02B7-$0350) ===")
    for i in range(0x02B7, min(0x0350, len(z80))):
        b = z80[i]
        extra = ""
        if i + 2 < len(z80):
            if b == 0xCD: extra = f" → CALL ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC3: extra = f" → JP ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x21: extra = f" → LD HL, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x3A: extra = f" → LD A, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0x32: extra = f" → LD (${z80[i+1] | (z80[i+2] << 8):04X}), A"
            elif b == 0x22: extra = f" → LD (${z80[i+1] | (z80[i+2] << 8):04X}), HL"
            elif b == 0x2A: extra = f" → LD HL, (${z80[i+1] | (z80[i+2] << 8):04X})"
            elif b == 0x01: extra = f" → LD BC, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x11: extra = f" → LD DE, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0x31: extra = f" → LD SP, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xCA: extra = f" → JP Z, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xC2: extra = f" → JP NZ, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xDA: extra = f" → JP C, ${z80[i+1] | (z80[i+2] << 8):04X}"
            elif b == 0xD2: extra = f" → JP NC, ${z80[i+1] | (z80[i+2] << 8):04X}"
        if b == 0xF3: extra = " → DI"
        elif b == 0xFB: extra = " → EI"
        elif b == 0xC9: extra = " → RET"
        elif b == 0xCF: extra = " → RST $08"
        elif b == 0xAF: extra = " → XOR A"
        elif b == 0x76: extra = " → HALT"
        elif i + 1 < len(z80) and b == 0xCB:
            op2 = z80[i+1]
            op_type = (op2 >> 6) & 3
            bit = (op2 >> 3) & 7
            reg = op2 & 7
            rn = ["B","C","D","E","H","L","(HL)","A"][reg]
            if op_type == 1: extra = f" {z80[i+1]:02X} → BIT {bit}, {rn}"
            elif op_type == 2: extra = f" {z80[i+1]:02X} → RES {bit}, {rn}"
            elif op_type == 3: extra = f" {z80[i+1]:02X} → SET {bit}, {rn}"

        print(f"  ${i:04X}: {b:02X}{extra}")

    # === Search for ALL writes to $0102 ===
    print("\n=== $0102 への書き込み命令検索 ===")
    # LD ($0102), A = 32 02 01
    # SET/RES bit, (HL) when HL=$0102 → needs LD HL, $0102 (21 02 01) then CB xx
    for i in range(len(z80) - 2):
        if z80[i+1] == 0x02 and z80[i+2] == 0x01:
            if z80[i] == 0x32:
                print(f"  ${i:04X}: LD ($0102), A")
            elif z80[i] == 0x21:
                # Check following bytes for BIT/SET/RES operations
                ctx = z80[i:min(i+10, len(z80))]
                hex_str = " ".join(f"{b:02X}" for b in ctx)
                # Find CB instructions after LD HL
                for j in range(3, min(8, len(ctx)-1)):
                    if ctx[j] == 0xCB:
                        op2 = ctx[j+1]
                        ot = (op2 >> 6) & 3
                        bit = (op2 >> 3) & 7
                        reg = op2 & 7
                        rn = ["B","C","D","E","H","L","(HL)","A"][reg]
                        if ot == 1: print(f"  ${i:04X}: LD HL, $0102 ... BIT {bit}, {rn} → [{hex_str}]")
                        elif ot == 3: print(f"  ${i:04X}: LD HL, $0102 → SET {bit}, {rn} → [{hex_str}]")
                        elif ot == 2: print(f"  ${i:04X}: LD HL, $0102 → RES {bit}, {rn} → [{hex_str}]")
                        break

    # === Search M68K ROM for writes to $A00102 ===
    print("\n=== M68K ROM: $A00102 への書き込み検索 ===")
    # Read ROM sections that handle Z80 init
    # The M68K code at $8200-$8700 handles initialization
    for region_start in [0x8000, 0x8200, 0x8400, 0x8600, 0x7C00, 0x7E00]:
        rom_data = read_mem(region_start, 0x200)
        for i in range(len(rom_data) - 5):
            # Look for $A00102 patterns
            # MOVE.B #xx, ($A00102) or similar
            # The address $A00102 in M68K is: 00 A0 01 02
            # In byte stream: might appear as 00 A0 01 02
            if i + 3 < len(rom_data):
                addr32 = (rom_data[i] << 24) | (rom_data[i+1] << 16) | (rom_data[i+2] << 8) | rom_data[i+3]
                if addr32 == 0x00A00102:
                    ctx = rom_data[max(0,i-4):min(len(rom_data),i+8)]
                    hex_str = " ".join(f"{b:02X}" for b in ctx)
                    print(f"  ROM ${region_start+i:06X}: ref to $A00102 → [{hex_str}]")

    # === Search full ROM for $A00102 reference ===
    print("\n=== M68K ROM全域: $00A00102 パターン検索 ===")
    # Check in 4KB chunks
    for chunk_start in range(0, 0x80000, 0x1000):  # First 512KB
        try:
            rom_data = read_mem(chunk_start, 0x1000)
        except:
            continue
        for i in range(len(rom_data) - 3):
            w = (rom_data[i] << 24) | (rom_data[i+1] << 16) | (rom_data[i+2] << 8) | rom_data[i+3]
            if w == 0x00A00102:
                ctx_start = max(0, i-6)
                ctx_end = min(len(rom_data), i+8)
                ctx = rom_data[ctx_start:ctx_end]
                hex_str = " ".join(f"{b:02X}" for b in ctx)
                abs_addr = chunk_start + i
                print(f"  ROM ${abs_addr:06X}: $00A00102 → [{hex_str}]")

    # === EXPERIMENT: Manually set bit 4 of $0102 and check result ===
    print("\n=== 実験: Z80[$0102] に bit 4 を手動設定 ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 50})

    # Read current $0102
    val = read_z80(0x0102, 1)
    print(f"  Before: Z80[$0102] = ${val[0]:02X}")

    # Set bit 4 → $90
    new_val = val[0] | 0x10
    api_post("/cpu/memory", {"addr": 0xA00102, "data": [new_val]})

    # Verify
    val2 = read_z80(0x0102, 1)
    print(f"  After write: Z80[$0102] = ${val2[0]:02X}")

    # Run 100 more frames
    api_post("/emulator/step", {"frames": 100})

    # Check results
    val3 = read_z80(0x0102, 1)
    ff019c = read_mem(0xFF019C, 2)
    ff0066 = read_mem(0xFF0066, 2)
    ff0062 = read_mem(0xFF0062, 2)
    ffa820 = read_mem(0xFFA820, 2)

    print(f"\n  After 100 frames:")
    print(f"    Z80[$0102] = ${val3[0]:02X}")
    print(f"    $FF019C = ${(ff019c[0]<<8)|ff019c[1]:04X}")
    print(f"    $FF0066 = ${(ff0066[0]<<8)|ff0066[1]:04X}")
    print(f"    $FF0062 = ${(ff0062[0]<<8)|ff0062[1]:04X}")
    print(f"    $FFA820 = ${(ffa820[0]<<8)|ffa820[1]:04X}")

    # Check Z80[$0161]
    val_0161 = read_z80(0x0161, 1)
    print(f"    Z80[$0161] = ${val_0161[0]:02X}")

    # Check Z80[$01FE] (the wait counter stored by $0B84 function)
    val_01FE = read_z80(0x01FE, 1)
    print(f"    Z80[$01FE] = ${val_01FE[0]:02X} (wait loop counter)")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
