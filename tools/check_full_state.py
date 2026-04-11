#!/usr/bin/env python3
"""Check comprehensive game state."""
import requests

API = "http://localhost:8080/api/v1"

state = requests.get(f"{API}/cpu/state").json()
m68k = state['cpu']['m68k']
print(f"PC=${m68k['pc']:06X} SP=${m68k['a'][7]:08X}")
for i in range(8):
    print(f"  D{i}=${m68k['d'][i]:08X}  A{i}=${m68k['a'][i]:08X}")

addrs = {
    0xFFADA6: "script flag",
    0xFF0042: "timer counter",
    0xFF004C: "frame counter",
    0xFF0062: "interrupt level",
    0xFF0064: "VBlank flag",
    0xFF0066: "sound flags",
    0xFF019C: "Z80 addr low",
    0xFF01A0: "dispatch step",
    0xFFA820: "Z80 bus counter",
    0xFFA831: "VDP Reg1 shadow",
}

for addr, name in addrs.items():
    resp = requests.get(f"{API}/cpu/memory?addr={addr}&len=4")
    data = resp.json()['data']
    val = (data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]
    print(f"  ${addr:06X} ({name}) = ${val:08X}")

# VDP
resp = requests.get(f"{API}/vdp/registers")
vdp = resp.json()
r1 = vdp["registers"][1]
print(f"  VDP Reg1 = ${r1:02X} (VINT_EN={'ON' if r1&0x20 else 'OFF'})")
debug = vdp.get("debug", {})
fc = debug.get("frame_count", "?")
print(f"  VDP frame_count = {fc}")
