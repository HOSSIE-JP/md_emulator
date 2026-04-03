#!/usr/bin/env python3
"""Debug M68K state after loading the correct ROM."""
import requests, json

BASE = "http://localhost:8080/api/v1"

def api(method, path, **kwargs):
    r = getattr(requests, method)(f"{BASE}{path}", **kwargs)
    r.raise_for_status()
    return r.json()

# Load correct ROM
api("post", "/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})

# Step 1 frame
api("post", "/emulator/step", json={"frames": 1})

# Get full CPU state
cpu = api("get", "/cpu/state")

# Extract M68K from nested structure
def find_m68k(d, path=""):
    if isinstance(d, dict):
        if "pc" in d and "sr" in d:
            return d, path
        for k, v in d.items():
            result = find_m68k(v, f"{path}.{k}")
            if result:
                return result
    return None

result = find_m68k(cpu)
if result:
    m68k, path = result
    print(f"M68K found at: {path}")
    for k in ["pc", "sr", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7"]:
        v = m68k.get(k, 0)
        print(f"  {k}: 0x{v:08X}" if isinstance(v, int) else f"  {k}: {v}")
    # Check address registers
    for k in ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"]:
        v = m68k.get(k, 0)
        print(f"  {k}: 0x{v:08X}" if isinstance(v, int) else f"  {k}: {v}")
    for k in ["ssp", "usp"]:
        v = m68k.get(k, 0)
        print(f"  {k}: 0x{v:08X}" if isinstance(v, int) else f"  {k}: {v}")
else:
    print("M68K state not found! Dumping top-level keys:")
    def dump_keys(d, prefix="", depth=0):
        if depth > 3:
            return
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    print(f"{prefix}{k}: {{...}}")
                    dump_keys(v, prefix + "  ", depth + 1)
                elif isinstance(v, list):
                    print(f"{prefix}{k}: [{len(v)} items]")
                elif isinstance(v, int) and abs(v) > 255:
                    print(f"{prefix}{k}: 0x{v:X}")
                else:
                    print(f"{prefix}{k}: {v}")
    dump_keys(cpu)

# Also check trace ring
trace_ring = cpu.get("cpu", {}).get("m68k_trace_ring", [])
if not trace_ring:
    # Try other paths
    for key_path in [["cpu", "cpu", "m68k_trace_ring"], ["m68k_trace_ring"]]:
        obj = cpu
        for k in key_path:
            obj = obj.get(k, {}) if isinstance(obj, dict) else obj
        if isinstance(obj, list) and obj:
            trace_ring = obj
            break

if trace_ring:
    print(f"\n=== M68K Trace Ring ({len(trace_ring)} entries, last 20) ===")
    for entry in trace_ring[-20:]:
        pc = entry.get("pc", 0)
        mn = entry.get("mnemonic", "")
        ops = entry.get("operands", "")
        cyc = entry.get("cycles", 0)
        print(f"  ${pc:06X}: {mn:<12s} {ops} [{cyc}T]")
else:
    print("\nNo trace ring found")

# Step to frame 200
print("\n=== Stepping to frame 200 ===")
api("post", "/emulator/step", json={"frames": 199})

result2 = find_m68k(api("get", "/cpu/state"))
if result2:
    m68k2, _ = result2
    print(f"  PC: 0x{m68k2.get('pc', 0):08X}")
    print(f"  SR: 0x{m68k2.get('sr', 0):04X}")
    print(f"  A7: 0x{m68k2.get('a7', 0):08X}")

# Z80 state
apu = api("get", "/apu/state")
print(f"\n=== Z80 State (frame 200) ===")
print(f"  Z80 reset: {apu.get('z80_reset')}")
print(f"  Z80 bus req: {apu.get('z80_bus_requested')}")
print(f"  Z80 PC: 0x{apu.get('z80_pc', 0):04X}")
print(f"  Z80 cycles: {apu.get('z80_total_cycles')}")
print(f"  Z80 INT count: {apu.get('z80_int_count')}")
print(f"  reg27: 0x{apu.get('reg27', 0):02X}")
print(f"  status: 0x{apu.get('status', 0):02X}")

# Check YM histogram
hist = apu.get("ym_histogram_port0_nonzero", [])
r27_writes = 0
r24_data = None
r25_data = None
for entry in hist:
    reg = entry.get("register", entry.get("reg", -1))
    count = entry.get("count", 0)
    if reg == 0x27:
        r27_writes = count
    if reg == 0x24:
        r24_data = count
    if reg == 0x25:
        r25_data = count
print(f"\n  Timer register writes: $24={r24_data}, $25={r25_data}, $27={r27_writes}")

# Get Timer A values from write log
wlog = apu.get("ym_write_log_first100", [])
for port, addr, data in wlog:
    if addr in [0x24, 0x25, 0x27] and port == 0:
        print(f"  Write: port={port} reg=0x{addr:02X} data=0x{data:02X}")
