#!/usr/bin/env python3
"""Track M68K PC frame-by-frame to find when it crashes to 0."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Fresh load
print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

for frame in range(30):
    post("/emulator/step", {"frames": 1})
    cpu = get("/cpu/state").get("cpu", {})
    m68k = cpu.get("m68k", {})
    pc = m68k.get("pc", 0)
    sr = m68k.get("sr", 0)
    
    # Check for crash
    crashed = " *** CRASHED!" if pc == 0 or pc < 0x100 else ""
    # Get trace on crash
    if pc < 0x100 and frame > 0:
        trace = get("/cpu/trace")
        ring = trace.get("trace_ring", [])
        exc = trace.get("exception_trace", [])
        print(f"Frame {frame+1}: PC=0x{pc:06X} SR=0x{sr:04X}{crashed}")
        print(f"  Exception trace ({len(exc)} entries):")
        for t in exc[:10]:
            print(f"    PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t.get('mnemonic','?')}")
        print(f"  Last 20 trace ring:")
        for t in ring[-20:]:
            print(f"    PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t.get('mnemonic','?')} cyc={t['cycles']}")
        break
    else:
        apu = get("/apu/state")
        ym_writes = apu.get('ym_write_total', 0)
        print(f"Frame {frame+1}: PC=0x{pc:06X} SR=0x{sr:04X} ym_writes={ym_writes}{crashed}")
