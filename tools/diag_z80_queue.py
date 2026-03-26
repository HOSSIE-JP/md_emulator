#!/usr/bin/env python3
"""Z80 GEMS command queue diagnostic.

Dumps Z80 RAM command queue area [0x00..0x2F] at various frame points,
and analyzes command flow between M68K and Z80.
"""
import urllib.request, json, struct, sys

BASE = "http://localhost:8090/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

def read_mem(addr, length):
    """Read memory via M68K address space."""
    d = get("/cpu/memory", {"addr": addr, "len": length})
    return bytes(d["data"])

def dump_z80_comm(label):
    """Dump Z80 comm area [0x00..0x2F] via M68K address $A00000."""
    data = read_mem(0xA00000, 0x30)
    print(f"\n=== {label} ===")
    print("Command queue slots [0x00..0x07]:", ' '.join(f'{b:02X}' for b in data[0x00:0x08]))
    print("Param1 slots       [0x08..0x0F]:", ' '.join(f'{b:02X}' for b in data[0x08:0x10]))
    print("Param2 slots       [0x10..0x17]:", ' '.join(f'{b:02X}' for b in data[0x10:0x18]))
    print("Z80 vars           [0x18..0x1F]:", ' '.join(f'{b:02X}' for b in data[0x18:0x20]))
    print("  [0x20]={:02X} [0x21]={:02X} [0x22]={:02X} [0x23]={:02X}".format(
        data[0x20], data[0x21], data[0x22], data[0x23]))
    print("  [0x24]={:02X} [0x25]={:02X} [0x26]={:02X} [0x27]={:02X}".format(
        data[0x24], data[0x25], data[0x26], data[0x27]))
    print("  [0x28..0x2F]:", ' '.join(f'{b:02X}' for b in data[0x28:0x30]))
    return data

def dump_work_ram(label):
    """Dump M68K work RAM sound command area."""
    data = read_mem(0xFF012C, 16)
    print(f"\n--- M68K Work RAM sound area ({label}) ---")
    print("  $FF012C={:02X} (cmd1)  $FF012D={:02X} (p1)  $FF012E={:02X} (p2)".format(
        data[0], data[1], data[2]))
    print("  $FF012F={:02X} (cmd2)".format(data[3]))
    print("  $FF0130={:02X} $FF0131={:02X} $FF0132={:02X} $FF0133={:02X} (cmds 3-6)".format(
        data[4], data[5], data[6], data[7]))
    print("  $FF0134={:02X}{:02X} (error flag)".format(data[8], data[9]))
    print("  $FF013A={:02X} (busy flag)".format(data[14]))
    return data

# --- Start ---
print("=== Z80 GEMS Command Queue Diagnostic ===")

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Run a few frames to let init complete
for i in range(5):
    post("/emulator/step", {"frames": 1})
dump_z80_comm(f"After 5 frames (init)")
dump_work_ram("After 5 frames")

# Run 30 more frames
for i in range(30):
    post("/emulator/step", {"frames": 1})
dump_z80_comm("After 35 frames")
dump_work_ram("After 35 frames")

# Run more frames to get past title screen setup
for i in range(65):
    post("/emulator/step", {"frames": 1})
dump_z80_comm("After 100 frames")
dump_work_ram("After 100 frames")

# Press Start button
print("\n*** Pressing Start button ***")
post("/input/controller", {"player": 1, "buttons": {"start": True}})
for i in range(5):
    post("/emulator/step", {"frames": 1})
    if i < 3:
        z80 = dump_z80_comm(f"After Start + {i+1} frame(s)")
        dump_work_ram(f"After Start + {i+1} frame(s)")

# Release Start
post("/input/controller", {"player": 1, "buttons": {}})
for i in range(10):
    post("/emulator/step", {"frames": 1})
dump_z80_comm("After Start + 15 frames")
dump_work_ram("After Start + 15 frames")

# Run more frames
for i in range(85):
    post("/emulator/step", {"frames": 1})
dump_z80_comm("After Start + 100 frames")
dump_work_ram("After Start + 100 frames")

# Now dump Z80 code around the main loop to understand command queue processing
print("\n\n=== Z80 Binary Analysis (main loop) ===")
# Read Z80 RAM around the main loop area ($116F)
z80_code = read_mem(0xA00000 + 0x1160, 0x100)
print(f"Z80 code $1160..${0x1160+0x100-1:04X}:")
for off in range(0, len(z80_code), 16):
    addr = 0x1160 + off
    hexstr = ' '.join(f'{b:02X}' for b in z80_code[off:off+16])
    print(f"  ${addr:04X}: {hexstr}")

# Also read Z80 code around $1000 (might have the read pointer logic)
z80_code2 = read_mem(0xA00000 + 0x1100, 0x60)
print(f"\nZ80 code $1100..${0x1100+0x60-1:04X}:")
for off in range(0, len(z80_code2), 16):
    addr = 0x1100 + off
    hexstr = ' '.join(f'{b:02X}' for b in z80_code2[off:off+16])
    print(f"  ${addr:04X}: {hexstr}")

# Also dump Z80 code at the very beginning (might have queue processing near $0018-$0050)
z80_low = read_mem(0xA00000, 0x20)
print(f"\nZ80 RAM $0000..001F (comm/queue area):")
for off in range(0, len(z80_low), 16):
    hexstr = ' '.join(f'{b:02X}' for b in z80_low[off:off+16])
    print(f"  ${off:04X}: {hexstr}")

# Check audio samples
samples = get("/audio/samples")
data = bytes(samples["data"])
nonzero = sum(1 for i in range(0, len(data), 2) if struct.unpack_from('<h', data, i)[0] != 0)
total = len(data) // 2
print(f"\nAudio: {nonzero}/{total} non-zero samples")

# Check APU state for any YM2612 activity
apu = get("/apu/state")
print(f"\nAPU state keys: {list(apu.keys())}")
if 'ym2612' in apu:
    ym = apu['ym2612']
    print(f"YM2612 keys: {list(ym.keys())}")
    if 'write_count' in ym:
        print(f"YM2612 write_count: {ym['write_count']}")

print("\nDone.")
