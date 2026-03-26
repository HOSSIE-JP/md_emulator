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


def run(rom: str, warmup: int, after: int, press_start: bool):
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
    first = apu.get("ym_write_log_first100", [])
    print("rom", rom)
    print("first100_len", len(first))
    print("first100")
    for s in first:
        print(s)

    def parse_addr(entry: str):
        if not isinstance(entry, str) or "$" not in entry:
            return None
        i = entry.find("$")
        if i < 0 or i + 3 >= len(entry):
            return None
        try:
            return int(entry[i + 1 : i + 3], 16)
        except ValueError:
            return None

    freq = [e for e in first if (a := parse_addr(e)) is not None and (0xA0 <= a <= 0xA6)]
    key = [e for e in first if "$28" in e]
    dac = [e for e in first if "$2A" in e or "$2B" in e]
    print("freq_writes", len(freq))
    for e in freq:
        print(" ", e)
    print("key_writes", len(key))
    for e in key[:20]:
        print(" ", e)
    print("dac_writes", len(dac))
    for e in dac[:20]:
        print(" ", e)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rom", required=True)
    p.add_argument("--warmup", type=int, default=120)
    p.add_argument("--after", type=int, default=300)
    p.add_argument("--press-start", action="store_true")
    args = p.parse_args()
    run(args.rom, args.warmup, args.after, args.press_start)
