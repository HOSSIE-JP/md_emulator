#!/usr/bin/env python3
"""Puyo Puyo Z80 crash investigation.

Loads the ROM, steps to ~frame 280, then steps frame-by-frame to find
the exact transition from the idle loop ($116F-$1176) to sequential
execution through RAM mirror / YM space.
"""

import json
import urllib.request
import sys

BASE = "http://127.0.0.1:8080/api/v1"
TIMEOUT = 120

def api_get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=TIMEOUT).read())

def api_post(path, data=None):
    req = urllib.request.Request(BASE + path, method="POST")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data or {}).encode()
    return json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read())

CYCLES_PER_FRAME = 896040  # ~one NTSC frame in M68K cycles

# ── 1. Load ROM ──────────────────────────────────────────────────────
print("=== Loading puyo.bin ===")
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# ── 2. Step 5 frames for Z80 driver to be loaded by M68K ────────────
print("=== Stepping 5 frames for Z80 driver load ===")
for i in range(5):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

# Dump early Z80 state
state = api_get("/cpu/state")
z80 = state.get("cpu", {}).get("z80", {})
print(f"  After 5 frames: Z80 PC=${z80.get('pc',0):04X}  SP=${z80.get('sp',0):04X}  "
      f"IFF1={z80.get('iff1')}  halted={z80.get('halted')}")

# Read Z80 RAM $0000-$001F (interrupt vector area) via M68K memory map
mem = api_get("/cpu/memory?addr=10485760&len=128")  # 0xA00000
z80_ram_00 = mem.get("data", [])[:128]
print(f"  Z80 RAM $0000-$003F: {' '.join(f'{b:02X}' for b in z80_ram_00[:64])}")
print(f"  Z80 RAM $0038-$0050: {' '.join(f'{b:02X}' for b in z80_ram_00[0x38:0x50])}")

# ── 3. Step to frame 280 ────────────────────────────────────────────
print("\n=== Stepping to frame 280 ===")
for i in range(5, 280):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})
    if i % 50 == 0:
        s = api_get("/cpu/state")
        z = s.get("cpu", {}).get("z80", {})
        print(f"  Frame {i}: Z80 PC=${z.get('pc',0):04X}  SP=${z.get('sp',0):04X}  "
              f"IFF1={z.get('iff1')}  halted={z.get('halted')}")

state280 = api_get("/cpu/state")
z80_280 = state280.get("cpu", {}).get("z80", {})
print(f"\n=== Frame 280 Z80 State ===")
for k in ["pc", "sp", "a", "f", "b", "c", "d", "e", "h", "l", "ix", "iy",
           "iff1", "iff2", "im", "int_pending", "ei_delay", "halted", "total_cycles"]:
    v = z80_280.get(k)
    if isinstance(v, int) and k not in ("iff1", "iff2", "int_pending", "halted", "im", "ei_delay", "total_cycles"):
        print(f"  {k:14s} = ${v:04X}  ({v})")
    else:
        print(f"  {k:14s} = {v}")

# ── 4. Step frame-by-frame 280→320, detect crash ────────────────────
print("\n=== Frame-by-frame scan 280→320 ===")
IDLE_RANGE = range(0x1100, 0x1200)  # known idle loop area
crash_frame = None

