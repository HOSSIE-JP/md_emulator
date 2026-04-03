#!/usr/bin/env python3
"""Get Timer A period and verify timer operation."""
import requests

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Load ROM and run to steady state
api("post", "/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
api("post", "/emulator/step", json={"frames": 200})

apu = api("get", "/apu/state")
print(f"reg27 = 0x{apu.get('reg27', 0):02X}")
print(f"status = 0x{apu.get('status', 0):02X}")
print(f"Z80 PC = 0x{apu.get('z80_pc', 0):04X}")
print(f"Z80 cycles = {apu.get('z80_total_cycles')}")

# Get Timer A values from write log
wlog = apu.get("ym_write_log_first100", [])
reg24_val = None
reg25_val = None
print("\n=== Timer-related writes in first 100 entries ===")
for entry in wlog:
    if isinstance(entry, list) and len(entry) == 3:
        port, addr, data = entry
        if addr in [0x24, 0x25, 0x26, 0x27]:
            print(f"  Port {port} Reg 0x{addr:02X} = 0x{data:02X} ({data})")
            if addr == 0x24 and port == 0:
                reg24_val = data
            if addr == 0x25 and port == 0:
                reg25_val = data

if reg24_val is not None and reg25_val is not None:
    timer_a_value = (reg24_val << 2) | (reg25_val & 0x03)
    timer_a_period = 1024 - timer_a_value
    MASTER_HZ = 7_670_453
    FM_TICKS_PER_SEC = MASTER_HZ / 144.0
    timer_a_freq = FM_TICKS_PER_SEC / timer_a_period if timer_a_period > 0 else 0
    FRAME_CYCLES = 127_856
    fm_ticks_per_frame = FRAME_CYCLES / 144.0
    overflows_per_frame = fm_ticks_per_frame / timer_a_period if timer_a_period > 0 else 0

    print(f"\n=== Timer A Period ===")
    print(f"  reg24 = 0x{reg24_val:02X} ({reg24_val})")
    print(f"  reg25 = 0x{reg25_val:02X} ({reg25_val})")
    print(f"  Timer A 10-bit = {timer_a_value} (0x{timer_a_value:03X})")
    print(f"  Period = {timer_a_period} FM ticks")
    print(f"  Period = {timer_a_period * 144} master clocks = {timer_a_period * 144 / 7:.0f} M68K cyc")
    print(f"  Frequency = {timer_a_freq:.1f} Hz")
    print(f"  Expected overflows/frame = {overflows_per_frame:.2f}")
else:
    print(f"\n  Timer A registers NOT in first 100 writes!")
    print(f"  Checking histogram for write counts...")

# Check histogram (may be list of strings like "reg:count")
hist = apu.get("ym_histogram_port0_nonzero", [])
print(f"\n=== YM Histogram Port 0 (non-zero, timer-related) ===")
for entry in hist:
    if isinstance(entry, dict):
        reg = entry.get("register", entry.get("reg", -1))
        count = entry.get("count", 0)
        if reg in [0x24, 0x25, 0x26, 0x27]:
            print(f"  Reg 0x{reg:02X}: {count} writes")
    elif isinstance(entry, str):
        # Could be "0x27: 32280" format
        print(f"  {entry}")
    elif isinstance(entry, list) and len(entry) == 2:
        reg, count = entry
        if reg in [0x24, 0x25, 0x26, 0x27]:
            print(f"  Reg 0x{reg:02X}: {count} writes")

# Also search recent non-DAC writes
recent = apu.get("ym_write_log_recent_non_dac", [])
print(f"\n=== Recent non-DAC writes (timer regs) ===")
for entry in recent:
    if isinstance(entry, list) and len(entry) == 3:
        port, addr, data = entry
        if addr in [0x24, 0x25, 0x26, 0x27]:
            print(f"  Port {port} Reg 0x{addr:02X} = 0x{data:02X}")

# If we couldn't find $24/$25 in logs, try reading them from Z80 RAM
# The Z80 driver might have the timer config in its memory
print(f"\n=== Z80 RAM Timer-related areas ===")
# Read Z80 RAM $0000-$001F (some drivers store config here)
mem = api("get", "/cpu/memory", params={"addr": 0xA00000, "len": 32})
data = mem.get("data", [])
print(f"  Z80 $0000-$001F: {' '.join(f'{b:02X}' for b in data)}")

# Read Z80 RAM around IX pointer ($0015)
mem2 = api("get", "/cpu/memory", params={"addr": 0xA00010, "len": 32})
data2 = mem2.get("data", [])
print(f"  Z80 $0010-$002F: {' '.join(f'{b:02X}' for b in data2)}")

# Read area where Timer A config might be stored (around $01F0)
mem3 = api("get", "/cpu/memory", params={"addr": 0xA001F0, "len": 16})
data3 = mem3.get("data", [])
print(f"  Z80 $01F0-$01FF: {' '.join(f'{b:02X}' for b in data3)}")
