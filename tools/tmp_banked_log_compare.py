#!/usr/bin/env python3
import json
import pathlib
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
    print("rom", rom)
    bank_raw = apu.get("z80_bank_68k_addr", 0)
    if isinstance(bank_raw, str):
        bank_value = int(bank_raw, 16) if bank_raw.startswith("0x") else int(bank_raw)
    else:
        bank_value = int(bank_raw)
    print("bank", hex(bank_value))
    log = apu.get("z80_banked_read_log", [])
    print("banked_log_len", len(log))
    print("banked_tail", log[-20:])
    rom_bytes = pathlib.Path(rom).read_bytes()
    checked = 0
    matched = 0
    for item in log[-20:]:
        if not isinstance(item, str) or "=$" not in item:
            continue
        left, right = item.split("=$", 1)
        try:
            addr = int(left.strip().lstrip("$"), 16)
            val = int(right.strip(), 16)
        except ValueError:
            continue
        if 0 <= addr < len(rom_bytes):
            checked += 1
            if rom_bytes[addr] == val:
                matched += 1
    print("rom_match", f"{matched}/{checked}")


if __name__ == "__main__":
    run("roms/puyo.bin", 120, 300, True)
    run("roms/ab2.smd", 700, 0, False)
