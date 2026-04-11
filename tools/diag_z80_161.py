#!/usr/bin/env python3
"""Z80[$0161]とROM $7F5Cのシンプルダンプ"""
import requests

BASE = "http://localhost:8080/api/v1"

def read_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def read_word(addr):
    d = read_mem(addr, 2)
    return (d[0] << 8) | d[1]

# Load ROM
requests.post(f"{BASE}/emulator/load-rom-path",
              json={"path": "frontend/roms/北へPM 鮎.bin"}).raise_for_status()

# ROM dump at $7F5C
print("=== ROM $7F5C (BEQ target) ===")
raw = read_mem(0x7F5C, 0x40)
for i in range(0, len(raw)-1, 2):
    w = (raw[i] << 8) | raw[i+1]
    print(f"  ${0x7F5C+i:04X}: ${w:04X}")

# Step to frame 40
requests.post(f"{BASE}/emulator/step", json={"frames": 40}).raise_for_status()

print("\n=== Frame 40 ===")
print(f"  FF019C=${read_word(0xFF019C):04X}")
z80_160 = read_mem(0xA00160, 8)
print(f"  Z80[$0160-$0167]: {' '.join(f'{b:02X}' for b in z80_160)}")

# Monitor frames 41-60
print("\n=== Z80[$0161] per frame ===")
for f in range(41, 61):
    requests.post(f"{BASE}/emulator/step", json={"frames": 1}).raise_for_status()
    z161 = read_mem(0xA00161, 1)[0]
    ff019c = read_word(0xFF019C)
    ffa820 = read_word(0xFFA820)
    print(f"  Frame {f}: Z80[$0161]={z161:02X} FF019C=${ff019c:04X} FFA820=${ffa820:04X}")

print("\nDone")
