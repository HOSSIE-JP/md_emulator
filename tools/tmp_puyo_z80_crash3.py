#!/usr/bin/env python3
"""Puyo Z80 crash Phase 3: Decode the stuck ISR and find M68K write pattern.

Key findings so far:
- Frame 179: M68K overwrites entire Z80 RAM with data patterns
- Frames 52-178: Z80 stuck at $12A3/$12A4 inside ISR, IFF1=False, SP slowly growing
- ISR at $0038 still intact until frame 179
- z80_bus_requested=False at corruption time

Questions:
1. What code is at $12A3? Why is the Z80 stuck there?
2. What M68K trace shows at frame 179? (writes to Z80 RAM?)
3. Did the M68K do BUSREQ/RESET before writing?
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"
TIMEOUT = 120

def api_get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=TIMEOUT).read())

def api_post(path, data=None):
    req = urllib.request.Request(BASE + path, method="POST")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data or {}).encode()
    return json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read())

CYCLES_PER_FRAME = 896040

def dump_z80_ram_region(start, length, label=""):
    """Read Z80 RAM via M68K memory map ($A00000+offset)."""
    addr = 0xA00000 + start
    mem = api_get("/cpu/memory?addr={}&len={}".format(addr, length))["data"]
    if label:
        print("  === {} (${:04X}-${:04X}) ===".format(label, start, start + length - 1))
    for off in range(0, length, 16):
        chunk = mem[off:off+16]
        hex_str = ' '.join('{:02X}'.format(b) for b in chunk)
        print("    ${:04X}: {}".format(start + off, hex_str))
    return mem

def disasm_z80(data, base_addr):
    """Simple Z80 disassembler for common instructions."""
    pc = 0
    lines = []
    while pc < len(data):
        op = data[pc]
        addr = base_addr + pc
        if op == 0x00:
            lines.append("${:04X}: {:02X}       NOP".format(addr, op))
            pc += 1
        elif op == 0x01:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} LD BC,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xC3:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} JP ${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xCD:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} CALL ${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xC9:
            lines.append("${:04X}: {:02X}       RET".format(addr, op))
            pc += 1
        elif op == 0xF3:
            lines.append("${:04X}: {:02X}       DI".format(addr, op))
            pc += 1
        elif op == 0xFB:
            lines.append("${:04X}: {:02X}       EI".format(addr, op))
            pc += 1
        elif op == 0x3A:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} LD A,(${:04X})".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0x32:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} LD (${:04X}),A".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xA7:
            lines.append("${:04X}: {:02X}       AND A".format(addr, op))
            pc += 1
        elif op == 0x28:
            if pc + 1 < len(data):
                off = data[pc+1]
                if off >= 128:
                    off -= 256
                target = addr + 2 + off
                lines.append("${:04X}: {:02X} {:02X}    JR Z,${:04X}".format(addr, op, data[pc+1], target & 0xFFFF))
                pc += 2
            else:
                break
        elif op == 0x20:
            if pc + 1 < len(data):
                off = data[pc+1]
                if off >= 128:
                    off -= 256
                target = addr + 2 + off
                lines.append("${:04X}: {:02X} {:02X}    JR NZ,${:04X}".format(addr, op, data[pc+1], target & 0xFFFF))
                pc += 2
            else:
                break
        elif op == 0x18:
            if pc + 1 < len(data):
                off = data[pc+1]
                if off >= 128:
                    off -= 256
                target = addr + 2 + off
                lines.append("${:04X}: {:02X} {:02X}    JR ${:04X}".format(addr, op, data[pc+1], target & 0xFFFF))
                pc += 2
            else:
                break
        elif op == 0xF6:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    OR ${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0xFE:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    CP ${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0xCB:
            if pc + 1 < len(data):
                cb_op = data[pc+1]
                bit_ops = {0x7E: "BIT 7,(HL)", 0x46: "BIT 0,(HL)", 0x4E: "BIT 1,(HL)",
                           0x76: "BIT 6,(HL)", 0x66: "BIT 4,(HL)", 0x6E: "BIT 5,(HL)",
                           0x56: "BIT 2,(HL)", 0x5E: "BIT 3,(HL)"}
                name = bit_ops.get(cb_op, "CB {:02X}".format(cb_op))
                lines.append("${:04X}: CB {:02X}    {}".format(addr, cb_op, name))
                pc += 2
            else:
                break
        elif op == 0xF5:
            lines.append("${:04X}: {:02X}       PUSH AF".format(addr, op))
            pc += 1
        elif op == 0xC5:
            lines.append("${:04X}: {:02X}       PUSH BC".format(addr, op))
            pc += 1
        elif op == 0xD5:
            lines.append("${:04X}: {:02X}       PUSH DE".format(addr, op))
            pc += 1
        elif op == 0xE5:
            lines.append("${:04X}: {:02X}       PUSH HL".format(addr, op))
            pc += 1
        elif op == 0xF1:
            lines.append("${:04X}: {:02X}       POP AF".format(addr, op))
            pc += 1
        elif op == 0xC1:
            lines.append("${:04X}: {:02X}       POP BC".format(addr, op))
            pc += 1
        elif op == 0xD1:
            lines.append("${:04X}: {:02X}       POP DE".format(addr, op))
            pc += 1
        elif op == 0xE1:
            lines.append("${:04X}: {:02X}       POP HL".format(addr, op))
            pc += 1
        elif op == 0xD9:
            lines.append("${:04X}: {:02X}       EXX".format(addr, op))
            pc += 1
        elif op == 0x21:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} LD HL,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0x2A:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} LD HL,(${:04X})".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xDB:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    IN A,(${:02X})".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0xED:
            if pc + 1 < len(data):
                ed_op = data[pc+1]
                if ed_op == 0x4D:
                    lines.append("${:04X}: ED 4D    RETI".format(addr))
                elif ed_op == 0x45:
                    lines.append("${:04X}: ED 45    RETN".format(addr))
                elif ed_op == 0xB0:
                    lines.append("${:04X}: ED B0    LDIR".format(addr))
                else:
                    lines.append("${:04X}: ED {:02X}    ED-prefix".format(addr, ed_op))
                pc += 2
            else:
                break
        elif op == 0x87:
            lines.append("${:04X}: {:02X}       ADD A,A".format(addr, op))
            pc += 1
        elif op == 0x5F:
            lines.append("${:04X}: {:02X}       LD E,A".format(addr, op))
            pc += 1
        elif op == 0x16:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    LD D,${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0x0E:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    LD C,${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0x06:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    LD B,${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0x36:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    LD (HL),${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0x77:
            lines.append("${:04X}: {:02X}       LD (HL),A".format(addr, op))
            pc += 1
        elif op == 0x7E:
            lines.append("${:04X}: {:02X}       LD A,(HL)".format(addr, op))
            pc += 1
        elif op == 0xBE:
            lines.append("${:04X}: {:02X}       CP (HL)".format(addr, op))
            pc += 1
        elif op == 0xB7:
            lines.append("${:04X}: {:02X}       OR A".format(addr, op))
            pc += 1
        elif op == 0xAF:
            lines.append("${:04X}: {:02X}       XOR A".format(addr, op))
            pc += 1
        elif op in (0xDD, 0xFD):
            prefix = "IX" if op == 0xDD else "IY"
            if pc + 1 < len(data):
                sub = data[pc+1]
                if sub == 0xE5:
                    lines.append("${:04X}: {:02X} E5    PUSH {}".format(addr, op, prefix))
                    pc += 2
                elif sub == 0xE1:
                    lines.append("${:04X}: {:02X} E1    POP {}".format(addr, op, prefix))
                    pc += 2
                else:
                    lines.append("${:04X}: {:02X} {:02X}    {}-prefix".format(addr, op, sub, prefix))
                    pc += 2
            else:
                break
        elif op == 0xDA:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} JP C,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0x0F:
            lines.append("${:04X}: {:02X}       RRCA".format(addr, op))
            pc += 1
        elif op == 0x3E:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    LD A,${:02X}".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0xD3:
            if pc + 1 < len(data):
                lines.append("${:04X}: {:02X} {:02X}    OUT (${:02X}),A".format(addr, op, data[pc+1], data[pc+1]))
                pc += 2
            else:
                break
        elif op == 0xC2:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} JP NZ,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xCA:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} JP Z,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xC4:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} CALL NZ,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0xCC:
            if pc + 2 < len(data):
                lo, hi = data[pc+1], data[pc+2]
                lines.append("${:04X}: {:02X} {:02X} {:02X} CALL Z,${:04X}".format(addr, op, lo, hi, (hi<<8)|lo))
                pc += 3
            else:
                break
        elif op == 0x23:
            lines.append("${:04X}: {:02X}       INC HL".format(addr, op))
            pc += 1
        elif op == 0x19:
            lines.append("${:04X}: {:02X}       ADD HL,DE".format(addr, op))
            pc += 1
        elif op == 0x09:
            lines.append("${:04X}: {:02X}       ADD HL,BC".format(addr, op))
            pc += 1
        elif op == 0x39:
            lines.append("${:04X}: {:02X}       ADD HL,SP".format(addr, op))
            pc += 1
        elif op == 0xE9:
            lines.append("${:04X}: {:02X}       JP (HL)".format(addr, op))
            pc += 1
        elif op == 0xFF:
            lines.append("${:04X}: {:02X}       RST $38".format(addr, op))
            pc += 1
        else:
            lines.append("${:04X}: {:02X}       ???".format(addr, op))
            pc += 1
        if len(lines) >= 80:
            break
    return lines

# ── Load ROM ─────────────────────────────────────────────────────────
print("=== Loading puyo.bin ===")
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# ── Step 5 frames for Z80 driver ─────────────────────────────────────
for i in range(5):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

# ── Dump & disassemble Z80 code areas at frame 5 ────────────────────
print("\n=== Z80 RAM code at frame 5 (clean) ===")
ram = api_get("/cpu/memory?addr=10485760&len=8192")["data"]

print("\n--- ISR handler at $0038 ---")
isr_code = ram[0x38:0x80]
for line in disasm_z80(isr_code, 0x0038):
    print("    " + line)

print("\n--- Code at $12A0-$12C0 (stuck area) ---")
stuck_code = ram[0x12A0:0x12C0]
for line in disasm_z80(stuck_code, 0x12A0):
    print("    " + line)

print("\n--- Idle loop at $1160-$11A0 ---")
idle_code = ram[0x1160:0x11A0]
for line in disasm_z80(idle_code, 0x1160):
    print("    " + line)

print("\n--- Reset vector at $0000 ---")
reset_code = ram[0x0000:0x0010]
for line in disasm_z80(reset_code, 0x0000):
    print("    " + line)

# ── Step to frame 160-178 to watch stack growth ──────────────────────
print("\n=== Stepping 5→175 (frame-by-frame 170-178) ===")
for i in range(5, 170):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

for frame in range(170, 180):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})
    s = api_get("/cpu/state")
    z = s.get("cpu", {}).get("z80", {})
    apu = api_get("/apu/state")
    print("  Frame {}: Z80 PC=${:04X}  SP=${:04X}  IFF1={}  bus_req={}  reset={}".format(
        frame + 1, z.get("pc", 0), z.get("sp", 0), z.get("iff1"),
        apu.get("z80_bus_requested"), apu.get("z80_reset")))

    if frame == 177:  # Frame just before corruption
        # Get the Z80 trace ring
        trace_ring = apu.get("z80_trace_ring", [])
        print("\n  === Z80 trace ring at frame 178 ({} entries) ===".format(len(trace_ring)))
        print("  Last 100 entries:")
        for i, entry in enumerate(trace_ring[:100]):
            print("    [{:5d}] {}".format(i, entry))

        # Also get M68K trace
        m68k = s.get("cpu", {}).get("m68k", {})
        print("\n  M68K state at frame 178: PC=${:08X}".format(m68k.get("pc", 0)))

    if frame == 178:  # The corruption frame
        trace_ring = apu.get("z80_trace_ring", [])
        print("\n  === Z80 trace ring at frame 179 ({} entries) ===".format(len(trace_ring)))
        # Find the transition from valid code to data execution
        # Look for last entry in valid code range ($0000-$1400ish but not $DA0E)
        valid_idx = None
        for i, entry in enumerate(trace_ring):
            if entry.startswith("$"):
                try:
                    addr = int(entry[1:5], 16)
                except ValueError:
                    continue
                # Valid code is < $2000 and not the RST $38 crash loop
                if addr < 0x2000 and "Rst(56)" not in entry:
                    valid_idx = i
                    break

        if valid_idx is not None:
            start = max(0, valid_idx - 10)
            end = min(len(trace_ring), valid_idx + 40)
            print("  Transition at index {}, showing [{}-{}]:".format(valid_idx, start, end))
            for i in range(start, end):
                mark = " <-- LAST VALID" if i == valid_idx else ""
                print("    [{:5d}] {}{}".format(i, trace_ring[i], mark))
        else:
            print("  No valid code found in trace! First 100 entries:")
            for i, entry in enumerate(trace_ring[:100]):
                print("    [{:5d}] {}".format(i, entry))

        # Dump Z80 RAM changes
        mem_post = api_get("/cpu/memory?addr=10485760&len=8192")["data"]
        changes = sum(1 for a, b in zip(ram, mem_post) if a != b)
        print("\n  RAM changes from frame 5: {} bytes".format(changes))

        # Find what the corrupted data looks like in 68K ROM space
        # bank_addr=$0F8000, data pattern might be from ROM
        bank_addr = 0x0F8000
        print("\n  === 68K ROM at bank address ${:06X} (what Z80 $8000+ maps to) ===".format(bank_addr))
        rom_data = api_get("/cpu/memory?addr={}&len=64".format(bank_addr))["data"]
        print("    " + ' '.join('{:02X}'.format(b) for b in rom_data[:32]))
        print("    " + ' '.join('{:02X}'.format(b) for b in rom_data[32:64]))

        # Also check if the corruption pattern appears in ROM
        # Pattern: 0F DA 3F 00 repeating
        print("\n  Searching for pattern 0F DA 3F 00 in ROM...")
        rom_check = api_get("/cpu/memory?addr=0&len=1024")["data"]
        for off in range(len(rom_check) - 4):
            if rom_check[off:off+4] == [0x0F, 0xDA, 0x3F, 0x00]:
                print("    Found at ROM ${:06X}".format(off))
                break

print("\n=== Done ===")
