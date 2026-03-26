#!/usr/bin/env python3
"""Load ROM, run frames, then check Z80 IM1 handler and queue."""
import urllib.request, json

BASE = "http://localhost:8092/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Load ROM and run frames
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
post("/emulator/step", {"frames": 10})
print("ROM loaded, 10 frames run")

# Read Z80 RAM $0000-$0080
z80 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x80})
fd = bytes(z80["data"])
print("\nZ80 RAM $0000-$007F:")
for off in range(0, 0x80, 16):
    hexstr = " ".join(f"{b:02X}" for b in fd[off:off+16])
    print(f"  ${off:04X}: {hexstr}")

# IM1 handler at $0038
print(f"\n=== IM1 handler at $0038 ===")
handler = fd[0x38:0x60]
print(f"  Raw: {' '.join(f'{b:02X}' for b in handler)}")

# Decode
pc = 0x38
i = 0
while i < len(handler) and pc < 0x60:
    b = handler[i]
    if b == 0xC9:
        print(f"  ${pc:04X}: C9         RET"); break
    elif b == 0xC3:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: C3 {lo:02X} {hi:02X}   JP ${hi:02X}{lo:02X}")
        i += 3; pc += 3; continue
    elif b == 0xFB:
        print(f"  ${pc:04X}: FB         EI")
    elif b == 0xF3:
        print(f"  ${pc:04X}: F3         DI")
    elif b == 0xED:
        b2 = handler[i+1] if i+1 < len(handler) else 0
        if b2 == 0x4D: print(f"  ${pc:04X}: ED 4D      RETI"); break
        elif b2 == 0x45: print(f"  ${pc:04X}: ED 45      RETN"); break
        else: print(f"  ${pc:04X}: ED {b2:02X}"); i += 2; pc += 2; continue
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
    elif b == 0xA7: print(f"  ${pc:04X}: A7         AND A")
    elif b == 0xC8: print(f"  ${pc:04X}: C8         RET Z"); break
    elif b == 0xC0: print(f"  ${pc:04X}: C0         RET NZ"); break
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
    elif b == 0xF6:
        print(f"  ${pc:04X}: F6 {handler[i+1]:02X}      OR ${handler[i+1]:02X}")
        i += 2; pc += 2; continue
    elif b == 0xE6:
        print(f"  ${pc:04X}: E6 {handler[i+1]:02X}      AND ${handler[i+1]:02X}")
        i += 2; pc += 2; continue
    elif b == 0xFE:
        print(f"  ${pc:04X}: FE {handler[i+1]:02X}      CP ${handler[i+1]:02X}")
        i += 2; pc += 2; continue
    elif b == 0x00: print(f"  ${pc:04X}: 00         NOP")
    elif b == 0xF5: print(f"  ${pc:04X}: F5         PUSH AF")
    elif b == 0xC5: print(f"  ${pc:04X}: C5         PUSH BC")
    elif b == 0xD5: print(f"  ${pc:04X}: D5         PUSH DE")
    elif b == 0xE5: print(f"  ${pc:04X}: E5         PUSH HL")
    elif b == 0xF1: print(f"  ${pc:04X}: F1         POP AF")
    elif b == 0xC1: print(f"  ${pc:04X}: C1         POP BC")
    elif b == 0xD1: print(f"  ${pc:04X}: D1         POP DE")
    elif b == 0xE1: print(f"  ${pc:04X}: E1         POP HL")
    elif b == 0x7E: print(f"  ${pc:04X}: 7E         LD A,(HL)")
    elif b == 0x23: print(f"  ${pc:04X}: 23         INC HL")
    elif b == 0x35: print(f"  ${pc:04X}: 35         DEC (HL)")
    elif b == 0x87: print(f"  ${pc:04X}: 87         ADD A,A")
    elif b == 0x5F: print(f"  ${pc:04X}: 5F         LD E,A")
    elif b == 0x16:
        print(f"  ${pc:04X}: 16 {handler[i+1]:02X}      LD D,${handler[i+1]:02X}")
        i += 2; pc += 2; continue
    elif b == 0x21:
        lo, hi = handler[i+1], handler[i+2]
        print(f"  ${pc:04X}: 21 {lo:02X} {hi:02X}   LD HL,${hi:02X}{lo:02X}")
        i += 3; pc += 3; continue
    elif b == 0x19: print(f"  ${pc:04X}: 19         ADD HL,DE")
    elif b == 0x5E: print(f"  ${pc:04X}: 5E         LD E,(HL)")
    elif b == 0x56: print(f"  ${pc:04X}: 56         LD D,(HL)")
    elif b == 0xEB: print(f"  ${pc:04X}: EB         EX DE,HL")
    elif b == 0xE9: print(f"  ${pc:04X}: E9         JP (HL)")
    elif b == 0x97: print(f"  ${pc:04X}: 97         SUB A")
    else:
        print(f"  ${pc:04X}: {b:02X}         ???")
    i += 1; pc += 1

# CPU state
cpu = get("/cpu/state")
print(f"\nZ80 PC=${cpu['cpu']['z80_pc']:04X}, cycles={cpu['cpu']['z80_cycles']}")
