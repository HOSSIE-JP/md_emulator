import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

# CPU state
m68k = api_get("/cpu/state")["cpu"]["m68k"]
pc = m68k["pc"]
sr = m68k["sr"]
mask = (sr >> 8) & 7
print(f"PC=0x{pc:08X} SR=0x{sr:04X} stopped={m68k['stopped']}")
print(f"Interrupt mask={mask}, pending_ipl={m68k['pending_ipl']}")
if m68k.get("last_exception"):
    print(f"last_exception={m68k['last_exception']}")

# VDP regs
regs = api_get("/vdp/registers")["registers"]
hint_en = (regs[0] >> 4) & 1
hs_mode = regs[0xB] & 3
print(f"HInt enabled={hint_en}, HScroll mode={hs_mode}, R0xA={regs[0xA]}")

# Check hscroll table  
hs_addr = (regs[0xD] & 0x3F) << 10
vram = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero = sum(1 for i in range(224) if i*4+3 < len(vram) and ((vram[i*4] << 8) | vram[i*4+1]) != 0)
print(f"HScroll nonzero lines: {nonzero}")

# Step 1 frame, check trace
api_post("/emulator/step", {"frames": 1})
trace = api_get("/cpu/trace")
ring = trace.get("trace_ring", [])
int4 = sum(1 for t in ring if "INT4" in t.get("mnemonic", ""))
int6 = sum(1 for t in ring if "INT6" in t.get("mnemonic", ""))
print(f"\nAfter +1 frame: trace ring={len(ring)}, INT4={int4}, INT6={int6}")

for t in ring[-15:]:
    print(f"  0x{t['pc']:08X} cyc={t['cycles']:3d} {t['mnemonic']}")

# Check hscroll after frame
vram2 = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero2 = sum(1 for i in range(224) if i*4+3 < len(vram2) and ((vram2[i*4] << 8) | vram2[i*4+1]) != 0)
print(f"\nHScroll after +1 frame: nonzero={nonzero2}")
if nonzero2 > 0:
    for i in range(224):
        off = i * 4
        if off + 3 < len(vram2):
            v = (vram2[off] << 8) | vram2[off + 1]
            if v != 0:
                vs = v if v < 0x8000 else v - 0x10000
                print(f"  line {i}: {vs}")
                if i > 30: break
