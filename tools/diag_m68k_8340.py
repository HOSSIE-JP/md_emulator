#!/usr/bin/env python3
"""$8340ハンドラの呼び出し元特定 + Phase 3カウンタ動作フロー確認"""
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

    # Read ROM before $8340 to find entry point
    print("=== ROM $8280-$8360: Handler 1 entry point ===")
    data = read_mem(0x8280, 0xC0)
    for i in range(0, len(data)-1, 2):
        addr = 0x8280 + i
        w = (data[i] << 8) | data[i+1]
        extra = ""
        # Decode common instructions
        if w == 0x4E75: extra = " → RTS"
        elif w == 0x4E71: extra = " → NOP"
        elif (w >> 8) == 0x67:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            extra = f" → BEQ.B ${addr+2+off:06X}"
        elif (w >> 8) == 0x66:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            extra = f" → BNE.B ${addr+2+off:06X}"
        elif (w >> 8) == 0x60:
            off = w & 0xFF
            if off == 0 and i + 3 < len(data):
                off = (data[i+2] << 8) | data[i+3]
                if off >= 0x8000: off -= 0x10000
                extra = f" → BRA.W ${addr+2+off:06X}"
            elif off >= 0x80: off -= 256; extra = f" → BRA.B ${addr+2+off:06X}"
            else: extra = f" → BRA.B ${addr+2+off:06X}"
        elif w == 0x4EB9 and i + 5 < len(data):
            a = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            extra = f" → JSR ${a:08X}"
        elif w == 0x4EF9 and i + 5 < len(data):
            a = (data[i+2]<<24)|(data[i+3]<<16)|(data[i+4]<<8)|data[i+5]
            extra = f" → JMP ${a:08X}"
        elif (w >> 12) == 7:
            dreg = (w >> 9) & 7
            imm = w & 0xFF
            extra = f" → MOVEQ #{imm}, D{dreg}"
        elif w == 0x4A40: extra = " → TST.W D0"
        elif (w & 0xFFF8) == 0x4A00: extra = f" → TST.B D{w&7}"
        print(f"  ${addr:06X}: {w:04X}{extra}")

    # Search entire ROM for references to $8340 area
    print("\n=== ROM検索: $8340/$83xx へのジャンプ ===")
    rom_size = 0x3A0000  # Approximate ROM size
    # Search for JSR $00008340 = 4E B9 00 00 83 40
    # And JMP $00008340 = 4E F9 00 00 83 40
    # Also check for BSR/BRA to nearby addresses
    
    search_targets = [0x8326, 0x8340, 0x8588, 0x85A0]
    for target in search_targets:
        # Search for JSR target
        target_bytes = [(target >> 24) & 0xFF, (target >> 16) & 0xFF, (target >> 8) & 0xFF, target & 0xFF]
        for chunk_start in range(0, min(rom_size, 0x20000), 0x1000):
            try:
                chunk = read_mem(chunk_start, 0x1000)
            except:
                continue
            for i in range(len(chunk) - 5):
                # JSR (abs).L = 4EB9 + 4 bytes addr
                if chunk[i] == 0x4E and chunk[i+1] == 0xB9:
                    a = (chunk[i+2]<<24)|(chunk[i+3]<<16)|(chunk[i+4]<<8)|chunk[i+5]
                    if a == target:
                        print(f"  ROM ${chunk_start+i:06X}: JSR ${target:06X}")
                # JMP (abs).L = 4EF9 + 4 bytes addr
                if chunk[i] == 0x4E and chunk[i+1] == 0xF9:
                    a = (chunk[i+2]<<24)|(chunk[i+3]<<16)|(chunk[i+4]<<8)|chunk[i+5]
                    if a == target:
                        print(f"  ROM ${chunk_start+i:06X}: JMP ${target:06X}")

    # === Key experiment: Track $FFA820 counter through Phase 7→3 transition ===
    print("\n=== $FFA820カウンタ + $0102 詳細追跡 (frames 20-42) ===")
    api_post("/emulator/load-rom-path", {"path": "frontend/roms/北へPM 鮎.bin"})
    api_post("/emulator/step", {"frames": 20})
    
    for frame in range(20, 42):
        api_post("/emulator/step", {"frames": 1})
        ffa820 = read_mem(0xFFA820, 2)
        ff019c = read_mem(0xFF019C, 2)
        ff0062 = read_mem(0xFF0062, 2)
        ff0066 = read_mem(0xFF0066, 2)
        ff019e = read_mem(0xFF019E, 2)
        
        v_a820 = (ffa820[0] << 8) | ffa820[1]
        v_019c = (ff019c[0] << 8) | ff019c[1]
        v_0062 = (ff0062[0] << 8) | ff0062[1]
        v_0066 = (ff0066[0] << 8) | ff0066[1]
        v_019e = (ff019e[0] << 8) | ff019e[1]
        
        # Z80 status
        z80_0102 = read_mem(0xA00102, 1).get("data", [0])[0]
        
        print(f"  Frame {frame:3d}: ctr=${v_a820:04X} $019C=${v_019c:04X} $0062=${v_0062:04X} "
              f"$0066=${v_0066:04X} $019E=${v_019e:04X} Z80[$0102]=${z80_0102:02X}")

    # === Decode $83CE (counter=0 path) more carefully ===
    print("\n=== $83CE counter=0 dispatch 詳細 ===")
    data2 = read_mem(0x83C0, 0x60)
    for i in range(0, len(data2)-1, 2):
        addr = 0x83C0 + i
        w = (data2[i] << 8) | data2[i+1]
        extra = ""
        if w == 0x4E75: extra = " → RTS"
        elif w == 0x4E92: extra = " → JSR (A2)"
        elif w == 0x4E93: extra = " → JSR (A3)"
        elif w == 0x4A42: extra = " → TST.B D2"
        elif (w >> 8) == 0x67:
            off = w & 0xFF; 
            if off >= 0x80: off -= 256
            extra = f" → BEQ.B ${addr+2+off:06X}"
        elif (w >> 8) == 0x66:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            extra = f" → BNE.B ${addr+2+off:06X}"
        elif (w >> 8) == 0x6C:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            extra = f" → BGE.B ${addr+2+off:06X}"
        elif (w >> 8) == 0x6D:
            off = w & 0xFF
            if off >= 0x80: off -= 256
            extra = f" → BLT.B ${addr+2+off:06X}"
        elif (w >> 12) == 7:
            dreg = (w >> 9) & 7
            imm = w & 0xFF
            extra = f" → MOVEQ #{imm}, D{dreg}"
        elif w == 0x33FC and i+5 < len(data2):
            imm = (data2[i+2]<<8)|data2[i+3]
            a = (data2[i+4]<<24)|(data2[i+5]<<16) if i+7<len(data2) else 0
            extra = f" → MOVE.W #${imm:04X}, ..."
        print(f"  ${addr:06X}: {w:04X}{extra}")

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
