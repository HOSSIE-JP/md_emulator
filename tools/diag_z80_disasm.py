#!/usr/bin/env python3
"""Disassemble Z80 code around the main loop to find command poll address."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run a few frames
for _ in range(10):
    post("/emulator/step", {"frames": 1})

# Read Z80 RAM at the code area (0x1100-0x1400 which is where Z80 PC visits)
z80_mem = get(f"/cpu/memory?addr={0xA01100}&len=768")
data = z80_mem.get("data", [])

# Simple Z80 disassembler for common instructions
def dis_z80(mem, start_addr, count):
    pc = 0
    lines = []
    while pc < len(mem) and len(lines) < count:
        addr = start_addr + pc
        b = mem[pc]
        
        if b == 0xF3:
            lines.append(f"  {addr:04X}: DI")
            pc += 1
        elif b == 0xFB:
            lines.append(f"  {addr:04X}: EI")
            pc += 1
        elif b == 0xC3 and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: JP 0x{t:04X}")
            pc += 3
        elif b == 0xCD and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: CALL 0x{t:04X}")
            pc += 3
        elif b == 0xC9:
            lines.append(f"  {addr:04X}: RET")
            pc += 1
        elif b == 0x3E and pc+1 < len(mem):
            lines.append(f"  {addr:04X}: LD A,0x{mem[pc+1]:02X}")
            pc += 2
        elif b == 0x21 and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: LD HL,0x{t:04X}")
            pc += 3
        elif b == 0x11 and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: LD DE,0x{t:04X}")
            pc += 3
        elif b == 0x01 and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: LD BC,0x{t:04X}")
            pc += 3
        elif b == 0x36 and pc+1 < len(mem):
            lines.append(f"  {addr:04X}: LD (HL),0x{mem[pc+1]:02X}")
            pc += 2
        elif b == 0x77:
            lines.append(f"  {addr:04X}: LD (HL),A")
            pc += 1
        elif b == 0x7E:
            lines.append(f"  {addr:04X}: LD A,(HL)")
            pc += 1
        elif b == 0x3A and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: LD A,(0x{t:04X})")
            pc += 3
        elif b == 0x32 and pc+2 < len(mem):
            t = mem[pc+1] | (mem[pc+2] << 8)
            lines.append(f"  {addr:04X}: LD (0x{t:04X}),A")
            pc += 3
        elif b == 0x18 and pc+1 < len(mem):
            off = mem[pc+1]
            if off > 127: off -= 256
            target = addr + 2 + off
            lines.append(f"  {addr:04X}: JR 0x{target:04X}")
            pc += 2
        elif b == 0x20 and pc+1 < len(mem):
            off = mem[pc+1]
            if off > 127: off -= 256
            target = addr + 2 + off
            lines.append(f"  {addr:04X}: JR NZ,0x{target:04X}")
            pc += 2
        elif b == 0x28 and pc+1 < len(mem):
            off = mem[pc+1]
            if off > 127: off -= 256
            target = addr + 2 + off
            lines.append(f"  {addr:04X}: JR Z,0x{target:04X}")
            pc += 2
        elif b == 0x30 and pc+1 < len(mem):
            off = mem[pc+1]
            if off > 127: off -= 256
            target = addr + 2 + off
            lines.append(f"  {addr:04X}: JR NC,0x{target:04X}")
            pc += 2
        elif b == 0x38 and pc+1 < len(mem):
            off = mem[pc+1]
            if off > 127: off -= 256
            target = addr + 2 + off
            lines.append(f"  {addr:04X}: JR C,0x{target:04X}")
            pc += 2
        elif b == 0xFE and pc+1 < len(mem):
            lines.append(f"  {addr:04X}: CP 0x{mem[pc+1]:02X}")
            pc += 2
        elif b == 0xD3 and pc+1 < len(mem):
            lines.append(f"  {addr:04X}: OUT (0x{mem[pc+1]:02X}),A")
            pc += 2
        elif b == 0x76:
            lines.append(f"  {addr:04X}: HALT")
            pc += 1
        elif b == 0x00:
            lines.append(f"  {addr:04X}: NOP")
            pc += 1
        elif b == 0xAF:
            lines.append(f"  {addr:04X}: XOR A")
            pc += 1
        elif b == 0xB7:
            lines.append(f"  {addr:04X}: OR A")
            pc += 1
        elif b == 0xA7:
            lines.append(f"  {addr:04X}: AND A")
            pc += 1
        elif b == 0xDD or b == 0xFD:
            prefix = "IX" if b == 0xDD else "IY"
            if pc+1 < len(mem):
                b2 = mem[pc+1]
                if b2 == 0x21 and pc+3 < len(mem):
                    t = mem[pc+2] | (mem[pc+3] << 8)
                    lines.append(f"  {addr:04X}: LD {prefix},0x{t:04X}")
                    pc += 4
                elif b2 == 0x7E and pc+2 < len(mem):
                    d = mem[pc+2]
                    if d > 127: d -= 256
                    lines.append(f"  {addr:04X}: LD A,({prefix}+{d})")
                    pc += 3
                elif b2 == 0x77 and pc+2 < len(mem):
                    d = mem[pc+2]
                    if d > 127: d -= 256
                    lines.append(f"  {addr:04X}: LD ({prefix}+{d}),A")
                    pc += 3
                elif b2 == 0x36 and pc+3 < len(mem):
                    d = mem[pc+2]
                    if d > 127: d -= 256
                    lines.append(f"  {addr:04X}: LD ({prefix}+{d}),0x{mem[pc+3]:02X}")
                    pc += 4
                elif b2 == 0xBE and pc+2 < len(mem):
                    d = mem[pc+2]
                    if d > 127: d -= 256
                    lines.append(f"  {addr:04X}: CP ({prefix}+{d})")
                    pc += 3
                elif b2 == 0xE5:
                    lines.append(f"  {addr:04X}: PUSH {prefix}")
                    pc += 2
                elif b2 == 0xE1:
                    lines.append(f"  {addr:04X}: POP {prefix}")
                    pc += 2
                elif b2 == 0xE9:
                    lines.append(f"  {addr:04X}: JP ({prefix})")
                    pc += 2
                else:
                    lines.append(f"  {addr:04X}: {prefix} prefix 0x{b2:02X} ... [{' '.join(f'{mem[pc+i]:02X}' for i in range(min(4, len(mem)-pc)))}]")
                    pc += 2
            else:
                pc += 1
        elif b == 0xED:
            if pc+1 < len(mem):
                b2 = mem[pc+1]
                lines.append(f"  {addr:04X}: ED prefix 0x{b2:02X} [{' '.join(f'{mem[pc+i]:02X}' for i in range(min(4, len(mem)-pc)))}]")
                pc += 2
            else:
                pc += 1
        elif b == 0xCB:
            if pc+1 < len(mem):
                b2 = mem[pc+1]
                lines.append(f"  {addr:04X}: CB prefix 0x{b2:02X}")
                pc += 2
            else:
                pc += 1
        else:
            lines.append(f"  {addr:04X}: [0x{b:02X}]")
            pc += 1
    return lines

# Disassemble around Z80 PCs we've seen: 0x1171, 0x12A3, 0x124A, 0x1213
# Show broad range
print("=== Z80 Code 0x1100-0x1300 ===")
for line in dis_z80(data, 0x1100, 200):
    print(line)

# Also check the entry point area (JP 0x114A)
z80_entry = get(f"/cpu/memory?addr={0xA0114A}&len=64")
entry_data = z80_entry.get("data", [])
print("\n=== Z80 Code 0x114A (entry) ===")
for line in dis_z80(entry_data, 0x114A, 30):
    print(line)
