"""Capture title screen from port 8116 (target32)."""
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

# Title
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})
frame = api_get("/video/frame")
write_png("tools/title_t32.png", frame["width"], frame["height"], frame["pixels_argb"])
print("Saved title_t32.png")

regs = api_get("/vdp/registers")
print(f"Title: hint_del={regs.get('hint_delivered',0)} vint_del={regs.get('vint_delivered',0)}")

# Transition (around 1200) 
api_post("/emulator/step", {"frames": 300})
frame2 = api_get("/video/frame")
write_png("tools/transition_t32.png", frame2["width"], frame2["height"], frame2["pixels_argb"])
print("Saved transition_t32.png")

regs2 = api_get("/vdp/registers")["registers"]
print(f"Transition: R0=0x{regs2[0]:02X} HInt_en={(regs2[0]>>4)&1}")
