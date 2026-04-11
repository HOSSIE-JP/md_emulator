#!/usr/bin/env python3
"""Z80 RAM deep analysis - search for $6000 bank register access patterns"""

import json
import urllib.request

BASE = "http://localhost:8080/api/v1"

def api_get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

def disasm_simple(ram, pc, count=20):
    """Very basic Z80 disassembly for common instructions"""
    lines = []
    i = pc
    for _ in range(count):
        if i >= len(ram):
            break
        op = ram[i]
        # Simple 1-byte instructions
        one_byte = {
            0x00: "NOP", 0xC9: "RET", 0xF3: "DI", 0xFB: "EI",
            0xAF: "XOR A", 0x76: "HALT", 0xD9: "EXX",
            0x08: "EX AF,AF'", 0xCF: "RST $08",
            0x2D: "DEC L", 0x23: "INC HL", 0x72: "LD (HL),D",
            0x77: "LD (HL),A", 0x7E: "LD A,(HL)", 0x46: "LD B,(HL)",
            0x4E: "LD C,(HL)", 0x56: "LD D,(HL)", 0x5E: "LD E,(HL)",
            0x57: "LD D,A", 0x79: "LD A,C",
            0xF5: "PUSH AF", 0xC5: "PUSH BC", 0xD5: "PUSH DE", 0xE5: "PUSH HL",
            0xF1: "POP AF", 0xC1: "POP BC", 0xD1: "POP DE", 0xE1: "POP HL",
            0x02: "LD (BC),A", 0x12: "LD (DE),A", 0x0A: "LD A,(BC)", 0x1A: "LD A,(DE)",
            0x0C: "INC C", 0x96: "SUB (HL)",
        }
        if op in one_byte:
            lines.append((i, f"{op:02X}", one_byte[op]))
            i += 1
        elif op == 0x01 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD BC,${nn:04X}"))
            i += 3
        elif op == 0x11 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD DE,${nn:04X}"))
            i += 3
        elif op == 0x21 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD HL,${nn:04X}"))
            i += 3
        elif op == 0x31 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD SP,${nn:04X}"))
            i += 3
        elif op == 0x32 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD (${nn:04X}),A"))
            i += 3
        elif op == 0x3A and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD A,(${nn:04X})"))
            i += 3
        elif op == 0x22 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD (${nn:04X}),HL"))
            i += 3
        elif op == 0x2A and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"LD HL,(${nn:04X})"))
            i += 3
        elif op == 0x3E and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD A,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x06 and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD B,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x0E and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD C,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x16 and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD D,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x1E and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD E,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x26 and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD H,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x2E and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD L,${ram[i+1]:02X}"))
            i += 2
        elif op == 0x36 and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"LD (HL),${ram[i+1]:02X}"))
            i += 2
        elif op == 0xFE and i+1 < len(ram):
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"CP ${ram[i+1]:02X}"))
            i += 2
        elif op == 0xC3 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"JP ${nn:04X}"))
            i += 3
        elif op == 0xCD and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"CALL ${nn:04X}"))
            i += 3
        elif op == 0x18 and i+1 < len(ram):
            off = ram[i+1] if ram[i+1] < 128 else ram[i+1] - 256
            target = i + 2 + off
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"JR ${target:04X}"))
            i += 2
        elif op == 0x20 and i+1 < len(ram):
            off = ram[i+1] if ram[i+1] < 128 else ram[i+1] - 256
            target = i + 2 + off
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"JR NZ,${target:04X}"))
            i += 2
        elif op == 0x28 and i+1 < len(ram):
            off = ram[i+1] if ram[i+1] < 128 else ram[i+1] - 256
            target = i + 2 + off
            lines.append((i, f"{op:02X} {ram[i+1]:02X}", f"JR Z,${target:04X}"))
            i += 2
        elif op == 0xCA and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"JP Z,${nn:04X}"))
            i += 3
        elif op == 0xC2 and i+2 < len(ram):
            nn = ram[i+1] | (ram[i+2] << 8)
            lines.append((i, f"{op:02X} {ram[i+1]:02X} {ram[i+2]:02X}", f"JP NZ,${nn:04X}"))
            i += 3
        elif op == 0xED and i+1 < len(ram):
            op2 = ram[i+1]
            if op2 == 0xB0:
                lines.append((i, f"ED B0", "LDIR"))
                i += 2
            else:
                lines.append((i, f"ED {op2:02X}", f"(ED prefix)"))
                i += 2
        elif op == 0xDD or op == 0xFD:
            prefix = "IX" if op == 0xDD else "IY"
            if i+1 < len(ram):
                op2 = ram[i+1]
                if op2 == 0xE5:
                    lines.append((i, f"{op:02X} E5", f"PUSH {prefix}"))
                    i += 2
                elif op2 == 0xE1:
                    lines.append((i, f"{op:02X} E1", f"POP {prefix}"))
                    i += 2
                elif op2 == 0x7D:
                    lines.append((i, f"{op:02X} 7D", f"LD A,{prefix}L"))
                    i += 2
                elif op2 == 0x7C:
                    lines.append((i, f"{op:02X} 7C", f"LD A,{prefix}H"))
                    i += 2
                else:
                    lines.append((i, f"{op:02X} {op2:02X}", f"({prefix} prefix)"))
                    i += 2
            else:
                lines.append((i, f"{op:02X}", f"({prefix} prefix incomplete)"))
                i += 1
        elif op == 0xCB and i+1 < len(ram):
            lines.append((i, f"CB {ram[i+1]:02X}", "(CB prefix)"))
            i += 2
        else:
            lines.append((i, f"{op:02X}", f"db ${op:02X}"))
            i += 1
    return lines

