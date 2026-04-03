#!/usr/bin/env python3
"""Verify Timer A overflow vs clear counts, and check Z80 command processing."""
import requests, time

BASE = "http://localhost:8080/api/v1"
time.sleep(2)

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

api("post", "/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})

# Check at several frame counts
for target_frame in [50, 100, 200]:
    if target_frame == 50:
        api("post", "/emulator/step", json={"frames": 50})
    else:
        api("post", "/emulator/step", json={"frames": 50})

    apu = api("get", "/apu/state")
    frame = apu.get("vdp_frame", "?")
    overflows = apu.get("timer_a_overflow_count", 0)
    clears = apu.get("timer_a_clear_count", 0)
    status = apu.get("status", 0)
    z80_pc = apu.get("z80_pc", 0)
    z80_cycles = apu.get("z80_total_cycles", 0)
    period = apu.get("timer_a_period", 0)
    counter = apu.get("timer_a_counter", 0)

    print(f"=== Frame {frame} ===")
    print(f"  Timer A: period={period} counter={counter}")
    print(f"  Overflows: {overflows}")
    print(f"  Clears: {clears}")
    print(f"  Ratio (overflows/clears): {overflows/clears:.2f}" if clears > 0 else "  No clears")
    print(f"  Status: 0x{status:02X}")
    print(f"  Z80 PC: 0x{z80_pc:04X}")
    print(f"  Z80 cycles: {z80_cycles}")
    if frame and isinstance(frame, (int, float)) and frame > 0:
        print(f"  Overflows/frame: {overflows/frame:.1f}")
        print(f"  Clears/frame: {clears/frame:.1f}")

# Check Z80 RAM at $0161 (command byte)
mem = api("get", "/cpu/memory", params={"addr": 0xA00160, "len": 8})
data = mem.get("data", [])
print(f"\n=== Z80 RAM $0160-$0167 ===")
print(f"  {' '.join(f'{b:02X}' for b in data)}")
print(f"  $0161 = 0x{data[1]:02X} (command byte)" if len(data) > 1 else "")

# Check M68K variable at $FF019C
mem2 = api("get", "/cpu/memory", params={"addr": 0xFF019C, "len": 2})
data2 = mem2.get("data", [])
print(f"\n  $FF019C = 0x{(data2[0]<<8)|data2[1]:04X}" if len(data2) >= 2 else "  Can't read $FF019C")

# Z80 trace to see what it's doing
print(f"\n=== Z80 Trace Ring (last 30) ===")
# Get trace from cpu state
cpu = api("get", "/cpu/state")
z80_trace = cpu.get("cpu", {}).get("z80_trace_ring", [])
if not z80_trace:
    z80_trace = apu.get("z80_trace_ring", [])
for entry in z80_trace[-30:]:
    pc = entry.get("pc", 0)
    mn = entry.get("mnemonic", "")
    ops = entry.get("operands", "")
    cyc = entry.get("cycles", 0)
    print(f"  ${pc:04X}: {mn:<8s} {ops:<20s} [{cyc}T]")
