#!/usr/bin/env python3
"""Check ROM data at GEMS binary offset and trace Z80 RAM with fine stepping."""
import json, urllib.request

API = "http://localhost:8081/api/v1"

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{API}{path}").read())

def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{API}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

# Fresh load
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Read ROM at $7E000 (GEMS binary area)
rom = api_get(f"/cpu/memory?addr={0x7E000}&len=64")
rom_data = rom.get("data", [])
print("=== ROM data at $7E000 (GEMS binary) ===")
for row in range(4):
    offset = row * 16
    hex_str = ' '.join(f'{b:02X}' for b in rom_data[offset:offset+16])
    print(f"  ${0x7E000+offset:06X}: {hex_str}")

print(f"\n  ROM[$7E024]={rom_data[0x24]:02X}  ROM[$7E025]={rom_data[0x25]:02X}  "
      f"ROM[$7E026]={rom_data[0x26]:02X}  ROM[$7E027]={rom_data[0x27]:02X}")

# Run 1.5 frames to get close to the upload time
api_post("/emulator/step", {"frames": 1})
print("(Ran 1 frame first...)")

# Now step with small increments
print("\n=== Fine-grained trace of Z80 RAM comm area ===")
prev_snapshot = None
total_cycles = 127856  # approx 1 frame
for i in range(2000):
    api_post("/emulator/step", {"cycles": 488})
    total_cycles += 488
    
    comm = api_get(f"/cpu/memory?addr={0xA00020}&len=16").get("data", [])
    entry = api_get(f"/cpu/memory?addr={0xA00000}&len=4").get("data", [])
    
    snapshot = (tuple(entry), tuple(comm))
    if snapshot != prev_snapshot:
        entry_str = ' '.join(f'{b:02X}' for b in entry)
        comm_str = ' '.join(f'{b:02X}' for b in comm)
        print(f"  Step {i:4d} (cyc ~{total_cycles:7d}): entry=[{entry_str}] "
              f"comm=[{comm_str}] 0x27={comm[7]:02X}")
        prev_snapshot = snapshot
    
    # Stop after 0x27 stabilizes at 0x83
    if comm[7] == 0x83 and i > 20:
        print(f"  ... (0x27 stabilized at 0x83)")
        break

print(f"\nTotal cycles stepped: {total_cycles}")
