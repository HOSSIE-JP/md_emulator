#!/usr/bin/env python3
"""Puyo Z80 crash Phase 4: Deep trace analysis.

Focus questions:
1. What is the Z80 code at $01DD-$0200? (the loop seen in frames 171-178)
2. How many INT entries does the trace ring show between frame 160-179?
3. Is the Z80 ISR doing EI/RETI that causes nested INTs?
4. What exactly triggers the RAM overwrite at frame 179?
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"
TIMEOUT = 120

def api_get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=TIMEOUT).read())

def api_post(path, data=None):
    req = urllib.request.Request(BASE + path, method="POST")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data or {}).encode()
    return json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read())

CYCLES_PER_FRAME = 896040

# Load ROM
print("=== Loading puyo.bin ===")
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Step 5 frames for driver load
for i in range(5):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

# Dump Z80 RAM code area at $0180-$0220 (the loop seen in frames 171-178)
print("\n=== Z80 code at $0180-$0220 (frame 5, clean) ===")
ram = api_get("/cpu/memory?addr=10485760&len=8192")["data"]
for off in range(0x0180, 0x0220, 16):
    chunk = ram[off:off+16]
    print("    ${:04X}: {}".format(off, ' '.join('{:02X}'.format(b) for b in chunk)))

# Also dump the ISR epilogue (the part that does RETI/EI) - scan for ED 4D (RETI) or FB (EI)
print("\n=== Searching for RETI (ED 4D) and EI (FB) in Z80 RAM ===")
for addr in range(0, 0x2000 - 1):
    # RETI = ED 4D
    if ram[addr] == 0xED and ram[addr+1] == 0x4D:
        context = ram[max(0,addr-4):addr+6]
        print("  RETI at ${:04X}: {}".format(addr, ' '.join('{:02X}'.format(b) for b in context)))
    # EI = FB
    if ram[addr] == 0xFB:
        context = ram[max(0,addr-2):addr+6]
        print("  EI   at ${:04X}: ...{} {}...".format(addr,
            ' '.join('{:02X}'.format(b) for b in ram[max(0,addr-2):addr]),
            ' '.join('{:02X}'.format(b) for b in ram[addr:addr+6])))

# Step to frame 160
print("\n=== Stepping to frame 160 ===")
for i in range(5, 160):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

# Now step frame-by-frame from 160 to 180, checking Z80 state
print("\n=== Frame-by-frame 160→180 ===")
for frame in range(160, 180):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})
    s = api_get("/cpu/state")
    z = s.get("cpu", {}).get("z80", {})
    pc = z.get("pc", 0)
    sp = z.get("sp", 0)
    a = z.get("a", 0)
    iff1 = z.get("iff1")
    iff2 = z.get("iff2")
    ei_delay = z.get("ei_delay", 0)
    int_pending = z.get("int_pending")
    halted = z.get("halted")
    print("  F{:3d}: PC=${:04X} SP=${:04X} A=${:02X} IFF1={} IFF2={} "
          "ei_d={} int_p={} halt={}".format(
        frame + 1, pc, sp, a, iff1, iff2, ei_delay, int_pending, halted))

    # At the critical transition frame (SP drops from ~$1FFE to much lower)
    if frame == 165:
        apu = api_get("/apu/state")
        trace_ring = apu.get("z80_trace_ring", [])
        print("\n  === Z80 trace ring at frame 166 ({} entries) ===".format(len(trace_ring)))

        # Count INT entries
        int_count = sum(1 for e in trace_ring if "INT" in e or (e.startswith("$") and ": FF Rst(56)" in e))
        print("  INT/RST38 entries in trace: {}".format(int_count))

        # Find all INT entries and their positions
        int_positions = [(i, e) for i, e in enumerate(trace_ring) if "INT" in e]
        if int_positions:
            print("  INT entries (first 20):")
            for idx, entry in int_positions[:20]:
                # Show surrounding context
                print("    [{:5d}] {}".format(idx, entry))
                if idx+1 < len(trace_ring):
                    print("           prev: {}".format(trace_ring[idx+1]))

        # Show the last 40 entries to see current loop
        print("\n  Last 40 trace entries:")
        for i, entry in enumerate(trace_ring[:40]):
            print("    [{:5d}] {}".format(i, entry))

    if frame == 170:
        apu = api_get("/apu/state")
        trace_ring = apu.get("z80_trace_ring", [])
        print("\n  === Z80 trace ring at frame 171 ({} entries) ===".format(len(trace_ring)))

        int_count = sum(1 for e in trace_ring if "INT" in e)
        print("  INT entries in trace: {}".format(int_count))

        # Show INT entries with context
        int_positions = [(i, e) for i, e in enumerate(trace_ring) if "INT" in e]
        print("  INT positions (first 30):")
        for idx, entry in int_positions[:30]:
            print("    [{:5d}] {}".format(idx, entry))
            # Show what came before (the instruction that was executing when INT fired)
            if idx+1 < len(trace_ring):
                print("           before: {}".format(trace_ring[idx+1]))

        # Look for what's between consecutive INTs (to understand re-entry pattern)
        if len(int_positions) >= 2:
            print("\n  Between first two INTs:")
            start = int_positions[0][0]
            end = int_positions[1][0]
            betw = end - start
            print("    Distance: {} entries".format(betw))
            for i in range(start, min(start + 50, end + 1)):
                print("    [{:5d}] {}".format(i, trace_ring[i]))

    if frame == 178:  # Frame 179 - corruption frame
        apu = api_get("/apu/state")
        trace_ring = apu.get("z80_trace_ring", [])
        print("\n  === Z80 trace ring at frame 179 ({} entries) ===".format(len(trace_ring)))

        int_count = sum(1 for e in trace_ring if "INT" in e)
        rst38_count = sum(1 for e in trace_ring if "Rst(56)" in e)
        print("  INT entries: {}".format(int_count))
        print("  RST $38 entries: {}".format(rst38_count))

        # Scan backwards to find the LAST valid code before crash
        for i, entry in enumerate(trace_ring):
            if entry.startswith("$"):
                try:
                    addr = int(entry[1:5], 16)
                except ValueError:
                    continue
                if addr < 0x2000 and "Rst(56)" not in entry and "INT" not in entry:
                    print("\n  Last valid code at trace index {}:".format(i))
                    start = max(0, i - 5)
                    end = min(len(trace_ring), i + 50)
                    for j in range(start, end):
                        mark = " <-- LAST VALID" if j == i else ""
                        print("    [{:5d}] {}{}".format(j, trace_ring[j], mark))
                    break

print("\n=== Done ===")
