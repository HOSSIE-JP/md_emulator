#!/usr/bin/env python3
"""Detailed Sonic sound diagnostic."""
import requests

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

requests.post(f"{API}/emulator/load-rom-path", json={"path": "roms/sonic.gen"})
requests.post(f"{API}/emulator/reset")

# Run 60 frames, press START, run 200 more
for i in range(60):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
for i in range(10):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

for i in range(200):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Get full APU state
apu = requests.get(f"{API}/apu/state").json()

# Key diagnostics
print(f"=== FM Debug ===")
print(f"  debug_fm_ticks: {apu.get('debug_fm_ticks')}")
print(f"  debug_fm_nonzero: {apu.get('debug_fm_nonzero')}")
print(f"  debug_output_total: {apu.get('debug_output_total')}")
print(f"  debug_output_nonzero: {apu.get('debug_output_nonzero')}")
print(f"  debug_dac_samples: {apu.get('debug_dac_samples')}")
print(f"  debug_dac_nonzero: {apu.get('debug_dac_nonzero')}")
print(f"  last_fm_left: {apu.get('last_fm_left')}")
print(f"  last_fm_right: {apu.get('last_fm_right')}")
print(f"  ym_write_total: {apu.get('ym_write_total')}")
print(f"  audio_buffer_len: {apu.get('audio_buffer_len')}")
print(f"  dac_enabled: {apu.get('dac_enabled')}")
print(f"  dac_data: {apu.get('dac_data')}")

# YM histogram
hist = apu.get('ym_histogram_port0_nonzero', [])
print(f"\n=== YM Port 0 Histogram (non-zero) ===")
for entry in hist[:20]:
    print(f"  {entry}")

# Check key registers
print(f"\n=== Key FM Registers ===")
print(f"  Port0 B4-B6 (panning): {apu.get('regs_port0_b4_b6')}")
print(f"  Port1 B4-B6 (panning): {apu.get('regs_port1_b4_b6')}")
print(f"  Port0 algo: {apu.get('regs_port0_algo')}")
print(f"  Port0 TL: {apu.get('regs_port0_tl')}")
print(f"  Port0 freq: {apu.get('regs_port0_freq')}")
print(f"  Port0 key: {apu.get('regs_port0_key')}")
print(f"  reg27: {apu.get('reg27')}")

# First 10 writes
first_writes = apu.get('ym_write_log_first100', [])
print(f"\n=== First 10 YM writes ===")
for w in first_writes[:10]:
    print(f"  {w}")

# Recent non-DAC writes
recent = apu.get('ym_write_log_recent_non_dac', [])
print(f"\n=== Last 10 non-DAC YM writes ===")
for w in recent[:10]:
    print(f"  {w}")

# Channels
channels = apu.get('channels', [])
for i, ch in enumerate(channels):
    ops = ch.get('operators', [])
    has_activity = any(op.get('key_on') or op.get('attenuation', 1023) < 1023 
                       or op.get('env_phase') != 'Release' for op in ops)
    if has_activity or ch.get('fnum', 0) > 0:
        print(f"\n  CH{i+1}: fnum={ch.get('fnum')} block={ch.get('block')} algo={ch.get('algorithm')} fb={ch.get('feedback')}")
        print(f"    pan_L={ch.get('pan_left')} pan_R={ch.get('pan_right')}")
        for j, op in enumerate(ops):
            print(f"    OP{j+1}: att={op.get('attenuation')} phase={op.get('env_phase')} key={op.get('key_on')}")
