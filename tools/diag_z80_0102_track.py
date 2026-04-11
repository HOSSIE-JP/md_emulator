#!/usr/bin/env python3
"""Z80[$0102]のフレーム毎変遷追跡 + M68K→Z80書き込み全体のフロー把握"""
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

def read_z80(start, length):
    result = []
    chunk = 256
    for off in range(0, length, chunk):
        sz = min(chunk, length - off)
        data = api_get(f"/cpu/memory?addr={0xA00000 + start + off}&len={sz}")
        result.extend(data.get("data", []))
    return result

def read_mem(addr, length):
    data = api_get(f"/cpu/memory?addr={addr}&len={length}")
    return data.get("data", [])

def main():
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})

    print("=== Z80[$0102] + $FF019C + $FF0062 フレーム毎変遷 ===")
    prev_0102 = None
    prev_019c = None
    prev_0062 = None

    for frame in range(0, 80):
        api_post("/emulator/step", {"frames": 1})

        val_0102 = read_z80(0x0102, 1)
        ff019c = read_mem(0xFF019C, 2)
        ff0062 = read_mem(0xFF0062, 2)
        ff0066 = read_mem(0xFF0066, 2)

        v102 = val_0102[0] if val_0102 else 0
        v019c = (ff019c[0] << 8) | ff019c[1]
        v0062 = (ff0062[0] << 8) | ff0062[1]
        v0066 = (ff0066[0] << 8) | ff0066[1]

        changed = ""
        if prev_0102 is not None and v102 != prev_0102:
            changed += f" *** $0102: ${prev_0102:02X}→${v102:02X}"
        if prev_019c is not None and v019c != prev_019c:
            changed += f" *** $019C: ${prev_019c:04X}→${v019c:04X}"
        if prev_0062 is not None and v0062 != prev_0062:
            changed += f" *** $0062: ${prev_0062:04X}→${v0062:04X}"

        # Show frame if there's a change or at key frames
        if changed or frame < 5 or frame % 10 == 0 or frame in [13, 14, 15, 24, 25, 26, 38, 39, 40]:
            # Also read additional Z80 status
            z80_flags = read_z80(0x0100, 16)
            flag_str = " ".join(f"{b:02X}" for b in z80_flags[:16])
            print(f"  Frame {frame:3d}: $0102=${v102:02X} $019C=${v019c:04X} $0062=${v0062:04X} $0066=${v0066:04X}{changed}")
            print(f"            Z80[$0100-$010F]: {flag_str}")

        prev_0102 = v102
        prev_019c = v019c
        prev_0062 = v0062

    # === Phase 7 analysis: what's $FF019C during Phase 7? ===
    print("\n=== Phase 7 中の $FF019C 値 ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})

    for frame in range(0, 45):
        api_post("/emulator/step", {"frames": 1})
        ff0062 = read_mem(0xFF0062, 2)
        ff019c = read_mem(0xFF019C, 2)
        v0062 = (ff0062[0] << 8) | ff0062[1]
        v019c = (ff019c[0] << 8) | ff019c[1]

        if v0062 == 7 or (frame < 20 and v019c != 0):
            val_0102 = read_z80(0x0102, 1)
            val_0161 = read_z80(0x0161, 1)
            print(f"  Frame {frame:3d}: $0062=${v0062:04X} $019C=${v019c:04X} Z80[$0102]=${val_0102[0]:02X} Z80[$0161]=${val_0161[0]:02X}")

    # === Deeper look at what M68K writes to Z80 during Phase 7 ===
    print("\n=== M68K ROM $7DF6 handler: $FF019C→D3 mapping ===")
    print("  Phase 7: $FF019C = $0102? → D3 = $A00102 → writes $01 to bit 0")
    print("  Phase 3: $FF019C = $0161  → D3 = $A00161 → writes $01 to bit 0")

    # === Check $04A4 and $048C dispatch tables ===
    print("\n=== $04A4 リターン値解析 (dispatch計算) ===")
    rom_04a4 = read_mem(0x04A4, 0x60)
    hex_str = " ".join(f"{b:02X}" for b in rom_04a4[:0x60])
    print(f"  ROM $04A4-$0503: {hex_str[:120]}...")

    rom_048c = read_mem(0x048C, 0x18)
    hex_str2 = " ".join(f"{b:02X}" for b in rom_048c[:0x18])
    print(f"  ROM $048C-$04A3: {hex_str2}")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
