#!/usr/bin/env python3
"""M68K→Z80 RAM書き込みの直接テスト
Z80バスを要求し、テスト値を書き込み、読み戻して確認"""
import requests

BASE = "http://localhost:8080/api/v1"

def read_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def write_mem(addr, data):
    r = requests.post(f"{BASE}/cpu/memory", json={"addr": addr, "data": data})
    r.raise_for_status()

def read_byte(addr):
    return read_mem(addr, 1)[0]

# Load ROM
requests.post(f"{BASE}/emulator/load-rom-path",
              json={"path": "frontend/roms/北へPM 鮎.bin"}).raise_for_status()

# Step a few frames for Z80 to initialize
requests.post(f"{BASE}/emulator/step", json={"frames": 10}).raise_for_status()

print("=== Z80 RAM Write Test ===")
print()

# Test 1: Direct write to Z80 RAM via API
test_addr = 0xA001F0  # Z80 address $01F0 (unlikely to conflict)
print(f"Test 1: Z80[$01F0] direct write via API")
orig = read_byte(test_addr)
print(f"  Before: Z80[$01F0] = ${orig:02X}")
write_mem(test_addr, [0xAB])
after = read_byte(test_addr)
print(f"  After write $AB: Z80[$01F0] = ${after:02X}")
if after == 0xAB:
    print(f"  PASS: Write works via API")
else:
    print(f"  FAIL: Expected $AB, got ${after:02X}")

# Restore
write_mem(test_addr, [orig])

print()

# Test 2: Write to Z80[$0161] specifically
print(f"Test 2: Z80[$0161] direct write")
orig161 = read_byte(0xA00161)
print(f"  Before: Z80[$0161] = ${orig161:02X}")
write_mem(0xA00161, [0x42])
after161 = read_byte(0xA00161)
print(f"  After write $42: Z80[$0161] = ${after161:02X}")
if after161 == 0x42:
    print(f"  PASS: Write to $0161 works")
else:
    print(f"  FAIL: Expected $42, got ${after161:02X}")

# Step one frame and check if Z80 cleared it
requests.post(f"{BASE}/emulator/step", json={"frames": 1}).raise_for_status()
after_frame = read_byte(0xA00161)
print(f"  After 1 frame: Z80[$0161] = ${after_frame:02X}")
if after_frame != 0x42:
    print(f"  Z80 modified $0161! (Z80 is reading this address)")
else:
    print(f"  Z80 did NOT modify $0161 (Z80 may not read this address)")

# Restore
write_mem(0xA00161, [orig161])

print()

# Test 3: Check Z80[$0161] around frame 40 (when FF019C gets set)
print("=== Test 3: Frame-by-frame Z80[$0161] near frame 40 ===")
requests.post(f"{BASE}/emulator/load-rom-path",
              json={"path": "frontend/roms/北へPM 鮎.bin"}).raise_for_status()

# Step to frame 38
requests.post(f"{BASE}/emulator/step", json={"frames": 38}).raise_for_status()

# Now step one frame at a time and check Z80[$0161] BEFORE and AFTER each step
for f in range(39, 50):
    z161_before = read_byte(0xA00161)
    requests.post(f"{BASE}/emulator/step", json={"frames": 1}).raise_for_status()
    z161_after = read_byte(0xA00161)
    ff019c = (read_mem(0xFF019C, 2)[0] << 8) | read_mem(0xFF019C, 2)[1]
    ffa820 = (read_mem(0xFFA820, 2)[0] << 8) | read_mem(0xFFA820, 2)[1]
    note = ""
    if z161_before != z161_after:
        note = f" *** CHANGED from ${z161_before:02X}"
    print(f"  Frame {f}: Z80[$0161]=${z161_after:02X}{note}  FF019C=${ff019c:04X}  FFA820={ffa820:04X}")

# Test 4: Manually write $01 to Z80[$0161] and see if Z80 picks it up
print()
print("=== Test 4: Manual command injection ===")
z161_orig = read_byte(0xA00161)
print(f"  Z80[$0161] before: ${z161_orig:02X}")
write_mem(0xA00161, [0x01])
z161_check = read_byte(0xA00161)
print(f"  After API write: ${z161_check:02X}")

# Step multiple frames and monitor
for f in range(50, 60):
    requests.post(f"{BASE}/emulator/step", json={"frames": 1}).raise_for_status()
    z161 = read_byte(0xA00161)
    ff019c = (read_mem(0xFF019C, 2)[0] << 8) | read_mem(0xFF019C, 2)[1]
    print(f"  Frame {f}: Z80[$0161]=${z161:02X}  FF019C=${ff019c:04X}")

print("\nDone")
