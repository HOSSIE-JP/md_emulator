#!/usr/bin/env python3
"""Verify the phantom command fix: check Z80 RAM 0x0020-0x002F state during boot."""
import json, urllib.request, time

API = "http://localhost:8081/api/v1"

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{API}{path}").read())

def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{API}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def read_z80_ram(offset, length):
    """Read Z80 RAM via M68K bus (0xA00000+offset)"""
    mem = api_get(f"/cpu/memory?addr={0xA00000 + offset}&len={length}")
    return mem.get("data", [])

# Load ROM fresh (ensures clean Z80 RAM from bus.reset())
print("=== Loading ROM fresh ===")
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Check Z80 RAM before any frames
z80_comm = read_z80_ram(0x20, 16)
print(f"After load (before frames): Z80 RAM 0x20-0x2F = {' '.join(f'{b:02X}' for b in z80_comm)}")
print(f"  0x24={z80_comm[4]:02X} 0x26={z80_comm[6]:02X} 0x27={z80_comm[7]:02X}")

# Run 1 frame
api_post("/emulator/step", {"frames": 1})
z80_comm = read_z80_ram(0x20, 16)
state = api_get("/apu/state")
z80_pc = state.get("z80_state", {}).get("pc", "?")
print(f"\nAfter frame 1: Z80 RAM 0x20-0x2F = {' '.join(f'{b:02X}' for b in z80_comm)}")
print(f"  0x24={z80_comm[4]:02X} 0x26={z80_comm[6]:02X} 0x27={z80_comm[7]:02X} Z80_PC={z80_pc}")

# Run 2 more frames 
api_post("/emulator/step", {"frames": 2})
z80_comm = read_z80_ram(0x20, 16)
state = api_get("/apu/state")
z80_pc = state.get("z80_state", {}).get("pc", "?")
print(f"\nAfter frame 3: Z80 RAM 0x20-0x2F = {' '.join(f'{b:02X}' for b in z80_comm)}")
print(f"  0x24={z80_comm[4]:02X} 0x26={z80_comm[6]:02X} 0x27={z80_comm[7]:02X} Z80_PC={z80_pc}")

# Check busy flags for 10 frames
print("\n=== Checking busy flags over frames ===")
for i in range(10):
    api_post("/emulator/step", {"frames": 1})
    z80_comm = read_z80_ram(0x20, 16)
    f24 = z80_comm[4]
    f26 = z80_comm[6]
    f27 = z80_comm[7]
    if f24 != 0 or f26 != 0:
        print(f"  Frame {4+i}: 0x24={f24:02X} 0x26={f26:02X} 0x27={f27:02X} <<< BUSY!")
    else:
        print(f"  Frame {4+i}: 0x24={f24:02X} 0x26={f26:02X} 0x27={f27:02X} (idle)")

# Check YM write histogram
state = api_get("/apu/state")
hist = state.get("write_histogram_port0", {})
hist1 = state.get("write_histogram_port1", {})
ym_writes = state.get("ym_write_total", 0)
print(f"\n=== YM2612 Write Stats (after ~13 frames) ===")
print(f"Total YM writes: {ym_writes}")
if hist:
    print(f"Port 0 histogram: {hist}")
if hist1:
    print(f"Port 1 histogram: {hist1}")

# Now press Start and run frames to see if commands get delivered
print("\n=== Pressing Start, running 200 frames ===")
api_post("/input/controller", {"player": 1, "buttons": 128})
for _ in range(10):
    api_post("/emulator/step", {"frames": 1})
api_post("/input/controller", {"player": 1, "buttons": 0})
for _ in range(190):
    api_post("/emulator/step", {"frames": 1})

# Check state after Start press
z80_comm = read_z80_ram(0x20, 16)
state = api_get("/apu/state")
ym_writes_after = state.get("ym_write_total", 0)
hist = state.get("write_histogram_port0", {})
hist1 = state.get("write_histogram_port1", {})
z80_pc = state.get("z80_state", {}).get("pc", "?")
print(f"Z80 RAM 0x20-0x2F = {' '.join(f'{b:02X}' for b in z80_comm)}")
print(f"  0x22(slot)={z80_comm[2]:02X} 0x24={z80_comm[4]:02X} 0x26={z80_comm[6]:02X} 0x27={z80_comm[7]:02X}")
print(f"Z80 PC: {z80_pc}")
print(f"Total YM writes: {ym_writes_after}")

# Check for frequency/algo/panning writes
has_freq = any(k for k in (hist or {}) if int(k, 16) >= 0xA0)
has_algo = any(k for k in (hist or {}) if 0xB0 <= int(k, 16) <= 0xB6)
has_pan = any(k for k in (hist or {}) if 0xB4 <= int(k, 16) <= 0xB6)
has_freq1 = any(k for k in (hist1 or {}) if int(k, 16) >= 0xA0)
print(f"\nFrequency writes (port0): {has_freq}")
print(f"Algorithm writes: {has_algo}")
print(f"Panning writes: {has_pan}")  
print(f"Frequency writes (port1): {has_freq1}")

if hist:
    print(f"\nPort 0 histogram: {hist}")
if hist1:
    print(f"Port 1 histogram: {hist1}")

# Check audio samples
fm_nonzero = state.get("debug_fm_nonzero", 0)
dac_samples = state.get("debug_dac_samples", 0)
dac_nonzero = state.get("debug_dac_nonzero", 0)
print(f"\nFM non-zero samples: {fm_nonzero}")
print(f"DAC samples: {dac_samples}, non-zero: {dac_nonzero}")

# Check command queue in M68K work RAM
cmd_area = api_get(f"/cpu/memory?addr={0xFF012C}&len=8")
cmd_data = cmd_area.get("data", [])
print(f"\nM68K command buffer (0xFF012C): {' '.join(f'{b:02X}' for b in cmd_data)}")
