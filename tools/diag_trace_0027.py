#!/usr/bin/env python3
"""Trace Z80 RAM 0x0027 changes frame by frame from boot."""
import json, urllib.request

API = "http://localhost:8081/api/v1"

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{API}{path}").read())

def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{API}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def read_z80_comm():
    mem = api_get(f"/cpu/memory?addr={0xA00020}&len=16")
    return mem.get("data", [])

# Fresh load
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

prev_27 = None
prev_24 = None
for frame in range(20):
    api_post("/emulator/step", {"frames": 1})
    comm = read_z80_comm()
    # Read Z80 entry point too
    entry = api_get(f"/cpu/memory?addr={0xA00000}&len=4")
    entry_data = entry.get("data", [])
    
    val_22 = comm[2]  # slot counter
    val_24 = comm[4]  # busy flag 1
    val_25 = comm[5]
    val_26 = comm[6]  # busy flag 2
    val_27 = comm[7]  # command byte
    
    changed = (val_27 != prev_27) or (val_24 != prev_24)
    marker = " <<<" if changed else ""
    if changed or frame < 10:
        print(f"Frame {frame:3d}: entry={' '.join(f'{b:02X}' for b in entry_data)} "
              f"0x22={val_22:02X} 0x24={val_24:02X} 0x25={val_25:02X} "
              f"0x26={val_26:02X} 0x27={val_27:02X}{marker}")
    prev_27 = val_27
    prev_24 = val_24

# Check M68K initialization code area for Z80 writes
print("\n=== Checking M68K ROM for writes to $A00027 ===")
# Read ROM around the init area
for search_start in [0x7200, 0x7300, 0x7380, 0x7100, 0x7000, 0x0300, 0x0400]:
    rom = api_get(f"/cpu/memory?addr={search_start}&len=256")
    data = rom.get("data", [])
    # Look for byte sequences that reference $A00027 or $0027
    for i in range(len(data) - 4):
        # Check for $A00027 in various forms
        # MOVE.B #xx,($A00027) → 13FC xx A0 0027 (but varies by addressing mode)
        # MOVE.B Dn,($A00027).L → 13C0 00A0 0027
        # CLR.B ($A00027).L → 4239 00A0 0027
        
        # Look for $00 $27 (Z80 offset) or $A0 $00 $27
        if i+2 < len(data) and data[i] == 0x00 and data[i+1] == 0x27:
            addr = search_start + i
            context = ' '.join(f'{b:02X}' for b in data[max(0,i-4):min(len(data),i+6)])
            print(f"  Found 00 27 at ROM ${addr:06X}: ...{context}...")
        if i+3 < len(data) and data[i] == 0xA0 and data[i+1] == 0x00 and data[i+2] == 0x27:
            addr = search_start + i
            context = ' '.join(f'{b:02X}' for b in data[max(0,i-4):min(len(data),i+6)])
            print(f"  Found A0 00 27 at ROM ${addr:06X}: ...{context}...")

# Also read M68K trace to understand what's been executing
print("\n=== M68K CPU State ===")
cpu_state = api_get("/cpu/state")
cpu = cpu_state.get("cpu", {})
print(f"  PC: {cpu.get('pc', '?')}")
d_regs = cpu.get("d", [])
a_regs = cpu.get("a", [])
for i in range(8):
    print(f"  D{i}={d_regs[i] if i < len(d_regs) else '?':08X}  A{i}={a_regs[i] if i < len(a_regs) else '?':08X}")
