#!/usr/bin/env python3
"""Compare Z80 RAM with both ROM copy sources to determine which was loaded."""
import urllib.request, json

BASE = "http://localhost:8091/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

def read_mem(addr, length):
    d = get("/cpu/memory", {"addr": addr, "len": length})
    return bytes(d["data"])

# Load fresh ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
post("/emulator/step", {"frames": 10})

# Read Z80 RAM (first 8KB)
z80_ram = read_mem(0xA00000, 0x2000)

# Read both ROM areas
rom_copy1 = read_mem(0x076C00, 0x1400)  # First copy: 5120 bytes
rom_copy2 = read_mem(0x07E000, 0x2000)  # Second copy: 8192 bytes

# Compare Z80 RAM with copy 1
match1 = 0
for i in range(min(len(rom_copy1), len(z80_ram))):
    if z80_ram[i] == rom_copy1[i]:
        match1 += 1

# Compare Z80 RAM with copy 2
match2 = 0
for i in range(min(len(rom_copy2), len(z80_ram))):
    if z80_ram[i] == rom_copy2[i]:
        match2 += 1

print(f"Z80 RAM vs ROM $076C00 (copy 1): {match1}/{len(rom_copy1)} matching bytes")
print(f"Z80 RAM vs ROM $07E000 (copy 2): {match2}/{len(rom_copy2)} matching bytes")

# Check specific areas
print(f"\nZ80 RAM $114A-$1150: {' '.join(f'{b:02X}' for b in z80_ram[0x114A:0x1150])}")
print(f"ROM1 +$114A: {' '.join(f'{b:02X}' for b in rom_copy1[0x114A:0x114A+6] if 0x114A < len(rom_copy1))}")
print(f"ROM2 +$114A: {' '.join(f'{b:02X}' for b in rom_copy2[0x114A:0x1150])}")

# Check area around $116F (main loop?)
print(f"\nZ80 RAM $1160-$1190:")
for off in range(0, 0x30, 16):
    addr = 0x1160 + off
    hexstr = ' '.join(f'{b:02X}' for b in z80_ram[addr:addr+16])
    print(f"  ${addr:04X}: {hexstr}")

print(f"\nROM2 $1160-$1190:")
for off in range(0, 0x30, 16):
    addr = 0x1160 + off
    hexstr = ' '.join(f'{b:02X}' for b in rom_copy2[addr:addr+16])
    print(f"  ${addr:04X}: {hexstr}")

# Check $1226 (command handler)
print(f"\nZ80 RAM $1220-$1240:")
hexstr = ' '.join(f'{b:02X}' for b in z80_ram[0x1220:0x1240])
print(f"  {hexstr}")
print(f"\nROM2 $1220-$1240:")
hexstr = ' '.join(f'{b:02X}' for b in rom_copy2[0x1220:0x1240])
print(f"  {hexstr}")

# Check first bytes (reset vector)
print(f"\nZ80 RAM $0000-$0003: {' '.join(f'{b:02X}' for b in z80_ram[0:4])}")
print(f"ROM2 $0000-$0003: {' '.join(f'{b:02X}' for b in rom_copy2[0:4])}")

# Dump Z80 RAM $1140-$11A0 (the init/main loop area we care about)
print(f"\nZ80 RAM $1140-$11A0:")
for off in range(0, 0x60, 16):
    addr = 0x1140 + off
    hexstr = ' '.join(f'{b:02X}' for b in z80_ram[addr:addr+16])
    print(f"  ${addr:04X}: {hexstr}")

# Check the complete init from $114A
print(f"\n=== Z80 Init code at $114A (first 64 bytes) ===")
for off in range(0, 64, 16):
    addr = 0x114A + off
    hexstr = ' '.join(f'{b:02X}' for b in z80_ram[addr:addr+16])
    print(f"  ${addr:04X}: {hexstr}")
