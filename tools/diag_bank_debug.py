"""Check Z80 bank register debug counters for 北へPM"""
import requests
BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})

for frame in [10, 50, 100, 200, 500, 1000]:
    if frame == 10:
        s.post(f"{BASE}/emulator/step", json={"frames": 10})
    else:
        prev = [10, 50, 100, 200, 500, 1000]
        idx = prev.index(frame)
        delta = frame - prev[idx - 1]
        s.post(f"{BASE}/emulator/step", json={"frames": delta})

    apu = s.get(f"{BASE}/apu/state").json()
    bank = apu.get("z80_bank_68k_addr", "?")
    writes = apu.get("z80_bank_write_count", "?")
    max_val = apu.get("z80_bank_max_value", "?")
    z80_pc = apu.get("z80_pc", "?")
    print(f"F{frame:5d}: bank={bank} writes={writes} max={max_val} Z80_PC={z80_pc}")

# Also test Sonic for comparison
print("\n--- Sonic comparison ---")
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path",
       json={"path": "/Users/hossie/development/md_emulator/roms/sonic.gen"})
s.post(f"{BASE}/emulator/step", json={"frames": 500})
apu = s.get(f"{BASE}/apu/state").json()
print(f"Sonic F500: bank={apu.get('z80_bank_68k_addr')} "
      f"writes={apu.get('z80_bank_write_count')} "
      f"max={apu.get('z80_bank_max_value')}")
