"""Deep trace of M68K sound communication with Z80"""
import requests

BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/roms/sonic.gen"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})

# Run 300 frames
s.post(f"{BASE}/emulator/step", json={"frames": 300})

cpu_data = s.get(f"{BASE}/cpu/state").json()
cpu = cpu_data.get("cpu", {})
m68k = cpu.get("m68k", {})
z80 = cpu.get("z80", {})

print("=== CPU State at Frame 300 ===")
print(f"M68K PC=0x{m68k.get('pc',0):06X} SR=0x{m68k.get('sr',0):04X}")
print(f"Z80  PC=0x{z80.get('pc',0):04X}")

# Check M68K RAM - sound communication area
# In Sonic 1, sound slots are typically around $FFFFF0+
for region_name, addr in [
    ("M68K Sound slots $FFFFF0", 0xFFF0),
    ("M68K Sound slots $FFFFE0", 0xFFE0),
    ("M68K VBlank routine $FFF62A area", 0xF620),
    ("M68K Game mode $FFF600", 0xF600),
]:
    # Work RAM is $FF0000-$FFFFFF, mirror $FFF000-$FFFFFF
    full_addr = 0xFF0000 + addr
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": full_addr, "len": 32}).json()
    data = mem.get("data", [])
    print(f"\n{region_name} (0x{full_addr:06X}):")
    for i in range(0, min(len(data), 32), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        print(f"  +{i:02X}: {hex_str}")

# Z80 RAM areas of interest
print("\n=== Z80 RAM ===")
for region_name, addr in [
    ("Z80 command area $1FE0-$1FFF", 0xA01FE0),
    ("Z80 start of RAM $0000", 0xA00000),
    ("Z80 $1C00 area", 0xA01C00),
]:
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": addr, "len": 32}).json()
    data = mem.get("data", [])
    z80_addr = addr - 0xA00000
    print(f"\n{region_name}:")
    for i in range(0, min(len(data), 32), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        print(f"  Z80 0x{z80_addr+i:04X}: {hex_str}")

# APU state
apu = s.get(f"{BASE}/apu/state").json()
print(f"\n=== APU State ===")
for key in sorted(apu.keys()):
    val = apu[key]
    if isinstance(val, list) and len(val) > 20:
        print(f"  {key}: [{len(val)} items]")
    else:
        print(f"  {key}: {val}")

# VDP
vdp = s.get(f"{BASE}/vdp/registers").json()
print(f"\nVINT delivered: {vdp.get('vint_delivered', '?')}")
print(f"HINT delivered: {vdp.get('hint_delivered', '?')}")
print(f"VDP frame: {vdp.get('frame', '?')}")
regs = vdp.get("registers", [])
if len(regs) > 1:
    print(f"VDP Reg1: 0x{regs[1]:02X} (VINT_en={bool(regs[1]&0x20)})")
