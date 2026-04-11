#!/usr/bin/env python3
"""Z80コマンド応答の詳細診断
- Z80[$0161]の変化を監視  
- $7F5C (BEQ target) のROMダンプ
- counter=0ディスパッチの挙動確認"""
import requests

BASE = "http://localhost:8080/api/v1"

def load_rom():
    requests.post(f"{BASE}/emulator/load-rom-path",
                  json={"path": "frontend/roms/北へPM 鮎.bin"}).raise_for_status()

def step(n=1):
    r = requests.post(f"{BASE}/emulator/step", json={"frames": n})
    r.raise_for_status()
    return r.json()

def read_mem(addr, length):
    r = requests.get(f"{BASE}/cpu/memory", params={"addr": addr, "len": length})
    r.raise_for_status()
    return r.json()["data"]

def read_word(addr):
    d = read_mem(addr, 2)
    return (d[0] << 8) | d[1]

def read_byte(addr):
    return read_mem(addr, 1)[0]

def read_z80_byte(addr):
    return read_byte(0xA00000 + addr)

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()

# ================================================================
load_rom()

print("=" * 60)
print("1. ROM $7F5C (BEQ target from INCREMENT counter=0)")
print("=" * 60)
raw = read_mem(0x7F5C, 0x40)
for i in range(0, len(raw)-1, 2):
    w = (raw[i] << 8) | raw[i+1]
    addr = 0x7F5C + i
    note = ""
    if w == 0x4E75: note = " RTS"
    elif w == 0x4E73: note = " RTE"
    elif w == 0x33FC: note = " MOVE.W#imm,(abs).L"
    elif (w & 0xF1FF) == 0x3039: note = f" MOVE.W(abs).L,D{(w>>9)&7}"
    elif w == 0x4279: note = " CLR.W(abs).L"
    elif w == 0x42B9: note = " CLR.L(abs).L"
    elif (w & 0xFF00) == 0x6600: note = " BNE"
    elif (w & 0xFF00) == 0x6700: note = " BEQ"
    elif (w & 0xFF00) == 0x6000: note = " BRA"
    elif w == 0x4EB9: note = " JSR(abs).L"
    elif w == 0x4EBA: note = " JSR(PC)"
    elif w == 0x4EF9: note = " JMP(abs).L"
    elif w == 0x48E7: note = " MOVEM.L-(SP)"
    elif w == 0x4CDF: note = " MOVEM.L(SP)+"
    elif (w & 0xFFF8) == 0x4A40: note = f" TST.W D{w&7}"
    elif (w & 0xFFF8) == 0x4A00: note = f" TST.B D{w&7}"
    elif w == 0x13C0: note = " MOVE.B D0,(abs).L"
    elif (w & 0xF1FF) == 0x1039: note = f" MOVE.B(abs).L,D{(w>>9)&7}"
    elif (w & 0xF100) == 0x7000: note = f" MOVEQ#{w&0xFF},D{(w>>9)&7}"
    print(f"  ${addr:04X}: ${w:04X}{note}")

print()
print("=" * 60)
print("2. ROM $7F92 (BEQ target when bus already held)")
print("=" * 60)
raw2 = read_mem(0x7F92, 0x20)
for i in range(0, len(raw2)-1, 2):
    w = (raw2[i] << 8) | raw2[i+1]
    addr = 0x7F92 + i
    note = ""
    if w == 0x4E75: note = " RTS"
    elif (w & 0xFF00) == 0x6000: note = " BRA"
    elif (w & 0xFF00) == 0x6600: note = " BNE"
    elif (w & 0xFF00) == 0x6700: note = " BEQ"
    elif w == 0x33FC: note = " MOVE.W#imm,(abs).L"
    elif w == 0x4279: note = " CLR.W(abs).L"
    elif (w & 0xF1FF) == 0x3039: note = f" MOVE.W(abs).L,D{(w>>9)&7}"
    print(f"  ${addr:04X}: ${w:04X}{note}")

print()
print("=" * 60)
print("3. Z80 RAM $0140-$0170 のダンプ (init後)")
print("=" * 60)
step(38)
z80_data = read_mem(0xA00140, 0x30)
for i in range(0, len(z80_data), 16):
    hex_str = " ".join(f"{b:02X}" for b in z80_data[i:i+16])
    print(f"  Z80[${0x0140+i:04X}]: {hex_str}")

# Before FF019C is set
print(f"\n  Frame 38: Z80[$0161]=${read_z80_byte(0x0161):02X}")
print(f"            $FF019C=${read_word(0xFF019C):04X}")

print()
print("=" * 60)
print("4. フレーム毎のZ80[$0161]と$FF019C監視")
print("=" * 60)
print(f"{'Frame':>5} {'FF019C':>8} {'FF0066':>8} {'FFA820':>8} {'Z80[0161]':>10} {'Z80[0100-0103]':>16}")
for frame in range(39, 65):
    step(1)
    ff019c = read_word(0xFF019C)
    ff0066 = read_word(0xFF0066)
    ffa820 = read_word(0xFFA820)
    z80_161 = read_z80_byte(0x0161)
    z80_status = read_mem(0xA00100, 4)
    z80_str = " ".join(f"{b:02X}" for b in z80_status)
    print(f"{frame:5d} {ff019c:08X} {ff0066:08X} {ffa820:08X} {z80_161:10d} {z80_str:>16}")

# Dump broader Z80 area after command should have been sent
print()
print("=" * 60)
print("5. Z80 RAM $0140-$01A0 (frame 65付近)")
print("=" * 60)
z80_data2 = read_mem(0xA00140, 0x60)
for i in range(0, len(z80_data2), 16):
    hex_str = " ".join(f"{b:02X}" for b in z80_data2[i:i+16])
    print(f"  Z80[${0x0140+i:04X}]: {hex_str}")

# Also check Z80 RAM around $1C00 and $1F00  
z80_1c = read_mem(0xA01C00, 0x20)
print(f"\n  Z80[$1C00-$1C1F]: {' '.join(f'{b:02X}' for b in z80_1c)}")
z80_1f = read_mem(0xA01F00, 0x10)
print(f"  Z80[$1F00-$1F0F]: {' '.join(f'{b:02X}' for b in z80_1f)}")

print()
print("=" * 60)
print("6. Z80 PC確認")
print("=" * 60)
try:
    r = requests.get(f"{BASE}/apu/state")
    r.raise_for_status()
    apu = r.json()
    print(f"  Z80 state: {apu}")
except Exception as e:
    print(f"  APU state error: {e}")

print("\n完了")
