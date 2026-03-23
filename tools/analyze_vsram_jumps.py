"""Analyze VSRAM jumps and look for artifacts in the title screen."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

sv = api_get("/vdp/scanline-vsram")
data = sv["scanline_vsram_a"]

# Convert to signed
signed = []
for v in data:
    if v > 32767:
        signed.append(v - 65536)
    else:
        signed.append(v)

print("Per-scanline VSRAM[0] (signed) - looking for jumps:")
prev = None
for i, v in enumerate(signed):
    jump = ""
    if prev is not None:
        diff = v - prev
        if abs(diff) > 1:
            jump = f"  <--- JUMP of {diff:+d}"
    print(f"  Line {i:3d}: vscroll = {v:+5d}{jump}")
    prev = v
    if i >= 160:
        break

# Also check: what's the scroll size?
regs = api_get("/vdp/registers")
r16 = regs["registers"][16]
sw_bits = r16 & 3
sh_bits = (r16 >> 4) & 3
sw_map = {0: 32, 1: 64, 3: 128}
sh_map = {0: 32, 1: 64, 3: 128}
sw = sw_map.get(sw_bits, 32)
sh = sh_map.get(sh_bits, 32)
print(f"\nScroll size: {sw}x{sh} cells = {sw*8}x{sh*8} pixels")
print(f"R16 = 0x{r16:02X} (sw_bits={sw_bits}, sh_bits={sh_bits})")

# Also check vscroll mode
r11 = regs["registers"][11]
vs_mode = (r11 >> 2) & 1
hs_mode = r11 & 3
print(f"R11 = 0x{r11:02X} (vscroll_mode={vs_mode}, hscroll_mode={hs_mode})")
