"""Step to different game states and save frames"""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

def api_get(path):
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

# Reset and load ROM fresh
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Title screen
api_post("/emulator/step", {"frames": 900})
frame = api_get("/video/frame")
write_png('tools/title_screen.png', frame['width'], frame['height'], frame['pixels_argb'])
regs = api_get("/vdp/registers")["registers"]
print(f"Title: R0=0x{regs[0]:02X} R0xA={regs[0xA]} R0xB=0x{regs[0xB]:02X}")
print(f"  HInt en={(regs[0]>>4)&1} HScroll={(regs[0xB]&3)} VScroll={((regs[0xB]>>2)&1)}")

# Demo transition - step more
api_post("/emulator/step", {"frames": 600})
frame = api_get("/video/frame")
write_png('tools/transition.png', frame['width'], frame['height'], frame['pixels_argb'])
regs = api_get("/vdp/registers")["registers"]
print(f"Transition: R0=0x{regs[0]:02X} R0xA={regs[0xA]} R0xB=0x{regs[0xB]:02X}")
print(f"  HInt en={(regs[0]>>4)&1} HScroll={(regs[0xB]&3)} VScroll={((regs[0xB]>>2)&1)}")

# Demo screen
api_post("/emulator/step", {"frames": 600})
frame = api_get("/video/frame")
write_png('tools/demo_screen2.png', frame['width'], frame['height'], frame['pixels_argb'])
regs = api_get("/vdp/registers")["registers"]
print(f"Demo: R0=0x{regs[0]:02X} R0xA={regs[0xA]} R0xB=0x{regs[0xB]:02X}")
print(f"  HInt en={(regs[0]>>4)&1} HScroll={(regs[0xB]&3)} VScroll={((regs[0xB]>>2)&1)}")

# More frames
api_post("/emulator/step", {"frames": 300})
frame = api_get("/video/frame")
write_png('tools/demo_screen3.png', frame['width'], frame['height'], frame['pixels_argb'])
regs = api_get("/vdp/registers")["registers"]
print(f"Demo2: R0=0x{regs[0]:02X} R0xA={regs[0xA]} R0xB=0x{regs[0xB]:02X}")
print(f"  HInt en={(regs[0]>>4)&1} HScroll={(regs[0xB]&3)} VScroll={((regs[0xB]>>2)&1)}")
