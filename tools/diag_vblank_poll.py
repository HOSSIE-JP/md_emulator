#!/usr/bin/env python3
"""Read M68K code around the VBlank polling loop and decode key instructions."""
import requests

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Read code around $7980-$79B0
mem = api("get", "/cpu/memory", params={"addr": 0x7980, "len": 64})
data = mem.get("data", [])
print("=== Code around $7980-$79BF (VBlank polling area) ===")
for i in range(0, len(data), 2):
    addr = 0x7980 + i
    if i + 1 < len(data):
        w = (data[i] << 8) | data[i + 1]
        marker = " <-- $798E" if addr == 0x798E else (" <-- $7994" if addr == 0x7994 else "")
        print(f"  ${addr:06X}: {data[i]:02X}{data[i+1]:02X}{marker}")

# Also read the VBlank wait function at $78B4
mem2 = api("get", "/cpu/memory", params={"addr": 0x78B0, "len": 48})
data2 = mem2.get("data", [])
print("\n=== Code around $78B0-$78DF (VBlank wait function) ===")
for i in range(0, len(data2), 2):
    addr = 0x78B0 + i
    if i + 1 < len(data2):
        print(f"  ${addr:06X}: {data2[i]:02X}{data2[i+1]:02X}")

# Read $FF0044 area (software VBlank flag)
mem3 = api("get", "/cpu/memory", params={"addr": 0xFF0040, "len": 16})
data3 = mem3.get("data", [])
print("\n=== RAM $FF0040-$FF004F (VBlank-related flags) ===")
for i in range(0, len(data3), 2):
    addr = 0xFF0040 + i
    if i + 1 < len(data3):
        w = (data3[i] << 8) | data3[i + 1]
        print(f"  ${addr:06X}: ${w:04X}")

# Read VDP registers
vdp_regs = api("get", "/apu/state")
print(f"\n  VDP R1 (VINT_EN): 0x{0x54:02X} → VINT={'ON' if (0x54 & 0x20) else 'OFF'}")
print(f"  VDP status: {vdp_regs.get('vdp_status', '?')}")
