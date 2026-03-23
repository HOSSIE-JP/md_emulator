"""Deep HInt diagnostic: check if HInt fires and whether hscroll is populated.
Uses correct API endpoints.
"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read().decode())

# Reset and step to title screen
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

# Read current state
regs = api_get("/vdp/registers")["registers"]
hint_en = (regs[0] >> 4) & 1
hs_mode = regs[0xB] & 3
hint_counter_reg = regs[0xA]
hs_addr = (regs[0xD] & 0x3F) << 10
sr_mask = None
print(f"HInt enabled={hint_en}, HScroll mode={hs_mode}, HInt counter reg=R0xA={hint_counter_reg}")
print(f"HScroll addr=0x{hs_addr:04X}")

# Get the HBlank vector from ROM (via cpu/memory endpoint)
hint_vec = api_get("/cpu/memory?addr=112&len=4")  # 0x70 = 112
data = hint_vec["data"]
handler_addr = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
print(f"HBlank handler at 0x{handler_addr:08X}")

# Read handler code
handler_code = api_get(f"/cpu/memory?addr={handler_addr}&len=64")["data"]
print(f"Handler bytes: {' '.join(f'{b:02X}' for b in handler_code[:64])}")

# VBlank vector
vbl_vec = api_get("/cpu/memory?addr=120&len=4")["data"]
vbl_addr = (vbl_vec[0] << 24) | (vbl_vec[1] << 16) | (vbl_vec[2] << 8) | vbl_vec[3]
print(f"VBlank handler at 0x{vbl_addr:08X}")

# CPU state (SR to check interrupt mask)
cpu = api_get("/cpu/state")
if "cpu" in cpu:
    c = cpu["cpu"]
    sr = c.get("sr", 0)
    mask = (sr >> 8) & 7
    print(f"CPU SR=0x{sr:04X}, interrupt mask={mask}")
    print(f"  PC=0x{c.get('pc', 0):08X}")

# Check hscroll table right now
vram_data = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero_a = 0
for line in range(224):
    offset = line * 4
    if offset + 3 < len(vram_data):
        hs_a = (vram_data[offset] << 8) | vram_data[offset + 1]
        if hs_a != 0: nonzero_a += 1
print(f"\nHScroll table now: nonzero_A={nonzero_a}")

# Step 1 more frame and check trace for INT4
api_post("/emulator/step", {"frames": 1})
trace = api_get("/cpu/trace")
ring = trace.get("trace_ring", [])
exc_trace = trace.get("exception_trace", [])
int4_count = sum(1 for t in ring if "INT4" in t.get("mnemonic", ""))
int6_count = sum(1 for t in ring if "INT6" in t.get("mnemonic", ""))
print(f"\nTrace ring: {len(ring)} entries, INT4={int4_count}, INT6={int6_count}")
if exc_trace:
    print(f"Exception trace: {len(exc_trace)} entries")
    for t in exc_trace[:5]:
        print(f"  {t.get('mnemonic','')} PC=0x{t.get('pc',0):08X}")

# Show some trace entries around INT
for i, t in enumerate(ring):
    m = t.get("mnemonic", "")
    if "INT" in m:
        print(f"  [{i}] {m} PC=0x{t.get('pc',0):08X} cycles={t.get('cycles',0)}")

# Re-check hscroll after the frame
vram_data2 = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero_a2 = 0
sample_lines = []
for line in range(224):
    offset = line * 4
    if offset + 3 < len(vram_data2):
        hs_a = (vram_data2[offset] << 8) | vram_data2[offset + 1]
        if hs_a != 0:
            nonzero_a2 += 1
            hs_a_s = hs_a if hs_a < 0x8000 else hs_a - 0x10000
            sample_lines.append((line, hs_a_s))
                
print(f"\nAfter +1 frame: nonzero_A lines={nonzero_a2}")
if sample_lines:
    for line, v in sample_lines[:20]:
        print(f"  line {line}: hs_A={v}")
