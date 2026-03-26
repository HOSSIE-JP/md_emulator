#!/usr/bin/env python3
"""Disassemble VBlank handler and sound processing function."""
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

# Dump VBlank handler at $0524
print("=== VBlank Handler at $0524 ===")
data = read_rom(0x0520, 0x30)
for off in range(0, len(data), 16):
    addr = 0x0520 + off
    hexstr = ' '.join(f'{b:02X}' for b in data[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# The BSR at $0532 targets $064C (displacement $0118)
# Let me also check: $0532: 61 00 XX XX
print(f"\n  $0532 displacement bytes: {data[0x12]:02X} {data[0x13]:02X}")
target1 = 0x0534 + (data[0x12] << 8 | data[0x13])
print(f"  BSR target 1: ${target1:06X}")
print(f"  $0536 displacement bytes: {data[0x16]:02X} {data[0x17]:02X}")
target2 = 0x0538 + (data[0x16] << 8 | data[0x17])
print(f"  BSR target 2: ${target2:06X}")

# Dump the sound processing function at $064C
print(f"\n=== Sound processing at ${target1:06X} ===")
data = read_rom(target1, 0x100)
for off in range(0, len(data), 16):
    addr = target1 + off
    hexstr = ' '.join(f'{b:02X}' for b in data[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Also dump $0700+ (where the BEQ at $0654 skips to)
print(f"\n=== Code at $0700 ===")
data2 = read_rom(0x0700, 0x40)
for off in range(0, len(data2), 16):
    addr = 0x0700 + off
    hexstr = ' '.join(f'{b:02X}' for b in data2[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Also dump the VBlank post-sound area ($0540-$05E0)
print(f"\n=== VBlank continuation ($0540+) ===")
data3 = read_rom(0x0540, 0xC0)
for off in range(0, len(data3), 16):
    addr = 0x0540 + off
    hexstr = ' '.join(f'{b:02X}' for b in data3[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Also dump the second BSR target
print(f"\n=== Second BSR target at ${target2:06X} ===")
data4 = read_rom(target2, 0x40)
for off in range(0, len(data4), 16):
    addr = target2 + off
    hexstr = ' '.join(f'{b:02X}' for b in data4[off:off+16])
    print(f"  ${addr:06X}: {hexstr}")

# Check what function at $01CFD0 does and who calls it
# Search for JSR/BSR $01CFD0
print("\n=== Searching for calls to GEMS API functions ===")
rom_full = read_rom(0, 0x80000)
rom = bytes(rom_full["data"])

# Function addresses to search for
targets = [0x72F0, 0x730A, 0x7324, 0x733E, 0x7358, 0x01CFD0, 0x064C]
for tgt in targets:
    # JSR abs.L = 4E B9 XX XX XX XX
    jsr_pattern = bytes([0x4E, 0xB9, (tgt >> 24) & 0xFF, (tgt >> 16) & 0xFF, (tgt >> 8) & 0xFF, tgt & 0xFF])
    pos = 0
    jsr_refs = []
    while True:
        idx = rom.find(jsr_pattern, pos)
        if idx == -1:
            break
        jsr_refs.append(idx)
        pos = idx + 1
    
    # BSR.W = 61 00 XX XX (16-bit displacement from PC+2)
    bsr_refs = []
    for i in range(0, len(rom) - 4, 2):
        if rom[i] == 0x61 and rom[i+1] == 0x00:
            disp = (rom[i+2] << 8) | rom[i+3]
            if disp & 0x8000:
                disp -= 0x10000
            t = (i + 2) + disp
            if t == tgt:
                bsr_refs.append(i)
    
    if jsr_refs or bsr_refs:
        print(f"\n  Calls to ${tgt:06X}:")
        for r in jsr_refs:
            print(f"    JSR at ${r:06X}")
        for r in bsr_refs:
            print(f"    BSR.W at ${r:06X}")
    else:
        print(f"\n  No calls to ${tgt:06X}")

print("\nDone.")