for frame in range(280, 320):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})
    s = api_get("/cpu/state")
    z = s.get("cpu", {}).get("z80", {})
    pc = z.get("pc", 0)
    sp = z.get("sp", 0)
    iff1 = z.get("iff1")

    in_idle = pc in IDLE_RANGE
    marker = "" if in_idle else " *** OUTSIDE IDLE ***"

    print(f"  Frame {frame+1}: PC=${pc:04X}  SP=${sp:04X}  IFF1={iff1}  "
          f"halted={z.get('halted')}{marker}")

    if not in_idle and crash_frame is None:
        crash_frame = frame + 1
        print(f"\n  >>> CRASH DETECTED at frame {crash_frame}! <<<")
        # Capture full Z80 registers
        print(f"  === Crash-frame Z80 registers ===")
        for k in ["pc", "sp", "a", "f", "b", "c", "d", "e", "h", "l",
                   "a_", "f_", "b_", "c_", "d_", "e_", "h_", "l_",
                   "ix", "iy", "iff1", "iff2", "im", "int_pending",
                   "ei_delay", "halted", "total_cycles"]:
            v = z.get(k)
            if isinstance(v, int) and k not in ("iff1", "iff2", "int_pending",
                                                  "halted", "im", "ei_delay", "total_cycles"):
                print(f"    {k:14s} = ${v:04X}  ({v})")
            else:
                print(f"    {k:14s} = {v}")

        # ── 5. Get trace ring ────────────────────────────────────
        print(f"\n  === Z80 trace ring (last entries, newest first) ===")
        apu = api_get("/apu/state")
        trace_ring = apu.get("z80_trace_ring", [])
        print(f"  Trace ring length: {len(trace_ring)}")

        # Find transition point: last entry in idle range vs first outside
        transition_idx = None
        for i, entry in enumerate(trace_ring):
            # Format: "$XXXX: YY mnemonic"
            if entry.startswith("$"):
                addr_str = entry[1:5]
                try:
                    addr = int(addr_str, 16)
                except ValueError:
                    continue
                if addr in IDLE_RANGE:
                    transition_idx = i
                    break

        if transition_idx is not None:
            print(f"\n  Transition found at trace index {transition_idx}")
            start = max(0, transition_idx - 5)
            end = min(len(trace_ring), transition_idx + 30)
            print(f"  Showing entries [{start}..{end}] (newest first):")
            for i in range(start, end):
                mark = " <-- TRANSITION" if i == transition_idx else ""
                print(f"    [{i:5d}] {trace_ring[i]}{mark}")
        else:
            print("  No transition found in trace ring; showing first 80 entries:")
            for i, entry in enumerate(trace_ring[:80]):
                print(f"    [{i:5d}] {entry}")

        # Show entries around $0038 (ISR)
        print(f"\n  === Entries at/near $0038 (INT handler) ===")
        isr_entries = [(i, e) for i, e in enumerate(trace_ring) if "$0038:" in e or "INT" in e]
        for i, e in isr_entries[:20]:
            print(f"    [{i:5d}] {e}")

        # ── 6. Dump Z80 RAM around stack pointer ─────────────────
        sp_val = z.get("sp", 0)
        # Read Z80 RAM via M68K address map: $A00000 + offset
        if sp_val < 0x2000:
            mem_sp = api_get(f"/cpu/memory?addr={0xA00000 + (sp_val & 0x1FFF)}&len=32")
            sp_data = mem_sp.get("data", [])
            print(f"\n  === Z80 RAM at SP=${sp_val:04X} (32 bytes) ===")
            print(f"    {' '.join(f'{b:02X}' for b in sp_data)}")
            # Decode return addresses on stack
            print(f"  Stack (word pairs, little-endian):")
            for j in range(0, min(len(sp_data), 16), 2):
                lo = sp_data[j] if j < len(sp_data) else 0
                hi = sp_data[j+1] if j+1 < len(sp_data) else 0
                word = (hi << 8) | lo
                print(f"    SP+{j:2d}: ${word:04X}")

        # Z80 RAM at $0038 (ISR handler code)
        mem_isr = api_get(f"/cpu/memory?addr={0xA00038}&len=32")
        isr_data = mem_isr.get("data", [])
        print(f"\n  === Z80 RAM $0038-$0057 (ISR area) ===")
        print(f"    {' '.join(f'{b:02X}' for b in isr_data)}")

        # Z80 RAM at idle loop area $1100-$1180
        mem_idle = api_get(f"/cpu/memory?addr={0xA01100}&len=128")
        idle_data = mem_idle.get("data", [])
        print(f"\n  === Z80 RAM $1100-$117F (idle loop area) ===")
        for off in range(0, 128, 16):
            chunk = idle_data[off:off+16]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            addr = 0x1100 + off
            print(f"    ${addr:04X}: {hex_str}")

        # Don't stop - continue scanning to see how Z80 evolves
        # but we only print the full crash analysis once

if crash_frame is None:
    print("\n  No crash detected in frames 280-320.")
    # Still dump the trace ring
    apu = api_get("/apu/state")
    trace_ring = apu.get("z80_trace_ring", [])
    print(f"  Trace ring length: {len(trace_ring)}")
    print(f"  Last 30 entries (newest first):")
    for i, entry in enumerate(trace_ring[:30]):
        print(f"    [{i:5d}] {entry}")

    # And final Z80 state
    state320 = api_get("/cpu/state")
    z320 = state320.get("cpu", {}).get("z80", {})
    print(f"\n  === Frame 320 Z80 State ===")
    for k in ["pc", "sp", "a", "f", "b", "c", "d", "e", "h", "l",
               "iff1", "iff2", "im", "int_pending", "halted"]:
        v = z320.get(k)
        if isinstance(v, int) and k not in ("iff1", "iff2", "int_pending", "halted", "im"):
            print(f"    {k:14s} = ${v:04X}")
        else:
            print(f"    {k:14s} = {v}")

print("\n=== Done ===")
