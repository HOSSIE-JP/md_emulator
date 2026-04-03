#!/usr/bin/env python3
"""Diagnose Timer A period, overflow rate, and Z80 visibility."""
import requests, json, sys, time

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Load ROM and run to frame where Timer A should be configured
api("post", "/emulator/load-rom-path", json={"path": "roms/ab2.smd"})
api("post", "/emulator/step", json={"frames": 50})

# Get APU state - check Timer A registers
apu = api("get", "/apu/state")
ym = apu.get("ym2612", apu)
regs = ym.get("regs_port0", [])

if len(regs) > 0x27:
    reg24 = regs[0x24]
    reg25 = regs[0x25]
    reg27 = regs[0x27]
    
    timer_a_msb = (reg24 << 2)
    timer_a_lsb = reg25 & 0x03
    timer_a_value = timer_a_msb | timer_a_lsb
    timer_a_period = 1024 - timer_a_value
    
    # FM clock divider = 144 master clocks per FM tick
    # Master clock ≈ 7,670,453 Hz (M68K clock, same for timer purposes)
    MASTER_HZ = 7_670_453
    FM_TICKS_PER_SEC = MASTER_HZ / 144.0
    timer_a_freq = FM_TICKS_PER_SEC / timer_a_period if timer_a_period > 0 else 0
    
    FRAME_CYCLES = 127_856  # M68K cycles per NTSC frame
    fm_ticks_per_frame = FRAME_CYCLES / 144.0
    overflows_per_frame = fm_ticks_per_frame / timer_a_period if timer_a_period > 0 else 0
    
    print(f"=== Timer A Configuration (frame 50) ===")
    print(f"  reg24 = 0x{reg24:02X} ({reg24})")
    print(f"  reg25 = 0x{reg25:02X} ({reg25})")
    print(f"  reg27 = 0x{reg27:02X} = {reg27:08b}b")
    print(f"  Timer A value (10-bit) = {timer_a_value} (0x{timer_a_value:03X})")
    print(f"  Timer A period = {timer_a_period} FM ticks")
    print(f"  Timer A period = {timer_a_period * 144} master clocks")
    print(f"  Timer A frequency = {timer_a_freq:.1f} Hz")
    print(f"  Overflows per frame = {overflows_per_frame:.1f}")
    print(f"  reg27 bits:")
    print(f"    bit 0 (Timer A run/load) = {(reg27 >> 0) & 1}")
    print(f"    bit 1 (Timer B run/load) = {(reg27 >> 1) & 1}")
    print(f"    bit 2 (Timer A enable/flag) = {(reg27 >> 2) & 1}")
    print(f"    bit 3 (Timer B enable/flag) = {(reg27 >> 3) & 1}")
    print(f"    bit 4 (Reset Timer A flag) = {(reg27 >> 4) & 1}")
    print(f"    bit 5 (Reset Timer B flag) = {(reg27 >> 5) & 1}")

    # Check current status
    status = ym.get("status", 0)
    print(f"\n  YM2612 status = 0x{status:02X}")
    print(f"    Timer A overflow = {(status & 0x01) != 0}")
    print(f"    Timer B overflow = {(status & 0x02) != 0}")
    
    # Check timer counter
    ta_counter = ym.get("timer_a_counter", "N/A")
    print(f"  timer_a_counter = {ta_counter}")
    
    # Check write histogram
    hist = ym.get("write_histogram", [])
    if hist:
        writes_24 = hist[0x24] if len(hist) > 0x24 else 0
        writes_25 = hist[0x25] if len(hist) > 0x25 else 0
        writes_27 = hist[0x27] if len(hist) > 0x27 else 0
        print(f"\n  Write counts: $24={writes_24}, $25={writes_25}, $27={writes_27}")
else:
    print("ERROR: regs_port0 not available or too short")
    print("Available keys:", list(ym.keys()) if isinstance(ym, dict) else "not a dict")

# Now step 1 frame at a time and track status changes
print(f"\n=== Stepping 10 frames, checking Timer A status ===")
for i in range(10):
    api("post", "/emulator/step", json={"frames": 1})
    apu2 = api("get", "/apu/state")
    ym2 = apu2.get("ym2612", apu2)
    st = ym2.get("status", 0)
    tc = ym2.get("timer_a_counter", "?")
    r27 = ym2.get("regs_port0", [0]*0x28)[0x27] if len(ym2.get("regs_port0", [])) > 0x27 else "?"
    hist2 = ym2.get("write_histogram", [])
    w27 = hist2[0x27] if len(hist2) > 0x27 else "?"
    
    # Z80 state
    cpu = api("get", "/cpu/state")
    z80 = cpu.get("cpu", {}).get("cpu", {}).get("z80", {})
    z80_pc = z80.get("pc", 0)
    z80_iff1 = z80.get("iff1", None)
    
    print(f"  Frame {51+i}: status=0x{st:02X} timer_counter={tc} reg27=0x{r27:02X} writes_27={w27} Z80_PC=0x{z80_pc:04X} IFF1={z80_iff1}")

# Check Z80 trace ring for Timer A read pattern
print(f"\n=== Z80 Trace Ring (last entries) ===")
cpu = api("get", "/cpu/state")
z80_trace = cpu.get("cpu", {}).get("z80_trace_ring", [])
for entry in z80_trace[-30:]:
    pc = entry.get("pc", 0)
    mnemonic = entry.get("mnemonic", "")
    operands = entry.get("operands", "")
    print(f"  ${pc:04X}: {mnemonic} {operands}")
