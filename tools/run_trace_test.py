#!/usr/bin/env python3
"""Load ROM and run frames, then check trace log."""
import requests, subprocess

API = "http://localhost:8080/api/v1"

# Load ROM
resp = requests.post(f"{API}/emulator/load-rom-path", 
                     json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {resp.status_code}")

# Run 100 frames
resp = requests.post(f"{API}/emulator/step", json={"count": 100})
print(f"Step 100: {resp.status_code}")

# Check state
state = requests.get(f"{API}/cpu/state").json()
m68k = state['cpu']['m68k']
print(f"After 100f: PC=${m68k['pc']:06X}")

# Run 5 more frames  
resp = requests.post(f"{API}/emulator/step", json={"count": 5})
print(f"Step 5: {resp.status_code}")

state = requests.get(f"{API}/cpu/state").json()
m68k = state['cpu']['m68k']
print(f"After 105f: PC=${m68k['pc']:06X}")
print(f"D0=${m68k['d'][0]:08X} D2=${m68k['d'][2]:08X} D3=${m68k['d'][3]:08X}")
