#!/usr/bin/env python3
"""Z80タイミング診断: Z80 RAMダンプ + M68K→Z80[$0161]書き込み間のZ80実行サイクル計測"""
import requests, struct, json, time

API = "http://localhost:8080/api/v1"

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=5)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    return api_get(f"/cpu/memory?addr={addr}&len={length}")

def write_mem(addr, values):
    return api_post("/cpu/memory", {"addr": addr, "data": values})

def step(n=1):
    return api_post("/emulator/step", {"frames": n})

def load_rom():
    return api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})

def dump_z80_ram(start, length):
    """Dump Z80 RAM via M68K-side address $A00000+ (chunked to avoid API limits)"""
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = read_mem(0xA00000 + start + off, sz)
        result.extend(data.get("data", []))
    return result

def disasm_z80(data, base_addr):
    """Simple Z80 disassembler for common instructions"""
    lines = []
    i = 0
    while i < len(data):
        addr = base_addr + i
        op = data[i]
        if op == 0x3A and i + 2 < len(data):  # LD A, (nn)
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: LD A, (${nn:04X})")
            i += 3
        elif op == 0x32 and i + 2 < len(data):  # LD (nn), A
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: LD (${nn:04X}), A")
            i += 3
        elif op == 0xB7:
            lines.append(f"${addr:04X}: OR A")
            i += 1
        elif op == 0xAF:
            lines.append(f"${addr:04X}: XOR A")
            i += 1
        elif op == 0xFE and i + 1 < len(data):  # CP n
            n = data[i+1]
            lines.append(f"${addr:04X}: CP ${n:02X}")
            i += 2
        elif op == 0x20 and i + 1 < len(data):  # JR NZ
            offset = data[i+1]
            if offset >= 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"${addr:04X}: JR NZ, ${target:04X}")
            i += 2
        elif op == 0x28 and i + 1 < len(data):  # JR Z
            offset = data[i+1]
            if offset >= 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"${addr:04X}: JR Z, ${target:04X}")
            i += 2
        elif op == 0x30 and i + 1 < len(data):  # JR NC
            offset = data[i+1]
            if offset >= 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"${addr:04X}: JR NC, ${target:04X}")
            i += 2
        elif op == 0x38 and i + 1 < len(data):  # JR C
            offset = data[i+1]
            if offset >= 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"${addr:04X}: JR C, ${target:04X}")
            i += 2
        elif op == 0x18 and i + 1 < len(data):  # JR
            offset = data[i+1]
            if offset >= 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"${addr:04X}: JR ${target:04X}")
            i += 2
        elif op == 0xC3 and i + 2 < len(data):  # JP nn
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: JP ${nn:04X}")
            i += 3
        elif op == 0xCA and i + 2 < len(data):  # JP Z
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: JP Z, ${nn:04X}")
            i += 3
        elif op == 0xC2 and i + 2 < len(data):  # JP NZ
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: JP NZ, ${nn:04X}")
            i += 3
        elif op == 0xCD and i + 2 < len(data):  # CALL nn
            nn = data[i+1] | (data[i+2] << 8)
            lines.append(f"${addr:04X}: CALL ${nn:04X}")
            i += 3
        elif op == 0xC9:
            lines.append(f"${addr:04X}: RET")
            i += 1
        elif op == 0xD3 and i + 1 < len(data):  # OUT (n), A
            n = data[i+1]
            lines.append(f"${addr:04X}: OUT (${n:02X}), A")
            i += 2
        elif op == 0xDB and i + 1 < len(data):  # IN A, (n)
            n = data[i+1]
            lines.append(f"${addr:04X}: IN A, (${n:02X})")
            i += 2
        elif op == 0x1F:
            lines.append(f"${addr:04X}: RRA")
            i += 1
        elif op == 0x07:
            lines.append(f"${addr:04X}: RLCA")
            i += 1
        elif op == 0x0F:
            lines.append(f"${addr:04X}: RRCA")
            i += 1
        elif op == 0x00:
            lines.append(f"${addr:04X}: NOP")
            i += 1
        elif op == 0x76:
            lines.append(f"${addr:04X}: HALT")
            i += 1
        elif op == 0xFB:
            lines.append(f"${addr:04X}: EI")
            i += 1
        elif op == 0xF3:
            lines.append(f"${addr:04X}: DI")
            i += 1
        elif op == 0xED and i + 1 < len(data):
            op2 = data[i+1]
            if op2 == 0x56:
                lines.append(f"${addr:04X}: IM 1")
            elif op2 == 0x4D:
                lines.append(f"${addr:04X}: RETI")
            else:
                lines.append(f"${addr:04X}: ED {op2:02X}")
            i += 2
        else:
            lines.append(f"${addr:04X}: DB ${op:02X}")
            i += 1
    return lines

# ========= Z80 $0161 reference search =========
def find_0161_refs(data, base_addr):
    """Search Z80 code for references to address $0161"""
    refs = []
    for i in range(len(data) - 2):
        # LD A, (nn) = 3A nn_lo nn_hi
        if data[i] == 0x3A and data[i+1] == 0x61 and data[i+2] == 0x01:
            refs.append((base_addr + i, "LD A, ($0161)"))
        # LD (nn), A = 32 nn_lo nn_hi
        if data[i] == 0x32 and data[i+1] == 0x61 and data[i+2] == 0x01:
            refs.append((base_addr + i, "LD ($0161), A"))
    return refs

