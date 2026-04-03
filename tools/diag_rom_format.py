"""Check ROM format - is it SMD or BIN?"""
import os
import requests

BASE = "http://localhost:8080/api/v1"
ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Check ROM info from API
s = requests.Session()
info = s.get(f"{BASE}/rom/info").json()
print(f"ROM info: {info}")

# Read ROM header from emulator's memory (what the CPU sees)
mem = s.get(f"{BASE}/cpu/memory", params={"addr": 0x100, "len": 256}).json()
data = mem.get("data", [])
if len(data) >= 16:
    sys_name = bytes(data[0:16]).decode("ascii", errors="replace")
    print(f"System name at $100: '{sys_name}'")
if len(data) >= 0x50:
    dom_name = bytes(data[0x20:0x50]).decode("ascii", errors="replace")
    print(f"Domestic at $120: '{dom_name}'")

# Check raw file
size = os.path.getsize(ROM_PATH)
print(f"\nRaw file: {size} bytes ({size/1024:.0f} KB)")

with open(ROM_PATH, "rb") as f:
    raw = f.read(0x400)

print(f"Raw[0:16]: {raw[0:16].hex(' ')}")
print(f"Raw[0x100:0x110]: {raw[0x100:0x110]}")
print(f"Raw[0x100:0x110] text: '{raw[0x100:0x110].decode('ascii', errors='replace')}'")

# SMD detection
# SMD has optional 512-byte header where byte 1=0x03 typically
# Also check if raw $100 has "SEGA" text
has_sega_at_100 = raw[0x100:0x104] == b"SEGA"
print(f"\n'SEGA' at raw $100: {has_sega_at_100}")

# Check $300 (= $100 + 512-byte SMD header)
if len(raw) >= 0x310:
    has_sega_at_300 = raw[0x300:0x304] == b"SEGA"
    print(f"'SEGA' at raw $300: {has_sega_at_300}")
    print(f"Raw $300-$310 text: '{raw[0x300:0x310].decode('ascii', errors='replace')}'")

# Check SMD header markers
print(f"\nSMD header check:")
print(f"  Byte 0: {raw[0]} (block count for SMD)")
print(f"  Byte 1: {raw[1]}")
print(f"  Byte 2: {raw[2]} (3 = SMD marker)")
print(f"  Bytes 8-9: {raw[8]:02X} {raw[9]:02X}")

# If it looks like SMD: size should be (n * 16384) + 512
if (size - 512) % 16384 == 0:
    blocks = (size - 512) // 16384
    print(f"  Possible SMD: {blocks} blocks of 16KB + 512 header = {blocks * 16384 + 512}")
if size % 16384 == 0:
    blocks = size // 16384
    print(f"  Possible raw: {blocks} blocks of 16KB = {blocks * 16384}")
