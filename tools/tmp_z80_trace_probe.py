#!/usr/bin/env python3
import argparse
import json
import urllib.parse
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


def run(rom: str, warmup: int, press_start: bool, after: int):
    post("/emulator/load-rom-path", {"path": rom})
    for _ in range(warmup):
        post("/emulator/step", {"frames": 1})

    if press_start:
        post("/input/controller", {"player": 1, "buttons": 0x80})
        for _ in range(8):
            post("/emulator/step", {"frames": 1})
        post("/input/controller", {"player": 1, "buttons": 0})

    for _ in range(after):
        post("/emulator/step", {"frames": 1})

    apu = get("/apu/state")
    ring = apu.get("z80_trace_ring", [])
    pc = apu.get("z80_pc", 0)
    mem_addr = 0xA00000 + max(0, pc - 16)
    q = urllib.parse.urlencode({"addr": mem_addr, "len": 64})
    mem = get(f"/cpu/memory?{q}").get("data", [])

    print("rom", rom)
    print("z80_pc", hex(pc), "trace_len", len(ring))
    print("trace_tail")
    for item in ring[-24:]:
        print(item)
    print("mem_from", hex(mem_addr))
    print(" ".join(f"{b:02X}" for b in mem))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rom", required=True)
    p.add_argument("--warmup", type=int, default=120)
    p.add_argument("--after", type=int, default=300)
    p.add_argument("--press-start", action="store_true")
    args = p.parse_args()
    run(args.rom, args.warmup, args.press_start, args.after)
