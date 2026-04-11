#!/usr/bin/env python3
"""Search ROM for any instruction that sets bit 3 of $FF0066/$FF0067"""
import json, sys, requests

r = requests.get("http://localhost:8080/api/v1/cpu/memory", params={"addr": 0, "len": 524288})
d = r.json()["data"]

count = 0
for i in range(len(d) - 8):
    # BSET #3,(abs).L = 08F9 0003 xxxx xxxx
    if d[i] == 0x08 and d[i+1] == 0xF9 and d[i+2] == 0x00 and d[i+3] == 0x03:
        if i + 7 < len(d):
            addr = (d[i+4] << 24) | (d[i+5] << 16) | (d[i+6] << 8) | d[i+7]
            masked = addr & 0x00FFFFFF
            if masked in (0xFF0067, 0xFF0066):
                print(f"  BSET #3,(abs).L at ${i:06X}: target ${addr:08X}")
                count += 1

    # BSET #3,(abs).W = 08F8 0003 xxxx  (wait, BSET #imm,(abs).W is not standard)
    # Actually BSET uses EA, so BSET #3,(xxx).L for absolute long
    
    # ORI.B #xx,(abs).L = 0039 00xx xxxx xxxx
    if d[i] == 0x00 and d[i+1] == 0x39 and i + 7 < len(d):
        val = d[i+3]
        if val & 0x08:
            addr = (d[i+4] << 24) | (d[i+5] << 16) | (d[i+6] << 8) | d[i+7]
            masked = addr & 0x00FFFFFF
            if masked in (0xFF0067, 0xFF0066):
                print(f"  ORI.B #${val:02X},(abs).L at ${i:06X}: sets bit 3, target ${addr:08X}")
                count += 1

    # ORI.W #xxxx,(abs).L = 0079 xxxx xxxx xxxx
    if d[i] == 0x00 and d[i+1] == 0x79 and i + 9 < len(d):
        val = (d[i+2] << 8) | d[i+3]
        if val & 0x0008:
            addr = (d[i+4] << 24) | (d[i+5] << 16) | (d[i+6] << 8) | d[i+7]
            masked = addr & 0x00FFFFFF
            if masked in (0xFF0066, 0xFF0067):
                print(f"  ORI.W #${val:04X},(abs).L at ${i:06X}: sets bit 3, target ${addr:08X}")
                count += 1

    # MOVE.W #xxxx,(abs).L = 33FC xxxx xxxx xxxx (sets bit 3 if xxxx has bit 3)
    if d[i] == 0x33 and d[i+1] == 0xFC and i + 9 < len(d):
        val = (d[i+2] << 8) | d[i+3]
        if val & 0x0008:
            addr = (d[i+4] << 24) | (d[i+5] << 16) | (d[i+6] << 8) | d[i+7]
            masked = addr & 0x00FFFFFF
            if masked in (0xFF0066, 0xFF0067):
                print(f"  MOVE.W #${val:04X},(abs).L at ${i:06X}: has bit 3, target ${addr:08X}")
                count += 1

    # MOVE.B #xx,(abs).L = 13FC 00xx xxxx xxxx
    if d[i] == 0x13 and d[i+1] == 0xFC and i + 7 < len(d):
        val = d[i+3]
        if val & 0x08:
            addr = (d[i+4] << 24) | (d[i+5] << 16) | (d[i+6] << 8) | d[i+7]
            masked = addr & 0x00FFFFFF
            if masked in (0xFF0066, 0xFF0067):
                print(f"  MOVE.B #${val:02X},(abs).L at ${i:06X}: has bit 3, target ${addr:08X}")
                count += 1

print(f"\nTotal bit 3 setters found: {count}")
