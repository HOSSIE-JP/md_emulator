#!/usr/bin/env python3
"""Diagnose YM2612 writes with histogram and write log."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 60 frames
for _ in range(60):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
print(f"ym_write_total: {apu.get('ym_write_total', 0)}")
print(f"ym_write_log_len: {apu.get('ym_write_log_len', 0)}")
print()

# Show first 100 writes
log = apu.get("ym_write_log_first100", [])
print(f"=== First {len(log)} YM writes ===")
for i, entry in enumerate(log):
    print(f"  [{i:3d}] {entry}")
print()

# Show histogram
h0 = apu.get("ym_histogram_port0_nonzero", [])
h1 = apu.get("ym_histogram_port1_nonzero", [])
print(f"=== Port 0 registers written ({len(h0)} unique) ===")
for h in h0:
    print(f"  {h}")
print()
print(f"=== Port 1 registers written ({len(h1)} unique) ===")
for h in h1:
    print(f"  {h}")
