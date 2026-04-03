"""Compare M68K-to-Z80 writes between KitaHe and Sonic, check communication"""
import requests
BASE = "http://localhost:8080/api/v1"
ROM_K = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"
ROM_S = "/Users/hossie/development/md_emulator/roms/sonic.gen"

s = requests.Session()

for rom_name, rom_path in [("KitaHe", ROM_K), ("Sonic", ROM_S)]:
    s.post(f"{BASE}/emulator/reset")
    s.post(f"{BASE}/emulator/load-rom-path", json={"path": rom_path})

    for frame in [10, 50, 100, 500]:
        if frame == 10:
            s.post(f"{BASE}/emulator/step", json={"frames": 10})
        else:
            prev = [10, 50, 100, 500]
            idx = prev.index(frame)
            delta = frame - prev[idx - 1]
            s.post(f"{BASE}/emulator/step", json={"frames": delta})

        apu = s.get(f"{BASE}/apu/state").json()
        m68k_writes = apu.get("z80_m68k_write_count", "?")
        bank_writes = apu.get("z80_bank_write_count", "?")
        bank = apu.get("z80_bank_68k_addr", "?")
        bank_max = apu.get("z80_bank_max_value", "?")
        banked_reads = len(apu.get("z80_banked_read_log", []))
        z80_pc = apu.get("z80_pc", "?")

        print(f"{rom_name:8s} F{frame:4d}: m68k_writes={m68k_writes:>6} "
              f"bank_writes={bank_writes:>4} bank={bank} "
              f"bank_max={bank_max} banked_reads={banked_reads} Z80={z80_pc}")

    # Check Z80 RAM $01FA
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA001F8, "len": 8}).json()
    data = mem.get("data", [])
    print(f"  Z80 $01F8-$01FF: {' '.join(f'{b:02X}' for b in data)}")

    # Check bank write log (last 10)
    log = apu.get("z80_bank_write_log", [])
    if log:
        print(f"  Last 5 bank writes: {log[-5:]}")
    print()