def main():
    print("=" * 60)
    print("Z80 タイミング診断")
    print("=" * 60)

    # Load ROM and run to frame 50
    load_rom()
    step(50)

    # === Part 1: Dump Z80 RAM and find $0161 references ===
    print("\n--- Part 1: Z80 RAM 内の $0161 参照検索 ---")
    # Dump entire Z80 RAM (8KB)
    full_ram = dump_z80_ram(0, 0x2000)
    print(f"Z80 RAM dump: {len(full_ram)} bytes")

    refs = find_0161_refs(full_ram, 0)
    print(f"\n$0161 を参照する命令: {len(refs)} 件")
    for addr, instr in refs:
        print(f"  ${addr:04X}: {instr}")
        # Disassemble context around each reference
        ctx_start = max(0, addr - 10)
        ctx_end = min(len(full_ram), addr + 20)
        ctx_data = full_ram[ctx_start:ctx_end]
        lines = disasm_z80(ctx_data, ctx_start)
        for line in lines:
            mark = " <<<" if "$0161" in line else ""
            print(f"    {line}{mark}")
        print()

    # === Part 2: Z80 trace ring analysis ===
    print("\n--- Part 2: Z80 トレースリング ---")
    try:
        apu = api_get("/apu/state")
        z80_trace = apu.get("z80_trace_ring", [])
        if z80_trace:
            print(f"Z80 trace entries: {len(z80_trace)}")
            # Show last 20 entries
            for entry in z80_trace[-20:]:
                pc = entry.get("pc", 0)
                op = entry.get("opcode_name", entry.get("opcode", "?"))
                cyc = entry.get("cycles", 0)
                print(f"  PC=${pc:04X} {op:20s} cycles={cyc}")
        else:
            print("Z80 trace ring is empty")
    except Exception as e:
        print(f"Z80 trace error: {e}")

    # === Part 3: Disassemble key Z80 code regions ===
    print("\n--- Part 3: Z80 主要コード逆アセンブル ---")

    # DAC output region ($0BF0-$0C20)
    regions = [
        (0x0000, 0x0060, "Z80 vector table & init"),
        (0x0038, 0x0020, "INT handler ($0038)"),
        (0x0066, 0x0020, "NMI handler ($0066)"),
        (0x0100, 0x0030, "GEMS status area ($0100)"),
        (0x0150, 0x0030, "Command area ($0150-$017F)"),
        (0x0BF0, 0x0030, "DAC output loop area"),
    ]

    for start, length, label in regions:
        end = min(start + length, len(full_ram))
        data = full_ram[start:end]
        print(f"\n  [{label}] ${start:04X}-${end-1:04X}:")
        if all(b == 0 for b in data):
            print(f"    (all zeros)")
            continue
        lines = disasm_z80(data, start)
        for line in lines:
            print(f"    {line}")

    # === Part 4: Monitor Z80[$0161] across frames ===
    print("\n--- Part 4: Z80[$0161] フレーム監視 ---")

    # Reset and run to frame 38 (just before $FF019C is set)
    load_rom()
    step(38)

    for frame in range(38, 65):
        step(1)
        val_0161 = dump_z80_ram(0x0161, 1)
        ff019c = read_mem(0xFF019C, 2).get("data", [0, 0])
        ff019c_val = (ff019c[0] << 8) | ff019c[1]

        # Also check Z80 ready flag
        val_0102 = dump_z80_ram(0x0102, 1)

        # Get Z80 trace ring to see current PC
        try:
            apu = api_get("/apu/state")
            z80_trace = apu.get("z80_trace_ring", [])
            last_pc = z80_trace[-1].get("pc", 0) if z80_trace else 0
        except:
            last_pc = 0

        flag = ""
        if val_0161 and val_0161[0] != 0:
            flag = " *** NON-ZERO ***"
        print(f"  Frame {frame:3d}: Z80[$0161]=${val_0161[0] if val_0161 else '??':02X}, "
              f"$FF019C=${ff019c_val:04X}, "
              f"Z80[$0102]=${val_0102[0] if val_0102 else '??':02X}, "
              f"Z80_PC=${last_pc:04X}{flag}")

    # === Part 5: Bus holding timing measurement ===
    print("\n--- Part 5: バス保持タイミング ---")
    print("  (M68K→Z80[$0161]書き込みパターンは stderr ログで確認)")
    print("  Z80 のポーリングループ長を推定:")

    # Find the polling loop by looking for the pattern:
    # LD A, ($0161) ; OR A ; JR Z, back
    for ref_addr, ref_instr in refs:
        print(f"\n  $0161ポーリングコード at ${ref_addr:04X}:")
        # Check surrounding code for loop structure
        loop_start = max(0, ref_addr - 32)
        loop_end = min(len(full_ram), ref_addr + 32)
        loop_data = full_ram[loop_start:loop_end]
        lines = disasm_z80(loop_data, loop_start)
        for line in lines:
            mark = " <<<" if "$0161" in line else ""
            print(f"    {line}{mark}")

    print("\n" + "=" * 60)
    print("診断完了")

if __name__ == "__main__":
    main()
