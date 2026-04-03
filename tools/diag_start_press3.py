"""Try pressing START to advance the game, then check sound"""
import requests
BASE = "http://localhost:8080/api/v1"
ROM_K = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM_K})

# Run 100 frames to let init complete
s.post(f"{BASE}/emulator/step", json={"frames": 100})

# Now press START button
# BTN_START = 0x0080 based on the bus code
s.post(f"{BASE}/input/controller", json={"player": 1, "buttons": 0x0080})
s.post(f"{BASE}/emulator/step", json={"frames": 10})
# Release
s.post(f"{BASE}/input/controller", json={"player": 1, "buttons": 0})
s.post(f"{BASE}/emulator/step", json={"frames": 50})

# Check M68K PC
cpu = s.get(f"{BASE}/cpu/state").json().get("cpu", {})
m68k = cpu.get("m68k", {})
print(f"After START: M68K PC=0x{m68k.get('pc',0):06X}")

# Try pressing START a few more times (some games need multiple presses)
for i in range(5):
    s.post(f"{BASE}/input/controller", json={"player": 1, "buttons": 0x0080})
    s.post(f"{BASE}/emulator/step", json={"frames": 3})
    s.post(f"{BASE}/input/controller", json={"player": 1, "buttons": 0})
    s.post(f"{BASE}/emulator/step", json={"frames": 60})

# Check state after button presses
apu = s.get(f"{BASE}/apu/state").json()
cpu = s.get(f"{BASE}/cpu/state").json().get("cpu", {})
m68k = cpu.get("m68k", {})
print(f"After 5x START: M68K PC=0x{m68k.get('pc',0):06X}")
print(f"Bank: {apu.get('z80_bank_68k_addr')}")
print(f"Bank writes: {apu.get('z80_bank_write_count')}")
print(f"M68K writes: {apu.get('z80_m68k_write_count')}")
print(f"FM nonzero: {apu.get('debug_fm_nonzero')}")
print(f"DAC nonzero: {apu.get('debug_dac_nonzero')}")

# Read Z80 RAM $01FA
mem = s.get(f"{BASE}/cpu/memory",
            params={"addr": 0xA001F8, "len": 8}).json()
data = mem.get("data", [])
print(f"Z80 $01F8-$01FF: {' '.join(f'{b:02X}' for b in data)}")

# Continue running
s.post(f"{BASE}/emulator/step", json={"frames": 500})
apu2 = s.get(f"{BASE}/apu/state").json()
cpu2 = s.get(f"{BASE}/cpu/state").json().get("cpu", {})
m68k2 = cpu2.get("m68k", {})
print(f"\nAfter 500 more frames: M68K PC=0x{m68k2.get('pc',0):06X}")
print(f"Bank: {apu2.get('z80_bank_68k_addr')}")
print(f"M68K writes: {apu2.get('z80_m68k_write_count')}")
print(f"FM nonzero: {apu2.get('debug_fm_nonzero')}")
print(f"DAC nonzero: {apu2.get('debug_dac_nonzero')}")

mem2 = s.get(f"{BASE}/cpu/memory",
             params={"addr": 0xA001F8, "len": 8}).json()
data2 = mem2.get("data", [])
print(f"Z80 $01F8-$01FF: {' '.join(f'{b:02X}' for b in data2)}")

# Banked read log
log = apu2.get("z80_banked_read_log", [])
print(f"Banked reads: {len(log)}")
if log:
    print(f"First 5: {log[:5]}")
