#!/usr/bin/env python3
"""Z80 GEMS コマンドハンドシェイクの診断
$FF019Cが$0161に設定された後、Z80がコマンドを処理・応答するか確認"""
import requests, sys

BASE = "http://localhost:8080/api/v1"

def load_rom():
    r = requests.post(f"{BASE}/emulator/load-rom-path",
                      json={"path": "frontend/roms/北へPM 鮎.bin"})
    r.raise_for_status()

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

def read_z80(addr, length):
    """Z80 RAMを読む (M68K addressは $A00000 + z80_addr)"""
    d = read_mem(0xA00000 + addr, length)
    return d

def get_cpu():
    r = requests.get(f"{BASE}/cpu/state")
    r.raise_for_status()
    return r.json()

def get_trace():
    r = requests.get(f"{BASE}/cpu/trace")
    r.raise_for_status()
    return r.json()

def dump_hex(data, base_addr, label=""):
    """16バイト単位でヘックスダンプ"""
    if label:
        print(f"  {label}:")
    for i in range(0, len(data), 16):
        addr = base_addr + i
        hex_str = " ".join(f"{b:02X}" for b in data[i:i+16])
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data[i:i+16])
        print(f"    ${addr:04X}: {hex_str}  {ascii_str}")

# ================================================================
print("=" * 60)
print("1. ROM: $7DF6 (Z80コマンドハンドラ) の逆アセンブル")
print("=" * 60)
load_rom()

# Dump raw bytes at $7DF6-$7E8F
raw = read_mem(0x7DF6, 0xA0)
print("  Raw words at $7DF6:")
for i in range(0, len(raw)-1, 2):
    w = (raw[i] << 8) | raw[i+1]
    addr = 0x7DF6 + i
    print(f"    ${addr:04X}: ${w:04X}", end="")
    # Try to identify some instructions
    if w == 0x4E75: print("  RTS", end="")
    elif w == 0x4E73: print("  RTE", end="")
    elif w == 0x4E71: print("  NOP", end="")
    elif w == 0x33FC: print("  MOVE.W #imm, (abs).L", end="")
    elif (w & 0xF1FF) == 0x3039: print(f"  MOVE.W (abs).L, D{(w>>9)&7}", end="")
    elif (w & 0xFFF8) == 0x4A40: print(f"  TST.W D{w&7}", end="")
    elif (w & 0xFFF8) == 0x4A00: print(f"  TST.B D{w&7}", end="")
    elif (w & 0xFFC0) == 0x0800: print(f"  BTST #imm", end="")
    elif (w & 0xFF00) == 0x6600: print(f"  BNE", end="")
    elif (w & 0xFF00) == 0x6700: print(f"  BEQ", end="")
    elif (w & 0xFF00) == 0x6000: print(f"  BRA", end="")
    elif w == 0x13C0: print("  MOVE.B D0, (abs).L", end="")
    elif (w & 0xF1FF) == 0x1039: print(f"  MOVE.B (abs).L, D{(w>>9)&7}", end="")
    elif w == 0x48E7: print("  MOVEM.L regs, -(SP)", end="")
    elif w == 0x4CDF: print("  MOVEM.L (SP)+, regs", end="")
    elif w == 0x4EB9: print("  JSR (abs).L", end="")
    elif w == 0x4EBA: print("  JSR (PC)+d16", end="")
    elif w == 0x4EF9: print("  JMP (abs).L", end="")
    print()

