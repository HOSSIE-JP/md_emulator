"""Render Plane A and B separately on the demo gameplay screen."""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

def save_png(filename, w, h, pixel_list):
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            argb = pixel_list[y * w + x] & 0xFFFFFFFF
            raw += bytes([(argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF])
    def png_chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    with open(filename, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)))
        f.write(png_chunk(b'IDAT', zlib.compress(raw)))
        f.write(png_chunk(b'IEND', b''))

for plane_name in ['A', 'B']:
    data = api_get(f"/vdp/plane?name={plane_name}")
    w = data["width"]
    h = data["height"]
    px = data["pixels_argb"]
    save_png(f"plane_{plane_name}_demo.png", w, h, px)
    print(f"Plane {plane_name}: {w}x{h}, saved")

frame = api_get("/video/frame")
save_png("demo_composite.png", frame["width"], frame["height"], frame["pixels_argb"])
print(f"Composite saved")
