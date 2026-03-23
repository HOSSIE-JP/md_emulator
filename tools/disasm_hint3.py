"""Disassemble the FULL HInt handler to see all VDP writes."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Handler starts at 0x6AC through at least 0x70A (RTR)
mem = api_get(f"/cpu/memory?addr={0x6AC}&len=128")["data"]

print("Full HInt handler disassembly:")
print(f"  (raw bytes from 0x6AC to 0x{0x6AC+127:04X})")
for i in range(0, 128, 2):
    addr = 0x6AC + i
    if i + 1 < len(mem):
        word = (mem[i] << 8) | mem[i+1]
        print(f"  0x{addr:04X}: 0x{word:04X}  ({mem[i]:3d} {mem[i+1]:3d})")
    if addr >= 0x070A:
        break

# Also check auto-increment register
regs = api_get("/vdp/registers")
auto_inc = regs["registers"][0x0F]
print(f"\nVDP auto-increment (R15): {auto_inc}")
