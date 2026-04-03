#!/usr/bin/env python3
"""Check Z80 RAM contents for Sonic."""
import requests

API = "http://localhost:8080/api/v1"

# Read Z80 RAM in chunks
for start in [0, 0x30, 0x80, 0x100, 0x600, 0x1000]:
    addr = 0xA00000 + start
    data = requests.get(f"{API}/cpu/memory", params={"addr": addr, "len": 64}).json().get("data", [])
    nonzero = sum(1 for b in data if b != 0)
    hex_str = " ".join(f"{b:02X}" for b in data[:32])
    print(f"Z80 RAM [{start:04X}]: {nonzero}/64 non-zero | {hex_str} ...")

# Check total non-zero bytes across all Z80 RAM
total_nonzero = 0
for offset in range(0, 0x2000, 256):
    addr = 0xA00000 + offset
    data = requests.get(f"{API}/cpu/memory", params={"addr": addr, "len": 256}).json().get("data", [])
    total_nonzero += sum(1 for b in data if b != 0)
print(f"\nTotal non-zero bytes in Z80 RAM (8KB): {total_nonzero}/8192")