def main():
    # Read Z80 RAM
    z80_ram = []
    for offset in range(0, 0x2000, 0x400):
        addr = 0xA00000 + offset
        resp = api_get("/cpu/memory", {"addr": str(addr), "len": "1024"})
        z80_ram.extend(resp["data"])
    
    print(f"Z80 RAM: {len(z80_ram)} bytes\n")
    
    # Search for ALL references to bytes 00 60 (little-endian $6000)
    print("=== All references to $6000 in Z80 RAM ===")
    refs = []
    for i in range(len(z80_ram) - 1):
        if z80_ram[i] == 0x00 and z80_ram[i+1] == 0x60:
            ctx_start = max(0, i-4)
            ctx_end = min(len(z80_ram), i+6)
            ctx = " ".join(f"{z80_ram[j]:02X}" for j in range(ctx_start, ctx_end))
            refs.append((i, ctx))
            print(f"  Z80:${i:04X}: ...{ctx}...")
    
    if not refs:
        print("  None found!")
    
    # For each reference, check the instruction context
    print("\n=== Disassembly around $6000 references ===")
    for ref_addr, _ in refs:
        # Check if this is part of LD BC,$6000
        if ref_addr >= 1 and z80_ram[ref_addr-1] == 0x01:
            print(f"\n  At ${ref_addr-1:04X}: LD BC,$6000")
            # This is GEMS-style bank switching! 
            # GEMS uses: LD BC,$6000; LD A,val; LD (BC),A (repeated 9 times)
            # The opcode for LD (BC),A is 0x02
            print("  Disassembly from here:")
            for addr, hexbytes, mnemonic in disasm_simple(z80_ram, ref_addr-1, 30):
                print(f"    ${addr:04X}: {hexbytes:12s} {mnemonic}")
    
    # Search for LD (BC),A = 0x02 near bank references
    # In GEMS, the bank set routine does:
    #   LD BC,$6000
    #   LD A,<bit>; LD (BC),A  (x9 for 9 bits)
    print("\n=== Search for bank set subroutine (LD BC,$6000 + LD (BC),A pattern) ===")
    for i in range(len(z80_ram) - 10):
        if z80_ram[i] == 0x01 and z80_ram[i+1] == 0x00 and z80_ram[i+2] == 0x60:
            # Found LD BC,$6000, now look for LD (BC),A = 0x02 nearby
            count_02 = 0
            for j in range(i+3, min(i+50, len(z80_ram))):
                if z80_ram[j] == 0x02:
                    count_02 += 1
            print(f"  LD BC,$6000 at ${i:04X}, LD (BC),A count in next 50 bytes: {count_02}")
            if count_02 >= 5:
                print(f"  *** LIKELY BANK SET ROUTINE! ***")
                print(f"  Full disassembly:")
                for addr, hexbytes, mnemonic in disasm_simple(z80_ram, i, 40):
                    print(f"    ${addr:04X}: {hexbytes:12s} {mnemonic}")
    
    # Search for accesses to $8000-$FFFF range (banked M68K access)
    print("\n=== Z80 code accessing banked window ($8000-$FFFF) ===")
    banked_accesses = []
    for i in range(len(z80_ram) - 2):
        op = z80_ram[i]
        if op in (0x32, 0x3A, 0x22, 0x2A) and i+2 < len(z80_ram):
            nn = z80_ram[i+1] | (z80_ram[i+2] << 8)
            if nn >= 0x8000:
                op_names = {0x32: "LD (nn),A [WRITE]", 0x3A: "LD A,(nn) [READ]",
                            0x22: "LD (nn),HL [WRITE]", 0x2A: "LD HL,(nn) [READ]"}
                banked_accesses.append((i, nn, op_names[op]))
    
    if banked_accesses:
        print(f"  Found {len(banked_accesses)} accesses to banked window:")
        for addr, target, desc in banked_accesses:
            z80_off = target & 0x7FFF
            print(f"    Z80:${addr:04X}: {desc} target=${target:04X} (offset=${z80_off:04X})")
    else:
        print("  No direct LD (nn)/LD A,(nn) to $8000+ found")
    
    # Also look for LD A,(HL) / LD (HL),A when HL could be $8000+
    # Check LD HL,$8xxx patterns
    print("\n=== LD HL,$8000+ patterns (potential banked access setup) ===")
    for i in range(len(z80_ram) - 2):
        if z80_ram[i] == 0x21:  # LD HL,nn
            nn = z80_ram[i+1] | (z80_ram[i+2] << 8)
            if nn >= 0x8000:
                print(f"    Z80:${i:04X}: LD HL,${nn:04X}")
                # Show what follows
                for addr, hexbytes, mnemonic in disasm_simple(z80_ram, i, 8):
                    print(f"      ${addr:04X}: {hexbytes:12s} {mnemonic}")
    
    # Check the code around PC (where Z80 is currently executing)
    apu = api_get("/apu/state")
    pc = apu.get("z80_pc", 0)
    print(f"\n=== Z80 code around current PC ${pc:04X} ===")
    for addr, hexbytes, mnemonic in disasm_simple(z80_ram, max(0, pc-16), 32):
        marker = " <<<< PC" if addr == pc else ""
        print(f"  ${addr:04X}: {hexbytes:12s} {mnemonic}{marker}")

if __name__ == "__main__":
    main()
