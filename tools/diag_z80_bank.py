#!/usr/bin/env python3
"""Z80 bank switching analysis - check if Z80 can access M68K work RAM $FF0066"""

import json
import urllib.request

BASE = "http://localhost:8080/api/v1"

def api_get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

def main():
    # 1. APU state - bank register info
    apu = api_get("/apu/state")
    print("=== Z80 Bank Register Info ===")
    bank_addr = apu.get('z80_bank_68k_addr', 0)
    if isinstance(bank_addr, str):
        bank_addr = int(bank_addr, 16) if bank_addr.startswith('0x') else int(bank_addr)
    bank_max = apu.get('z80_bank_max_value', 0)
    if isinstance(bank_max, str):
        bank_max = int(bank_max, 16) if bank_max.startswith('0x') else int(bank_max)
    print(f"  Current bank 68K addr: 0x{bank_addr:08X}")
    print(f"  Max bank value seen:   0x{bank_max:08X}")
    print(f"  Bank write count:      {apu.get('z80_bank_write_count', 0)}")
    
    # Check bank write log
    log = apu.get("z80_bank_write_log", [])
    print(f"  Bank write log entries: {len(log) if isinstance(log, list) else 'N/A'}")
    
    if isinstance(log, list) and len(log) > 0:
        print("\n  First 20 entries:")
        for i, e in enumerate(log[:20]):
            print(f"    [{i}] {e}")
        if len(log) > 20:
            print("  ...")
            print("  Last 10 entries:")
            for i, e in enumerate(log[-10:]):
                print(f"    [{len(log)-10+i}] {e}")
        
        # Unique values
        unique_vals = set()
        for e in log:
            if isinstance(e, dict):
                v = e.get("bank", e.get("value", e.get("addr", None)))
                if v is not None:
                    unique_vals.add(v)
            elif isinstance(e, (int, float)):
                unique_vals.add(int(e))
            else:
                unique_vals.add(str(e))
        print(f"\n  Unique bank values: {sorted(unique_vals)}")
        
        # Check if any value could map to $FF0066
        target = 0xFF0066
        target_bank = target >> 15  # = 0x1FE
        print(f"\n  Target: $FF0066 needs bank = 0x{target_bank:X} ({target_bank})")
        print(f"  => M68K range: 0x{target_bank << 15:06X} - 0x{(target_bank << 15) + 0x7FFF:06X}")
        
        found_workram = False
        for e in log:
            v = None
            if isinstance(e, dict):
                v = e.get("bank", e.get("value", e.get("addr", None)))
            elif isinstance(e, (int, float)):
                v = int(e)
            if v is not None and isinstance(v, int):
                m68k_base = v << 15 if v < 0x200 else v
                if m68k_base >= 0xFF0000:
                    found_workram = True
                    print(f"  *** FOUND work RAM bank: {v} (0x{v:X}) => M68K 0x{m68k_base:06X}")
        
        if not found_workram:
            print("  => No bank values mapping to work RAM ($FF0000+) found in log")
    
    # Banked read log
    read_log = apu.get("z80_banked_read_log", [])
    print(f"\n  Banked read log entries: {len(read_log) if isinstance(read_log, list) else 'N/A'}")
    if isinstance(read_log, list) and len(read_log) > 0:
        print("  First 10:")
        for i, e in enumerate(read_log[:10]):
            print(f"    [{i}] {e}")

    # 2. Read Z80 RAM and search for bank register writes ($6000)
    print("\n=== Z80 RAM Analysis: Bank Register Writes ===")
    
    # Read Z80 RAM 0x0000-0x1FFF via M68K bus (0xA00000-0xA01FFF)
    z80_ram = []
    for offset in range(0, 0x2000, 0x400):
        addr = 0xA00000 + offset
        resp = api_get("/cpu/memory", {"addr": str(addr), "len": "1024"})
        z80_ram.extend(resp["data"])
    
    print(f"  Z80 RAM read: {len(z80_ram)} bytes")
    
    # Search for references to $6000 (bank register)
    # Z80 opcodes that write to memory address:
    # LD (nn), A: 0x32 lo hi => 32 00 60
    # LD (nn), HL: 0x22 lo hi => 22 00 60
    # LD (nn), r: ED 43/53/63/73 lo hi
    
    print("\n  Searching for Z80 instructions writing to $6000 (bank register)...")
    bank_write_sites = []
    
    for i in range(len(z80_ram) - 2):
        # LD (nn), A  = 32 00 60
        if z80_ram[i] == 0x32 and z80_ram[i+1] == 0x00 and z80_ram[i+2] == 0x60:
            ctx_start = max(0, i-4)
            ctx_end = min(len(z80_ram), i+8)
            ctx = " ".join(f"{z80_ram[j]:02X}" for j in range(ctx_start, ctx_end))
            bank_write_sites.append((i, "LD ($6000), A", ctx))
        
        # Check for any reference to $60xx (could be bank area)
        if i < len(z80_ram) - 2:
            if z80_ram[i+2] == 0x60 and z80_ram[i+1] == 0x00:
                opcode = z80_ram[i]
                if opcode in (0x32, 0x22, 0x3A, 0x2A):
                    op_names = {0x32: "LD ($6000),A", 0x22: "LD ($6000),HL", 
                                0x3A: "LD A,($6000)", 0x2A: "LD HL,($6000)"}
                    if (i, op_names.get(opcode, ""), "") not in [(s[0], s[1], "") for s in bank_write_sites]:
                        ctx_start = max(0, i-4)
                        ctx_end = min(len(z80_ram), i+8)
                        ctx = " ".join(f"{z80_ram[j]:02X}" for j in range(ctx_start, ctx_end))
                        bank_write_sites.append((i, op_names.get(opcode, f"opcode {opcode:02X}"), ctx))
    
    # Also search for ED-prefixed instructions targeting $6000
    for i in range(len(z80_ram) - 3):
        if z80_ram[i] == 0xED and z80_ram[i+2] == 0x00 and z80_ram[i+3] == 0x60:
            op2 = z80_ram[i+1]
            op_names = {0x43: "LD ($6000),BC", 0x53: "LD ($6000),DE", 
                        0x63: "LD ($6000),HL", 0x73: "LD ($6000),SP"}
            name = op_names.get(op2, f"ED {op2:02X}")
            ctx_start = max(0, i-4)
            ctx_end = min(len(z80_ram), i+8)
            ctx = " ".join(f"{z80_ram[j]:02X}" for j in range(ctx_start, ctx_end))
            bank_write_sites.append((i, name, ctx))
    
    if bank_write_sites:
        print(f"  Found {len(bank_write_sites)} bank register access sites:")
        for addr, name, ctx in sorted(bank_write_sites):
            print(f"    Z80:${addr:04X}: {name}  [{ctx}]")
    else:
        print("  No direct bank register access found!")
    
    # 3. Analyze what bank values the Z80 code sets
    # Look at the code around each write site to understand what A register contains
    print("\n=== Bank Value Analysis ===")
    for addr, name, ctx in sorted(bank_write_sites):
        if "LD ($6000),A" in name:
            # Look backwards for what loads A
            print(f"\n  Site Z80:${addr:04X}: {name}")
            # Show surrounding code
            start = max(0, addr - 16)
            end = min(len(z80_ram), addr + 8)
            print(f"    Context (${start:04X}-${end:04X}):")
            for j in range(start, end):
                marker = " <<<" if j == addr else ""
                print(f"      ${j:04X}: {z80_ram[j]:02X}{marker}")
    
    # 4. Check the Z80 INT handler at $0038
    print("\n=== Z80 INT Handler ($0038) ===")
    for i in range(0x38, min(0x60, len(z80_ram))):
        print(f"  ${i:04X}: {z80_ram[i]:02X}", end="")
        if (i - 0x38) % 16 == 15:
            print()
    print()
    
    # 5. Check Z80 PC and what it's currently doing
    pc = apu.get("z80_pc", 0)
    print(f"\n=== Z80 Current PC: ${pc:04X} ===")
    if pc < len(z80_ram):
        start = max(0, pc - 8)
        end = min(len(z80_ram), pc + 16)
        code = " ".join(f"{z80_ram[j]:02X}" for j in range(start, end))
        print(f"  Code around PC: {code}")
    
    # 6. Calculate if bank switching to $FF0066 is theoretically possible
    print("\n=== Theoretical Analysis ===")
    target = 0xFF0066
    bank_needed = target >> 15
    z80_offset = target & 0x7FFF
    z80_addr = 0x8000 + z80_offset
    print(f"  To access M68K $FF0066:")
    print(f"    Bank register value needed: {bank_needed} (0x{bank_needed:X})")
    print(f"    Z80 address would be: ${z80_addr:04X}")
    print(f"    M68K mapped range: ${bank_needed << 15:06X}-${(bank_needed << 15) + 0x7FFF:06X}")
    print(f"    Bank register is 9 bits (0-511), needed value {bank_needed} = {'WITHIN' if bank_needed < 512 else 'EXCEEDS'} range")
    
    # Also check: does the Z80 driver routine ever do a series of writes
    # to $6000 that could shift in high bits for work RAM?
    # Mega Drive bank register: each write to $6000 shifts in bit 0 of data
    # After 9 writes, the 9-bit bank value is complete
    # So the M68K address = bank_9bit << 15
    #   Max addressable = 511 << 15 = 0xFF8000
    #   $FF0066 needs bank = $FF0066 >> 15 = 510.003... => bank 510 = 0x1FE
    #   510 in 9 bits = 0b111111110 => valid!
    #   Z80 offset = $FF0066 & $7FFF = $0066
    #   Z80 address = $8000 + $0066 = $8066
    
    print(f"\n  Bank 510 (0x1FE) in binary: {510:09b}")
    print(f"  This IS within the 9-bit range (max 511)")
    print(f"  If bank=510, Z80 addr $8066 => M68K $FF0066")
    print(f"  If bank=510, Z80 addr $8067 => M68K $FF0067")

if __name__ == "__main__":
    main()
