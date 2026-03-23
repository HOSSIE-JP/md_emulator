"""Trace VBlank handler and SAT update routine"""
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

# Read vectors
r = api("GET", f"/api/v1/cpu/memory?addr=0&len=256")
vectors = r.get("data", [])

print("=== Exception Vectors ===")
vector_names = {
    0: "Initial SP", 4: "Initial PC", 8: "Bus Error", 12: "Address Error",
    16: "Illegal Instr", 20: "Zero Divide", 24: "CHK", 28: "TRAPV",
    32: "Privilege", 36: "Trace", 40: "Line A", 44: "Line F",
    96: "Spurious", 100: "Level 1 (TMS)", 104: "Level 2 (EXT)", 108: "Level 3",
    112: "Level 4 (HInt)", 116: "Level 5", 120: "Level 6 (VInt)", 124: "Level 7 (NMI)",
}
for offset, name in sorted(vector_names.items()):
    addr = (vectors[offset] << 24) | (vectors[offset+1] << 16) | (vectors[offset+2] << 8) | vectors[offset+3]
    print(f"  {offset:3d} ({name:20s}): 0x{addr:06X}")

# Read VBlank handler code
vint_addr = (vectors[120] << 24) | (vectors[121] << 16) | (vectors[122] << 8) | vectors[123]
print(f"\n=== VBlank handler at 0x{vint_addr:06X} ===")
r = api("GET", f"/api/v1/cpu/memory?addr={vint_addr}&len=256")
code = r.get("data", [])
print("Code bytes:")
for i in range(0, min(256, len(code)), 16):
    addr = vint_addr + i
    hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
    print(f"  0x{addr:06X}: {hex_str}")

# Read HInt handler
hint_addr = (vectors[112] << 24) | (vectors[113] << 16) | (vectors[114] << 8) | vectors[115]
print(f"\n=== HInt handler at 0x{hint_addr:06X} ===")
r = api("GET", f"/api/v1/cpu/memory?addr={hint_addr}&len=128")
code = r.get("data", [])
print("Code bytes:")
for i in range(0, min(128, len(code)), 16):
    addr = hint_addr + i
    hex_str = ' '.join(f'{code[i+j]:02X}' for j in range(min(16, len(code)-i)))
    print(f"  0x{addr:06X}: {hex_str}")

# Also check VDP writes near SAT address
# Let's search ROM for 0xBC00 pattern (SAT address setup in DMA)
print("\n=== ROM search for DMA to 0xBC00 ===")
# DMA target address is set via control port:
# First word: 01xx xxxx xxxx xxxx (VRAM write) where lower 14 bits = low address
# Second word: 0000 0000 00AA xxxx where AA = high 2 bits of address
# For 0xBC00: low 14 bits = 0x3C00, high 2 bits = 0x02
# First word bits: CD1:CD0 = 01 (VRAM write), A13:A0 = 0x3C00
# First word = 0100 + 3C00 = 0x7C00
# Second word: address bits[15:14] = 10b → bits[1:0] = 0x02, plus CD5=1 → bit 4+ = 0x80
# Second word = 0x0082 (for DMA VRAM write)
# Actually, for DMA: CD5 must be 1 → bits[4] of second word = 1
# Let me search for the raw bytes
r_rom = api("GET", f"/api/v1/cpu/memory?addr=0&len=524288")
rom = r_rom.get("data", [])
print(f"ROM size: {len(rom)} bytes")

# Search for control port sequence that sets address to 0xBC00
# VDP control port address: 0xC00004
# First word would have VRAM write (CD0=1) + address low 14 bits
# 0xBC00 = 1011 1100 0000 0000
# Address bits: A15:A14 = 10b = 2, A13:A0 = 11 1100 0000 0000 = 0x3C00
# First word format: CD1:CD0 = 01 (bits 15:14) + A13:A0 (bits 13:0)
# = 0b01_11_1100_0000_0000 = 0x7C00
# Look for 7C00 in ROM
target = 0x7C00
count = 0
for i in range(0, len(rom)-1, 2):
    word = (rom[i] << 8) | rom[i+1]
    if word == target:
        # Check context (±8 bytes)
        ctx_start = max(0, i-8)
        ctx_end = min(len(rom), i+10)
        ctx = ' '.join(f'{rom[j]:02X}' for j in range(ctx_start, ctx_end))
        # Highlight position
        print(f"  0x{i:06X}: ...{ctx}...")
        count += 1
        if count >= 20:
            break
print(f"Total matches for 0x7C00: {count}")
