#!/usr/bin/env python3
"""XGM2 PCM multi-channel diagnostic: load ROM, run frames, check APU state."""
import requests
import json
import sys
import os

BASE = os.environ.get("MD_API_BASE", "http://localhost:8080/api/v1")

def load_rom(path):
    r = requests.post(f"{BASE}/emulator/load-rom-path", json={"path": path}, timeout=10)
    r.raise_for_status()
    print(f"ROM loaded: {path}")

def step_frames(n):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n}, timeout=300)
    r.raise_for_status()
    return r.json()

def get_apu():
    r = requests.get(f"{BASE}/apu/state", timeout=10)
    r.raise_for_status()
    return r.json()

def print_apu_summary(apu, label=""):
    print(f"\n=== APU State {label} ===")
    print(f"  Status reg:        0x{apu.get('status', 0):02X}")
    print(f"  Reg 0x27:          0x{apu.get('reg27', 0):02X}")
    print(f"  DAC enabled:       {apu.get('dac_enabled')}")
    print(f"  DAC data:          {apu.get('dac_data')}")
    print(f"  Audio buffer len:  {apu.get('audio_buffer_len')}")
    print(f"  YM write total:    {apu.get('ym_write_total')}")
    print(f"  FM ticks:          {apu.get('debug_fm_ticks')}")
    print(f"  DAC samples:       {apu.get('debug_dac_samples')}")
    print(f"  DAC nonzero:       {apu.get('debug_dac_nonzero')}")
    print(f"  FM nonzero:        {apu.get('debug_fm_nonzero')}")
    print(f"  Output nonzero:    {apu.get('debug_output_nonzero')}")
    print(f"  Output total:      {apu.get('debug_output_total')}")
    print(f"  Last FM L/R:       {apu.get('last_fm_left'):.6f} / {apu.get('last_fm_right'):.6f}")
    print(f"  Z80 PC:            0x{apu.get('z80_pc', 0):04X}")
    print(f"  Z80 halted:        {apu.get('z80_halted')}")
    print(f"  Z80 bus req:       {apu.get('z80_bus_requested')}")
    print(f"  Z80 reset:         {apu.get('z80_reset')}")
    print(f"  Z80 IFF1:          {apu.get('z80_iff1')}")
    print(f"  Z80 bank addr:     {apu.get('z80_bank_68k_addr')}")
    print(f"  VDP frame:         {apu.get('vdp_frame')}")
    print(f"  VINT delivered:    {apu.get('vint_delivered')}")

    # Channel info
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        algo = ch.get("algorithm", 0)
        fb = ch.get("feedback", 0)
        pan_l = ch.get("pan_left", False)
        pan_r = ch.get("pan_right", False)
        ops = ch.get("operators", [])
        key_on_flags = [op.get("key_on", False) for op in ops]
        env_phases = [op.get("env_phase", "?") for op in ops]
        attens = [op.get("attenuation", 0) for op in ops]
        print(f"  CH{i+1}: fnum={fnum:4d} blk={block} algo={algo} fb={fb} pan={'L' if pan_l else ''}{'R' if pan_r else ''} keys={key_on_flags} env={env_phases} att={attens}")

    # PSG
    print(f"  PSG volumes:       {apu.get('psg_volumes')}")
    print(f"  PSG periods:       {apu.get('psg_periods')}")

    # Recent YM writes (non-DAC)
    log = apu.get("ym_write_log_recent_non_dac", [])
    if log:
        print(f"  Recent YM writes (non-DAC, last {min(20, len(log))}):")
        for entry in log[:20]:
            print(f"    {entry}")

    # Z80 trace
    z80_trace = apu.get("z80_trace_ring", [])
    if z80_trace:
        print(f"  Z80 trace (last {min(10, len(z80_trace))}):")
        for entry in z80_trace[:10]:
            print(f"    {entry}")

def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "frontend/roms/北へPM 鮎.bin"
    
    print(f"Loading ROM: {rom_path}")
    load_rom(rom_path)
    
    # Step in batches and observe APU state
    for batch in [100, 200, 300, 400]:
        print(f"\n--- Stepping {batch} frames ---")
        step_frames(batch)
        apu = get_apu()
        total_frame = apu.get("vdp_frame", 0)
        print_apu_summary(apu, f"(frame ~{total_frame})")

if __name__ == "__main__":
    main()
