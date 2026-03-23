"""Capture demo screen and analyze Plane B striping."""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

def write_png(filename, w, h, pixels_argb):
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            argb = pixels_argb[y * w + x] & 0xFFFFFFFF
            r = (argb >> 16) & 0xFF
            g = (argb >> 8) & 0xFF
            b = argb & 0xFF
            raw += bytes([r, g, b])
    compressed = zlib.compress(raw)
    def chunk(ctype, cdata):
        c = ctype + cdata
        return struct.pack('>I', len(cdata)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    with open(filename, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b'IDAT', compressed))
        f.write(chunk(b'IEND', b''))

# Reset and go to demo screen
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 2700})

# Capture frame
frame = api_get("/video/frame")
write_png("tools/demo_t32.png", frame["width"], frame["height"], frame["pixels_argb"])
print(f"Saved demo_t32.png ({frame['width']}x{frame['height']})")

regs = api_get("/vdp/registers")["registers"]
print(f"R0=0x{regs[0]:02X} R1=0x{regs[1]:02X} R0xB=0x{regs[0xB]:02X} R0xC=0x{regs[0xC]:02X}")
print(f"R16=0x{regs[0x10]:02X} R11=0x{regs[0x11]:02X} R12=0x{regs[0x12]:02X}")
print(f"HInt en={(regs[0]>>4)&1}, HScroll mode={regs[0xB]&3}, VScroll mode={(regs[0xB]>>2)&1}")

# Plane B analysis
plane_b_addr = (regs[4] & 0x07) << 13
sw, sh = {0:32,1:64,3:128}.get(regs[0x10]&3, 32), {0:32,1:64,3:128}.get((regs[0x10]>>4)&3, 32)
print(f"\nPlane B at 0x{plane_b_addr:04X}, scroll={sw}x{sh}")

# Read plane B nametable
vram = api_get(f"/vdp/vram?addr={plane_b_addr}&len={sw*sh*2}")["data"]

# Analyze tile patterns row by row for first 28 visible rows
print("\nPlane B first 40 cols, rows 0-27:")
for row in range(28):
    tiles = []
    for col in range(40):
        off = (row * sw + col) * 2
        if off + 1 < len(vram):
            entry = (vram[off] << 8) | vram[off + 1]
            tile_idx = entry & 0x7FF
            tiles.append(tile_idx)
    # Check if this row is identical to any earlier row
    print(f"  Row {row:2d}: tiles {min(tiles):4d}-{max(tiles):4d} unique={len(set(tiles)):2d}")

# Also check the per-line framebuffer hashes to find the stripe pattern
fb = frame["pixels_argb"]
w = frame["width"]
print("\nFramebuffer per-line hash (looking for pattern):")
prev_hash = None
repeat_count = 0
for y in range(224):
    row_data = tuple(fb[y*w:(y+1)*w])
    h = hash(row_data)
    if h == prev_hash:
        repeat_count += 1
    else:
        if repeat_count > 0:
            print(f"    (repeated {repeat_count} more times)")
        # Count unique colors in this line
        colors = set(c & 0xFFFFFFFF for c in row_data)
        print(f"  line {y:3d}: {len(colors):2d} colors, first_px=0x{row_data[0]&0xFFFFFFFF:08X}")
        repeat_count = 0
    prev_hash = h
if repeat_count > 0:
    print(f"    (repeated {repeat_count} more times)")
