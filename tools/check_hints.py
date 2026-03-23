"""Check if HInt handler modifies CRAM or other VDP registers during gameplay"""
import urllib.request, json

BASE = "http://127.0.0.1:8117/api/v1"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    d = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=d,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

# Reset and step to demo gameplay
post("/emulator/reset")
post("/emulator/step", {"frames": 3000})

# Get HInt vector
mem = get("/cpu/memory?addr=104&len=4")  # HInt vec at 0x68 = 104 dec
mdata = mem.get("data") or mem.get("memory")
hint_addr = (mdata[0] << 24) | (mdata[1] << 16) | (mdata[2] << 8) | mdata[3]
print(f"HInt vector: 0x{hint_addr:06X}")

# Read HInt handler code
handler_size = 128  # read 128 bytes
hcode = get(f"/cpu/memory?addr={hint_addr}&len={handler_size}")
hdata = hcode.get("data") or hcode.get("memory")

# Simple 68k disassembly of common patterns
print(f"\nHInt handler at 0x{hint_addr:06X}:")
i = 0
while i < len(hdata) - 1:
    w = (hdata[i] << 8) | hdata[i+1]
    addr_hex = hint_addr + i
    
    # Show raw words
    if i + 3 < len(hdata):
        w2 = (hdata[i+2] << 8) | hdata[i+3]
        if i + 5 < len(hdata):
            w3 = (hdata[i+4] << 8) | hdata[i+5]
            print(f"  {addr_hex:06X}: {w:04X} {w2:04X} {w3:04X}")
        else:
            print(f"  {addr_hex:06X}: {w:04X} {w2:04X}")
    else:
        print(f"  {addr_hex:06X}: {w:04X}")
    
    # Check for RTE (0x4E73)
    if w == 0x4E73:
        print(f"  --> RTE at 0x{addr_hex:06X}")
        break
    
    # Check for writes to VDP (0x00C00000-0x00C00008)
    # MOVE.L #imm, addr.l = 23FC xxxx xxxx aaaa aaaa
    if w == 0x23FC and i + 9 < len(hdata):
        imm = (hdata[i+2] << 24) | (hdata[i+3] << 16) | (hdata[i+4] << 8) | hdata[i+5]
        dst = (hdata[i+6] << 24) | (hdata[i+7] << 16) | (hdata[i+8] << 8) | hdata[i+9]
        print(f"  --> MOVE.L #0x{imm:08X}, (0x{dst:08X}).l")
        if 0xC00000 <= dst <= 0xC00008:
            if dst == 0xC00000:
                print(f"      VDP DATA PORT write = 0x{imm:08X}")
            elif dst == 0xC00004:
                # Decode VDP command
                cd_low = (imm >> 14) & 0x03
                cd_high = (imm >> 4) & 0x0F
                code = cd_low | (cd_high << 2)
                addr_field = (imm & 0x3FFF) | ((imm >> 16) & 0x03) << 14
                print(f"      VDP CTRL PORT: code={code:#x} addr={addr_field:#06x}")
                if code == 0x01: print("        -> VRAM write")
                elif code == 0x03: print("        -> CRAM write")
                elif code == 0x05: print("        -> VSRAM write")
    
    # MOVE.W #imm, addr.l = 33FC xxxx aaaa aaaa
    if w == 0x33FC and i + 7 < len(hdata):
        imm = (hdata[i+2] << 8) | hdata[i+3]
        dst = (hdata[i+4] << 24) | (hdata[i+5] << 16) | (hdata[i+6] << 8) | hdata[i+7]
        print(f"  --> MOVE.W #0x{imm:04X}, (0x{dst:08X}).l")
        if 0xC00000 <= dst <= 0xC00008:
            if dst == 0xC00000 or dst == 0xC00002:
                print(f"      VDP DATA PORT write = 0x{imm:04X}")
            elif dst == 0xC00004 or dst == 0xC00006:
                print(f"      VDP CTRL PORT write = 0x{imm:04X}")
    
    i += 2

# Also check VInt handler
mem2 = get("/cpu/memory?addr=120&len=4")  # VInt vec at 0x78 = 120 dec
mdata2 = mem2.get("data") or mem2.get("memory")
vint_addr = (mdata2[0] << 24) | (mdata2[1] << 16) | (mdata2[2] << 8) | mdata2[3]
print(f"\n\nVInt vector: 0x{vint_addr:06X}")

# Read VInt handler code (first 256 bytes)
vcode = get(f"/cpu/memory?addr={vint_addr}&len=256")
vdata = vcode.get("data") or vcode.get("memory")
print(f"VInt handler at 0x{vint_addr:06X}:")

# Look for VDP writes in VInt handler
for i in range(0, len(vdata) - 9, 2):
    w = (vdata[i] << 8) | vdata[i+1]
    addr_hex = vint_addr + i
    
    if w == 0x4E73:
        print(f"  {addr_hex:06X}: RTE")
        break
    
    # Look for MOVE.L #imm, addr
    if w == 0x23FC and i + 9 < len(vdata):
        imm = (vdata[i+2] << 24) | (vdata[i+3] << 16) | (vdata[i+4] << 8) | vdata[i+5]
        dst = (vdata[i+6] << 24) | (vdata[i+7] << 16) | (vdata[i+8] << 8) | vdata[i+9]
        if 0xC00000 <= dst <= 0xC00008:
            print(f"  {addr_hex:06X}: MOVE.L #0x{imm:08X}, (0x{dst:08X}).l  ** VDP WRITE **")
            if dst == 0xC00004:
                cd_low = (imm >> 14) & 0x03
                cd_high = (imm >> 4) & 0x0F
                code = cd_low | (cd_high << 2)
                addr_field = (imm & 0x3FFF) | ((imm >> 16) & 0x03) << 14
                print(f"    -> code={code:#x} addr={addr_field:#06x}")
                if code == 0x03: print("       CRAM write!")
                elif code == 0x05: print("       VSRAM write!")

    if w == 0x33FC and i + 7 < len(vdata):
        imm = (vdata[i+2] << 8) | vdata[i+3]
        dst = (vdata[i+4] << 24) | (vdata[i+5] << 16) | (vdata[i+6] << 8) | vdata[i+7]
        if 0xC00000 <= dst <= 0xC00008:
            print(f"  {addr_hex:06X}: MOVE.W #0x{imm:04X}, (0x{dst:08X}).l  ** VDP WRITE **")

# Check hint counter register (R0A)
regs = get("/vdp/registers")
rdata = regs.get("registers") or regs.get("data")
print(f"\nR0A (HInt counter): {rdata[0x0A]}")
# Check if display is enabled
r01 = rdata[0x01]
display_en = (r01 & 0x40) != 0
hint_en = (rdata[0x00] & 0x10) != 0
vint_en = (r01 & 0x20) != 0
print(f"Display: {'ON' if display_en else 'OFF'}, HInt: {'ON' if hint_en else 'OFF'}, VInt: {'ON' if vint_en else 'OFF'}")
