"""Verify Puyo Puyo with immediate DMA fix (target30, port 8113) - correct API"""
import requests

BASE = "http://127.0.0.1:8113/api/v1"

def api(method, path, **kw):
    r = getattr(requests, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

# Reset first - reload ROM
api("post", "/emulator/load-rom-path", json={"path": "D:/homebrew/puyo.bin"})
print("ROM loaded")

# Run 300 frames 
api("post", "/emulator/step", json={"frames": 300})
print("After 300 frames:")

# Check CPU state
cpu = api("get", "/cpu/state")
m = cpu["cpu"]["m68k"]
print(f"  PC=0x{m['pc']:06X} SR=0x{m['sr']:04X} cycles={m['total_cycles']}")

# Check DMA debug
vdp = api("get", "/vdp/registers")
print(f"  Frame: {vdp['frame']}")
print(f"  DMA count: {vdp.get('dma_68k_count', 'N/A')}")
print(f"  DMA total words: {vdp.get('dma_68k_total_words', 'N/A')}")
print(f"  Last DMA target: 0x{vdp.get('last_dma_target_addr', 0):04X}")
print(f"  Last DMA source: 0x{vdp.get('last_dma_source', 0):06X}")
print(f"  Last DMA length: {vdp.get('last_dma_length', 0)}")
print(f"  VDP ctrl writes: {vdp['ctrl_writes']}, data writes: {vdp['data_writes']}")

# Check SAT in VRAM at 0xBC00
sat_data = api("get", "/vdp/vram", params={"addr": 0xBC00, "len": 128})
sat_bytes = bytes(sat_data["data"])
print(f"\n  SAT first 32 bytes: {sat_bytes[:32].hex()}")

# Check RAM SAT buffer at 0xFF0E86
ram_sat = api("get", "/cpu/memory", params={"addr": 0xFF0E86, "len": 128})
ram_bytes = bytes(ram_sat["data"])
print(f"  RAM SAT first 32: {ram_bytes[:32].hex()}")

match = sat_bytes[:64] == ram_bytes[:64]
print(f"  SAT VRAM == RAM buffer: {match}")

# Count sprites via link chain
sprites = 0
idx = 0
visited = set()
while True:
    off = idx * 8
    if off + 8 > len(sat_bytes) or idx in visited:
        break
    visited.add(idx)
    entry = sat_bytes[off:off+8]
    if any(b != 0 for b in entry):
        sprites += 1
    link = entry[3] & 0x7F
    if link == 0:
        break
    idx = link
print(f"  Sprite chain length: {sprites}")

# Parse first visible sprites
print("\n  First 8 SAT entries:")
for i in range(8):
    off = i * 8
    if off + 8 > len(sat_bytes):
        break
    y = ((sat_bytes[off] << 8) | sat_bytes[off+1]) & 0x3FF
    size = sat_bytes[off+2]
    link = sat_bytes[off+3] & 0x7F
    attr = (sat_bytes[off+4] << 8) | sat_bytes[off+5]
    x = ((sat_bytes[off+6] << 8) | sat_bytes[off+7]) & 0x1FF
    h = ((size >> 2) & 3) + 1
    w = (size & 3) + 1
    tile = attr & 0x7FF
    pal = (attr >> 13) & 3
    pri = (attr >> 15) & 1
    print(f"    [{i}] Y={y-128:4d} X={x-128:4d} size={w}x{h} tile=0x{tile:03X} pal={pal} pri={pri} link={link}")

# Run more to title screen
api("post", "/emulator/step", json={"frames": 600})
print("\nAfter 900 frames total:")

vdp2 = api("get", "/vdp/registers")
print(f"  Frame: {vdp2['frame']}")
print(f"  DMA count: {vdp2.get('dma_68k_count', 'N/A')}")

# CRAM
cram = api("get", "/vdp/cram")
cram_data = cram["cram"]
non_zero = sum(1 for c in cram_data if c != 0)
print(f"  CRAM non-zero: {non_zero}/64")

# SAT again
sat_data2 = api("get", "/vdp/vram", params={"addr": 0xBC00, "len": 128})
sat_bytes2 = bytes(sat_data2["data"])
print(f"  SAT first 32 bytes: {sat_bytes2[:32].hex()}")

# Sprites at 900
sprites2 = 0
idx = 0
visited = set()
while True:
    off = idx * 8
    if off + 8 > len(sat_bytes2) or idx in visited:
        break
    visited.add(idx)
    entry = sat_bytes2[off:off+8]
    if any(b != 0 for b in entry):
        sprites2 += 1
    link = entry[3] & 0x7F
    if link == 0:
        break
    idx = link
print(f"  Sprite chain length: {sprites2}")

print("\n=== DMA fix verification complete ===")
