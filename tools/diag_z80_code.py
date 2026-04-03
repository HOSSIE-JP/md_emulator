"""Check Z80 RAM code/data to understand bank register behavior"""
import requests
BASE = "http://localhost:8080/api/v1"

s = requests.Session()

# Read Z80 RAM at critical areas
regions = [
    (0xA00000, 0x80, "Z80 init code $0000-$007F"),
    (0xA00080, 0x80, "Z80 code $0080-$00FF"),
    (0xA00100, 0x80, "Z80 code $0100-$017F"),
    (0xA01E00, 0x40, "Z80 comm area $1E00-$1E3F"),
    (0xA01F00, 0x40, "Z80 comm area $1F00-$1F3F"),
    (0xA01FC0, 0x40, "Z80 comm area $1FC0-$1FFF"),
]

for addr, length, desc in regions:
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": addr, "len": length}).json()
    data = mem.get("data", [])
    z80_base = addr - 0xA00000
    print(f"\n{desc}:")
    for i in range(0, len(data), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"  ${z80_base+i:04X}: {hex_str}  |{ascii_str}|")

# Check: is the Z80 init code writing to bank register?
# LD A, 1; LD ($6000), A  = 3E 01 32 00 60
# LD A, 7; LD ($6000), A  = 3E 07 32 00 60
data0 = s.get(f"{BASE}/cpu/memory",
              params={"addr": 0xA00000, "len": 32}).json().get("data", [])
print("\n=== Z80 init decode ===")
if len(data0) >= 32:
    # Check for 3E 01 32 00 60 pattern
    for i in range(len(data0) - 4):
        if data0[i] == 0x32 and data0[i+1] == 0x00 and data0[i+2] == 0x60:
            print(f"  Found LD ($6000), A at Z80 ${i:04X} "
                  f"(prev bytes: {' '.join(f'{data0[max(0,i-3):i][j]:02X}' for j in range(min(3,i)))})")
