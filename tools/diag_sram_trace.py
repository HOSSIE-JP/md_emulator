"""Check ROM header SRAM flags and trace M68K execution after VBlank"""
import urllib.request, json, struct

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def read_mem(addr, length):
    r = api("GET", f"/cpu/memory?addr={addr}&len={length}")
    return r.get("data") or r.get("memory", [])

# === 1. Check ROM header for SRAM ===
print("=== ROM Header SRAM Info ===")
ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"
with open(ROM_PATH, "rb") as f:
    rom = f.read()

# SRAM header at $1B0
sram_marker = rom[0x1B0:0x1B2]
sram_type = rom[0x1B2]
sram_flags = rom[0x1B3]
sram_start = struct.unpack(">I", rom[0x1B4:0x1B8])[0]
sram_end = struct.unpack(">I", rom[0x1B8:0x1BC])[0]
print(f"  SRAM marker: {sram_marker} ({sram_marker.hex()})")
print(f"  SRAM type: 0x{sram_type:02X}")
print(f"  SRAM flags: 0x{sram_flags:02X}")
print(f"  SRAM start: 0x{sram_start:08X}")
print(f"  SRAM end:   0x{sram_end:08X}")
if sram_marker == b'RA':
    print("  >>> SRAM IS DECLARED in ROM header! <<<")
    sram_size = sram_end - sram_start + 1
    print(f"  SRAM size: {sram_size} bytes")
    even_only = (sram_flags & 0x40) != 0
    odd_only = (sram_flags & 0x20) != 0
    print(f"  Even-only: {even_only}, Odd-only: {odd_only}")
else:
    print("  No SRAM declared in header")

# Modem info at $1BC
modem = rom[0x1BC:0x1C8]
print(f"\n  Modem info: {modem}")

# ROM start/end from header
rom_start_h = struct.unpack(">I", rom[0x1A0:0x1A4])[0]
rom_end_h = struct.unpack(">I", rom[0x1A4:0x1A8])[0]
print(f"\n  ROM start (header): 0x{rom_start_h:08X}")
print(f"  ROM end (header):   0x{rom_end_h:08X}")
print(f"  ROM actual size:    0x{len(rom):08X} ({len(rom)} bytes)")

# === 2. Fresh load and trace M68K ===
print("\n=== Fresh ROM Load and M68K Trace ===")
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 1})

# Get initial CPU state
cpu = api("GET", "/cpu/state")
m68k = cpu.get("cpu", cpu).get("m68k", {})
print(f"Frame 1: PC=0x{m68k['pc']:06X}, SR=0x{m68k['sr']:04X}")

# Step to various points and check SRAM access + V-int status
checkpoints = [10, 50, 100, 150, 200, 300, 500, 800, 1000]
for target in checkpoints:
    api("POST", "/emulator/step", {"frames": target - (10 if target > 10 else 1)})
    cpu = api("GET", "/cpu/state")
    m68k = cpu.get("cpu", cpu).get("m68k", {})
    vdp = api("GET", "/vdp/registers")
    regs = vdp.get("registers", vdp)
    reg1 = regs.get("1", regs.get(1, 0))
    vint_en = (reg1 & 0x20) != 0
    
    # Check if game is accessing SRAM region
    pc = m68k['pc']
    
    # Read Z80 communication area 
    z80_comm = read_mem(0xA00100, 32)
    z80_1fa = read_mem(0xA001FA, 2)
    
    print(f"F{target:4d}: PC=0x{pc:06X} SR=0x{m68k['sr']:04X} VINT={'ON ' if vint_en else 'OFF'} "
          f"Z80[$1FA]={z80_1fa}")

# === 3. Check what M68K does around frame 100-150 (when VINT toggles) ===
print("\n=== Frame-by-frame around VINT disable ===")
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 100})
for i in range(100, 160):
    api("POST", "/emulator/step", {"frames": 1})
    cpu = api("GET", "/cpu/state")
    m68k = cpu.get("cpu", cpu).get("m68k", {})
    vdp = api("GET", "/vdp/registers")
    regs = vdp.get("registers", vdp)
    reg1 = regs.get("1", regs.get(1, 0))
    vint_en = (reg1 & 0x20) != 0
    pc = m68k['pc']
    d0 = m68k['d'][0]
    # Check SR for interrupt mask
    sr = m68k['sr']
    int_mask = (sr >> 8) & 7
    print(f"F{i+1:3d}: PC=${pc:06X} SR=${sr:04X} I={int_mask} VINT={'ON ' if vint_en else 'OFF'} D0=${d0:08X}")
