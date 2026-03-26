#!/usr/bin/env python3
"""Quick Z80 debug check."""
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

apu0 = get("/apu/state")
print(f"Initial: z80_pc={apu0['z80_pc']} cycles={apu0['z80_total_cycles']} halted={apu0['z80_halted']} reset={apu0['z80_reset']}")
ram = apu0['z80_ram_first_64']
print(f"Z80 RAM[0:32]: {' '.join(f'{b:02X}' for b in ram[:32])}")

# Run 1 frame
post("/emulator/step", {"frames": 1})
apu1 = get("/apu/state")
print(f"\nAfter 1 frame: z80_pc={apu1['z80_pc']} cycles={apu1['z80_total_cycles']} halted={apu1['z80_halted']} reset={apu1['z80_reset']} bus_req={apu1['z80_bus_requested']} ym_writes={apu1['ym_write_total']}")
ram1 = apu1['z80_ram_first_64']
print(f"Z80 RAM[0:32]: {' '.join(f'{b:02X}' for b in ram1[:32])}")

# Run 9 more frames (total 10)
for _ in range(9):
    post("/emulator/step", {"frames": 1})
apu10 = get("/apu/state")
print(f"\nAfter 10 frames: z80_pc={apu10['z80_pc']} cycles={apu10['z80_total_cycles']} halted={apu10['z80_halted']} reset={apu10['z80_reset']} bus_req={apu10['z80_bus_requested']} ym_writes={apu10['ym_write_total']}")
ram10 = apu10['z80_ram_first_64']
print(f"Z80 RAM[0:64]: {' '.join(f'{b:02X}' for b in ram10)}")

# Run 50 more frames (total 60)
for _ in range(50):
    post("/emulator/step", {"frames": 1})
apu60 = get("/apu/state")
print(f"\nAfter 60 frames: z80_pc={apu60['z80_pc']} cycles={apu60['z80_total_cycles']} halted={apu60['z80_halted']} reset={apu60['z80_reset']} bus_req={apu60['z80_bus_requested']} ym_writes={apu60['ym_write_total']}")

# Run 300 more frames (total 360)
for _ in range(300):
    post("/emulator/step", {"frames": 1})
apu360 = get("/apu/state")
print(f"\nAfter 360 frames: z80_pc={apu360['z80_pc']} cycles={apu360['z80_total_cycles']} halted={apu360['z80_halted']} reset={apu360['z80_reset']} bus_req={apu360['z80_bus_requested']} ym_writes={apu360['ym_write_total']}")
