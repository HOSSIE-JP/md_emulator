"""Check Z80 init continuation and M68K communication writes"""
import requests
BASE = "http://localhost:8080/api/v1"

s = requests.Session()

# Read Z80 init code continuation at $02D0-$0400
for start in [0x02D0, 0x0300, 0x0330, 0x0340]:
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA00000 + start, "len": 48}).json()
    data = mem.get("data", [])
    print(f"\nZ80 ${start:04X}:")
    for i in range(0, len(data), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        print(f"  ${start+i:04X}: {hex_str}")

# Check Z80 code at execution points we've seen
for pc in [0x034F, 0x087A, 0x0BFA, 0x0C07]:
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA00000 + pc, "len": 16}).json()
    data = mem.get("data", [])
    hex_str = ' '.join(f'{b:02X}' for b in data)
    print(f"\nZ80 code at ${pc:04X}: {hex_str}")

# Check what M68K wrote to Z80 RAM: compare init comm area
# Read areas typically used for XGM2 communication
for area_name, addr in [
    ("$0100-$01FF (data area)", 0x0100),
    ("$1800-$18FF (command area)", 0x1800),
    ("$1A00-$1AFF (PCM data?)", 0x1A00),
    ("$1B00-$1BFF (pointers?)", 0x1B00),
]:
    mem = s.get(f"{BASE}/cpu/memory",
                params={"addr": 0xA00000 + addr, "len": 64}).json()
    data = mem.get("data", [])
    nonzero = sum(1 for b in data if b != 0)
    print(f"\n{area_name}: {nonzero}/64 non-zero")
    for i in range(0, min(len(data), 64), 16):
        hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
        print(f"  ${addr+i:04X}: {hex_str}")

# Check what the apu state says about z80_m68k_write_count
apu = s.get(f"{BASE}/apu/state").json()
print(f"\nz80_m68k_write_count: {apu.get('z80_m68k_write_count', 'N/A')}")
print(f"z80_banked_read_log: {apu.get('z80_banked_read_log', [])[:10]}")
