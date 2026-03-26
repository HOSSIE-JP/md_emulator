#!/usr/bin/env python3
"""Search ROM for references to GEMS sound command addresses."""
import urllib.request, json, struct

BASE = "http://localhost:8090/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded")

# Read entire ROM
rom_data = get("/cpu/memory", {"addr": 0, "len": 0x80000})
rom = bytes(rom_data["data"])
print(f"ROM size: {len(rom)} bytes")

# Search for references to $FF012C (sound command byte)
# In M68K absolute long addressing, this appears as 00 FF 01 2C
targets = {
    "FF012C": bytes([0x00, 0xFF, 0x01, 0x2C]),
    "FF012D": bytes([0x00, 0xFF, 0x01, 0x2D]),
    "FF012E": bytes([0x00, 0xFF, 0x01, 0x2E]),
    "FF012F": bytes([0x00, 0xFF, 0x01, 0x2F]),
    "FF0130": bytes([0x00, 0xFF, 0x01, 0x30]),
    "FF0134": bytes([0x00, 0xFF, 0x01, 0x34]),
    "FF013A": bytes([0x00, 0xFF, 0x01, 0x3A]),
}

for name, pattern in targets.items():
    print(f"\n=== References to ${name} ===")
    pos = 0
    count = 0
    while True:
        idx = rom.find(pattern, pos)
        if idx == -1:
            break
        # Show surrounding context (16 bytes before and after)
        start = max(0, idx - 8)
        end = min(len(rom), idx + len(pattern) + 8)
        ctx = rom[start:end]
        hexstr = ' '.join(f'{b:02X}' for b in ctx)
        print(f"  ROM ${idx:06X} (context from ${start:06X}): {hexstr}")
        pos = idx + 1
        count += 1
    print(f"  Total: {count} references")

# Also search for where the game might store sound command data
# Look for references to $FF012C with 2-byte offset (short addressing)
# Short addressing: $012C
print("\n=== Search for word-size references to $012C ===")
target_w = bytes([0x01, 0x2C])
pos = 0
count = 0
for i in range(0, len(rom) - 6, 2):  # only check even addresses
    if rom[i:i+2] == target_w:
        count += 1
if count < 50:
    pos = 0
    while True:
        idx = rom.find(target_w, pos)
        if idx == -1:
            break
        if idx % 2 == 0:  # only even addresses (M68K is word-aligned)
            start = max(0, idx - 8)
            end = min(len(rom), idx + 10)
            ctx = rom[start:end]
            hexstr = ' '.join(f'{b:02X}' for b in ctx)
            # Suppress if it's inside the sound handler we already know
            if 0x7378 <= idx <= 0x74A0:
                pass
            else:
                print(f"  ROM ${idx:06X}: {hexstr}")
        pos = idx + 1
print(f"  Total even-aligned: {count}")

# Search for the GEMS API init (where game sets up GEMS)
# Look for writes to $A00027 (Z80 command byte)
print("\n=== Direct writes to Z80 $A00027 (command register) ===")
target_z80 = bytes([0x00, 0xA0, 0x00, 0x27])
pos = 0
while True:
    idx = rom.find(target_z80, pos)
    if idx == -1:
        break
    start = max(0, idx - 12)
    end = min(len(rom), idx + 8)
    ctx = rom[start:end]
    hexstr = ' '.join(f'{b:02X}' for b in ctx)
    print(f"  ROM ${idx:06X}: {hexstr}")
    pos = idx + 1

# Also search for the GEMS init routine - typically writes $01 to the command area
print("\n=== Searching for MOVE.B #$01 or #$02 patterns near sound code ===")
# MOVE.B #imm,abs.long = 13FC XX XX 00 FF 01 2C
for imm_val, name in [(0x01, "init"), (0x02, "play")]:
    pattern = bytes([0x13, 0xFC, 0x00, imm_val, 0x00, 0xFF, 0x01, 0x2C])
    idx = rom.find(pattern)
    if idx != -1:
        print(f"  MOVE.B #${imm_val:02X},$FF012C ({name}) at ROM ${idx:06X}")
    else:
        print(f"  MOVE.B #${imm_val:02X},$FF012C ({name}) NOT FOUND")

# Search for the sound initialization routine
# Look for references to $A00027 in the init area
print("\n=== Init area around $7100-$7300 ===")
init_area = rom[0x7100:0x7370]
for off in range(0, len(init_area), 16):
    addr = 0x7100 + off
    hexstr = ' '.join(f'{b:02X}' for b in init_area[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

print("\nDone.")
