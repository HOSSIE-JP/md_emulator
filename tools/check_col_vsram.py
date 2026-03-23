"""Examine per-column VSRAM during demo gameplay."""
import urllib.request, json

BASE = "http://localhost:8117/api/v1"

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Already at around frame 3900
vsram = api_get("/vdp/vsram")["vsram"]
print(f"VSRAM entries (all 40 words):")
for i in range(40):
    v = vsram[i]
    signed = v - 65536 if v > 32767 else v
    plane = "A" if i % 2 == 0 else "B"
    col = i // 2
    print(f"  VSRAM[{i:2d}] = {v:5d} (0x{v:04X}) signed={signed:+6d}  [Plane {plane}, col {col}]")

regs = api_get("/vdp/registers")["registers"]
print(f"\nVDP registers:")
print(f"  R11 = 0x{regs[11]:02X} (HS={regs[11] & 3}, VS={(regs[11] >> 2) & 1})")
print(f"  R16 = 0x{regs[16]:02X} (scroll size)")

# Scroll size
r16 = regs[16]
sw = {0:32, 1:64, 3:128}.get(r16 & 3, 32)
sh = {0:32, 1:64, 3:128}.get((r16 >> 4) & 3, 32)
print(f"  Scroll size: {sw}x{sh} cells = {sw*8}x{sh*8} px")

# Mode
h40 = (regs[12] & 0x81) != 0
print(f"  H40 mode: {h40}")
cols = 40 if h40 else 32
print(f"  Screen columns: {cols}")
print(f"  Per-col VSRAM entries: {cols // 2} 2-cell columns")
