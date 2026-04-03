"""Test sound with 北へPM ROM"""
import requests

BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
resp = s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})
print(f"Load ROM: {resp.json()}")

prev_ym = 0
for frame in range(0, 2001, 50):
    if frame == 0:
        continue
    s.post(f"{BASE}/emulator/step", json={"frames": 50})

    cpu_data = s.get(f"{BASE}/cpu/state").json()
    cpu = cpu_data.get("cpu", {})
    m68k = cpu.get("m68k", {})
    pc = m68k.get("pc", 0)
    sr = m68k.get("sr", 0)
    ipl = (sr >> 8) & 7
    z80_pc = cpu.get("z80", {}).get("pc", 0)

    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA01FFF, "len": 1}).json()
    cmd = mem.get("data", [0])[0]

    apu = s.get(f"{BASE}/apu/state").json()
    ym_total = apu.get("ym_write_total", 0)
    fm_nz = apu.get("debug_fm_nonzero", 0)
    dac_nz = apu.get("debug_dac_nonzero", 0)
    ym_delta = ym_total - prev_ym
    prev_ym = ym_total

    flag = ""
    if fm_nz > 0:
        flag += " FM!"
    if dac_nz > 0:
        flag += " DAC!"

    print(f"F{frame:5d}: PC=0x{pc:06X} IPL={ipl} Z80=0x{z80_pc:04X} "
          f"z80cmd=0x{cmd:02X} YM+={ym_delta:6d} "
          f"FM_nz={fm_nz} DAC_nz={dac_nz}{flag}")

print("\n=== Final ===")
apu = s.get(f"{BASE}/apu/state").json()
print(f"YM writes: {apu.get('ym_write_total')}")
print(f"FM non-zero: {apu.get('debug_fm_nonzero')}")
print(f"DAC non-zero: {apu.get('debug_dac_nonzero')}")
print(f"DAC data: {apu.get('dac_data')}")
print(f"Bank: 0x{apu.get('z80_bank_68k_addr', 0):08X}")
hist = apu.get("ym_histogram_port0_nonzero", [])
print(f"Port0 hist: {hist[:20]}")
