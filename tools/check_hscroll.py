"""Check hscroll table values for Plane A and B."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

regs = api_get("/vdp/registers")
r13 = regs["registers"][13]
hs_addr = (r13 & 0x3F) << 10  # hscroll table base in VRAM
print(f"R13 = 0x{r13:02X}, hscroll base = 0x{hs_addr:04X}")

# Read hscroll table for 224 lines (each line: 4 bytes = 2 words)
hs_len = 224 * 4
vram_data = api_get(f"/vdp/vram?addr={hs_addr}&len={hs_len}")
data = vram_data["data"]

print(f"\nHscroll table (first 30 lines):")
nonzero_a = 0
nonzero_b = 0
for i in range(min(30, 224)):
    off = i * 4
    hs_a = ((data[off] << 8) | data[off+1])
    hs_b = ((data[off+2] << 8) | data[off+3])
    if hs_a > 32767: hs_a -= 65536
    if hs_b > 32767: hs_b -= 65536
    marker = ""
    if hs_a != 0 or hs_b != 0:
        marker = " <-- NON-ZERO"
    print(f"  Line {i:3d}: hscroll_a = {hs_a:+5d}, hscroll_b = {hs_b:+5d}{marker}")

for i in range(224):
    off = i * 4
    hs_a = ((data[off] << 8) | data[off+1])
    hs_b = ((data[off+2] << 8) | data[off+3])
    if hs_a != 0: nonzero_a += 1
    if hs_b != 0: nonzero_b += 1

print(f"\nNon-zero hscroll_a lines: {nonzero_a}")
print(f"Non-zero hscroll_b lines: {nonzero_b}")
