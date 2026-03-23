"""Check tile 0x500 to see if it's transparent."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Tile 0x500, each tile is 32 bytes (8x8 4bpp)
tile_addr = 0x500 * 32  # = 0xA000
tile_data = api_get(f"/vdp/vram?addr={tile_addr}&len=32")["data"]

# Decode all pixels
all_zero = True
for byte_idx in range(32):
    hi = (tile_data[byte_idx] >> 4) & 0xF
    lo = tile_data[byte_idx] & 0xF
    if hi != 0 or lo != 0:
        all_zero = False
        
print(f"Tile 0x500 at VRAM 0x{tile_addr:04X}:")
print(f"  Raw: {' '.join(f'{b:02X}' for b in tile_data)}")
print(f"  All zero pixels: {all_zero}")

if not all_zero:
    print("  Pixel grid:")
    for row in range(8):
        pixels = []
        for col in range(4):
            byte = tile_data[row * 4 + col]
            pixels.append((byte >> 4) & 0xF)
            pixels.append(byte & 0xF)
        print(f"    {''.join(f'{p:X}' for p in pixels)}")
