"""Detailed disassembly of DMA routines"""
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

# Read wider range
for base_addr in [0x0007E0, 0x000850]:
    r = api("GET", f"/api/v1/cpu/memory?addr={base_addr}&len=128")
    code = r.get("data", [])
    print(f"\n=== Code at 0x{base_addr:06X} ===")
    for i in range(0, len(code), 2):
        addr = base_addr + i
        if i + 1 < len(code):
            word = (code[i] << 8) | code[i+1]
            # Simple opcode identification
            note = ""
            if (word & 0xC000) == 0x8000 and (word & 0xFF00) >= 0x8000:
                reg = (word >> 8) & 0x1F
                val = word & 0xFF
                note = f"  ; VDP REG {reg} = 0x{val:02X}"
            print(f"  0x{addr:06X}: {code[i]:02X} {code[i+1]:02X} = 0x{word:04X}{note}")

# The DMA routine at 0x850 is interesting:
# 0x850: 43 F9 00 FF 0E 86    LEA $FF0E86, A1  (source address in RAM)
# 0x856: 33 FC 7C 00 00 C0 00 04   MOVE.W #$7C00, $C00004 (first ctrl word)
# 0x85E: 33 FC 00 02 00 C0 00 04   MOVE.W #$0002, $C00004 (second ctrl word)
# 
# First: 7C00 → CD1:CD0 = 01, A13:A0 = 0x3C00
# Second: 0002 → A15:A14 = 10, CD5:CD2 = 0000 → code = 0x01 (VRAM write, NO DMA!)
# Address = 0x3C00 | (0x02 << 14) = 0x3C00 | 0x8000 = 0xBC00
# 
# So this sets up VRAM write to 0xBC00 (SAT!) but with NO DMA flag.
# Then it does a loop: MOVE.W (A1)+, $C00000 (data port)
# This is a CPU copy of SAT data from work RAM 0xFF0E86

print("\n\n=== SAT copy routine analysis at 0x000850 ===")
r = api("GET", f"/api/v1/cpu/memory?addr=0x000850&len=48")
code = r.get("data", [])
for i in range(0, len(code), 16):
    addr = 0x850 + i
    hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
    print(f"  0x{addr:06X}: {hex_str}")

# Decode:
# 0x850: 43 F9 00 FF 0E 86  → LEA $FF0E86, A1
# 0x856: 33 FC 7C 00 00 C0 00 04 → MOVE.W #$7C00, $00C00004
# 0x85E: 33 FC 00 02 00 C0 00 04 → MOVE.W #$0002, $00C00004
# Address = (0x7C00 & 0x3FFF) | ((0x0002 & 0x03) << 14)
#         = 0x3C00 | (2 << 14) = 0x3C00 | 0x8000 = 0xBC00
# Code = ((0x7C00 >> 14) & 3) | (((0x0002 >> 4) & 0xF) << 2)
#       = 1 | 0 = 0x01 → VRAM write (no DMA)
print(f"\nAddress calculation: 0x3C00 | (2<<14) = 0x{0x3C00 | (2<<14):04X}")
print(f"Code: {((0x7C00 >> 14) & 3)} | {(((0x0002 >> 4) & 0xF) << 2)} = {((0x7C00 >> 14) & 3) | (((0x0002 >> 4) & 0xF) << 2)}")

# 0x866: 30 39 00 FF 0D E4  → MOVE.W $FF0DE4, D0 (loop count)
# 0x86C: 53 40              → SUBQ.W #1, D0
# 0x86E: 33 D9 00 C0 00 00  → MOVE.W (A1)+, $C00000 (write word to VDP data port)
# 0x874: 51 C8 FF F8        → DBRA D0, -8 (loop back to 0x86E)
# 0x878: 42 79 00 FF 0D E4  → CLR.W $FF0DE4
# 0x87E: 4E 75              → RTS

# So: This routine copies $FF0DE4 words from $FF0E86 to VRAM $BC00 via data port
# This is the SAT update routine!

# Check the work RAM SAT buffer
r = api("GET", f"/api/v1/cpu/memory?addr={0xFF0DE4}&len=4")
count_data = r.get("data", [])
count = (count_data[0] << 8) | count_data[1]
print(f"\nSAT copy count at $FF0DE4: {count}")

r = api("GET", f"/api/v1/cpu/memory?addr={0xFF0E86}&len=128")
sat_ram = r.get("data", [])
print(f"\nWork RAM SAT buffer at $FF0E86:")
for i in range(0, 128, 16):
    addr = 0xFF0E86 + i
    hex_str = ' '.join(f'{sat_ram[i+j]:02X}' for j in range(16))
    print(f"  0x{addr:06X}: {hex_str}")
