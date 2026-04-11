#!/usr/bin/env python3
"""M68Kトレースリングで$83xx/$82xx領域の実行を確認 + $FFA820カウンタ詳細追跡"""
import requests

API = "http://localhost:8080/api/v1"

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    data = api_get(f"/cpu/memory?addr={addr}&len={length}")
    return data.get("data", [])

def main():
    # === Part 1: M68K trace ring analysis ===
    print("=== Part 1: M68K トレースリング (各フレームで$8xxx実行確認) ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})

    for frame in range(0, 50):
        api_post("/emulator/step", {"frames": 1})

        # Get M68K trace ring
        trace_data = api_get("/cpu/trace")
        trace_ring = trace_data.get("trace_ring", [])

        # Count PCs in $8000-$8FFF range
        count_8xxx = 0
        hit_83ea = False
        hit_83ce = False
        hit_8326 = False
        hit_8340 = False
        hit_8354 = False  # Z80 reset
        hit_8292 = False
        pc_8xxx = set()

        for entry in trace_ring:
            pc = 0
            if isinstance(entry, dict):
                pc = entry.get("pc", 0)
            elif isinstance(entry, str):
                try:
                    pc_str = entry.split(":")[0].strip().lstrip("$")
                    pc = int(pc_str, 16)
                except:
                    continue

            if 0x8000 <= pc <= 0x8FFF:
                count_8xxx += 1
                pc_8xxx.add(pc)
            if pc == 0x83EA: hit_83ea = True
            if pc == 0x83CE: hit_83ce = True
            if pc == 0x8326: hit_8326 = True
            if pc == 0x8340: hit_8340 = True
            if pc == 0x8354: hit_8354 = True
            if pc == 0x8292: hit_8292 = True

        if count_8xxx > 0 or frame < 5 or frame in [24,25,26,29,30,38,39,40]:
            ff0062 = read_mem(0xFF0062, 2)
            ff0066 = read_mem(0xFF0066, 2)
            v_0062 = (ff0062[0]<<8)|ff0062[1]
            v_0066 = (ff0066[0]<<8)|ff0066[1]

            flags = []
            if hit_8292: flags.append("$8292")
            if hit_8326: flags.append("$8326")
            if hit_8340: flags.append("$8340")
            if hit_8354: flags.append("Z80RST")
            if hit_83ce: flags.append("$83CE")
            if hit_83ea: flags.append("BIT3!")

            flag_str = " HIT: " + ", ".join(flags) if flags else ""
            pc_min = min(pc_8xxx) if pc_8xxx else 0
            pc_max = max(pc_8xxx) if pc_8xxx else 0
            print(f"  Frame {frame:3d}: {count_8xxx:4d} $8xxx instrs  "
                  f"$0062=${v_0062:04X} $0066=${v_0066:04X}  "
                  f"PC range: ${pc_min:04X}-${pc_max:04X}{flag_str}")

    # === Part 2: Check M68K trace format ===
    print("\n=== Part 2: M68K trace entry format sample ===")
    trace_data = api_get("/cpu/trace")
    trace_ring = trace_data.get("trace_ring", [])
    if trace_ring:
        print(f"  Total entries: {len(trace_ring)}")
        print(f"  First entry type: {type(trace_ring[0])}")
        for entry in trace_ring[:3]:
            print(f"  Sample: {str(entry)[:200]}")

    # === Part 3: Focused experiment - check Phase 3 handler execution ===
    print("\n=== Part 3: Phase 3 中の $83EA 到達確認 (frames 25-45) ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 25})

    for frame in range(25, 45):
        api_post("/emulator/step", {"frames": 1})
        trace_data = api_get("/cpu/trace")
        trace_ring = trace_data.get("trace_ring", [])

        # Check for specific PCs
        hits = {}
        for entry in trace_ring:
            pc = 0
            if isinstance(entry, dict):
                pc = entry.get("pc", 0)
            elif isinstance(entry, str):
                try:
                    pc_str = entry.split(":")[0].strip().lstrip("$")
                    pc = int(pc_str, 16)
                except:
                    continue
            for target in [0x8292, 0x82C8, 0x8326, 0x8340, 0x8354, 0x836A, 0x83AA, 0x83C6, 0x83CE, 0x83DC, 0x83E0, 0x83EA]:
                if pc == target:
                    hits[target] = hits.get(target, 0) + 1

        if hits:
            hit_str = " ".join(f"${k:04X}:{v}" for k,v in sorted(hits.items()))
            z80_0102 = read_mem(0xA00102, 1)
            ff019c = read_mem(0xFF019C, 2)
            ffa820 = read_mem(0xFFA820, 2)
            ff019e = read_mem(0xFF019E, 2)
            v_0102 = z80_0102[0]
            v_019c = (ff019c[0]<<8)|ff019c[1]
            v_a820 = (ffa820[0]<<8)|ffa820[1]
            v_019e = (ff019e[0]<<8)|ff019e[1]
            print(f"  Frame {frame:3d}: Z80[$0102]=${v_0102:02X} $019C=${v_019c:04X} "
                  f"ctr=${v_a820:04X} $019E=${v_019e:04X}  {hit_str}")
        else:
            print(f"  Frame {frame:3d}: (no $8xxx hits)")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
