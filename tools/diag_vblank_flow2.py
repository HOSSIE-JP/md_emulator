#!/usr/bin/env python3
"""Disassemble the correct VBlank sound processing functions."""
import urllib.request, json

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

def read_rom(addr, length):
    d = get("/cpu/memory", {"addr": addr, "len": length})
    return bytes(d["data"])

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# VBlank at $0524 calls:
# 1. BSR $064C (displacement $0118 from $0534)
# 2. BSR $0606 (displacement $00CE from $0538)
# 3. JSR $7378

# Read the function at $064C
print("=== Sound function at $064C ===")
data = read_rom(0x064C, 0xC0)
for off in range(0, len(data), 16):
    addr = 0x064C + off
    hexstr = ' '.join(f'{b:02X}' for b in data[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Read the function at $0606
print("\n=== Function at $0606 ===")
data2 = read_rom(0x0606, 0x50)
for off in range(0, len(data2), 16):
    addr = 0x0606 + off
    hexstr = ' '.join(f'{b:02X}' for b in data2[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Read the area at $06B2 which references $FF013A
print("\n=== Function referencing $FF013A at $06B2 ===")
data3 = read_rom(0x06B0, 0x60)
for off in range(0, len(data3), 16):
    addr = 0x06B0 + off
    hexstr = ' '.join(f'{b:02X}' for b in data3[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Search ROM for JSR/BSR calls to GEMS API functions
rom = read_rom(0, 0x80000)

# Function addresses to search for
gem_fns = {
    0x72EA: "write_FF012F",
    0x72F0: "play_song_20",
    0x730A: "stop_sound",
    0x7324: "pause",
    0x733E: "resume",
    0x7358: "play_sfx",
    0x064C: "vbl_sound_proc",
}

print("\n=== Calls to GEMS API functions ===")
for tgt, name in gem_fns.items():
    refs = []
    # JSR abs.L = 4E B9 00 HH HL LL
    jsr_pat = bytes([0x4E, 0xB9, (tgt >> 24) & 0xFF, (tgt >> 16) & 0xFF, (tgt >> 8) & 0xFF, tgt & 0xFF])
    pos = 0
    while True:
        idx = rom.find(jsr_pat, pos)
        if idx == -1:
            break
        refs.append(("JSR", idx))
        pos = idx + 1
    
    # BSR.W = 61 00 XX XX
    for i in range(0, len(rom) - 4, 2):
        if rom[i] == 0x61 and rom[i+1] == 0x00:
            disp = (rom[i+2] << 8) | rom[i+3]
            if disp & 0x8000:
                disp -= 0x10000
            t = (i + 2) + disp
            if t == tgt:
                refs.append(("BSR.W", i))
    
    # BSR.B = 61 XX (8-bit displacement, non-zero)
    for i in range(0, len(rom) - 2, 2):
        if rom[i] == 0x61 and rom[i+1] != 0x00 and rom[i+1] != 0xFF:
            disp = rom[i+1]
            if disp & 0x80:
                disp -= 0x100
            t = (i + 2) + disp
            if t == tgt:
                refs.append(("BSR.B", i))
    
    if refs:
        print(f"\n  ${tgt:06X} ({name}):")
        for typ, addr in sorted(refs, key=lambda x: x[1]):
            print(f"    {typ} at ${addr:06X}")
    else:
        print(f"\n  ${tgt:06X} ({name}): NO CALLERS FOUND")

# Also search for callers of the general sound function at $01CFD0
tgt = 0x01CFD0
refs = []
jsr_pat = bytes([0x4E, 0xB9, (tgt >> 24) & 0xFF, (tgt >> 16) & 0xFF, (tgt >> 8) & 0xFF, tgt & 0xFF])
pos = 0
while True:
    idx = rom.find(jsr_pat, pos)
    if idx == -1:
        break
    refs.append(("JSR", idx))
    pos = idx + 1
for i in range(0, len(rom) - 4, 2):
    if rom[i] == 0x61 and rom[i+1] == 0x00:
        disp = (rom[i+2] << 8) | rom[i+3]
        if disp & 0x8000:
            disp -= 0x10000
        t = (i + 2) + disp
        if t == tgt:
            refs.append(("BSR.W", i))
print(f"\n  ${tgt:06X} (general_play_sound):")
for typ, addr in sorted(refs, key=lambda x: x[1]):
    print(f"    {typ} at ${addr:06X}")
if not refs:
    print("    NO CALLERS FOUND")

# Also search for who writes to $FF012C (command byte)
# MOVE.B #imm,$FF012C.L = 13 FC XX XX 00 FF 01 2C
print("\n\n=== All code that writes to $FF012C ===")
pattern = bytes([0x00, 0xFF, 0x01, 0x2C])
pos = 0
while True:
    idx = rom.find(pattern, pos)
    if idx == -1:
        break
    # Show 12 bytes before and 4 after
    start = max(0, idx - 12)
    end = min(len(rom), idx + 8)
    ctx = rom[start:end]
    hexstr = ' '.join(f'{b:02X}' for b in ctx)
    print(f"  ROM ${idx:06X} (from ${start:06X}): {hexstr}")
    pos = idx + 1

# Check where the game code at $01CFD0 is
print("\n=== Code at $01CFD0 ===")
data4 = read_rom(0x01CFB0, 0x80)
for off in range(0, len(data4), 16):
    addr = 0x01CFB0 + off
    hexstr = ' '.join(f'{b:02X}' for b in data4[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

print("\nDone.")
