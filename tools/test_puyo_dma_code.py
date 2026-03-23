"""Analyze VBlank DMA SAT setup code"""
import urllib.request
import json

BASE = "http://127.0.0.1:8111"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Wider context around 0x000824 (the DMA SAT code)
for start in [0x000800, 0x000840, 0x000580]:
    r = api("GET", f"/api/v1/cpu/memory?addr={start}&len=96")
    code = r.get("data", [])
    print(f"\n=== Code at 0x{start:06X} ===")
    for i in range(0, len(code), 16):
        addr = start + i
        hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
        print(f"  0x{addr:06X}: {hex_str}")

# Also read the subroutine at 0x064C and 0x0606 (called from VBlank)
for sub_addr in [0x064C, 0x0606, 0x0738]:
    r = api("GET", f"/api/v1/cpu/memory?addr={sub_addr}&len=128")
    code = r.get("data", [])
    print(f"\n=== Subroutine at 0x{sub_addr:06X} ===")
    for i in range(0, len(code), 16):
        addr = sub_addr + i
        hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
        print(f"  0x{addr:06X}: {hex_str}")

# Check what's at 0x5E4 (the CRAM/palette DMA routine found in VBlank)
# 0x5E4 contains: 33 FC 40 00 00 C0 00 04 + 33 FC 00 03 00 C0 00 04
# That is: MOVE.W #$4000, $C00004; MOVE.W #$0003, $C00004
# Address = $4000_0003 → address = (0x4000 & 0x3FFF) << 0 | (0x0003 & 3) << 14 = 0x0000 | 0xC000 = 0xC000
# Code = (0x4000 >> 14) & 3 = 1, (0x0003 >> 4) & 0xF = 0 → code = 0x01 (VRAM write)
# Combined: VRAM write to address 0xC000
# Then: loop writing 0x700 words to VRAM from (A1) which points to FF:C000 (work RAM)
print("\n=== Check SAT DMA subroutine path ===")
# Let's look at the sub at 0x064C more carefully
r = api("GET", f"/api/v1/cpu/memory?addr={0x064C}&len=256")
code = r.get("data", [])
print(f"\n=== Full sub @ 0x064C ===")
for i in range(0, len(code), 16):
    addr = 0x064C + i
    hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
    print(f"  0x{addr:06X}: {hex_str}")
