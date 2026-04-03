#!/usr/bin/env python3
"""Dump raw CPU state JSON to understand structure."""
import requests
import json

BASE = "http://localhost:8080/api/v1"

r = requests.get(f"{BASE}/cpu/state", timeout=10)
print("CPU state (raw):")
print(json.dumps(r.json(), indent=2, default=str)[:3000])

print("\n\nVDP registers:")
r2 = requests.get(f"{BASE}/vdp/registers", timeout=10)
regs = r2.json().get("registers", [])
for i, val in enumerate(regs):
    if i < 24:
        print(f"  Reg {i:2d}: 0x{val:02X} ({val:08b})")