print()
print("=" * 60)
print("2. ROM: $7C3C (bit2ハンドラ) のraw dump")  
print("=" * 60)
raw2 = read_mem(0x7C3C, 0xC0)
print("  Raw words at $7C3C:")
for i in range(0, len(raw2)-1, 2):
    w = (raw2[i] << 8) | raw2[i+1]
    addr = 0x7C3C + i
    print(f"    ${addr:04X}: ${w:04X}", end="")
    if w == 0x4E75: print("  RTS", end="")
    elif w == 0x33FC: print("  MOVE.W #imm, (abs).L", end="")
    elif (w & 0xF1FF) == 0x3039: print(f"  MOVE.W (abs).L, D{(w>>9)&7}", end="")
    elif (w & 0xFFF8) == 0x4A40: print(f"  TST.W D{w&7}", end="")
    elif (w & 0xFFF8) == 0x4A00: print(f"  TST.B D{w&7}", end="")
    elif (w & 0xFF00) == 0x6600: print(f"  BNE", end="")
    elif (w & 0xFF00) == 0x6700: print(f"  BEQ", end="")
    elif (w & 0xFF00) == 0x6000: print(f"  BRA", end="")
    elif w == 0x4EB9: print("  JSR (abs).L", end="")
    elif w == 0x4EBA: print("  JSR (PC)+d16", end="")
    elif w == 0x4EF9: print("  JMP (abs).L", end="")
    print()

print()
print("=" * 60)
print("3. ROM: $7DCC (VBlank処理ハンドラ) のraw dump")
print("=" * 60)
raw3 = read_mem(0x7DCC, 0x40)
print("  Raw words at $7DCC:")
for i in range(0, len(raw3)-1, 2):
    w = (raw3[i] << 8) | raw3[i+1]
    addr = 0x7DCC + i
    print(f"    ${addr:04X}: ${w:04X}", end="")
    if w == 0x4E75: print("  RTS", end="")
    elif w == 0x33FC: print("  MOVE.W #imm, (abs).L", end="")
    elif (w & 0xF1FF) == 0x3039: print(f"  MOVE.W (abs).L, D{(w>>9)&7}", end="")
    print()

print()
print("=" * 60)
print("4. Z80 GEMS領域の監視")
print("=" * 60)

# Step to frame 37 (just before FF019C is set)
step(37)
print(f"\n--- Frame 37 ---")
ff019c = read_word(0xFF019C)
print(f"  $FF019C = ${ff019c:04X}")

# Z80 RAM areas used by GEMS
for area_start, area_name in [(0x1C00, "GEMS cmd"), (0x0100, "GEMS status"), (0x1F00, "GEMS mailbox")]:
    try:
        d = read_z80(area_start, 32)
        dump_hex(d, area_start, area_name)
    except Exception as e:
        print(f"  {area_name}: 読み取りエラー: {e}")

# Step frame by frame and monitor Z80 RAM changes
for frame in range(38, 55):
    step(1)
    ff019c = read_word(0xFF019C)
    ff0066 = read_word(0xFF0066)
    cpu = get_cpu()
    pc = cpu.get("pc", 0)
    
    print(f"\n--- Frame {frame} ---")
    print(f"  PC=${pc:08X}  $FF019C=${ff019c:04X}  $FF0066=${ff0066:04X}")
    
    # Check key Z80 areas
    try:
        gems_cmd = read_z80(0x1C00, 16)
        gems_status = read_z80(0x0100, 8)
        print(f"  Z80[$1C00-$1C0F]: {' '.join(f'{b:02X}' for b in gems_cmd)}")
        print(f"  Z80[$0100-$0107]: {' '.join(f'{b:02X}' for b in gems_status)}")
    except Exception as e:
        print(f"  Z80読み取りエラー: {e}")

print()
print("=" * 60)
print("5. トレースリング (frame 54付近)")
print("=" * 60)
trace = get_trace()
ring = trace.get("trace_ring", [])
print(f"  トレースエントリ数: {len(ring)}")
for entry in ring:
    pc_val = entry.get("pc", 0)
    # Look for code in $7C3C-$7E90 range (main loop Z80 paths)
    if 0x7C3C <= pc_val <= 0x7EA0:
        print(f"  PC=${pc_val:08X}")
    if 0x85B0 <= pc_val <= 0x86B0:
        print(f"  PC=${pc_val:08X} (Phase A?)")

print("\n完了")
