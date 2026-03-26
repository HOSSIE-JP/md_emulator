#!/usr/bin/env python3
"""Deep Z80 investigation: dump memory around Z80 PC, check full audio buffer."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 60 frames (past Z80 init)
for _ in range(60):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print(f"After 60 frames: z80_pc={apu['z80_pc']} cycles={apu['z80_total_cycles']} ym_writes={apu['ym_write_total']} halted={apu['z80_halted']}")
print(f"  reset={apu['z80_reset']} bus_req={apu['z80_bus_requested']}")

# Dump Z80 RAM around the PC
z80_pc = apu['z80_pc']
# Fetch Z80 RAM via memory API (Z80 RAM is at 0xA00000 in M68K address space)
ram_0x200 = get(f"/cpu/memory?addr={0xA00000 + 0x200}&len=256")
ram_data = ram_0x200.get("data", [])
print(f"\nZ80 RAM [0x0200..0x02FF]:")
for i in range(0, len(ram_data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in ram_data[i:i+16])
    addr = 0x200 + i
    print(f"  {addr:04X}: {hex_str}")

# Also dump around PC
pc_base = (z80_pc // 16) * 16
dump_start = max(0, pc_base - 32)
dump_end = pc_base + 48
ram_pc = get(f"/cpu/memory?addr={0xA00000 + dump_start}&len={dump_end - dump_start}")
ram_pc_data = ram_pc.get("data", [])
print(f"\nZ80 RAM around PC={z80_pc} (0x{z80_pc:04X}):")
for i in range(0, len(ram_pc_data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in ram_pc_data[i:i+16])
    addr = dump_start + i
    marker = " <-- PC" if pc_base <= addr + 16 and pc_base >= addr else ""
    print(f"  {addr:04X}: {hex_str}{marker}")

# Dump full Z80 RAM for program analysis (first 0x100 bytes)
ram_0 = get(f"/cpu/memory?addr={0xA00000}&len=256")
ram_0_data = ram_0.get("data", [])
print(f"\nZ80 RAM [0x0000..0x00FF] (program start):")
for i in range(0, len(ram_0_data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in ram_0_data[i:i+16])
    addr = i
    print(f"  {addr:04X}: {hex_str}")

# Now drain the FULL audio buffer and check
print("\n=== Full Audio Buffer Analysis ===")
samples = get("/audio/samples?frames=100000").get("samples", [])
nonzero = sum(1 for s in samples if abs(s) > 1e-6)
print(f"Total samples: {len(samples)}, Non-zero: {nonzero}")
if nonzero > 0:
    maxval = max(abs(s) for s in samples)
    print(f"Max amplitude: {maxval:.6f}")
    # Find first non-zero
    for i, s in enumerate(samples):
        if abs(s) > 1e-6:
            print(f"First non-zero at sample {i}: {s:.6f}")
            break

# Run 300 more frames and check again
for _ in range(300):
    post("/emulator/step", {"frames": 1})

apu2 = get("/apu/state")
print(f"\nAfter 360 frames: z80_pc={apu2['z80_pc']} ym_writes={apu2['ym_write_total']}")
print(f"  psg_volumes: {apu2['psg_volumes']}")

samples2 = get("/audio/samples?frames=100000").get("samples", [])
nonzero2 = sum(1 for s in samples2 if abs(s) > 1e-6)
print(f"Batch 2: {len(samples2)} samples, {nonzero2} non-zero")
if nonzero2 > 0:
    maxval2 = max(abs(s) for s in samples2)
    print(f"Max amplitude: {maxval2:.6f}")
