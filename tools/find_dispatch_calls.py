#!/usr/bin/env python3
"""Find all calls to GEMS dispatch ($8BBC) in ROM."""
import requests

resp = requests.get("http://localhost:8080/api/v1/cpu/memory?addr=0&len=524288")
data = resp.json()['data']

print(f"ROM size: {len(data)} bytes")
print("Searching for BSR/JSR to $8BBC...")

for i in range(0, len(data)-5, 2):
    w = (data[i]<<8)|data[i+1]
    target = None
    call_type = None

    # BSR.W: $6100 $xxxx
    if w == 0x6100 and i+3 < len(data):
        offset = (data[i+2]<<8)|data[i+3]
        if offset >= 0x8000:
            offset -= 0x10000
        target = (i + 2 + offset) & 0xFFFFFF
        call_type = "BSR.W"

    # JSR absolute: $4EB9 $xxxx $xxxx
    elif w == 0x4EB9 and i+5 < len(data):
        target = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
        call_type = "JSR"

    # BSR PC-relative (4EBA): used in some contexts
    elif w == 0x4EBA and i+3 < len(data):
        offset = (data[i+2]<<8)|data[i+3]
        if offset >= 0x8000:
            offset -= 0x10000
        target = (i + 2 + offset) & 0xFFFFFF
        call_type = "BSR(PC)"

    if target == 0x8BBC:
        # Look backwards for PEA instructions to find arguments
        context = []
        for back in range(12, 0, -2):
            if i >= back:
                prev_w = (data[i-back]<<8)|data[i-back+1]
                context.append(f"${i-back:06X}: ${prev_w:04X}")
        # Specifically look for PEA #N pattern ($4878 $00NN) before the call
        args = []
        for back in range(2, 20, 2):
            if i >= back:
                pw = (data[i-back]<<8)|data[i-back+1]
                if i >= back+2:
                    ppw = (data[i-back-2]<<8)|data[i-back-1]
                    if ppw == 0x4878:
                        args.append(f"PEA #{pw}")
        print(f"\n  {call_type} $8BBC at ${i:06X} (return addr ${i+4:06X})")
        print(f"    Args found: {args if args else 'none detected'}")
        print(f"    Context: {' | '.join(context)}")
