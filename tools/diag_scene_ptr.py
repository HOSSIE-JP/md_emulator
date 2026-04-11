#!/usr/bin/env python3
"""Search for what sets $FF0306 and trace the scene function pointer lifecycle.
Also check if there's an init table that should include $8300."""
import requests

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

def step(n=1):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n})
    r.raise_for_status()

def get_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def read_long(addr):
    d = get_mem(addr, 4)
    return (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]

def main():
    load_rom()
    
    # Search ROM for E0FF0306 pattern
    print("References to $E0FF0306 (scene function pointer):")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 3):
            if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x03 and data[i+3] == 0x06:
                addr = chunk_start + i
                s = max(0, i - 8)
                e = min(len(data), i + 8)
                ctx = ' '.join(f'{b:02X}' for b in data[s:e])
                print(f"  ${addr:06X}: {ctx}")
    
    # Search for E0FF005E (VBlank scene controller)
    print("\nReferences to $E0FF005E (VBlank scene controller):")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(len(data) - 3):
            if data[i] == 0xE0 and data[i+1] == 0xFF and data[i+2] == 0x00 and data[i+3] == 0x5E:
                addr = chunk_start + i
                s = max(0, i - 8)
                e = min(len(data), i + 8)
                ctx = ' '.join(f'{b:02X}' for b in data[s:e])
                print(f"  ${addr:06X}: {ctx}")
    
    # Trace $FF0306 during init frames
    print("\n$FF0306 tracking during init (frame by frame):")
    for frame in range(1, 16):
        step(1)
        ff0306 = read_long(0xFF0306)
        ff005e = read_long(0xFF005E)
        ff0066 = get_mem(0xFF0066, 2)
        ff0066_w = (ff0066[0] << 8) | ff0066[1]
        print(f"  Frame {frame:3d}: $FF0306=${ff0306:08X}, $FF005E=${ff005e:08X}, $FF0066=${ff0066_w:04X}")
    
    # Check if there's a function pointer table near the addresses we found
    # Look at ROM around $4E1A to see if there's a table of function pointers
    print("\nChecking ROM area around $4E00 for function pointer table:")
    data = get_mem(0x4E00, 0x40)
    for i in range(0, len(data) - 3, 4):
        val = (data[i] << 24) | (data[i+1] << 16) | (data[i+2] << 8) | data[i+3]
        print(f"  ${0x4E00+i:06X}: ${val:08X}")
    
    # Also dump the work RAM area $FF0300-$FF0320 to see what's there
    print("\nWork RAM $FF0300-$FF0320:")
    data = get_mem(0xFF0300, 0x20)
    for i in range(0, len(data) - 3, 4):
        val = (data[i] << 24) | (data[i+1] << 16) | (data[i+2] << 8) | data[i+3]
        print(f"  $FF{0x0300+i:04X}: ${val:08X}")
    
    # Check if there's a table of phase functions somewhere
    # The game might use a state machine with phase numbers
    # Look for table of pointers that includes $8300 or $8600
    print("\nSearching ROM for tables containing $00008300:")
    for chunk_start in range(0, 0x10000, 0x4000):
        data = get_mem(chunk_start, 0x4000)
        for i in range(0, len(data) - 3, 2):
            val = (data[i] << 24) | (data[i+1] << 16) | (data[i+2] << 8) | data[i+3]
            if val == 0x00008300:
                # Check if there are other reasonable pointers nearby
                ptrs = []
                for j in range(-16, 20, 4):
                    idx = i + j
                    if 0 <= idx < len(data) - 3:
                        p = (data[idx] << 24) | (data[idx+1] << 16) | (data[idx+2] << 8) | data[idx+3]
                        ptrs.append(f"${p:08X}")
                print(f"  ${chunk_start+i:06X}: {' '.join(ptrs)}")

if __name__ == "__main__":
    main()
