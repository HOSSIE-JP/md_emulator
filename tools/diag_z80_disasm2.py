#!/usr/bin/env python3
"""Disassemble Z80 GEMS code: main loop and command handlers."""
import json, urllib.request

API = "http://localhost:8081/api/v1"

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{API}{path}").read())

def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{API}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def read_z80_ram(offset, length):
    mem = api_get(f"/cpu/memory?addr={0xA00000 + offset}&len={length}")
    return mem.get("data", [])

# Load ROM and run a few frames so Z80 code is in place
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
for _ in range(5):
    api_post("/emulator/step", {"frames": 1})

# Simple Z80 disassembler (key instructions only)
def disasm_z80(code, base_addr):
    i = 0
    lines = []
    while i < len(code):
        addr = base_addr + i
        b = code[i]
        
        if b == 0x00:
            lines.append(f"  {addr:04X}: NOP")
            i += 1
        elif b == 0x3E and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD A,${code[i+1]:02X}")
            i += 2
        elif b == 0x32 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD (${nn:04X}),A")
            i += 3
        elif b == 0x3A and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD A,(${nn:04X})")
            i += 3
        elif b == 0xC3 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: JP ${nn:04X}")
            i += 3
        elif b == 0xCA and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: JP Z,${nn:04X}")
            i += 3
        elif b == 0xC2 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: JP NZ,${nn:04X}")
            i += 3
        elif b == 0xCD and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: CALL ${nn:04X}")
            i += 3
        elif b == 0xCC and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: CALL Z,${nn:04X}")
            i += 3
        elif b == 0xC4 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: CALL NZ,${nn:04X}")
            i += 3
        elif b == 0xC9:
            lines.append(f"  {addr:04X}: RET")
            i += 1
        elif b == 0xC8:
            lines.append(f"  {addr:04X}: RET Z")
            i += 1
        elif b == 0xC0:
            lines.append(f"  {addr:04X}: RET NZ")
            i += 1
        elif b == 0x18 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: JR ${target:04X}")
            i += 2
        elif b == 0x28 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: JR Z,${target:04X}")
            i += 2
        elif b == 0x20 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: JR NZ,${target:04X}")
            i += 2
        elif b == 0xF6 and i+1 < len(code):
            lines.append(f"  {addr:04X}: OR ${code[i+1]:02X}")
            i += 2
        elif b == 0xE6 and i+1 < len(code):
            lines.append(f"  {addr:04X}: AND ${code[i+1]:02X}")
            i += 2
        elif b == 0xFE and i+1 < len(code):
            lines.append(f"  {addr:04X}: CP ${code[i+1]:02X}")
            i += 2
        elif b == 0xA7:
            lines.append(f"  {addr:04X}: AND A")
            i += 1
        elif b == 0xAF:
            lines.append(f"  {addr:04X}: XOR A")
            i += 1
        elif b == 0xB7:
            lines.append(f"  {addr:04X}: OR A")
            i += 1
        elif b == 0x21 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD HL,${nn:04X}")
            i += 3
        elif b == 0x11 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD DE,${nn:04X}")
            i += 3
        elif b == 0x01 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD BC,${nn:04X}")
            i += 3
        elif b == 0x36 and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD (HL),${code[i+1]:02X}")
            i += 2
        elif b == 0x77:
            lines.append(f"  {addr:04X}: LD (HL),A")
            i += 1
        elif b == 0x7E:
            lines.append(f"  {addr:04X}: LD A,(HL)")
            i += 1
        elif b == 0x23:
            lines.append(f"  {addr:04X}: INC HL")
            i += 1
        elif b == 0x2B:
            lines.append(f"  {addr:04X}: DEC HL")
            i += 1
        elif b == 0x3C:
            lines.append(f"  {addr:04X}: INC A")
            i += 1
        elif b == 0x3D:
            lines.append(f"  {addr:04X}: DEC A")
            i += 1
        elif b == 0xE5:
            lines.append(f"  {addr:04X}: PUSH HL")
            i += 1
        elif b == 0xE1:
            lines.append(f"  {addr:04X}: POP HL")
            i += 1
        elif b == 0xC5:
            lines.append(f"  {addr:04X}: PUSH BC")
            i += 1
        elif b == 0xC1:
            lines.append(f"  {addr:04X}: POP BC")
            i += 1
        elif b == 0xD5:
            lines.append(f"  {addr:04X}: PUSH DE")
            i += 1
        elif b == 0xD1:
            lines.append(f"  {addr:04X}: POP DE")
            i += 1
        elif b == 0xF5:
            lines.append(f"  {addr:04X}: PUSH AF")
            i += 1
        elif b == 0xF1:
            lines.append(f"  {addr:04X}: POP AF")
            i += 1
        elif b == 0xE9:
            lines.append(f"  {addr:04X}: JP (HL)")
            i += 1
        elif b == 0x47:
            lines.append(f"  {addr:04X}: LD B,A")
            i += 1
        elif b == 0x4F:
            lines.append(f"  {addr:04X}: LD C,A")
            i += 1
        elif b == 0x57:
            lines.append(f"  {addr:04X}: LD D,A")
            i += 1
        elif b == 0x5F:
            lines.append(f"  {addr:04X}: LD E,A")
            i += 1
        elif b == 0x67:
            lines.append(f"  {addr:04X}: LD H,A")
            i += 1
        elif b == 0x6F:
            lines.append(f"  {addr:04X}: LD L,A")
            i += 1
        elif b == 0x78:
            lines.append(f"  {addr:04X}: LD A,B")
            i += 1
        elif b == 0x79:
            lines.append(f"  {addr:04X}: LD A,C")
            i += 1
        elif b == 0x7A:
            lines.append(f"  {addr:04X}: LD A,D")
            i += 1
        elif b == 0x7B:
            lines.append(f"  {addr:04X}: LD A,E")
            i += 1
        elif b == 0x7C:
            lines.append(f"  {addr:04X}: LD A,H")
            i += 1
        elif b == 0x7D:
            lines.append(f"  {addr:04X}: LD A,L")
            i += 1
        elif b == 0x87:
            lines.append(f"  {addr:04X}: ADD A,A")
            i += 1
        elif b == 0xC6 and i+1 < len(code):
            lines.append(f"  {addr:04X}: ADD A,${code[i+1]:02X}")
            i += 2
        elif b == 0xD6 and i+1 < len(code):
            lines.append(f"  {addr:04X}: SUB ${code[i+1]:02X}")
            i += 2
        elif b == 0x06 and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD B,${code[i+1]:02X}")
            i += 2
        elif b == 0x0E and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD C,${code[i+1]:02X}")
            i += 2
        elif b == 0x16 and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD D,${code[i+1]:02X}")
            i += 2
        elif b == 0x1E and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD E,${code[i+1]:02X}")
            i += 2
        elif b == 0x26 and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD H,${code[i+1]:02X}")
            i += 2
        elif b == 0x2E and i+1 < len(code):
            lines.append(f"  {addr:04X}: LD L,${code[i+1]:02X}")
            i += 2
        elif b == 0xF3:
            lines.append(f"  {addr:04X}: DI")
            i += 1
        elif b == 0xFB:
            lines.append(f"  {addr:04X}: EI")
            i += 1
        elif b == 0x76:
            lines.append(f"  {addr:04X}: HALT")
            i += 1
        elif b == 0x10 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: DJNZ ${target:04X}")
            i += 2
        elif b == 0xD3 and i+1 < len(code):
            lines.append(f"  {addr:04X}: OUT (${code[i+1]:02X}),A")
            i += 2
        elif b == 0xDB and i+1 < len(code):
            lines.append(f"  {addr:04X}: IN A,(${code[i+1]:02X})")
            i += 2
        elif b == 0xED:
            if i+1 < len(code):
                b2 = code[i+1]
                if b2 == 0xB0:
                    lines.append(f"  {addr:04X}: LDIR")
                    i += 2
                elif b2 == 0xB8:
                    lines.append(f"  {addr:04X}: LDDR")
                    i += 2
                elif b2 == 0x56:
                    lines.append(f"  {addr:04X}: IM 1")
                    i += 2
                elif b2 == 0x5E:
                    lines.append(f"  {addr:04X}: IM 2")
                    i += 2
                else:
                    lines.append(f"  {addr:04X}: ED {b2:02X} (?)")
                    i += 2
            else:
                lines.append(f"  {addr:04X}: ED (?)")
                i += 1
        elif b == 0xCB:
            if i+1 < len(code):
                b2 = code[i+1]
                bit_n = (b2 >> 3) & 7
                reg_names = ["B","C","D","E","H","L","(HL)","A"]
                r = reg_names[b2 & 7]
                if b2 >= 0x40 and b2 <= 0x7F:
                    lines.append(f"  {addr:04X}: BIT {bit_n},{r}")
                elif b2 >= 0xC0:
                    lines.append(f"  {addr:04X}: SET {bit_n},{r}")
                elif b2 >= 0x80:
                    lines.append(f"  {addr:04X}: RES {bit_n},{r}")
                else:
                    lines.append(f"  {addr:04X}: CB {b2:02X} (?)")
                i += 2
            else:
                lines.append(f"  {addr:04X}: CB (?)")
                i += 1
        elif b == 0x0A:
            lines.append(f"  {addr:04X}: LD A,(BC)")
            i += 1
        elif b == 0x1A:
            lines.append(f"  {addr:04X}: LD A,(DE)")
            i += 1
        elif b == 0x02:
            lines.append(f"  {addr:04X}: LD (BC),A")
            i += 1
        elif b == 0x12:
            lines.append(f"  {addr:04X}: LD (DE),A")
            i += 1
        elif b == 0x13:
            lines.append(f"  {addr:04X}: INC DE")
            i += 1
        elif b == 0x03:
            lines.append(f"  {addr:04X}: INC BC")
            i += 1
        elif b == 0x0B:
            lines.append(f"  {addr:04X}: DEC BC")
            i += 1
        elif b == 0x1B:
            lines.append(f"  {addr:04X}: DEC DE")
            i += 1
        elif b == 0x09:
            lines.append(f"  {addr:04X}: ADD HL,BC")
            i += 1
        elif b == 0x19:
            lines.append(f"  {addr:04X}: ADD HL,DE")
            i += 1
        elif b == 0x29:
            lines.append(f"  {addr:04X}: ADD HL,HL")
            i += 1
        elif b == 0x39:
            lines.append(f"  {addr:04X}: ADD HL,SP")
            i += 1
        elif b == 0xD9:
            lines.append(f"  {addr:04X}: EXX")
            i += 1
        elif b == 0x08:
            lines.append(f"  {addr:04X}: EX AF,AF'")
            i += 1
        elif b == 0xEB:
            lines.append(f"  {addr:04X}: EX DE,HL")
            i += 1
        elif b == 0x17:
            lines.append(f"  {addr:04X}: RLA")
            i += 1
        elif b == 0x1F:
            lines.append(f"  {addr:04X}: RRA")
            i += 1
        elif b == 0x07:
            lines.append(f"  {addr:04X}: RLCA")
            i += 1
        elif b == 0x0F:
            lines.append(f"  {addr:04X}: RRCA")
            i += 1
        elif b == 0x2F:
            lines.append(f"  {addr:04X}: CPL")
            i += 1
        elif b == 0x37:
            lines.append(f"  {addr:04X}: SCF")
            i += 1
        elif b == 0x3F:
            lines.append(f"  {addr:04X}: CCF")
            i += 1
        elif b == 0x46:
            lines.append(f"  {addr:04X}: LD B,(HL)")
            i += 1
        elif b == 0x4E:
            lines.append(f"  {addr:04X}: LD C,(HL)")
            i += 1
        elif b == 0x56:
            lines.append(f"  {addr:04X}: LD D,(HL)")
            i += 1
        elif b == 0x5E:
            lines.append(f"  {addr:04X}: LD E,(HL)")
            i += 1
        elif b == 0x66:
            lines.append(f"  {addr:04X}: LD H,(HL)")
            i += 1
        elif b == 0x6E:
            lines.append(f"  {addr:04X}: LD L,(HL)")
            i += 1
        elif b == 0xD2 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: JP NC,${nn:04X}")
            i += 3
        elif b == 0xDA and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: JP C,${nn:04X}")
            i += 3
        elif b == 0x30 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: JR NC,${target:04X}")
            i += 2
        elif b == 0x38 and i+1 < len(code):
            offset = code[i+1]
            if offset & 0x80: offset -= 256
            target = addr + 2 + offset
            lines.append(f"  {addr:04X}: JR C,${target:04X}")
            i += 2
        elif b == 0xD0:
            lines.append(f"  {addr:04X}: RET NC")
            i += 1
        elif b == 0xD8:
            lines.append(f"  {addr:04X}: RET C")
            i += 1
        elif b == 0x04:
            lines.append(f"  {addr:04X}: INC B")
            i += 1
        elif b == 0x05:
            lines.append(f"  {addr:04X}: DEC B")
            i += 1
        elif b == 0x0C:
            lines.append(f"  {addr:04X}: INC C")
            i += 1
        elif b == 0x0D:
            lines.append(f"  {addr:04X}: DEC C")
            i += 1
        elif b == 0x14:
            lines.append(f"  {addr:04X}: INC D")
            i += 1
        elif b == 0x15:
            lines.append(f"  {addr:04X}: DEC D")
            i += 1
        elif b == 0x1C:
            lines.append(f"  {addr:04X}: INC E")
            i += 1
        elif b == 0x1D:
            lines.append(f"  {addr:04X}: DEC E")
            i += 1
        elif b == 0x24:
            lines.append(f"  {addr:04X}: INC H")
            i += 1
        elif b == 0x25:
            lines.append(f"  {addr:04X}: DEC H")
            i += 1
        elif b == 0x2C:
            lines.append(f"  {addr:04X}: INC L")
            i += 1
        elif b == 0x2D:
            lines.append(f"  {addr:04X}: DEC L")
            i += 1
        elif b == 0x34:
            lines.append(f"  {addr:04X}: INC (HL)")
            i += 1
        elif b == 0x35:
            lines.append(f"  {addr:04X}: DEC (HL)")
            i += 1
        elif b == 0x86:
            lines.append(f"  {addr:04X}: ADD A,(HL)")
            i += 1
        elif b == 0x96:
            lines.append(f"  {addr:04X}: SUB (HL)")
            i += 1
        elif b == 0xBE:
            lines.append(f"  {addr:04X}: CP (HL)")
            i += 1
        elif b == 0xB6:
            lines.append(f"  {addr:04X}: OR (HL)")
            i += 1
        elif b == 0xA6:
            lines.append(f"  {addr:04X}: AND (HL)")
            i += 1
        elif b == 0xAE:
            lines.append(f"  {addr:04X}: XOR (HL)")
            i += 1
        elif b == 0x22 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD (${nn:04X}),HL")
            i += 3
        elif b == 0x2A and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD HL,(${nn:04X})")
            i += 3
        elif b == 0x31 and i+2 < len(code):
            nn = code[i+1] | (code[i+2] << 8)
            lines.append(f"  {addr:04X}: LD SP,${nn:04X}")
            i += 3
        elif b == 0xF9:
            lines.append(f"  {addr:04X}: LD SP,HL")
            i += 1
        else:
            lines.append(f"  {addr:04X}: DB ${b:02X}")
            i += 1
    return lines

