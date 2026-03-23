"""Check what code is at PC=0x334 and trace execution"""
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

# Read ROM around PC=0x334 (decimal 820)
r = api("GET", f"/api/v1/cpu/memory?addr=800&len=48")
mem = r.get("data", [])
print("ROM at 0x000320:")
for i in range(0, len(mem), 16):
    addr = 0x320 + i
    hex_str = ' '.join(f'{mem[i+j]:02X}' for j in range(min(16, len(mem)-i)))
    print(f"  0x{addr:06X}: {hex_str}")

# CPU state
r = api("GET", "/api/v1/cpu/state")
m68k = r["cpu"]["m68k"]
print(f"\nPC: 0x{m68k['pc']:06X}")
print(f"SR: 0x{m68k['sr']:04X}")
for i in range(8):
    print(f"D{i}: 0x{m68k['d'][i]:08X}  A{i}: 0x{m68k['a'][i]:08X}")
print(f"stopped: {m68k['stopped']}")

# Single step a few instructions
print("\nStepping 10 instructions:")
for _ in range(10):
    r = api("GET", "/api/v1/cpu/state")
    m68k = r["cpu"]["m68k"]
    pc = m68k['pc']
    # Read instruction at PC
    r_mem = api("GET", f"/api/v1/cpu/memory?addr={pc}&len=6")
    instr_bytes = r_mem.get("data", [])
    instr_hex = ' '.join(f'{b:02X}' for b in instr_bytes[:6])
    print(f"  PC=0x{pc:06X}: {instr_hex}")
    # Step a tiny amount
    api("POST", "/api/v1/emulator/step", {"cycles": 4})

# Check work RAM
r = api("GET", f"/api/v1/cpu/memory?addr={0xFF0000}&len=256")
ram_data = r.get("data", [])
print("\nWork RAM 0xFF0000-0xFF00FF:")
for i in range(0, 256, 16):
    addr = 0xFF0000 + i
    hex_str = ' '.join(f'{ram_data[i+j]:02X}' for j in range(16))
    print(f"  0x{addr:06X}: {hex_str}")
