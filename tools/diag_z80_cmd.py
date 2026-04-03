"""Check Z80 command byte and M68K progress over frames"""
import requests

BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/roms/sonic.gen"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})

for frame_target in [1, 5, 10, 30, 60, 100, 150, 200, 250, 300]:
    # Step by 1 frame at a time from wherever we are
    if frame_target == 1:
        s.post(f"{BASE}/emulator/step", json={"frames": 1})
    else:
        prev = [1, 5, 10, 30, 60, 100, 150, 200, 250, 300]
        idx = prev.index(frame_target)
        delta = frame_target - prev[idx - 1]
        s.post(f"{BASE}/emulator/step", json={"frames": delta})

    cpu_data = s.get(f"{BASE}/cpu/state").json()
    cpu = cpu_data.get("cpu", {})
    m68k_pc = cpu.get("m68k", {}).get("pc", 0)
    z80_pc = cpu.get("z80", {}).get("pc", 0)

    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA01FF0, "len": 16}).json()
    data = mem.get("data", [])
    cmd = data[15] if len(data) >= 16 else -1

    print(f"Frame {frame_target:4d}: M68K_PC=0x{m68k_pc:06X}  Z80_PC=0x{z80_pc:04X}  "
          f"z80[0x1FFF]=0x{cmd:02X}  "
          f"1FF0..FF={' '.join(f'{b:02X}' for b in data)}")

# Final APU state
apu = s.get(f"{BASE}/apu/state").json()
print(f"\nYM writes: {apu.get('ym_write_total', '?')}")
print(f"FM non-zero: {apu.get('debug_fm_nonzero', '?')}")
print(f"DAC non-zero: {apu.get('debug_dac_nonzero', '?')}")
print(f"Z80 M68K writes: {apu.get('z80_m68k_write_count', '?')}")
