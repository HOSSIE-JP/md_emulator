#!/usr/bin/env python3
"""Diagnose Timer A period from write log and histogram."""
import requests, json, sys

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Load ROM and run to steady state
api("post", "/emulator/load-rom-path", json={"path": "roms/s_a_t_d.smd"})
api("post", "/emulator/step", json={"frames": 50})

apu = api("get", "/apu/state")

# Check reg27 directly
reg27 = apu.get("reg27", "N/A")
status = apu.get("status", "N/A")
print(f"reg27 = 0x{reg27:02X} ({reg27:08b}b)" if isinstance(reg27, int) else f"reg27 = {reg27}")
print(f"status = 0x{status:02X}" if isinstance(status, int) else f"status = {status}")

# Check write log for $24/$25 writes  
write_log = apu.get("ym_write_log_first100", [])
print(f"\n=== YM Write Log (first 100 entries) ===")
timer_writes = []
for entry in write_log:
    port, addr, data = entry
    if addr in [0x24, 0x25, 0x26, 0x27]:
        timer_writes.append((port, addr, data))
        print(f"  Port {port} Reg 0x{addr:02X} = 0x{data:02X} ({data})")

# Extract Timer A value
reg24_val = None
reg25_val = None
for port, addr, data in timer_writes:
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
    
    print(f"\n=== Timer A Period Calculation ===")
    print(f"  reg24 = 0x{reg24_val:02X} ({reg24_val})")
    print(f"  reg25 = 0x{reg25_val:02X} ({reg25_val})")
    print(f"  Timer A 10-bit value = {timer_a_value} (0x{timer_a_value:03X})")
    print(f"  Timer A period = {timer_a_period} FM ticks")
    print(f"  Timer A period in master clocks = {timer_a_period * 144}")
    print(f"  Timer A period in M68K cycles = {timer_a_period * 144 / 7:.1f}")
    print(f"  Timer A period in Z80 cycles = {timer_a_period * 144 / 15:.1f}")
    print(f"  Timer A overflow frequency = {timer_a_freq:.1f} Hz")
    print(f"  Expected overflows per frame = {overflows_per_frame:.2f}")
    print(f"  Duration per overflow = {1000.0/timer_a_freq:.3f} ms" if timer_a_freq > 0 else "")
else:
    print(f"\nTimer A registers not found in write log!")
    print(f"  reg24 = {reg24_val}, reg25 = {reg25_val}")

# Check histogram for write counts
hist_p0 = apu.get("ym_histogram_port0_nonzero", [])
print(f"\n=== Non-zero Port 0 histogram entries (relevant) ===")
for entry in hist_p0:
    addr = entry.get("register", entry.get("reg", 0))
    count = entry.get("count", 0)
    if addr in [0x24, 0x25, 0x26, 0x27]:
        print(f"  Reg 0x{addr:02X}: {count} writes")

# Check non-DAC recent writes
recent = apu.get("ym_write_log_recent_non_dac", [])
print(f"\n=== Recent non-DAC writes (last entries, looking for $24/$25) ===")
for entry in recent[-20:]:
    port, addr, data = entry
    if addr in [0x24, 0x25, 0x26, 0x27]:
        print(f"  Port {port} Reg 0x{addr:02X} = 0x{data:02X}")

# Z80 state
print(f"\n=== Z80 State ===")
print(f"  Z80 PC = 0x{apu.get('z80_pc', 0):04X}")
print(f"  Z80 IFF1 = {apu.get('z80_iff1')}")
print(f"  Z80 INT pending = {apu.get('z80_int_pending')}")
print(f"  Z80 INT count = {apu.get('z80_int_count')}")
print(f"  Z80 total cycles = {apu.get('z80_total_cycles')}")

# Z80 trace ring
trace = apu.get("z80_trace_ring", [])
print(f"\n=== Z80 Trace Ring (last 20 entries) ===")
for entry in trace[-20:]:
    pc = entry.get("pc", 0)
    mn = entry.get("mnemonic", "")
    ops = entry.get("operands", "")
    cyc = entry.get("cycles", 0)
    print(f"  ${pc:04X}: {mn:<8s} {ops:<20s} [{cyc}T]")

# Step more and check again
print(f"\n=== After 200 more frames ===")
api("post", "/emulator/step", json={"frames": 200})
apu2 = api("get", "/apu/state")
status2 = apu2.get("status", 0)
reg27_2 = apu2.get("reg27", 0)
hist_2 = apu2.get("ym_histogram_port0_nonzero", [])
r27_count = 0
for e in hist_2:
    if e.get("register", e.get("reg", 0)) == 0x27:
        r27_count = e.get("count", 0)

print(f"  status = 0x{status2:02X}")
print(f"  reg27 = 0x{reg27_2:02X}")
print(f"  reg27 total writes = {r27_count}")
print(f"  Z80 PC = 0x{apu2.get('z80_pc', 0):04X}")
print(f"  Z80 INT count = {apu2.get('z80_int_count')}")
print(f"  Z80 total cycles = {apu2.get('z80_total_cycles')}")
