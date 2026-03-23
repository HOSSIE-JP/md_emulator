"""Go to demo gameplay screen and capture."""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

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

# Reset and go far ahead
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Go to demo screen (around 1800+)
api_post("/emulator/step", {"frames": 1800})

# Check state
regs = api_get("/vdp/registers")["registers"]
print(f"Frame 1800: HS mode={regs[11] & 3}, VS mode={(regs[11] >> 2) & 1}")

f = api_get("/video/frame")
save_png("demo_1800.png", f["width"], f["height"], f["pixels_argb"])
print("Saved demo_1800.png")

# Try even further
api_post("/emulator/step", {"frames": 300})
regs = api_get("/vdp/registers")["registers"]
flag = api_get("/cpu/memory?addr=16711994&len=1")["data"][0]
print(f"\nFrame 2100: flag={flag}, HS mode={regs[11] & 3}, VS mode={(regs[11] >> 2) & 1}")
f = api_get("/video/frame")
save_png("demo_2100.png", f["width"], f["height"], f["pixels_argb"])
print("Saved demo_2100.png")

# Even further
api_post("/emulator/step", {"frames": 300})
regs = api_get("/vdp/registers")["registers"]
flag = api_get("/cpu/memory?addr=16711994&len=1")["data"][0]
sv = api_get("/vdp/scanline-vsram")["scanline_vsram_a"]
nonzero = sum(1 for v in sv if v != 0)
print(f"\nFrame 2400: flag={flag}, HS mode={regs[11] & 3}, VS mode={(regs[11] >> 2) & 1}, vsram_nonzero={nonzero}")
f = api_get("/video/frame")
save_png("demo_2400.png", f["width"], f["height"], f["pixels_argb"])
print("Saved demo_2400.png")

# Go even further to find the demo game
for step in range(5):
    api_post("/emulator/step", {"frames": 300})
    regs = api_get("/vdp/registers")["registers"]
    flag = api_get("/cpu/memory?addr=16711994&len=1")["data"][0]
    frame_num = 2400 + (step + 1) * 300
    vs_mode = (regs[11] >> 2) & 1
    hs_mode = regs[11] & 3
    print(f"\nFrame {frame_num}: flag={flag}, HS={hs_mode}, VS={vs_mode}")
    if vs_mode != 0 or hs_mode != 3:
        f = api_get("/video/frame")
        save_png(f"demo_{frame_num}.png", f["width"], f["height"], f["pixels_argb"])
        print(f"  ** Different mode! Saved demo_{frame_num}.png")
