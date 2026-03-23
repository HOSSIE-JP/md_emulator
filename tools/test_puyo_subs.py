"""Check subroutine at 0x0880 and 0x07BC"""
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

# Read subroutines
for sub_addr in [0x0880, 0x07BC, 0x0570, 0x054C, 0x7378]:
    r = api("GET", f"/api/v1/cpu/memory?addr={sub_addr}&len=128")
    code = r.get("data", [])
    print(f"\n=== Sub at 0x{sub_addr:06X} ===")
    for i in range(0, min(128, len(code)), 16):
        addr = sub_addr + i
        hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
        print(f"  0x{addr:06X}: {hex_str}")

# Also carefully re-read VBlank handler
r = api("GET", f"/api/v1/cpu/memory?addr={0x524}&len=80")
code = r.get("data", [])
print(f"\n=== VBlank handler 0x000524 ===")
for i in range(0, min(80, len(code)), 2):
    addr = 0x524 + i
    word = (code[i] << 8) | code[i+1]
    
    # Identify BSR/JSR targets
    note = ""
    if (word & 0xFF00) == 0x6100:  # BSR.B
        offset = code[i+1]
        if offset > 127:
            offset = offset - 256
        target = addr + 2 + offset
        note = f"  ; BSR.B ${target:06X}"
    elif word == 0x6100:  # BSR.W
        if i+3 < len(code):
            offset = (code[i+2] << 8) | code[i+3]
            if offset > 32767:
                offset = offset - 65536
            target = addr + 2 + offset
            note = f"  ; BSR.W ${target:06X}"
    elif word == 0x4EB9:  # JSR
        if i+5 < len(code):
            target = (code[i+2] << 24) | (code[i+3] << 16) | (code[i+4] << 8) | code[i+5]
            note = f"  ; JSR ${target:06X}"
    
    print(f"  0x{addr:06X}: {code[i]:02X} {code[i+1]:02X}{note}")
