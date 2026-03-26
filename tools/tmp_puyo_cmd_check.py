#!/usr/bin/env python3
"""Check when M68K sends music command to Z80"""
import json, urllib.request

B = 'http://127.0.0.1:8080/api/v1'

def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=30).read())

def post(p, d=None):
    if d is None:
        d = {}
    req = urllib.request.Request(
        B + p, data=json.dumps(d).encode(),
        headers={'Content-Type': 'application/json'}
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def read_mem(addr, length):
    r = get(f'/cpu/memory?addr={addr}&len={length}')
    return r.get('data', [])

# Load ROM
print("=== Loading Puyo Puyo ===")
post('/emulator/load-rom-path', {'path': 'roms/puyo.bin'})

# Check Z80 command byte and YM writes over time
prev_frame = 0
for checkpoint in [10, 30, 60, 120, 180, 240, 300, 360, 420, 480, 600]:
    frames_needed = checkpoint - prev_frame
    if frames_needed > 0:
        for _ in range(frames_needed):
            post('/emulator/step', {'frames': 1})
    prev_frame = checkpoint
    
    # Read command byte at Z80 $0027
    cmd_val = read_mem(0xA00027, 1)
    cmd_byte = cmd_val[0] if cmd_val else -1
    
    apu = get('/apu/state')
    ym_writes = apu.get('ym_write_total', 0)
    vint = apu.get('vint_delivered', 0)
    z80_pc = apu.get('z80_pc', 0)
    
    # Read audio samples  
    samples = get('/audio/samples')
    samps = samples.get('samples', [])
    nonzero = sum(1 for s in samps if abs(s) > 0.001)
    
    print(f"Frame {checkpoint:4d}: cmd=${cmd_byte:02X}, "
          f"ym_writes={ym_writes}, vint={vint}, "
          f"z80_pc=${z80_pc:04X}, audio_nz={nonzero}/{len(samps)}")

print("\nDone.")
