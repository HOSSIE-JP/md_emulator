#!/usr/bin/env python3
"""Search handler 5 for references to key RAM addresses."""
import urllib.request, json

BASE = "http://localhost:8080/api/v1/cpu/memory"

def read_mem(addr, length):
    url = f"{BASE}?addr={addr}&len={length}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())["data"]

data = read_mem(0x8540, 512)

# Search for references to E0FF00xx pattern (FF00xx addresses)
targets = {0x66: "FF0066", 0x67: "FF0067"}
for i in range(len(data) - 3):
    if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x00:
        if data[i+3] in targets:
            addr = 0x8540 + i
            start = max(0, i - 6)
            end = min(len(data), i + 8)
            ctx = ' '.join('%02X' % data[j] for j in range(start, end))
            print(f"Ref to {targets[data[i+3]]} at ${addr:06X}: {ctx}")

# Search for FF019C, FF0198, FF019A, FF0116, FF010E, FF0106
for target_name, hi, lo in [
    ("FF019C", 0x01, 0x9C),
    ("FF0198", 0x01, 0x98),
    ("FF019A", 0x01, 0x9A),
    ("FF0116", 0x01, 0x16),
    ("FF010E", 0x01, 0x0E),
    ("FF0106", 0x01, 0x06),
]:
    for i in range(len(data) - 3):
        if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == hi and data[i+3] == lo:
            addr = 0x8540 + i
            start = max(0, i - 6)
            end = min(len(data), i + 8)
            ctx = ' '.join('%02X' % data[j] for j in range(start, end))
            print(f"Ref to {target_name} at ${addr:06X}: {ctx}")

# Also check for BSET/ORI that write to FF0066
# BSET #n, ($FF0067).B = 08F9 00nn 00FF 0067  (but this ROM uses E0FF mirror)
# ORI.W #nn, ($FF0066) = 0079 nnnn E0FF 0066
for i in range(len(data) - 7):
    w = (data[i] << 8) | data[i+1]
    if w == 0x0079:  # ORI.W
        if i + 7 < len(data):
            if data[i+4] == 0xE0 and data[i+5] == 0xFF and data[i+6] == 0x00 and data[i+7] == 0x66:
                val = (data[i+2] << 8) | data[i+3]
                addr = 0x8540 + i
                print(f"ORI.W #${val:04X}, ($FF0066) at ${addr:06X}")
    if w == 0x08F9:  # BSET
        if i + 7 < len(data):
            if data[i+4] == 0xE0 and data[i+5] == 0xFF and data[i+6] == 0x00 and data[i+7] == 0x67:
                bit = (data[i+2] << 8) | data[i+3]
                addr = 0x8540 + i
                print(f"BSET #{bit}, ($FF0067) at ${addr:06X}")
