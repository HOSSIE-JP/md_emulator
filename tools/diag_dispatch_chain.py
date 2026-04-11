#!/usr/bin/env python3
"""Dispatch chain analysis - read key memory regions and RAM state."""
import urllib.request, json, sys

BASE = "http://localhost:8080/api/v1/cpu/memory"

def read_mem(addr, length):
    url = f"{BASE}?addr={addr}&len={length}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())["data"]

def read_word(addr):
    d = read_mem(addr, 2)
    return (d[0] << 8) | d[1]

def dump(addr, length, label):
    data = read_mem(addr, length)
    print(f"\n=== {label} (${addr:06X}-${addr+length-1:06X}) ===")
    for i in range(0, len(data), 16):
        h = ' '.join('%02X' % data[i+j] for j in range(min(16, len(data)-i)))
        print(f"  ${addr+i:06X}: {h}")
    return data

# 1. $048C function (64 bytes)
dump(0x048C, 64, "$048C function (called from handler completion)")

# 2. $04A4 function (64 bytes)
dump(0x04A4, 64, "$04A4 function (called from $6CB4)")

# 3. Handler 5 at $8540 (384 bytes to cover full function)
dump(0x8540, 384, "Handler 5 at $8540 (Z80 driver loader)")

# 4. Also read $6C8E handler 0 for context (128 bytes)
dump(0x6C8E, 128, "Handler 0 at $6C8E (sound reset)")

# 5. RAM state
print("\n=== RAM State ===")
labels = [
    (0xFF0062, "FF0062 (next dispatch step)"),
    (0xFF0064, "FF0064"),
    (0xFF0066, "FF0066 (flags)"),
    (0xFF01A0, "FF01A0 (current dispatch step)"),
    (0xFF0116, "FF0116"),
    (0xFF0198, "FF0198"),
    (0xFF019A, "FF019A"),
    (0xFF019C, "FF019C"),
    (0xFFA820, "FFA820 (retry counter?)"),
    (0xFF010E, "FF010E"),
    (0xFF0106, "FF0106"),
]
for addr, label in labels:
    val = read_word(addr)
    print(f"  {label}: 0x{val:04X} ({val})")

# 6. Dispatch table at $8BBC area
dump(0x8BBC, 64, "Dispatch table at $8BBC")
