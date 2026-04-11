#!/usr/bin/env python3
"""Z80 $0B84 呼び出し元検索 + Z80トレースリングでの$0B84到達確認"""
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

def read_z80_chunk(start, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={0xA00000 + start + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def main():
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 50})

    z80 = read_z80_chunk(0, 0x2000)
    print(f"Z80 RAM: {len(z80)} bytes")

    # === Search for CALL $0B84 / JP $0B84 ===
    print("\n=== CALL/JP $0B84 検索 ===")
    # CD 84 0B = CALL $0B84
    # C3 84 0B = JP $0B84
    for i in range(len(z80) - 2):
        if z80[i+1] == 0x84 and z80[i+2] == 0x0B:
            if z80[i] == 0xCD:
                print(f"  ${i:04X}: CALL $0B84")
            elif z80[i] == 0xC3:
                print(f"  ${i:04X}: JP $0B84")
            elif z80[i] in (0xC2, 0xCA, 0xD2, 0xDA):
                cc_map = {0xC2: "NZ", 0xCA: "Z", 0xD2: "NC", 0xDA: "C"}
                print(f"  ${i:04X}: JP {cc_map[z80[i]]}, $0B84")
            elif z80[i] in (0xC4, 0xCC, 0xD4, 0xDC):
                cc_map = {0xC4: "NZ", 0xCC: "Z", 0xD4: "NC", 0xDC: "C"}
                print(f"  ${i:04X}: CALL {cc_map[z80[i]]}, $0B84")

    # === Search for CALL $0B87 / JP $0B87 (the BIT 0 test entry) ===
    print("\n=== CALL/JP $0B87 検索 ===")
    for i in range(len(z80) - 2):
        if z80[i+1] == 0x87 and z80[i+2] == 0x0B:
            if z80[i] == 0xCD:
                print(f"  ${i:04X}: CALL $0B87")
            elif z80[i] == 0xC3:
                print(f"  ${i:04X}: JP $0B87")
            elif z80[i] in (0xC2, 0xCA, 0xD2, 0xDA):
                cc_map = {0xC2: "NZ", 0xCA: "Z", 0xD2: "NC", 0xDA: "C"}
                print(f"  ${i:04X}: JP {cc_map[z80[i]]}, $0B87")

    # === Disassemble around the callers ===
    # Also disassemble the full function at $0B84
    print("\n=== $0B70-$0BA0 全体の逆アセンブル ===")
    data = z80[0x0B70:0x0BA0]
    for i in range(len(data)):
        b = data[i]
        addr = 0x0B70 + i
        print(f"  ${addr:04X}: {b:02X}", end="")
        if i + 2 < len(data) and b in (0xCD, 0xC3):
            target = data[i+1] | (data[i+2] << 8)
            print(f"  → {'CALL' if b == 0xCD else 'JP'} ${target:04X}", end="")
        elif i + 1 < len(data) and b == 0xCB:
            operand = data[i+1]
            op_type = (operand >> 6) & 3
            bit = (operand >> 3) & 7
            reg = operand & 7
            reg_names = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
            if op_type == 1:
                print(f"  → BIT {bit}, {reg_names[reg]}", end="")
            elif op_type == 2:
                print(f"  → RES {bit}, {reg_names[reg]}", end="")
            elif op_type == 3:
                print(f"  → SET {bit}, {reg_names[reg]}", end="")
        elif b == 0x21 and i + 2 < len(data):
            nn = data[i+1] | (data[i+2] << 8)
            print(f"  → LD HL, ${nn:04X}", end="")
        elif b == 0xCA and i + 2 < len(data):
            nn = data[i+1] | (data[i+2] << 8)
            print(f"  → JP Z, ${nn:04X}", end="")
        elif b == 0xC9:
            print(f"  → RET", end="")
        elif b == 0xCF:
            print(f"  → RST $08", end="")
        elif b == 0x04:
            print(f"  → INC B", end="")
        elif b == 0x70:
            print(f"  → LD (HL), B", end="")
        print()

    # === Z80 trace ring full scan for $0B84-$0B8E ===
    print("\n=== Z80トレースリング: $0B84-$0B91 を検索 ===")
    apu = api_get("/apu/state")
    z80_trace = apu.get("z80_trace_ring", [])
    print(f"Total trace entries: {len(z80_trace)}")

    count_0b84 = 0
    count_0b87 = 0
    count_total = 0
    for entry in z80_trace:
        if isinstance(entry, str):
            # Parse string: "$0B84: CB BIT 0, (HL)"
            try:
                pc_str = entry.split(":")[0].strip().lstrip("$")
                pc = int(pc_str, 16)
            except:
                continue
        elif isinstance(entry, dict):
            pc = entry.get("pc", 0)
        else:
            continue
        count_total += 1
        if pc == 0x0B84:
            count_0b84 += 1
        if pc == 0x0B87:
            count_0b87 += 1

    print(f"  Total entries parsed: {count_total}")
    print(f"  PC=$0B84 count: {count_0b84}")
    print(f"  PC=$0B87 count: {count_0b87}")

    # Show unique PCs and their frequency (top 20)
    from collections import Counter
    pc_counts = Counter()
    for entry in z80_trace:
        if isinstance(entry, str):
            try:
                pc_str = entry.split(":")[0].strip().lstrip("$")
                pc = int(pc_str, 16)
                pc_counts[pc] += 1
            except:
                continue
        elif isinstance(entry, dict):
            pc_counts[entry.get("pc", 0)] += 1

    print(f"\n  ユニーク PC 数: {len(pc_counts)}")
    print(f"  上位20 PC:")
    for pc, cnt in pc_counts.most_common(20):
        print(f"    ${pc:04X}: {cnt:6d} ({100*cnt/count_total:.1f}%)")

    # Check if $0B84, $0B87, $0B89, $0B8C etc. appear at all
    poll_addrs = [0x0B84, 0x0B87, 0x0B89, 0x0B8C, 0x0B8D, 0x0B8E, 0x0B91]
    print(f"\n  $0B84付近のPC:")
    for addr in poll_addrs:
        cnt = pc_counts.get(addr, 0)
        print(f"    ${addr:04X}: {cnt}")

    # === Check where $086E CALL goes ===
    print("\n=== $086E: CALL target ===")
    if len(z80) > 0x0870:
        target = z80[0x086F] | (z80[0x0870] << 8)
        print(f"  $086E: CD {z80[0x086F]:02X} {z80[0x0870]:02X} → CALL ${target:04X}")

    # Show $0884 JP target
    if len(z80) > 0x0886:
        target = z80[0x0885] | (z80[0x0886] << 8)
        print(f"  $0884: C3 {z80[0x0885]:02X} {z80[0x0886]:02X} → JP ${target:04X}")

    # === Disassemble GEMS main loop $0860-$08C0 ===
    print("\n=== GEMS メインループ $0860-$08C0 ===")
    for i in range(0x0860, min(0x08C0, len(z80))):
        b = z80[i]
        print(f"  ${i:04X}: {b:02X}", end="")
        if i + 2 < len(z80):
            if b == 0xCD:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → CALL ${t:04X}", end="")
            elif b == 0xC3:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → JP ${t:04X}", end="")
            elif b == 0x21:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → LD HL, ${t:04X}", end="")
            elif b == 0x3A:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → LD A, (${t:04X})", end="")
            elif b == 0xCA:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → JP Z, ${t:04X}", end="")
            elif b == 0xDA:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → JP C, ${t:04X}", end="")
            elif b == 0xC2:
                t = z80[i+1] | (z80[i+2] << 8)
                print(f"  → JP NZ, ${t:04X}", end="")
        if b == 0xCF: print(f"  → RST $08", end="")
        elif b == 0xC9: print(f"  → RET", end="")
        elif b == 0xFB: print(f"  → EI", end="")
        elif b == 0xF3: print(f"  → DI", end="")
        print()

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
