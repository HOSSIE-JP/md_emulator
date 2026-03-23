"""Render planes A and B separately and save as PNG"""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8115/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

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

for plane_name in ['A', 'B']:
    data = api(f"/vdp/plane?name={plane_name}")
    w = data['width']
    h = data['height']
    pixels = data['pixels_argb']
    write_png(f'tools/plane_{plane_name}.png', w, h, pixels)
    print(f"Plane {plane_name}: {w}x{h} saved")

# Also render tile sheet
data = api("/vdp/tiles?palette=0")
w = data['width']
h = data['height']
pixels = data['pixels_argb']
write_png('tools/tiles_pal0.png', w, h, pixels)
print(f"Tiles (pal 0): {w}x{h} saved")
