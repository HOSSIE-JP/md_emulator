#!/usr/bin/env python3
"""Z80 bank set analysis - determine what values A register has before bank writes"""

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
    # Read Z80 RAM
    z80_ram = []
    for offset in range(0, 0x2000, 0x400):
        addr = 0xA00000 + offset
        resp = api_get("/cpu/memory", {"addr": str(addr), "len": "1024"})
        z80_ram.extend(resp["data"])
    
    # The bank set routine pattern is always:
    #   LD BC,$6000      ; 01 00 60
    #   LD (BC),A; RRCA  ; 02 0F  (x7 times for bits 0-6)
    #   LD (BC),A        ; 02     (bit 7)
    #   XOR A; LD (BC),A ; AF 02  (bit 8 = 0 always)
    #   LD (BC),A        ; 02     (final write resets shift register)
    #
    # The RRCA (0x0F) rotates A right through carry, so each LD (BC),A
    # writes bit 0 of A to the bank register shift register.
    # After 9 writes, the bank value is complete.
    #
    # So the bank value is derived from:
    # - bits 0-6 come from A (bit 0 first, then bit 1 after RRCA, etc.)
    # - bit 7 comes from A after 7 RRCAs
    # - bits 8 = always 0 (XOR A sets A=0)
    
    # Bank set routines found at: $0A21, $0A64, $0B96, $0C13
    # Each is inline (not a shared subroutine)
    
    # Now trace BACK from each bank set to find what's in A
    bank_sites = [0x0A21, 0x0A64, 0x0B96, 0x0C13]
    
    for site in bank_sites:
        print(f"\n=== Bank set at ${site:04X} ===")
        # Show 32 bytes before the LD BC,$6000
        start = max(0, site - 32)
        print(f"  Code leading to bank set (${start:04X}-${site:04X}):")
        for i in range(start, site):
            print(f"    ${i:04X}: {z80_ram[i]:02X}", end="")
            if (i - start) % 16 == 15:
                print()
        print()
    
    # Special case: $0284 reference
    # At $0284 we found: ... 3A FA 01 21 00 60 77 0F 77 0F ...
    # This is: LD A,($01FA); LD HL,$6000; LD (HL),A; RRCA; LD (HL),A; RRCA; ...
    # This is ANOTHER bank set pattern using LD (HL),A instead of LD (BC),A
    print("\n=== Special bank set at $0284 (using HL) ===")
    start = 0x0278
    end = min(len(z80_ram), 0x02B0)
    print(f"  Code ${start:04X}-${end:04X}:")
    for i in range(start, end):
        print(f"    ${i:04X}: {z80_ram[i]:02X}", end="")
        if (i - start) % 16 == 15:
            print()
    print()
    
    # Also search for LD (HL),A patterns to $6000
    print("\n=== LD HL,$6000; LD (HL),A patterns ===")
    for i in range(len(z80_ram) - 4):
        if z80_ram[i] == 0x21 and z80_ram[i+1] == 0x00 and z80_ram[i+2] == 0x60:
            # LD HL,$6000
            # Check for LD (HL),A = 0x77 nearby
            count_77 = 0
            for j in range(i+3, min(i+30, len(z80_ram))):
                if z80_ram[j] == 0x77:
                    count_77 += 1
            print(f"  LD HL,$6000 at ${i:04X}, LD (HL),A count in next 30: {count_77}")
            if count_77 >= 5:
                print(f"  *** BANK SET ROUTINE (HL variant)! ***")
                end_ctx = min(len(z80_ram), i+30)
                code = " ".join(f"{z80_ram[j]:02X}" for j in range(i, end_ctx))
                print(f"    {code}")
    
    # Key question: What value is in A at each bank set site?
    # 
    # For the $0284 site: LD A,($01FA) loads A from RAM $01FA
    print("\n=== RAM $01FA value (bank source for $0284) ===")
    if 0x01FA < len(z80_ram):
        print(f"  Z80 RAM[$01FA] = 0x{z80_ram[0x01FA]:02X}")
        print(f"  -> Bank would be: value bits 0-7 + bit8=0")
        val = z80_ram[0x01FA]
        # RRCA rotates right by 1 each time, and bit 0 is what gets written
        # Write sequence: bit0, bit1, bit2, ..., bit6, bit7, then 0, 0
        # So bank = bits [0:8] of the value = the value itself for 8-bit
        print(f"  -> bank = {val} (0x{val:02X})")
        m68k_addr = val << 15
        print(f"  -> M68K base = 0x{m68k_addr:06X}")
        # Is this ever set to 0x1FE (510)?
        print(f"  -> For $FF0066: need bank=510 (0x1FE), need A=0xFE with bit8=1")
        print(f"  -> But bit 8 is always XOR A (=0), so max bank=255!")
    
    # For the $0A21 site: what loads A before?
    print("\n=== Analysis: $0A21 bank set caller ===")
    # Look at what's before $0A21
    # $0A1E: DD 7C = LD A,IXH
    # $0A20: 17 = RLA (rotate left through carry)
    print("  Before $0A21:")
    for i in range(0x0A10, 0x0A24):
        print(f"    ${i:04X}: {z80_ram[i]:02X}")
    
    # Check if the $0A64 variant uses different A source
    print("\n=== Analysis: $0A64 bank set ===")
    print("  Before $0A64:")
    for i in range(0x0A58, 0x0A68):
        print(f"    ${i:04X}: {z80_ram[i]:02X}")
    
    # Check $0B96
    print("\n=== Analysis: $0B96 bank set (restore routine) ===")
    print("  Before $0B96:")
    for i in range(0x0B88, 0x0B9A):
        print(f"    ${i:04X}: {z80_ram[i]:02X}")
    
    # Check $0C13
    print("\n=== Analysis: $0C13 bank set ===")
    print("  Before $0C13:")
    for i in range(0x0C06, 0x0C16):
        print(f"    ${i:04X}: {z80_ram[i]:02X}")
    
    # CRITICAL INSIGHT:
    # In the GEMS driver, the bank set always clears bits 8 with XOR A
    # This means the bank register can only be 0-255 (8 bits from A + bit8=0)
    # Bank 510 (0x1FE) requires bit 8 = 1, which is NEVER set!
    print("\n" + "="*60)
    print("=== CONCLUSION ===")
    print("="*60)
    print()
    print("Bank set pattern in this Z80 GEMS driver:")
    print("  LD BC,$6000 / LD HL,$6000")
    print("  LD (BC/HL),A; RRCA  x7  (writes bits 0-6 of A)")
    print("  LD (BC/HL),A           (writes bit 7 of A)")
    print("  XOR A                  *** ALWAYS clears A! ***")
    print("  LD (BC/HL),A           (writes bit 8 = 0)")
    print("  LD (BC/HL),A           (writes bit 9 = 0, not used)")
    print()
    print("This means:")
    print("  - Bank register max value = 255 (0xFF)")
    print("  - Max M68K address = 255 << 15 = 0x7F8000")
    print("  - M68K work RAM starts at 0xFF0000")
    print("  - Bank 510 (0x1FE) needed for $FF0066 is UNREACHABLE")
    print("  - Bank 510 binary = 111111110, bit 8 = 1")
    print("  - But GEMS always sets bit 8 = 0 via XOR A")
    print()
    print(">>> Z80 CANNOT access $FF0066 via bank switching <<<")
    print(">>> The GEMS driver ONLY banks to ROM area (0x000000-0x7F8000) <<<")

if __name__ == "__main__":
    main()
