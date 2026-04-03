"""Search Z80 RAM for bank register write patterns and check init code"""
import requests
BASE = "http://localhost:8080/api/v1"

s = requests.Session()

# Read entire Z80 RAM (8KB)
all_data = []
for offset in range(0, 0x2000, 0x100):
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA00000 + offset, "len": 0x100}).json()
    all_data.extend(mem.get("data", []))

print(f"Z80 RAM size: {len(all_data)} bytes")
print(f"Non-zero bytes: {sum(1 for b in all_data if b != 0)}")

# Search for LD ($6000), A = 0x32 0x00 0x60
print("\n=== LD ($6000), A pattern (32 00 60) ===")
for i in range(len(all_data) - 2):
    if all_data[i] == 0x32 and all_data[i+1] == 0x00 and all_data[i+2] == 0x60:
        ctx_start = max(0, i - 8)
        ctx_end = min(len(all_data), i + 8)
        ctx = ' '.join(f'{all_data[j]:02X}' for j in range(ctx_start, ctx_end))
        print(f"  Found at Z80 ${i:04X}: ...{ctx}...")

# Also search for OUT-based access (unlikely but check)
# OUT (C), r = ED xx pattern
print("\n=== Other $6000 patterns ===")
# LD HL, $6000 = 21 00 60
for i in range(len(all_data) - 2):
    if all_data[i] == 0x21 and all_data[i+1] == 0x00 and all_data[i+2] == 0x60:
        ctx_start = max(0, i - 4)
        ctx_end = min(len(all_data), i + 8)
        ctx = ' '.join(f'{all_data[j]:02X}' for j in range(ctx_start, ctx_end))
        print(f"  LD HL,$6000 at Z80 ${i:04X}: {ctx}")

# Read the init code at $02B7
print("\n=== Z80 init code at $02B7 ===")
mem = s.get(f"{BASE}/cpu/memory",
            params={"addr": 0xA002B7, "len": 64}).json()
data = mem.get("data", [])
for i in range(0, len(data), 16):
    hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
    addr = 0x02B7 + i
    print(f"  ${addr:04X}: {hex_str}")

# Also read around the bank setting code if found
# Read Z80 trace ring (last few entries) for PC addresses
apu = s.get(f"{BASE}/apu/state").json()
z80_pc = apu.get("z80_pc", 0)
bank = apu.get("z80_bank_68k_addr", "?")
bank_writes = apu.get("z80_bank_write_count", 0)
print(f"\nZ80 PC: {z80_pc}, Bank: {bank}, Bank writes: {bank_writes}")
