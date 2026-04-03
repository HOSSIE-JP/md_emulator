#!/usr/bin/env python3
"""Deep M68K trace to find why VINT stays disabled after START."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

# Load and reset
requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
requests.post(f"{API}/emulator/reset")

# Run to just before VINT disable (frame 120)
for i in range(120):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Capture M68K state at frame 120 (VINT still ON)
cpu = requests.get(f"{API}/cpu/state").json()
m68k = cpu["cpu"]["m68k"]
print(f"=== Frame 120 (VINT ON) ===")
print(f"PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")
d = m68k['d']
a = m68k['a']
print(f"D0-D3: {d[0]:08X} {d[1]:08X} {d[2]:08X} {d[3]:08X}")
print(f"A0-A3: {a[0]:08X} {a[1]:08X} {a[2]:08X} {a[3]:08X}")

# Check I/O control and data registers
io_regs = {}
for addr in [0xA10001, 0xA10003, 0xA10005, 0xA10009, 0xA1000B, 0xA1000D]:
    data = requests.get(f"{API}/cpu/memory", params={"addr": addr, "len": 1}).json().get("data", [0])
    io_regs[f"0x{addr:06X}"] = f"0x{data[0]:02X}"
print(f"I/O regs: {io_regs}")

# Check VDP register cache in RAM
vdp_cache = requests.get(f"{API}/cpu/memory", params={"addr": 0xFFA830, "len": 8}).json().get("data", [])
print(f"VDP cache [0xFFA830..]: {' '.join(f'{b:02X}' for b in vdp_cache)}")

# Step frames 120-140 one by one, tracing VINT changes
for frame in range(120, 140):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    apu = requests.get(f"{API}/apu/state").json()
    vint_en = apu.get("vdp_vint_enabled")
    if frame == 124 or frame == 125 or frame == 126 or not vint_en:
        cpu = requests.get(f"{API}/cpu/state").json()
        m68k = cpu["cpu"]["m68k"]
        print(f"\nFrame {frame}: VINT={'ON' if vint_en else 'OFF'} PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")
        d = m68k['d']
        a = m68k['a']
        print(f"D0=0x{d[0]:08X} D1=0x{d[1]:08X} A0=0x{a[0]:08X} A6=0x{a[6]:08X} A7=0x{a[7]:08X}")
        
        # Check the VDP reg cache
        vdp_cache = requests.get(f"{API}/cpu/memory", params={"addr": 0xFFA830, "len": 4}).json().get("data", [])
        print(f"VDP cache [FFA830..]: {' '.join(f'{b:02X}' for b in vdp_cache)}")
        
        if not vint_en:
            break

# Now press START and observe for 500 more frames
print("\n=== Pressing START ===")
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})

prev_pc = 0
for frame_offset in range(500):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
    
    if frame_offset % 50 == 0 or frame_offset < 5:
        cpu = requests.get(f"{API}/cpu/state").json()
        apu = requests.get(f"{API}/apu/state").json()
        m68k = cpu["cpu"]["m68k"]
        vint_en = apu.get("vdp_vint_enabled")
        
        # Check Z80 comm
        z80_comm = requests.get(f"{API}/cpu/memory", params={"addr": 0xA00100, "len": 4}).json().get("data", [])
        
        print(f"Frame {126+frame_offset}: VINT={'ON' if vint_en else 'OFF'} "
              f"PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X} "
              f"comm={' '.join(f'{b:02X}' for b in z80_comm)}")
        
        if vint_en:
            print("  >>> VINT RE-ENABLED!")
            break

# Release START
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Check final state
cpu = requests.get(f"{API}/cpu/state").json()
apu = requests.get(f"{API}/apu/state").json()
m68k = cpu["cpu"]["m68k"]
z80_comm = requests.get(f"{API}/cpu/memory", params={"addr": 0xA00100, "len": 16}).json().get("data", [])
print(f"\n=== Final ===")
print(f"M68K PC=0x{m68k['pc']:06X} SR=0x{m68k['sr']:04X}")
print(f"VINT={'ON' if apu.get('vdp_vint_enabled') else 'OFF'} delivered={apu.get('vint_delivered')}")
print(f"Z80 comm: {' '.join(f'{b:02X}' for b in z80_comm[:16])}")
print(f"Bank={apu.get('z80_bank_68k_addr')}")

# Check what M68K instructions are at the loop PC
# Read ROM at PC
m68k_pc = m68k['pc']
rom_data = requests.get(f"{API}/cpu/memory", params={"addr": m68k_pc, "len": 32}).json().get("data", [])
print(f"\nCode at PC 0x{m68k_pc:06X}: {' '.join(f'{b:02X}' for b in rom_data[:32])}")
