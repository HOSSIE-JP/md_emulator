#!/usr/bin/env python3
import argparse
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


def run(rom: str, warmup: int, start_press: bool, after: int):
    post("/emulator/load-rom-path", {"path": rom})
    for _ in range(warmup):
        post("/emulator/step", {"frames": 1})

    if start_press:
        post("/input/controller", {"player": 1, "buttons": 0x80})
        for _ in range(8):
            post("/emulator/step", {"frames": 1})
        post("/input/controller", {"player": 1, "buttons": 0})

    for _ in range(after):
        post("/emulator/step", {"frames": 1})

    apu = get("/apu/state")
    print("rom", rom)
    print(
        "z80",
        {
            "pc": apu.get("z80_pc"),
            "sp": apu.get("z80_sp"),
            "iff1": apu.get("z80_iff1"),
            "int_pending": apu.get("z80_int_pending"),
            "im": apu.get("z80_im"),
            "total_cycles": apu.get("z80_total_cycles"),
        },
    )
    print(
        "ym",
        {
            "write_total": apu.get("ym_write_total"),
            "dac_enabled": apu.get("dac_enabled"),
            "regs_port0_2b": apu.get("regs_port0_2b"),
            "hist0": apu.get("ym_histogram_port0_nonzero"),
            "hist1": apu.get("ym_histogram_port1_nonzero"),
            "recent_non_dac": apu.get("ym_write_log_recent_non_dac", [])[:24],
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rom", required=True)
    p.add_argument("--warmup", type=int, default=120)
    p.add_argument("--after", type=int, default=300)
    p.add_argument("--press-start", action="store_true")
    args = p.parse_args()
    run(args.rom, args.warmup, args.press_start, args.after)
