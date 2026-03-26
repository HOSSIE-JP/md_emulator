#!/usr/bin/env python3
"""Puyo Puyo Z80 crash - Phase 2: Find exact RAM corruption timing.

Keys from Phase 1:
- Z80 RAM at frame 5: valid code (DI; JP $114A at $0000, proper ISR at $0038)
- Z80 RAM at frame 281: all overwritten with 0F DA 3F 00 pattern
- SP drops ~10 per frame after crash
- IFF1=False but SP still dropping → corrupted code must contain EI somewhere

This script steps frame by frame from frame 50, checking Z80 RAM $0000-$0003
and $0038-$003B to detect when the corruption happens.
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

# ── 1. Load ROM ──────────────────────────────────────────────────────
print("=== Loading puyo.bin ===")
api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# ── 2. Step 5 frames ────────────────────────────────────────────────
for i in range(5):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

# Baseline: Z80 RAM at $0000 and $0038
mem0 = api_get("/cpu/memory?addr=10485760&len=8192")["data"]  # 0xA00000, 8KB = full Z80 RAM
print(f"Frame 5 baseline:")
print(f"  $0000-$0007: {' '.join(f'{mem0[i]:02X}' for i in range(8))}")
print(f"  $0038-$003F: {' '.join(f'{mem0[0x38+i]:02X}' for i in range(8))}")
print(f"  $1160-$117F: {' '.join(f'{mem0[0x1160+i]:02X}' for i in range(32))}")

prev_0000 = mem0[0:4]
prev_0038 = mem0[0x38:0x3C]

# ── 3. Step frame-by-frame, check key locations ─────────────────────
print("\n=== Frame-by-frame RAM check (frames 6-210) ===")
corruption_frame = None

for frame in range(6, 210):
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

    # Check Z80 state
    state = api_get("/cpu/state")
    z80 = state.get("cpu", {}).get("z80", {})
    pc = z80.get("pc", 0)
    sp = z80.get("sp", 0)
    bus_req = state.get("cpu", {}).get("z80_bus_requested", None)  # might not exist here

    # Check Z80 RAM key locations
    mem = api_get("/cpu/memory?addr=10485760&len=8192")["data"]
    cur_0000 = mem[0:4]
    cur_0038 = mem[0x38:0x3C]

    changed_0000 = cur_0000 != prev_0000
    changed_0038 = cur_0038 != prev_0038

    if changed_0000 or changed_0038:
        print(f"\n  *** RAM CHANGED at frame {frame} ***")
        print(f"  Z80: PC=${pc:04X}  SP=${sp:04X}  IFF1={z80.get('iff1')}")
        print(f"  $0000 was: {' '.join(f'{b:02X}' for b in prev_0000)} → is: {' '.join(f'{b:02X}' for b in cur_0000)}")
        print(f"  $0038 was: {' '.join(f'{b:02X}' for b in prev_0038)} → is: {' '.join(f'{b:02X}' for b in cur_0038)}")

        # Dump more context
        print(f"  $0000-$000F: {' '.join(f'{mem[i]:02X}' for i in range(16))}")
        print(f"  $0030-$004F: {' '.join(f'{mem[0x30+i]:02X}' for i in range(32))}")
        print(f"  $1160-$117F: {' '.join(f'{mem[0x1160+i]:02X}' for i in range(32))}")

        if corruption_frame is None and cur_0038 != prev_0038:
            corruption_frame = frame
            # Do a deeper dump
            print(f"\n  === First corruption frame: {frame} ===")
            # Check the APU state for bus_requested
            apu = api_get("/apu/state")
            print(f"  z80_bus_requested: {apu.get('z80_bus_requested')}")
            print(f"  z80_reset: {apu.get('z80_reset')}")
            print(f"  z80_bank_68k_addr: {apu.get('z80_bank_68k_addr')}")

            # Dump first 256 bytes of Z80 RAM
            print(f"\n  Z80 RAM $0000-$00FF:")
            for off in range(0, 256, 16):
                chunk = mem[off:off+16]
                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f"    ${off:04X}: {hex_str}  |{ascii_str}|")

            # Dump the Z80 trace ring to find what the Z80 was doing
            trace_ring = apu.get("z80_trace_ring", [])
            print(f"\n  Z80 trace ring length: {len(trace_ring)}")
            print(f"  Last 60 entries (newest first):")
            for i, entry in enumerate(trace_ring[:60]):
                print(f"    [{i:5d}] {entry}")

            # Also check M68K trace
            m68k_state = state.get("cpu", {}).get("m68k", {})
            print(f"\n  M68K PC: ${m68k_state.get('pc', 0):08X}")
            a_vals = ' '.join('${:08X}'.format(m68k_state.get('a{}'.format(i), 0)) for i in range(4))
            print(f"  M68K A0-A3: {a_vals}")

        prev_0000 = cur_0000
        prev_0038 = cur_0038
    elif frame % 20 == 0:
        print(f"  Frame {frame}: Z80 PC=${pc:04X}  SP=${sp:04X}  RAM ok")

if corruption_frame:
    print(f"\n=== Summary: Z80 RAM first corrupted at frame {corruption_frame} ===")

    # Now let's step back: reload and step to corruption_frame-1
    # to capture the pre-corruption state and M68K trace
    print(f"\n=== Replaying to frame {corruption_frame - 1} for pre-corruption analysis ===")
    api_post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
    for i in range(corruption_frame - 1):
        api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})

    state_pre = api_get("/cpu/state")
    z80_pre = state_pre.get("cpu", {}).get("z80", {})
    print(f"  Pre-corruption Z80: PC=${z80_pre.get('pc',0):04X}  SP=${z80_pre.get('sp',0):04X}  "
          f"IFF1={z80_pre.get('iff1')}  halted={z80_pre.get('halted')}")

    mem_pre = api_get("/cpu/memory?addr=10485760&len=8192")["data"]
    print(f"  Pre-corruption $0000-$0007: {' '.join(f'{mem_pre[i]:02X}' for i in range(8))}")
    print(f"  Pre-corruption $0038-$003F: {' '.join(f'{mem_pre[0x38+i]:02X}' for i in range(8))}")

    apu_pre = api_get("/apu/state")
    print(f"  Pre-corruption z80_bus_requested: {apu_pre.get('z80_bus_requested')}")
    print(f"  Pre-corruption z80_reset: {apu_pre.get('z80_reset')}")

    # Now step one more frame (the corruption frame)
    api_post("/emulator/step", {"cycles": CYCLES_PER_FRAME})
    state_post = api_get("/cpu/state")
    z80_post = state_post.get("cpu", {}).get("z80", {})
    mem_post = api_get("/cpu/memory?addr=10485760&len=8192")["data"]
    apu_post = api_get("/apu/state")

    print(f"\n  Post-corruption Z80: PC=${z80_post.get('pc',0):04X}  SP=${z80_post.get('sp',0):04X}  "
          f"IFF1={z80_post.get('iff1')}  halted={z80_post.get('halted')}")
    print(f"  Post-corruption $0000-$0007: {' '.join(f'{mem_post[i]:02X}' for i in range(8))}")
    print(f"  Post-corruption $0038-$003F: {' '.join(f'{mem_post[0x38+i]:02X}' for i in range(8))}")
    print(f"  Post-corruption z80_bus_requested: {apu_post.get('z80_bus_requested')}")
    print(f"  Post-corruption z80_reset: {apu_post.get('z80_reset')}")

    # Diff: find first changed byte in Z80 RAM
    first_change = None
    change_count = 0
    for i in range(min(len(mem_pre), len(mem_post), 8192)):
        if mem_pre[i] != mem_post[i]:
            change_count += 1
            if first_change is None:
                first_change = i
    print(f"\n  Changed bytes in Z80 RAM: {change_count}")
    if first_change is not None:
        print(f"  First change at offset ${first_change:04X}")
        # Show surrounding context
        start = max(0, first_change - 8)
        end = min(8192, first_change + 24)
        print(f"  Pre:  {' '.join(f'{mem_pre[i]:02X}' for i in range(start, end))}")
        print(f"  Post: {' '.join(f'{mem_post[i]:02X}' for i in range(start, end))}")

    # Z80 trace ring at corruption
    trace_ring = apu_post.get("z80_trace_ring", [])
    print(f"\n  Z80 trace ring at corruption ({len(trace_ring)} entries):")
    print(f"  Last 80 entries (newest first):")
    for i, entry in enumerate(trace_ring[:80]):
        print(f"    [{i:5d}] {entry}")

    # M68K trace at corruption
    m68k_post = state_post.get("cpu", {}).get("m68k", {})
    print(f"\n  M68K at corruption: PC=${m68k_post.get('pc',0):08X}")

else:
    print("\n  No corruption detected in frames 6-210!")

print("\n=== Done ===")
