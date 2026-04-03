"""Test SRAM implementation with 北へPM"""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def read_mem(addr, length):
    r = api("GET", f"/cpu/memory?addr={addr}&len={length}")
    return r.get("data") or r.get("memory", [])

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Load ROM
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("ROM loaded")

# Check SRAM area: read from $200001 (odd, should be SRAM = 0xFF uninitialized)
sram_data = read_mem(0x200001, 16)
print(f"SRAM $200001 (16 bytes): {[f'0x{b:02X}' for b in sram_data]}")

# Read from $200000 (even, should be ROM data, not SRAM)
rom_data = read_mem(0x200000, 16)
print(f"ROM  $200000 (16 bytes): {[f'0x{b:02X}' for b in rom_data]}")

# Write to SRAM: write a pattern then read back  
# We can't directly write via API, but let's step and see if game writes

# Step to frame 50 (driver loading)
api("POST", "/emulator/step", {"frames": 50})
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"\nF50: PC=0x{m68k['pc']:06X}")

# Check Z80 state
z80 = cpu["cpu"]["z80"]
print(f"F50: Z80 PC=0x{z80['pc']:04X}")

# Check SRAM for any writes
sram_data = read_mem(0x200001, 32)
has_sram_writes = any(b != 0xFF for b in sram_data)
print(f"SRAM has writes at F50: {has_sram_writes}")
print(f"SRAM $200001 (32 bytes): {[f'0x{b:02X}' for b in sram_data]}")

# Step to frame 200
api("POST", "/emulator/step", {"frames": 150})
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"\nF200: PC=0x{m68k['pc']:06X}")

# Check SRAM
sram_data = read_mem(0x200001, 32)
has_sram_writes = any(b != 0xFF for b in sram_data)
print(f"SRAM has writes at F200: {has_sram_writes}")
if has_sram_writes:
    print(f"SRAM $200001: {[f'0x{b:02X}' for b in sram_data]}")

# Check Z80 bank register and communication
apu = api("GET", "/apu/state")
bank = apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", 0))
print(f"Z80 bank: 0x{bank:06X}")

# Check VDP
vdp = api("GET", "/vdp/registers")
regs = vdp.get("registers", vdp)
if isinstance(regs, list):
    reg1 = regs[1] if len(regs) > 1 else 0
else:
    reg1 = regs.get("1", 0)
vint = (reg1 & 0x20) != 0
print(f"VDP Reg1=0x{reg1:02X} VINT={'ON' if vint else 'OFF'}")

# Step to frame 500
api("POST", "/emulator/step", {"frames": 300})

# Check Z80 bank and APU state
apu = api("GET", "/apu/state")
bank = apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", 0))
bank_writes = apu.get("z80_bank_write_count", 0)
bank_max = apu.get("z80_bank_max_value", 0)
print(f"\nF500: Z80 bank=0x{bank:06X}, writes={bank_writes}, max=0x{bank_max:06X}")

cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"F500: PC=0x{m68k['pc']:06X}")

# Step to frame 1000
api("POST", "/emulator/step", {"frames": 500})
apu = api("GET", "/apu/state")
bank = apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", 0))
bank_writes = apu.get("z80_bank_write_count", 0)
bank_max = apu.get("z80_bank_max_value", 0)
print(f"\nF1000: Z80 bank=0x{bank:06X}, writes={bank_writes}, max=0x{bank_max:06X}")

# Check if YM2612 has any non-timer writes
ym_state = apu.get("ym2612", {})
if ym_state:
    print(f"YM state available: {list(ym_state.keys())[:10]}")

# Check if game now progresses (different PC?)
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
print(f"F1000: PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")

# Check SRAM at F1000
sram_data = read_mem(0x200001, 64)
has_sram_writes = any(b != 0xFF for b in sram_data)
print(f"SRAM has writes at F1000: {has_sram_writes}")
if has_sram_writes:
    # Show first 20 non-FF values
    changed = [(i, b) for i, b in enumerate(sram_data) if b != 0xFF]
    print(f"  Changed positions: {changed[:20]}")

# Step to 1500 with START
api("POST", "/input/controller", {"player": 1, "buttons": 0x0080})
api("POST", "/emulator/step", {"frames": 50})
api("POST", "/input/controller", {"player": 1, "buttons": 0})
api("POST", "/emulator/step", {"frames": 450})

cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
apu = api("GET", "/apu/state")
bank = apu.get("z80_bank_68k_addr", apu.get("bank_68k_addr", 0))
bank_writes = apu.get("z80_bank_write_count", 0)
bank_max = apu.get("z80_bank_max_value", 0)
z80_writes = apu.get("z80_m68k_write_count", 0)
print(f"\nF1500 (after START): PC=0x{m68k['pc']:06X}, bank=0x{bank:06X}, "
      f"bank_writes={bank_writes}, bank_max=0x{bank_max:06X}, z80_writes={z80_writes}")

# Check Z80 RAM communication area
z80_comm = read_mem(0xA00100, 32)
print(f"Z80 $100-$11F: {[f'{b:02X}' for b in z80_comm]}")

# Check more SRAM
sram_scan = read_mem(0x200000, 128)
sram_odd = [sram_scan[i] for i in range(1, 128, 2)]  # odd bytes = SRAM
sram_has_data = any(b != 0xFF for b in sram_odd)
print(f"SRAM odd bytes (64 values): has data = {sram_has_data}")
if sram_has_data:
    changed_odd = [(i, b) for i, b in enumerate(sram_odd) if b != 0xFF]
    print(f"  Changed: {changed_odd[:20]}")
