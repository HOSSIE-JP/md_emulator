#!/usr/bin/env python3
"""Fetch and display subroutines called from $6C8E init function."""
import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1/cpu/memory"

def fetch(addr, length):
    url = f"{BASE}?addr={addr}&len={length}"
    with urllib.request.urlopen(url) as resp:
        d = json.loads(resp.read())
    return bytes(d["data"])

def dump(data, base, label):
    print(f"=== {label} ===")
    for i in range(0, len(data), 16):
        h = " ".join(f"{data[i+j]:02X}" for j in range(min(16, len(data) - i)))
        print(f"  ${base+i:06X}: {h}")
    print()

def scan_for_addresses(data, base):
    """Scan for references to key addresses."""
    targets = {
        b"\xE0\xFF\x00\x66": "FF0066",
        b"\xE0\xFF\x00\x67": "FF0067",
        b"\xE0\xFF\x01\x16": "FF0116",
        b"\xE0\xFF\x01\x98": "FF0198",
        b"\xE0\xFF\x01\x9A": "FF019A",
        b"\xE0\xFF\x03\x0B": "FF030B",
        b"\xE0\xFF\x06\x28": "FF0628",
    }
    for pattern, name in targets.items():
        offset = 0
        while True:
            idx = data.find(pattern, offset)
            if idx == -1:
                break
            ctx_start = max(0, idx - 4)
            ctx_end = min(len(data), idx + len(pattern) + 4)
            ctx = " ".join(f"{data[ctx_start+j]:02X}" for j in range(ctx_end - ctx_start))
            print(f"  *** Found {name} ref at ${base+idx:06X}: {ctx}")
            offset = idx + 1


# Subroutines called from the init path
subs = [
    (0x6C0E, 128, "$6C0E - called from init via JSR $6C0E(PC)"),
    (0x64E2, 256, "$64E2 - called from init via JSR $64E2(PC) - likely YM2612 init"),
    (0x4EA8, 512, "$4EA8 - called from init via JSR $4EA8(PC) - likely Z80 upload"),
]

for addr, size, label in subs:
    data = fetch(addr, size)
    dump(data, addr, label)
    scan_for_addresses(data, addr)
    print()

# Also quick-scan $04A4 since it's called with param 7
data_04a4 = fetch(0x04A4, 128)
dump(data_04a4, 0x04A4, "$04A4 - scene selector called with param 7")
scan_for_addresses(data_04a4, 0x04A4)

# Also scan $048C
data_048c = fetch(0x048C, 64)
dump(data_048c, 0x048C, "$048C - dispatch handler")
scan_for_addresses(data_048c, 0x048C)
