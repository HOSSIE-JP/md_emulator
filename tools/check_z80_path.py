#!/usr/bin/env python3
"""Add stderr tracing for $7C3C/$7DF6 path execution during one frame."""
import requests, time

API = "http://localhost:8080/api/v1"

# Check current state
state = requests.get(f"{API}/cpu/state").json()
m68k = state['cpu']['m68k']
print(f"Before: PC=${m68k['pc']:06X}, D2=${m68k['d'][2]:08X}")

# Read $FF0066 bit pattern
mem = requests.get(f"{API}/cpu/memory?addr={0xFF0066}&len=2").json()['data']
ff0066 = (mem[0] << 8) | mem[1]
print(f"$FF0066 = ${ff0066:04X} (bit 2 = {(ff0066>>2)&1})")

mem = requests.get(f"{API}/cpu/memory?addr={0xFF019C}&len=2").json()['data']  
ff019c = (mem[0] << 8) | mem[1]
print(f"$FF019C = ${ff019c:04X}")

mem = requests.get(f"{API}/cpu/memory?addr={0xFFA820}&len=2").json()['data']
ffa820 = (mem[0] << 8) | mem[1]
print(f"$FFA820 = ${ffa820:04X}")

# Run 5 frames
print("\n--- Running 5 frames ---")
for i in range(5):
    resp = requests.post(f"{API}/emulator/step", json={"count": 1})
    state = requests.get(f"{API}/cpu/state").json()
    m68k = state['cpu']['m68k']
    
    mem = requests.get(f"{API}/cpu/memory?addr={0xFF0066}&len=2").json()['data']
    ff0066 = (mem[0] << 8) | mem[1]
    
    mem = requests.get(f"{API}/cpu/memory?addr={0xFFA820}&len=2").json()['data']
    ffa820 = (mem[0] << 8) | mem[1]
    
    mem = requests.get(f"{API}/cpu/memory?addr={0xFF0064}&len=2").json()['data']
    ff0064 = (mem[0] << 8) | mem[1]
    
    z80_pc = state['cpu'].get('z80', {}).get('pc', 0)
    
    print(f"  Frame {i}: PC=${m68k['pc']:06X} $FF0066=${ff0066:04X} $FF0064=${ff0064:04X} $FFA820=${ffa820:04X} Z80_PC=${z80_pc:04X}")

# Check Z80 RAM communication area after frames
print("\n--- Z80 RAM communication area ---")
for base in [0xA00100, 0xA00160]:
    mem = requests.get(f"{API}/cpu/memory?addr={base}&len=16").json()['data']
    hexes = ' '.join(f'{b:02X}' for b in mem)
    print(f"  ${base:06X}: {hexes}")

# The key question: is $7DF6 path actually being reached?
# Let's check D3 after execution - if $7C3C executed, D3 should be set
print(f"\nD3 = ${state['cpu']['m68k']['d'][3]:08X}")
print(f"A0 = ${state['cpu']['m68k']['a'][0]:08X}")
