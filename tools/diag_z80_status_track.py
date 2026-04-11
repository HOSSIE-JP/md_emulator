#!/usr/bin/env python3
"""Z80ステータス領域の変化追跡: 全フレームで$0100-$010F + $0160-$016F を監視"""
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

    print("=== Z80 ステータスエリア フレーム毎追跡 ===")
    prev_status = None
    prev_cmd = None

    for frame in range(0, 55):
        api_post("/emulator/step", {"frames": 1})
        status = read_z80(0x0100, 0x10)  # $0100-$010F
        cmd = read_z80(0x0160, 0x10)  # $0160-$016F

        changes = []
        if prev_status:
            for i in range(len(status)):
                if status[i] != prev_status[i]:
                    changes.append(f"${0x100+i:04X}:{prev_status[i]:02X}→{status[i]:02X}")
        if prev_cmd:
            for i in range(len(cmd)):
                if cmd[i] != prev_cmd[i]:
                    changes.append(f"${0x160+i:04X}:{prev_cmd[i]:02X}→{cmd[i]:02X}")

        if changes or frame < 3 or frame in [13,14,15,24,25,26,29,30,38,39,40,41]:
            stat_str = " ".join(f"{b:02X}" for b in status)
            cmd_str = " ".join(f"{b:02X}" for b in cmd)
            ch_str = " CHANGES: " + ", ".join(changes) if changes else ""
            print(f"  Frame {frame:3d}: [$0100] {stat_str}")
            print(f"            [$0160] {cmd_str}{ch_str}")

        prev_status = status
        prev_cmd = cmd

    # === Also check $1C00-$1C0F (GEMS command buffer) ===
    print("\n=== GEMS コマンドバッファ $1C00-$1C0F ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    prev_gems = None

    for frame in range(0, 55):
        api_post("/emulator/step", {"frames": 1})
        gems = read_z80(0x1C00, 0x10)

        changes = []
        if prev_gems:
            for i in range(len(gems)):
                if gems[i] != prev_gems[i]:
                    changes.append(f"${0x1C00+i:04X}:{prev_gems[i]:02X}→{gems[i]:02X}")

        if changes or frame in [14,25,30,38,39,40]:
            gems_str = " ".join(f"{b:02X}" for b in gems)
            ch_str = " " + ", ".join(changes) if changes else ""
            print(f"  Frame {frame:3d}: [$1C00] {gems_str}{ch_str}")

        prev_gems = gems

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
