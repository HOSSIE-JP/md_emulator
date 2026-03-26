#!/usr/bin/env python3
"""Deep Z80 diagnosis: check ISR, command address, RAM contents"""
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
    """Read M68K memory (for Z80 RAM, use A0xxxx addresses)"""
    r = get(f'/cpu/memory?addr={addr}&len={length}')
    return r.get('data', [])

# Load ROM fresh
print("=== Loading Puyo Puyo ===")
post('/emulator/load-rom-path', {'path': 'roms/puyo.bin'})

# Advance a few frames for Z80 to initialize
for _ in range(10):
    post('/emulator/step', {'frames': 1})

# Read Z80 RAM via M68K addresses ($A00000-$A01FFF)
print("\n=== Z80 ISR at $0038 (M68K addr $A00038) ===")
isr_data = read_mem(0xA00038, 32)
if isr_data:
    for i in range(0, len(isr_data), 16):
        hex_str = ' '.join(f'{b:02X}' for b in isr_data[i:i+16])
        print(f"  ${0x0038+i:04X}: {hex_str}")
else:
    print("  Could not read ISR data")

# Read the polling address from LD A,(addr) at Z80 $1172
# LD A,(addr) = 3A LL HH  (3 bytes: opcode + little-endian address)
print("\n=== LD A,(addr) at $1172 ===")
ld_data = read_mem(0xA01172, 3)
if ld_data and len(ld_data) >= 3:
    opcode = ld_data[0]
    poll_addr = ld_data[1] | (ld_data[2] << 8)
    print(f"  Opcode: ${opcode:02X}, Address: ${poll_addr:04X}")
    # Read the value at that address
    poll_val = read_mem(0xA00000 + poll_addr, 1)
    if poll_val:
        print(f"  Current value at ${poll_addr:04X}: ${poll_val[0]:02X}")
else:
    print(f"  Raw: {ld_data}")

# Read around the idle loop to understand full context
print("\n=== Z80 Code around $1168-$1180 ===")
code = read_mem(0xA01168, 32)
if code:
    for i in range(0, len(code), 16):
        hex_str = ' '.join(f'{b:02X}' for b in code[i:i+16])
        addr = 0x1168 + i
        print(f"  ${addr:04X}: {hex_str}")

# Check APU state for Z80 reset/bus status
apu = get('/apu/state')
print(f"\n=== Z80 State ===")
print(f"  z80_reset: {apu.get('z80_reset')}")
print(f"  z80_bus_requested: {apu.get('z80_bus_requested')}")
print(f"  z80_pc: 0x{apu.get('z80_pc', 0):04X}")
print(f"  z80_iff1: {apu.get('z80_iff1')}")
print(f"  z80_int_pending: {apu.get('z80_int_pending')}")
print(f"  vint_delivered: {apu.get('vint_delivered')}")
print(f"  vdp_frame: {apu.get('vdp_frame')}")
print(f"  ym_write_total: {apu.get('ym_write_total')}")

# Check Z80 trace ring for any INT entries
trace = apu.get('z80_trace_ring', [])
int_entries = [t for t in trace if 'INT' in str(t)]
print(f"\n  INT entries in trace ring ({len(trace)} total): {len(int_entries)}")
if int_entries:
    for e in int_entries[:10]:
        print(f"    {e}")

# Advance 50 more frames and check for changes
for _ in range(50):
    post('/emulator/step', {'frames': 1})

apu2 = get('/apu/state')
print(f"\n=== After 50 more frames (total ~60f) ===")
print(f"  z80_pc: 0x{apu2.get('z80_pc', 0):04X}")
print(f"  z80_iff1: {apu2.get('z80_iff1')}")
print(f"  vint_delivered: {apu2.get('vint_delivered')}")
print(f"  ym_write_total: {apu2.get('ym_write_total')}")

# Check trace for INT entries now
trace2 = apu2.get('z80_trace_ring', [])
int_entries2 = [t for t in trace2 if 'INT' in str(t)]
print(f"  INT entries in trace ring: {len(int_entries2)}")

# Read command byte again
if ld_data and len(ld_data) >= 3:
    poll_addr = ld_data[1] | (ld_data[2] << 8)
    poll_val2 = read_mem(0xA00000 + poll_addr, 1)
    if poll_val2:
        print(f"  Value at poll addr ${poll_addr:04X}: ${poll_val2[0]:02X}")

# Check Z80 stack area (SP typically around $1FFF)
print(f"\n=== Z80 SP area ===")
sp_data = read_mem(0xA01FF0, 16)
if sp_data:
    hex_str = ' '.join(f'{b:02X}' for b in sp_data)
    print(f"  $1FF0: {hex_str}")

print("\nDone.")
