#!/usr/bin/env python3
import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())


def post(path, data=None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
for _ in range(120):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0x80})
for _ in range(8):
    post("/emulator/step", {"frames": 1})
post("/input/controller", {"player": 1, "buttons": 0})
for _ in range(300):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print("ym_write_total", apu.get("ym_write_total"))
print("regs_port0_b4_b6", apu.get("regs_port0_b4_b6"))
print("regs_port1_b4_b6", apu.get("regs_port1_b4_b6"))
print("regs_port0_algo", apu.get("regs_port0_algo"))
print("regs_port1_algo", apu.get("regs_port1_algo"))
print("regs_port0_freq", apu.get("regs_port0_freq"))
print("regs_port1_freq", apu.get("regs_port1_freq"))
print("hist0", apu.get("ym_histogram_port0_nonzero"))
print("hist1", apu.get("ym_histogram_port1_nonzero"))
print("recent_non_dac")
for s in apu.get("ym_write_log_recent_non_dac", [])[:50]:
    print(" ", s)
