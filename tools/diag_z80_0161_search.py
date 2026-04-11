#!/usr/bin/env python3
"""Z80 RAM内の$0161参照を徹底検索 + Z80トレースリング解析"""
import requests, json

API = "http://localhost:8080/api/v1"

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=5)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def read_z80_chunk(start, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={0xA00000 + start + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def main():
    # Load and run
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 50})

    # Dump full Z80 RAM
    z80 = read_z80_chunk(0, 0x2000)
    print(f"Z80 RAM: {len(z80)} bytes")

    # === Search for byte pattern 61 01 (address $0161 in little-endian) ===
    print("\n=== 0x61 0x01 バイトパターン検索 ===")
    for i in range(len(z80) - 1):
        if z80[i] == 0x61 and z80[i+1] == 0x01:
            # Show context
            ctx_start = max(0, i - 4)
            ctx_end = min(len(z80), i + 6)
            ctx = z80[ctx_start:ctx_end]
            hex_str = " ".join(f"{b:02X}" for b in ctx)
            # Check preceding opcode
            prefix = z80[i-1] if i > 0 else 0
            prefix2 = z80[i-2] if i > 1 else 0
            instr = "???"
            if prefix == 0x3A: instr = "LD A, ($0161)"
            elif prefix == 0x32: instr = "LD ($0161), A"
            elif prefix == 0x21: instr = "LD HL, $0161"
            elif prefix == 0x01: instr = "LD BC, $0161"
            elif prefix == 0x11: instr = "LD DE, $0161"
            elif prefix2 == 0xDD and prefix == 0x21: instr = "LD IX, $0161"
            elif prefix2 == 0xFD and prefix == 0x21: instr = "LD IY, $0161"
            elif prefix == 0x22: instr = "LD ($0161), HL"
            elif prefix == 0x2A: instr = "LD HL, ($0161)"
            elif prefix2 == 0xED and prefix == 0x4B: instr = "LD BC, ($0161)"
            elif prefix2 == 0xED and prefix == 0x5B: instr = "LD DE, ($0161)"
            elif prefix2 == 0xED and prefix == 0x7B: instr = "LD SP, ($0161)"
            elif prefix == 0xCD: instr = "CALL $0161"
            elif prefix == 0xC3: instr = "JP $0161"
            elif prefix == 0xC2: instr = "JP NZ, $0161"
            elif prefix == 0xCA: instr = "JP Z, $0161"
            elif prefix == 0xD2: instr = "JP NC, $0161"
            elif prefix == 0xDA: instr = "JP C, $0161"
            print(f"  offset ${i:04X}: [{hex_str}] → {instr}")

    # === Search for how Z80 accesses the command area ($0150-$016F) ===
    print("\n=== $0150-$016F 範囲参照の検索 ===")
    for target_lo in range(0x50, 0x70):  # $0150-$016F
        target_hi = 0x01
        for i in range(len(z80) - 1):
            if z80[i] == target_lo and z80[i+1] == target_hi:
                prefix = z80[i-1] if i > 0 else 0
                # Only show instruction-like patterns
                if prefix in [0x3A, 0x32, 0x21, 0x01, 0x11, 0x22, 0x2A, 0xCD, 0xC3]:
                    instr_map = {
                        0x3A: "LD A,", 0x32: "LD (),A", 0x21: "LD HL,",
                        0x01: "LD BC,", 0x11: "LD DE,", 0x22: "LD (),HL",
                        0x2A: "LD HL,()", 0xCD: "CALL", 0xC3: "JP"
                    }
                    addr = target_lo | (target_hi << 8)
                    print(f"  offset ${i-1:04X}: {instr_map.get(prefix,'?')} ${addr:04X}")

    # === Z80 trace ring analysis ===
    print("\n=== Z80 トレースリング (最後の40エントリ) ===")
    try:
        apu = api_get("/apu/state")
        z80_trace = apu.get("z80_trace_ring", [])
        if z80_trace:
            print(f"Total trace entries: {len(z80_trace)}")
            # Parse trace entries (may be strings or objects)
            for entry in z80_trace[-40:]:
                if isinstance(entry, str):
                    print(f"  {entry}")
                elif isinstance(entry, dict):
                    pc = entry.get("pc", 0)
                    op = entry.get("opcode_name", "?")
                    cyc = entry.get("cycles", 0)
                    print(f"  PC=${pc:04X} {op:20s} cycles={cyc}")
                else:
                    print(f"  {entry}")
        else:
            print("Z80 trace ring is empty")
    except Exception as e:
        print(f"Z80 trace error: {e}")

    # === Check what address the Z80 INT handler accesses ===
    print("\n=== Z80 INTハンドラ詳細 ($0038-$00FF) ===")
    int_data = z80[0x0038:0x0100]
    print("  Raw bytes:")
    for row in range(0, len(int_data), 16):
        hex_str = " ".join(f"{b:02X}" for b in int_data[row:row+16])
        addr = 0x0038 + row
        print(f"    ${addr:04X}: {hex_str}")

    # === Check GEMS main loop region ===
    print("\n=== GEMS メインループ候補 ($0200-$0400) ===")
    main_data = z80[0x0200:0x0400]
    # Search for LD A, (IX+d) or LD A, (IY+d) patterns
    # DD 7E dd = LD A, (IX+d)
    # FD 7E dd = LD A, (IY+d)
    for i in range(len(main_data) - 2):
        if main_data[i] in (0xDD, 0xFD) and main_data[i+1] == 0x7E:
            prefix = "IX" if main_data[i] == 0xDD else "IY"
            d = main_data[i+2]
            if d >= 0x80: d_signed = d - 256
            else: d_signed = d
            addr = 0x0200 + i
            print(f"  ${addr:04X}: LD A, ({prefix}+{d_signed})")

    # === Check $0100-$01FF area as data ===
    print("\n=== Z80 ステータスエリア $0100-$01FF ===")
    status_data = z80[0x0100:0x0200]
    non_zero = [(i, status_data[i]) for i in range(len(status_data)) if status_data[i] != 0]
    for offset, val in non_zero:
        print(f"  $01{offset:02X} = ${val:02X}")

    # === Search for BIT/SET/RES instructions on address $0161 ===
    print("\n=== BIT操作命令の検索 ===")
    # CB prefix + opcode for BIT/SET/RES on (HL) when HL=$0161
    # Also look for LD (HL), value when HL is loaded with $0161 nearby
    for i in range(len(z80) - 3):
        # Pattern: LD HL, $0161 → 21 61 01
        if z80[i] == 0x21 and z80[i+1] == 0x61 and z80[i+2] == 0x01:
            # Show next ~16 bytes
            ctx = z80[i:min(i+20, len(z80))]
            hex_str = " ".join(f"{b:02X}" for b in ctx)
            print(f"  ${i:04X}: LD HL, $0161 → {hex_str}")

    # === Check the actual poll code: search for BIT n, (HL) after LD HL with $015x ===
    print("\n=== LD HL, $01xx 検索 (xx=50-70) ===")
    for i in range(len(z80) - 2):
        if z80[i] == 0x21 and z80[i+2] == 0x01:
            target = z80[i+1] | (z80[i+2] << 8)
            if 0x0150 <= target <= 0x0170:
                ctx = z80[i:min(i+24, len(z80))]
                hex_str = " ".join(f"{b:02X}" for b in ctx)
                print(f"  ${i:04X}: LD HL, ${target:04X} → {hex_str}")

    print("\nDone.")

if __name__ == "__main__":
    main()
