#!/usr/bin/env python3
"""Diagnose Puyo Puyo audio via MD API"""
import json, urllib.request, sys

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

# 1. Load Puyo Puyo ROM
print("=== Loading Puyo Puyo ===")
r = post('/emulator/load-rom-path', {'path': 'roms/puyo.bin'})
print("Load:", r)

# 2. Advance 60 frames (1 second)
print("\n=== Advancing 60 frames ===")
for i in range(60):
    post('/emulator/step', {'frames': 1})

# 3. Check APU state
apu = get('/apu/state')
print("\n=== APU State after 60 frames ===")
print("DAC enabled:", apu.get('dac_enabled'))
print("DAC data:", apu.get('dac_data'))
print("YM status:", apu.get('ym_status'))
print("Z80 bank:", apu.get('z80_bank_68k_addr'))

# Check YM channel info
if 'ym_channels' in apu:
    for i, ch in enumerate(apu['ym_channels']):
        ops = ch.get('operators', [])
        key_on_any = any(op.get('key_on', False) for op in ops) if ops else False
        attens = [op.get('attenuation', 0) for op in ops]
        env_phases = [op.get('env_phase', '?') for op in ops]
        print(f"  CH{i}: fnum={ch.get('fnum')}, block={ch.get('block')}, "
              f"alg={ch.get('algorithm')}, fb={ch.get('feedback')}, "
              f"pan=({ch.get('pan_left')},{ch.get('pan_right')}), "
              f"key_on={key_on_any}, attens={attens}, env={env_phases}")

# Check write histogram
if 'ym_write_histogram' in apu:
    hist = apu['ym_write_histogram']
    active_regs = [(i, v) for i, v in enumerate(hist) if v > 0]
    print(f"\n  Active YM registers: {len(active_regs)}")
    for idx, count in sorted(active_regs, key=lambda x: -x[1])[:20]:
        port = idx // 256
        addr = idx % 256
        print(f"    Port{port} Reg 0x{addr:02X}: {count} writes")

# 4. Get audio samples
samples = get('/audio/samples')
if 'samples' in samples:
    samps = samples['samples']
    print(f"\n=== Audio Samples: {len(samps)} ===")
    nonzero = sum(1 for s in samps if abs(s) > 0.001)
    maxval = max(abs(s) for s in samps) if samps else 0
    print(f"  Non-zero: {nonzero}/{len(samps)}, Max: {maxval:.6f}")
else:
    print("\n=== Audio Samples: none in response ===")
    print("  Keys:", list(samples.keys())[:10])

# 5. Advance 120 more frames (total ~3 sec) — should be in BGM territory
print("\n=== Advancing 120 more frames ===")
for i in range(120):
    post('/emulator/step', {'frames': 1})

# Check again
apu2 = get('/apu/state')
print("\n=== APU State after 180 frames ===")
if 'ym_channels' in apu2:
    for i, ch in enumerate(apu2['ym_channels']):
        ops = ch.get('operators', [])
        key_on_any = any(op.get('key_on', False) for op in ops) if ops else False
        attens = [op.get('attenuation', 0) for op in ops]
        env_phases = [op.get('env_phase', '?') for op in ops]
        print(f"  CH{i}: fnum={ch.get('fnum')}, block={ch.get('block')}, "
              f"alg={ch.get('algorithm')}, fb={ch.get('feedback')}, "
              f"pan=({ch.get('pan_left')},{ch.get('pan_right')}), "
              f"key_on={key_on_any}, attens={attens}, env={env_phases}")

samples2 = get('/audio/samples')
if 'samples' in samples2:
    samps2 = samples2['samples']
    nonzero2 = sum(1 for s in samps2 if abs(s) > 0.001)
    maxval2 = max(abs(s) for s in samps2) if samps2 else 0
    print(f"\n  Audio after 180f: {len(samps2)} samples, Non-zero: {nonzero2}, Max: {maxval2:.6f}")

# 6. Check YM write log for recent writes
if 'ym_write_log' in apu2:
    log = apu2['ym_write_log']
    print(f"\n  YM write log: {len(log)} entries, last 20:")
    for entry in log[-20:]:
        print(f"    {entry}")

# 7. Check Z80 state
print("\n=== Z80 State ===")
z80_keys = ['z80_pc', 'z80_sp', 'z80_iff1', 'z80_iff2', 'z80_halted',
            'z80_total_cycles', 'z80_int_pending']
for k in z80_keys:
    if k in apu2:
        v = apu2[k]
        if isinstance(v, int) and v > 255:
            print(f"  {k}: 0x{v:04X} ({v})")
        else:
            print(f"  {k}: {v}")

print("\nDone.")
