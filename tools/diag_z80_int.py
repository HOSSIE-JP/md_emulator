#!/usr/bin/env python3
"""Check Z80 IM1 interrupt handler and command queue processing."""
import urllib.request, json

BASE = "http://localhost:8092/api/v1"

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Read Z80 RAM $0000-$0080 (includes IM1 vector at $0038)
z80_full = get("/cpu/memory", {"addr": 0xA00000, "len": 0x80})
fd = bytes(z80_full["data"])
print("Z80 RAM $0000-$007F (CURRENT):")
for off in range(0, 0x80, 16):
    hexstr = " ".join(f"{b:02X}" for b in fd[off:off+16])
    print(f"  ${off:04X}: {hexstr}")

# Read original ROM at $076C00+$0000 to compare
rom_area = get("/cpu/memory", {"addr": 0x076C00, "len": 0x80})
rd = bytes(rom_area["data"])
print("\nROM $076C00 (original Z80 binary, first 128 bytes):")
for off in range(0, 0x80, 16):
    hexstr = " ".join(f"{b:02X}" for b in rd[off:off+16])
    print(f"  ${off:04X}: {hexstr}")

# IM1 handler is at $0038
print(f"\n=== IM1 handler at $0038 ===")
print(f"  Z80 RAM: {' '.join(f'{b:02X}' for b in fd[0x38:0x50])}")
print(f"  ROM orig: {' '.join(f'{b:02X}' for b in rd[0x38:0x50])}")

# Decode IM1 handler
handler = fd[0x38:0x60]
print(f"\nDecoding Z80 at $0038:")
pc = 0x38
i = 0
while i < len(handler) and pc < 0x60:
    b = handler[i]
    if b == 0xC9:
        print(f"  ${pc:04X}: C9         RET")
        break
    elif b == 0xC3:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: C3 {lo:02X} {hi:02X}   JP ${hi:02X}{lo:02X}")
        i += 3; pc += 3; continue
    elif b == 0xFB:
        print(f"  ${pc:04X}: FB         EI")
    elif b == 0xF3:
        print(f"  ${pc:04X}: F3         DI")
    elif b == 0xED:
        if i+1 < len(handler):
            b2 = handler[i+1]
            if b2 == 0x4D:
                print(f"  ${pc:04X}: ED 4D      RETI")
                break
            elif b2 == 0x45:
                print(f"  ${pc:04X}: ED 45      RETN")
                break
            else:
                print(f"  ${pc:04X}: ED {b2:02X}      (prefix)")
                i += 2; pc += 2; continue
    elif b == 0x3A:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: 3A {lo:02X} {hi:02X}   LD A,(${hi:02X}{lo:02X})")
        i += 3; pc += 3; continue
    elif b == 0x32:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: 32 {lo:02X} {hi:02X}   LD (${hi:02X}{lo:02X}),A")
        i += 3; pc += 3; continue
    elif b == 0xCD:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: CD {lo:02X} {hi:02X}   CALL ${hi:02X}{lo:02X}")
        i += 3; pc += 3; continue
    elif b == 0xFE:
        print(f"  ${pc:04X}: FE {handler[i+1]:02X}      CP ${handler[i+1]:02X}")
        i += 2; pc += 2; continue
    elif b == 0xA7:
        print(f"  ${pc:04X}: A7         AND A")
    elif b == 0xC8:
        print(f"  ${pc:04X}: C8         RET Z")
        break
    elif b == 0x28:
        disp = handler[i+1]
        if disp & 0x80: disp -= 0x100
        print(f"  ${pc:04X}: 28 {handler[i+1]:02X}      JR Z,${pc+2+disp:04X}")
        i += 2; pc += 2; continue
    elif b == 0x20:
        disp = handler[i+1]
        if disp & 0x80: disp -= 0x100
        print(f"  ${pc:04X}: 20 {handler[i+1]:02X}      JR NZ,${pc+2+disp:04X}")
        i += 2; pc += 2; continue
    else:
        print(f"  ${pc:04X}: {b:02X}         (opcode {b:02X})")
    i += 1; pc += 1

# Also check: is the Z80 receiving interrupts?
# The Z80 interrupt is triggered by VDP VBlank.
# Check if Z80 has had any interrupts since last frame
cpu = get("/cpu/state")
print(f"\nZ80 PC=${cpu['cpu']['z80_pc']:04X}, cycles={cpu['cpu']['z80_cycles']}")
