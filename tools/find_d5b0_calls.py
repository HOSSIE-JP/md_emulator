#!/usr/bin/env python3
"""Find all calls to $D5B0 (sound update) in ROM."""
import requests

resp = requests.get("http://localhost:8080/api/v1/cpu/memory?addr=0&len=524288")
data = resp.json()['data']

print("Searching for calls to $D5B0...")
for i in range(0, len(data)-5, 2):
    w = (data[i]<<8)|data[i+1]
    target = None
    call_type = None
    
    if w == 0x4EB9 and i+5 < len(data):  # JSR absolute
        target = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
        call_type = "JSR"
    elif w == 0x4EBA and i+3 < len(data):  # JSR (d16,PC) 
        offset = (data[i+2]<<8)|data[i+3]
        if offset >= 0x8000:
            offset -= 0x10000
        target = (i + 2 + offset) & 0xFFFFFF
        call_type = "BSR(PC)"

    if target == 0xD5B0:
        # Context
        before = ""
        for b in range(min(i, 8), 0, -2):
            pw = (data[i-b]<<8)|data[i-b+1]
            before += f"${pw:04X} "
        print(f"  {call_type} $D5B0 at ${i:06X}, context before: {before}")