# Disassemble key areas
print("=== Z80 GEMS Entry / Init (0x114A-0x116F) ===")
code = read_z80_ram(0x114A, 0x40)
for line in disasm_z80(code, 0x114A):
    print(line)

print("\n=== Z80 Main Loop (0x116F-0x11A0) ===")
code = read_z80_ram(0x116F, 0x50)
for line in disasm_z80(code, 0x116F):
    print(line)

print("\n=== Z80 Jump Table area (0x118F-0x11D0) ===")
jt = read_z80_ram(0x118F, 0x50)
# Display as raw hex for jump table interpretation
for i in range(0, min(len(jt), 0x20), 2):
    addr = jt[i] | (jt[i+1] << 8)
    print(f"  {0x118F+i:04X}: word ${addr:04X}")

print("\n=== Z80 Command Handlers ===")
# Disassemble areas that jump table points to
for start_offset in [0x1196, 0x11A0, 0x11B0, 0x11C0, 0x11D0, 0x11E0, 0x1200, 0x1220]:
    code = read_z80_ram(start_offset, 0x30)
    print(f"\n--- Handler at ${start_offset:04X} ---")
    for line in disasm_z80(code, start_offset):
        print(line)

# Also check if 0x0027 clearing is in the main loop or elsewhere
print("\n=== Z80 RAM first 64 bytes (communication area) ===")
raw = read_z80_ram(0x00, 0x40)
print(' '.join(f'{b:02X}' for b in raw[:0x20]))
print(' '.join(f'{b:02X}' for b in raw[0x20:0x40]))

# Check 0x0EF3 (Z80 init subroutine)
print("\n=== Z80 Init Subroutine (0x0EF3-0x0F30) ===")
code = read_z80_ram(0x0EF3, 0x40)
for line in disasm_z80(code, 0x0EF3):
    print(line)
