"""Verify Puyo Puyo with immediate DMA fix (target30, port 8113)"""
import requests, struct, time

BASE = "http://127.0.0.1:8113/api/v1"

def api(method, path, **kw):
    r = getattr(requests, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

# Load ROM
api("post", "/emulator/load-rom-path", json={"path": "D:/homebrew/puyo.bin"})
print("ROM loaded")

# Run 300 frames to get past SEGA logo
api("post", "/emulator/step", json={"cycles": 300, "unit": "frame"})
print("After 300 frames:")

# Check DMA debug
vdp = api("get", "/vdp/registers")
print(f"  DMA count: {vdp.get('dma_68k_count', 'N/A')}")
print(f"  DMA total words: {vdp.get('dma_68k_total_words', 'N/A')}")
print(f"  Last DMA target: 0x{vdp.get('last_dma_target_addr', 0):04X}")
print(f"  Last DMA source: 0x{vdp.get('last_dma_source', 0):06X}")
print(f"  Last DMA length: {vdp.get('last_dma_length', 0)}")

# Check SAT in VRAM at 0xBC00
sat_data = api("get", "/vdp/vram", params={"addr": 0xBC00, "len": 128})
sat_bytes = bytes(sat_data["data"])
print(f"\n  SAT first 32 bytes: {sat_bytes[:32].hex()}")

# Check RAM SAT buffer at 0xFF0E86
ram_sat = api("get", "/cpu/memory", params={"addr": 0xFF0E86, "len": 128})
ram_bytes = bytes(ram_sat["data"])
print(f"  RAM SAT first 32: {ram_bytes[:32].hex()}")

# Compare
match = sat_bytes[:64] == ram_bytes[:64]
print(f"  SAT VRAM == RAM buffer: {match}")

# Count non-zero SAT entries  
sprites = 0
for i in range(0, min(640, len(sat_bytes)), 8):
    entry = sat_bytes[i:i+8]
    if any(b != 0 for b in entry):
        sprites += 1
    # Check link field - if 0, end of list (except entry 0)
    if i > 0:
        link = entry[3] & 0x7F
        if link == 0:
            break
print(f"  Active SAT entries: {sprites}")

# Parse first few sprites
print("\n  First 5 SAT entries:")
for i in range(5):
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
    hf = (attr >> 11) & 1
    vf = (attr >> 12) & 1
    print(f"    [{i}] Y={y-128:4d} X={x-128:4d} size={w}x{h} tile=0x{tile:03X} pal={pal} pri={pri} link={link}")

# Run more frames to title screen
api("post", "/emulator/step", json={"cycles": 600, "unit": "frame"})
print("\nAfter 900 frames:")

# Check CRAM
cram = api("get", "/vdp/cram")
cram_data = cram["cram"]
non_zero = sum(1 for c in cram_data if c != 0)
print(f"  CRAM non-zero: {non_zero}/64")

# Check SAT again
sat_data2 = api("get", "/vdp/vram", params={"addr": 0xBC00, "len": 128})
sat_bytes2 = bytes(sat_data2["data"])
print(f"  SAT first 32 bytes: {sat_bytes2[:32].hex()}")

sprites2 = 0
for i in range(0, min(640, len(sat_bytes2)), 8):
    entry = sat_bytes2[i:i+8]
    if any(b != 0 for b in entry):
        sprites2 += 1
    if i > 0:
        link = entry[3] & 0x7F
        if link == 0:
            break
print(f"  Active SAT entries: {sprites2}")

# Framebuffer check
fb = api("get", "/vdp/framebuffer")
pixels = fb.get("pixels", fb.get("data", []))
non_black = sum(1 for i in range(0, len(pixels)-2, 4) if pixels[i] or pixels[i+1] or pixels[i+2])
total = 320 * 224
print(f"  Non-black pixels: {non_black}/{total}")

print("\n=== DMA fix verification complete ===")
