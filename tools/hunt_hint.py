"""Step through title/transition and look for HInt stripe frames"""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read().decode())

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

# Reset
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step and capture at various points
frame_counts = [300, 300, 300, 300, 300, 300, 120, 120, 120, 120]
total = 0
for i, fc in enumerate(frame_counts):
    api_post("/emulator/step", {"frames": fc})
    total += fc
    regs = api_get("/vdp/registers")["registers"]
    hint_en = (regs[0] >> 4) & 1
    hscroll_mode = regs[0xB] & 3
    vscroll_mode = (regs[0xB] >> 2) & 1
    
    # Check hscroll table for non-zero values
    hscroll_addr = (regs[0xD] & 0x3F) << 10
    vram = bytes(api_get(f"/vdp/vram?addr={hscroll_addr}&len=896")["data"])
    nonzero_hs = 0
    if hscroll_mode == 3:
        for line in range(224):
            offset = line * 4
            if offset + 3 < len(vram):
                hs_a = (vram[offset] << 8) | vram[offset + 1]
                if hs_a != 0:
                    nonzero_hs += 1
    
    frame = api_get("/video/frame")
    fb = frame['pixels_argb']
    
    # Count unique colors to detect if something interesting is happening
    colors = set(c & 0xFFFFFFFF for c in fb)
    
    marker = " <-- HINT+nonzero_hs" if (hint_en and nonzero_hs > 0) else ""
    print(f"Frame {total:5d}: HInt={hint_en} hs_mode={hscroll_mode} vs_mode={vscroll_mode} "
          f"nonzero_hs={nonzero_hs:3d} colors={len(colors)}{marker}")
    
    if hint_en and nonzero_hs > 0:
        write_png(f'tools/hint_frame_{total}.png', frame['width'], frame['height'], fb)
        print(f"  Saved hint_frame_{total}.png")
        # Show some hscroll values
        print(f"  Hscroll samples:")
        for line in [0, 50, 100, 150, 200]:
            offset = line * 4
            if offset + 3 < len(vram):
                hs_a = (vram[offset] << 8) | vram[offset + 1]
                hs_a_signed = hs_a if hs_a < 0x8000 else hs_a - 0x10000
                print(f"    line {line}: A={hs_a_signed}")
