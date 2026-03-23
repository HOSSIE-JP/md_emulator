"""Check VSRAM + save frame for demo screen analysis"""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8115/api/v1"

def api(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# Get VSRAM
vsram = api("/vdp/vsram")["vsram"]
print(f"VSRAM entries: {len(vsram)}")
for i, v in enumerate(vsram):
    label = "A" if i % 2 == 0 else "B"
    col = i // 2
    print(f"  [{i:2d}] col={col} plane={label} = 0x{v:04X} ({v})")

# Get registers
regs = api("/vdp/registers")["registers"]
print(f"\nVDP key registers:")
print(f"  R0=0x{regs[0]:02X} (HInt en={(regs[0]>>4)&1})")
print(f"  R1=0x{regs[1]:02X} (Display en={(regs[1]>>6)&1})")
print(f"  R0xA=0x{regs[0xA]:02X} (HInt counter={regs[0xA]})")
print(f"  R0xB=0x{regs[0xB]:02X} (hscroll_mode={regs[0xB]&3} vscroll_mode={(regs[0xB]>>2)&1})")
print(f"  R0xC=0x{regs[0xC]:02X} (H40={((regs[0xC])&0x81)!=0})")
print(f"  R0xD=0x{regs[0xD]:02X} (hscroll_addr=0x{((regs[0xD]&0x3F)<<10):04X})")

# Get hscroll data
hscroll_addr = (regs[0xD] & 0x3F) << 10
hscroll_mode = regs[0xB] & 3
print(f"\nHScroll mode={hscroll_mode}, data at 0x{hscroll_addr:04X}")

vram = bytes(api(f"/vdp/vram?addr={hscroll_addr}&len=1792")["data"])
if hscroll_mode == 0:
    hs_a = (vram[0] << 8) | vram[1]
    hs_b = (vram[2] << 8) | vram[3]
    print(f"  Full screen: hscroll_A=0x{hs_a:04X}({(hs_a ^ 0x8000) - 0x8000 if hs_a > 0x7FFF else hs_a}) hscroll_B=0x{hs_b:04X}({(hs_b ^ 0x8000) - 0x8000 if hs_b > 0x7FFF else hs_b})")
elif hscroll_mode == 3:
    print("  Per-line hscroll (first 20 lines):")
    for line in range(20):
        offset = line * 4
        if offset + 3 < len(vram):
            hs_a = (vram[offset] << 8) | vram[offset + 1]
            hs_b = (vram[offset + 2] << 8) | vram[offset + 3]
            hs_a_signed = hs_a if hs_a < 0x8000 else hs_a - 0x10000
            hs_b_signed = hs_b if hs_b < 0x8000 else hs_b - 0x10000
            print(f"    line {line:3d}: A={hs_a_signed:5d} B={hs_b_signed:5d}")

# Save frame
frame = api("/video/frame")
fb = frame['pixels_argb']
w = frame.get('width', 320)
h = frame.get('height', 224)

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

write_png('tools/demo_frame_8115.png', w, h, fb)
print(f"\nSaved demo_frame_8115.png")
