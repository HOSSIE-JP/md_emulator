"""Diagnose VBlank interrupt delivery and sound command issues"""
import requests

BASE = "http://localhost:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/roms/sonic.gen"

s = requests.Session()
s.post(f"{BASE}/emulator/reset")
s.post(f"{BASE}/emulator/load-rom-path", json={"path": ROM})

for frame_target in [10, 30, 60, 100, 200, 300, 400, 500, 600]:
    if frame_target == 10:
        s.post(f"{BASE}/emulator/step", json={"frames": 10})
    else:
        prev_targets = [10, 30, 60, 100, 200, 300, 400, 500, 600]
        idx = prev_targets.index(frame_target)
        delta = frame_target - prev_targets[idx - 1]
        s.post(f"{BASE}/emulator/step", json={"frames": delta})

    cpu_data = s.get(f"{BASE}/cpu/state").json()
    cpu = cpu_data.get("cpu", {})
    m68k = cpu.get("m68k", {})
    m68k_pc = m68k.get("pc", 0)
    m68k_sr = m68k.get("sr", 0)
    z80_pc = cpu.get("z80", {}).get("pc", 0)

    vdp = s.get(f"{BASE}/vdp/registers").json()
    regs = vdp.get("registers", [])
    reg1 = regs[1] if len(regs) > 1 else 0
    vint_en = bool(reg1 & 0x20)
    vint_del = vdp.get("vint_delivered", "?")
    hint_del = vdp.get("hint_delivered", "?")

    # Z80 command byte
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA01FFF, "len": 1}).json()
    data = mem.get("data", [])
    cmd = data[0] if data else -1

    # VBlank sync variable
    mem2 = s.get(f"{BASE}/cpu/memory",
                 params={"addr": 0xFFF62A, "len": 1}).json()
    sync = mem2.get("data", [0])[0]

    ipl = (m68k_sr >> 8) & 7
    print(f"F{frame_target:4d}: PC=0x{m68k_pc:06X} SR=0x{m68k_sr:04X}(IPL={ipl}) "
          f"Z80=0x{z80_pc:04X} VINT_en={vint_en} VINT_del={vint_del} "
          f"z80cmd=0x{cmd:02X} sync=0x{sync:02X}")

# Final APU
apu = s.get(f"{BASE}/apu/state").json()
print(f"\nYM writes: {apu.get('ym_write_total', '?')}")
print(f"FM non-zero: {apu.get('debug_fm_nonzero', '?')}")
print(f"DAC non-zero: {apu.get('debug_dac_nonzero', '?')}")
