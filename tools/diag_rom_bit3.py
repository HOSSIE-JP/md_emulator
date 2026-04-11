#!/usr/bin/env python3
"""ROM全体で$FF0066 bit 3セットパターン検索 + Frame 39のトレース詳細分析"""
import requests
from collections import Counter

API = "http://localhost:8080/api/v1"

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=60)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={addr + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def main():
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 1})

    # === Search ROM for ORI #$0008 pattern (sets bit 3) near $FF0066 reference ===
    print("=== ROM全体: $FF0066 bit 3 セットパターン検索 ===")
    print("  パターン: MOVE.W ($FF0066), D0 / ORI #$0008, D0 / MOVE.W D0, ($FF0066)")
    print("  バイト: 3039 E0FF 0066 ... 0040 0008 ... 33C0 E0FF 0066")
    print()

    # Search for 0040 0008 (ORI.W #$0008, D0) in ROM
    for chunk_start in range(0, 0x40000, 0x1000):
        try:
            rom = read_mem(chunk_start, 0x1000)
        except:
            continue
        for i in range(len(rom) - 3):
            if rom[i] == 0x00 and rom[i+1] == 0x40 and rom[i+2] == 0x00 and rom[i+3] == 0x08:
                abs_addr = chunk_start + i
                # Check context: is this near a $FF0066 reference?
                # Look back for 3039 E0FF 0066
                ctx_start = max(0, i-12)
                ctx_end = min(len(rom), i+16)
                ctx = rom[ctx_start:ctx_end]
                hex_str = " ".join(f"{b:02X}" for b in ctx)

                # Check if $FF0066 (E0FF0066) is in nearby context
                has_ff0066 = False
                for j in range(max(0, i-10), min(len(rom)-3, i+10)):
                    if rom[j] == 0xE0 and rom[j+1] == 0xFF and rom[j+2] == 0x00 and rom[j+3] == 0x66:
                        has_ff0066 = True
                        break

                if has_ff0066:
                    print(f"  ROM ${abs_addr:06X}: ORI #$0008 near $FF0066 → [{hex_str}]")

    # === Frame 39 trace analysis ===
    print("\n=== Frame 39 トレース詳細分析 ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 39})

    trace_data = api_get("/cpu/trace")
    trace_ring = trace_data.get("trace_ring", [])
    print(f"Total trace entries: {len(trace_ring)}")

    # Count PCs in various ranges
    pc_8xxx = Counter()
    for entry in trace_ring:
        if isinstance(entry, dict):
            pc = entry.get("pc", 0)
            if 0x8000 <= pc <= 0x8FFF:
                pc_8xxx[pc] += 1

    print(f"\n$8xxx unique PCs: {len(pc_8xxx)}")
    print("Top 30 $8xxx PCs:")
    for pc, cnt in pc_8xxx.most_common(30):
        print(f"  ${pc:06X}: {cnt:5d}")

    # Check for specific handler addresses
    print(f"\nHandler 1 ($8292-$83FA):")
    h1_count = sum(v for k,v in pc_8xxx.items() if 0x8292 <= k <= 0x83FA)
    print(f"  Total: {h1_count}")

    print(f"Handler 2 ($85A0-$8660):")
    h2_count = sum(v for k,v in pc_8xxx.items() if 0x85A0 <= k <= 0x8660)
    print(f"  Total: {h2_count}")

    print(f"Handler 3 ($8768-$8800):")
    h3_count = sum(v for k,v in pc_8xxx.items() if 0x8768 <= k <= 0x8800)
    print(f"  Total: {h3_count}")

    # Check which specific addresses from Handler 2 are hit
    print(f"\nHandler 2 specific addresses:")
    for addr in [0x85A0, 0x85A2, 0x85B6, 0x85CC, 0x85D2, 0x85EE, 0x860C, 0x8628, 0x862E, 0x8630, 0x863E, 0x8640, 0x8642, 0x8646, 0x864A]:
        cnt = pc_8xxx.get(addr, 0)
        if cnt > 0:
            print(f"  ${addr:06X}: {cnt}")

    # Check which $8xxx range is most active
    print(f"\n$8xxx範囲別分布:")
    for block_start in range(0x8000, 0x9000, 0x100):
        block_count = sum(v for k,v in pc_8xxx.items() if block_start <= k < block_start + 0x100)
        if block_count > 0:
            print(f"  ${block_start:04X}-${block_start+0xFF:04X}: {block_count:5d}")

    # === Check $FF0066 write log from the build ===
    print("\n=== stderr ログから $FF0066 書き込み確認 ===")
    import subprocess
    result = subprocess.run(['grep', '-c', 'FF0066\\|0066', '/tmp/md_api_stderr.log'],
                          capture_output=True, text=True)
    print(f"  $0066 write entries in log: {result.stdout.strip()}")

    result2 = subprocess.run(['head', '-20', '/tmp/md_api_stderr.log'],
                           capture_output=True, text=True)
    print(f"  First 20 lines:\n{result2.stdout}")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
