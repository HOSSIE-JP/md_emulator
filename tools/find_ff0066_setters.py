#!/usr/bin/env python3
"""Find all code paths that set bit 3 of $FF0066/$FF0067."""
import requests

resp = requests.get("http://localhost:8080/api/v1/cpu/memory?addr=0&len=524288")
data = resp.json()['data']

print(f"ROM size: {len(data)} bytes")

# Method 1: Search for MOVE.W with $FF0066 destination that includes bit 3
# ORI.W #$0008, D0 = $0040 $0008 (but ORI to memory is different)
# ORI.W #$0008, ($E0FF0066).L = $0079 $0008 $E0FF $0066
print("\n--- Searching for ORI.W #$0008 to $E0FF0066 ---")
pattern1 = [0x00, 0x79, 0x00, 0x08, 0xE0, 0xFF, 0x00, 0x66]
for i in range(len(data) - len(pattern1)):
    if data[i:i+len(pattern1)] == pattern1:
        print(f"  Found ORI.W #$0008, ($E0FF0066) at ${i:06X}")

# Method 2: ORI.W #$0008 to register (D0 etc)  = $0040 $0008
# Then MOVE.W Dn, ($E0FF0066).L or ($FF0066).W
print("\n--- Searching for $83F4 area (MOVE.W D0, ($E0FF0066)) ---")
# $33C0 $E0FF $0066 = MOVE.W D0, ($E0FF0066).L
pattern2 = [0x33, 0xC0, 0xE0, 0xFF, 0x00, 0x66]
for i in range(len(data) - len(pattern2)):
    if data[i:i+len(pattern2)] == pattern2:
        print(f"  Found MOVE.W D0, ($E0FF0066).L at ${i:06X}")

# Method 3: MOVE.W D2, ($E0FF0066).L = $33C2 $E0FF $0066
pattern3 = [0x33, 0xC2, 0xE0, 0xFF, 0x00, 0x66]
for i in range(len(data) - len(pattern3)):
    if data[i:i+len(pattern3)] == pattern3:
        print(f"  Found MOVE.W D2, ($E0FF0066).L at ${i:06X}")

# Method 4: Any MOVE.W Dx, ($E0FF0066).L = $33Cx $E0FF $0066
print("\n--- Searching for MOVE.W Dn, ($E0FF0066).L ---")
for reg in range(8):
    pattern = [0x33, 0xC0 | reg, 0xE0, 0xFF, 0x00, 0x66]
    for i in range(len(data) - len(pattern)):
        if data[i:i+len(pattern)] == pattern:
            print(f"  Found MOVE.W D{reg}, ($E0FF0066).L at ${i:06X}")

# Method 5: BSET #3, ($E0FF0067)
# BSET #n is $08F9 (absolute long) or $08B9 (immediate)
# $08F9 $0003 $E0FF $0067
print("\n--- Searching for BSET/ORI to $FF0067 bit 3 ---")
pattern4 = [0x08, 0xF9, 0x00, 0x03, 0xE0, 0xFF, 0x00, 0x67]
for i in range(len(data) - len(pattern4)):
    if data[i:i+len(pattern4)] == pattern4:
        print(f"  Found BSET #3, ($E0FF0067) at ${i:06X}")

# ORI.B #$08, ($E0FF0067).L = $0039 $0008 $E0FF $0067
pattern5 = [0x00, 0x39, 0x00, 0x08, 0xE0, 0xFF, 0x00, 0x67]
for i in range(len(data) - len(pattern5)):
    if data[i:i+len(pattern5)] == pattern5:
        print(f"  Found ORI.B #$08, ($E0FF0067) at ${i:06X}")

# Method 6: Search for Handler 1 callers (JSR/BSR $8292)
print("\n--- Searching for calls to Handler 1 ($8292) ---")
for i in range(0, len(data)-5, 2):
    w = (data[i]<<8)|data[i+1]
    target = None
    if w == 0x4EB9 and i+5 < len(data):  # JSR abs
        target = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
    elif w == 0x4EBA and i+3 < len(data):  # BSR PC-rel
        offset = (data[i+2]<<8)|data[i+3]
        if offset >= 0x8000:
            offset -= 0x10000
        target = (i + 2 + offset) & 0xFFFFFF
    if target == 0x8292:
        print(f"  Call to $8292 at ${i:06X}")

# Method 7: Search for ORI.W #$0008, D0 anywhere followed by write to $FF0066
print("\n--- Searching for ORI.W #$0008, D0 ($0040 $0008) ---")
for i in range(0, len(data)-3, 2):
    w1 = (data[i]<<8)|data[i+1]
    w2 = (data[i+2]<<8)|data[i+3]
    if w1 == 0x0040 and w2 == 0x0008:
        context_after = ""
        if i+9 < len(data):
            for j in range(i+4, min(i+20, len(data)-1), 2):
                wj = (data[j]<<8)|data[j+1]
                context_after += f"${wj:04X} "
        print(f"  ORI.W #$0008, D0 at ${i:06X}, followed by: {context_after}")
