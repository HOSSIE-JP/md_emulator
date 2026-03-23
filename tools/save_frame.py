"""Save current frame as PNG for viewing"""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8114/api/v1"
frame = json.loads(urllib.request.urlopen(f'{BASE}/video/frame').read())
fb = frame['pixels_argb']
width = frame.get('width', 320)
height = frame.get('height', 224)

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

write_png('tools/demo_screen.png', width, height, fb)
print(f'Saved demo_screen.png ({width}x{height})')

# Quick color analysis
color_counts = {}
for c in fb:
    c = c & 0xFFFFFFFF
    color_counts[c] = color_counts.get(c, 0) + 1
print(f'Unique colors: {len(color_counts)}')
for cv, cnt in sorted(color_counts.items(), key=lambda x: -x[1])[:5]:
    print(f'  0x{cv:08X}: {cnt} px')
