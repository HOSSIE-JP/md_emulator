#!/usr/bin/env python3
"""Trace key PC addresses during frame execution to verify Z80 access path."""
import requests, json, time

API = "http://localhost:8080/api/v1"

def get_state():
    return requests.get(f"{API}/cpu/state").json()

def read_mem(addr, length):
    return requests.get(f"{API}/cpu/memory?addr={addr}&len={length}").json()['data']

# Get initial state
state = get_state()
m68k = state['cpu']['m68k']
print(f"Initial PC=${m68k['pc']:06X}, D2=${m68k['d'][2]:08X}")
print(f"$FF0066 = {read_mem(0xFF0066, 2)}")
print(f"$FF019C = {read_mem(0xFF019C, 4)}")
print(f"$FFA820 = {read_mem(0xFFA820, 2)}")

# Run one frame and look at the PC trace
print("\n--- Running 1 frame ---")
resp = requests.post(f"{API}/emulator/step", json={"count": 1})
print(f"Step result: {resp.status_code}")

state = get_state()
m68k = state['cpu']['m68k']
print(f"After 1 frame: PC=${m68k['pc']:06X}")
print(f"$FF0066 = {read_mem(0xFF0066, 2)}")
print(f"$FFA820 = {read_mem(0xFFA820, 2)}")

# Check Z80 state
z80 = state['cpu'].get('z80', {})
if z80:
    print(f"Z80 PC=${z80.get('pc', 'N/A'):04X}")
    print(f"Z80 halted={z80.get('halted', 'N/A')}")
else:
    print("Z80 state not available in response")

# Check Z80 RAM at $A00100-$A00110 (GEMS communication area)
print(f"\nZ80 RAM $A00100-$A00110:")
z80ram = read_mem(0xA00100, 32)
for off in range(0, 32, 16):
    hexes = ' '.join(f'{b:02X}' for b in z80ram[off:off+16])
    print(f"  ${0xA00100+off:06X}: {hexes}")

# Check Z80 RAM $A00000-$A00020 (beginning of Z80 program)
print(f"\nZ80 RAM start $A00000-$A00020:")
z80prog = read_mem(0xA00000, 32)
hexes = ' '.join(f'{b:02X}' for b in z80prog[:32])
print(f"  ${0xA00000:06X}: {hexes}")
