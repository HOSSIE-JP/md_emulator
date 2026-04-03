#!/usr/bin/env python3
"""Run game for extended period, inject START, monitor progression."""
import requests, time

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

def get_state():
    apu = api("get", "/apu/state")
    cpu = api("get", "/cpu/state")
    m68k = cpu.get("cpu", {}).get("m68k", {})
    return {
        "pc": m68k.get("pc", 0),
        "sr": m68k.get("sr", 0),
        "frame": apu.get("vdp_frame", 0),
        "vint": apu.get("vdp_vint_enabled", False),
        "z80_pc": apu.get("z80_pc", 0),
        "status": apu.get("status", 0),
        "reg27": apu.get("reg27", 0),
    }

# Load ROM
api("post", "/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})

# Run and monitor
prev_pc = 0
for i in range(20):
    target = (i + 1) * 50
    api("post", "/emulator/step", json={"frames": 50})

    # Try pressing START at frame 100 and 200
    if target in [100, 200]:
        api("post", "/input/controller", json={"player": 1, "buttons": 0x0080})
        api("post", "/emulator/step", json={"frames": 2})
        api("post", "/input/controller", json={"player": 1, "buttons": 0x0000})
        api("post", "/emulator/step", json={"frames": 3})

    s = get_state()
    changed = "(changed!)" if s["pc"] != prev_pc else ""
    print(f"Frame {target:4d}: PC=0x{s['pc']:06X} VINT={'ON ' if s['vint'] else 'OFF'} Z80=0x{s['z80_pc']:04X} reg27=0x{s['reg27']:02X} status=0x{s['status']:02X} {changed}")
    prev_pc = s["pc"]

# Final state
print("\n=== Final state at frame 1000 ===")
s = get_state()
print(f"  PC=0x{s['pc']:06X}")
print(f"  VINT={'ON' if s['vint'] else 'OFF'}")

# Check if any sound has been produced
apu = api("get", "/apu/state")
print(f"  Audio buffer: {apu.get('audio_buffer_len')} samples")
print(f"  FM nonzero: {apu.get('debug_fm_nonzero')}")
print(f"  DAC nonzero: {apu.get('debug_dac_nonzero')}")
print(f"  Output nonzero: {apu.get('debug_output_nonzero')}")
print(f"  Timer A overflows: {apu.get('timer_a_overflow_count')}")
print(f"  Timer A clears: {apu.get('timer_a_clear_count')}")
print(f"  VINT delivered: {apu.get('vint_delivered')}")
