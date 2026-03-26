#!/usr/bin/env python3
import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())


def post(path: str, data=None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def trace_unique_pcs(ring):
    pcs = []
    for item in ring[-256:]:
        if not isinstance(item, str) or not item.startswith("$"):
            continue
        head = item.split(":", 1)[0][1:]
        try:
            pcs.append(int(head, 16))
        except ValueError:
            pass
    return len(set(pcs))


post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
for _ in range(120):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0x80})
for _ in range(8):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0})

last_total = 0
for i in range(0, 360, 30):
    for _ in range(30):
        post("/emulator/step", {"frames": 1})
    apu = get("/apu/state")
    total = int(apu.get("ym_write_total", 0))
    delta = total - last_total
    last_total = total
    ring = apu.get("z80_trace_ring", [])
    print(
        f"after+{i+30:03d} pc=0x{int(apu.get('z80_pc',0)):04X} "
        f"iff1={apu.get('z80_iff1')} int={apu.get('z80_int_pending')} "
        f"ym_total={total} ym_delta={delta} uniq_pc_tail={trace_unique_pcs(ring)}"
    )
