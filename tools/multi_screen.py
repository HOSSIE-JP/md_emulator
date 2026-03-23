"""Check multiple screens for stripe artifacts.
Capture title, transition, and demo screens."""
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

# Reset and load
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Check various frames
for target_frame in [100, 300, 600, 900, 1200, 1500, 1800]:
    api_post("/emulator/step", {"frames": target_frame - (target_frame - target_frame)})  
    # Actually need cumulative steps
    
# Let me redo this properly
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

prev = 0
for target_frame in [900, 1200, 1500, 1800]:
    api_post("/emulator/step", {"frames": target_frame - prev})
    prev = target_frame
    
    # Check state
    flag_data = api_get("/cpu/memory?addr=16711994&len=2")["data"]
    flag = flag_data[0]
    
    regs = api_get("/vdp/registers")
    r = regs["registers"]
    hs_mode = r[11] & 3
    vs_mode = (r[11] >> 2) & 1
    
    vsram = api_get("/vdp/vsram")["vsram"]
    
    sv = api_get("/vdp/scanline-vsram")["scanline_vsram_a"]
    nonzero = sum(1 for v in sv if v != 0)
    
    # Check if Plane A has non-transparent tiles
    pa_addr = (r[2] & 0x38) << 10
    pa_first = api_get(f"/vdp/vram?addr={pa_addr}&len=40")["data"]
    first_tiles = []
    for i in range(20):
        entry = (pa_first[i*2] << 8) | pa_first[i*2+1]
        first_tiles.append(entry & 0x7FF)
    
    f = api_get("/video/frame")
    save_png(f"screen_{target_frame}.png", f["width"], f["height"], f["pixels_argb"])
    
    print(f"\nFrame {target_frame}:")
    print(f"  Wave flag=$FF013A: {flag}")
    print(f"  HS mode={hs_mode}, VS mode={vs_mode}")
    print(f"  VSRAM[0]={vsram[0]}, VSRAM[1]={vsram[1]}")
    print(f"  Non-zero scanline VSRAM[0]: {nonzero}/224")
    print(f"  Plane A first tiles: {[hex(t) for t in first_tiles[:5]]}")
    print(f"  Saved screen_{target_frame}.png")
