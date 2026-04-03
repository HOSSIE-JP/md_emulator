"""Quick check of bank register write values"""
import requests
BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})
s.post(f"{BASE}/emulator/step", json={"frames": 50})

apu = s.get(f"{BASE}/apu/state").json()
print(f"Bank: {apu.get('z80_bank_68k_addr')}")
print(f"Writes: {apu.get('z80_bank_write_count')}")
print(f"Max: {apu.get('z80_bank_max_value')}")
log = apu.get("z80_bank_write_log", [])
print(f"\nBank write log ({len(log)} entries):")
for entry in log:
    print(f"  {entry}")
