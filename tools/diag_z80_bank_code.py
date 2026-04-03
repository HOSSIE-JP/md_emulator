"""Check Z80 RAM $01FA and surrounding bank-related data"""
import requests
BASE = "http://localhost:8080/api/v1"

s = requests.Session()

# Read Z80 RAM around $01F0-$01FF (the bank address storage)
mem = s.get(f"{BASE}/cpu/memory",
            params={"addr": 0xA001E0, "len": 64}).json()
data = mem.get("data", [])
print("Z80 RAM $01E0-$021F:")
for i in range(0, len(data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
    print(f"  ${0x01E0+i:04X}: {hex_str}")

# Specifically check $01FA
if len(data) > 0x1A:
    val_01fa = data[0x1A]  # offset from $01E0
    print(f"\n$01FA = 0x{val_01fa:02X}")
    print(f"$01FB = 0x{data[0x1B]:02X}")

# Read the full bank setting routine at $0280-$02B0
mem2 = s.get(f"{BASE}/cpu/memory",
             params={"addr": 0xA00280, "len": 64}).json()
data2 = mem2.get("data", [])
print("\nBank setting routine ($0280-$02BF):")
for i in range(0, len(data2), 16):
    hex_str = ' '.join(f'{b:02X}' for b in data2[i:i+16])
    print(f"  ${0x0280+i:04X}: {hex_str}")

# Decode the setBank routine
print("\n=== Decoded bank setting routine ===")
i = 0
base = 0x0280
while i < len(data2) and i < 48:
    addr = base + i
    b = data2[i]
    if b == 0xCF:
        print(f"  ${addr:04X}: RST $08")
        i += 1
    elif b == 0x3A and i+2 < len(data2):
        nn = data2[i+1] | (data2[i+2] << 8)
        print(f"  ${addr:04X}: LD A, (${nn:04X})")
        i += 3
    elif b == 0x21 and i+2 < len(data2):
        nn = data2[i+1] | (data2[i+2] << 8)
        print(f"  ${addr:04X}: LD HL, ${nn:04X}")
        i += 3
    elif b == 0x77:
        print(f"  ${addr:04X}: LD (HL), A   ; write to bank reg")
        i += 1
    elif b == 0x0F:
        print(f"  ${addr:04X}: RRCA")
        i += 1
    elif b == 0xC9:
        print(f"  ${addr:04X}: RET")
        i += 1
        break
    elif b == 0xC3 and i+2 < len(data2):
        nn = data2[i+1] | (data2[i+2] << 8)
        print(f"  ${addr:04X}: JP ${nn:04X}")
        i += 3
    elif b == 0xAF:
        print(f"  ${addr:04X}: XOR A")
        i += 1
    elif b == 0x7E:
        print(f"  ${addr:04X}: LD A, (HL)")
        i += 1
    elif b == 0x23:
        print(f"  ${addr:04X}: INC HL")
        i += 1
    elif b == 0x2B:
        print(f"  ${addr:04X}: DEC HL")
        i += 1
    elif b == 0x46:
        print(f"  ${addr:04X}: LD B, (HL)")
        i += 1
    elif b == 0x32 and i+2 < len(data2):
        nn = data2[i+1] | (data2[i+2] << 8)
        print(f"  ${addr:04X}: LD (${nn:04X}), A")
        i += 3
    elif b == 0x3E and i+1 < len(data2):
        print(f"  ${addr:04X}: LD A, ${data2[i+1]:02X}")
        i += 2
    elif b == 0xCD and i+2 < len(data2):
        nn = data2[i+1] | (data2[i+2] << 8)
        print(f"  ${addr:04X}: CALL ${nn:04X}")
        i += 3
    elif b == 0x7D:
        print(f"  ${addr:04X}: LD A, L")
        i += 1
    elif b == 0x7C:
        print(f"  ${addr:04X}: LD A, H")
        i += 1
    elif b == 0xCB and i+1 < len(data2):
        print(f"  ${addr:04X}: CB prefix: ${data2[i+1]:02X}")
        i += 2
    else:
        print(f"  ${addr:04X}: ??? ${b:02X}")
        i += 1
