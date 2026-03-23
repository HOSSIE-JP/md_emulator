"""Check HInt/VInt delivery counts at different frame points."""
import urllib.request, json

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

checkpoints = [10, 90, 300, 500, 900]
for fc in checkpoints:
    api_post("/emulator/step", {"frames": fc})
    vdp = api_get("/vdp/registers")
    regs = vdp["registers"]
    hint_en = (regs[0] >> 4) & 1 
    hint_del = vdp.get("hint_delivered", "N/A")
    vint_del = vdp.get("vint_delivered", "N/A")
    frame = vdp.get("frame", "?")
    
    m68k = api_get("/cpu/state")["cpu"]["m68k"]
    sr = m68k["sr"]
    mask = (sr >> 8) & 7
    
    print(f"After +{fc:4d} frames (frame={frame}): "
          f"HInt_en={hint_en} hint_del={hint_del} vint_del={vint_del} "
          f"SR_mask={mask} pending_ipl={m68k['pending_ipl']}")

# Now at title screen (frame ~1800)
# Step 1 more and check
prev_hint = api_get("/vdp/registers").get("hint_delivered", 0)
prev_vint = api_get("/vdp/registers").get("vint_delivered", 0)
api_post("/emulator/step", {"frames": 1})
post = api_get("/vdp/registers")
new_hint = post.get("hint_delivered", 0)
new_vint = post.get("vint_delivered", 0)
print(f"\nDuring 1 frame at title: hint_delivered +{new_hint - prev_hint}, vint_delivered +{new_vint - prev_vint}")

# Check hscroll table
regs = post["registers"]
hs_addr = (regs[0xD] & 0x3F) << 10
hs_mode = regs[0xB] & 3
vram = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero = sum(1 for i in range(224) if i*4+3 < len(vram) and ((vram[i*4] << 8) | vram[i*4+1]) != 0)
print(f"HScroll mode={hs_mode} addr=0x{hs_addr:04X} nonzero_lines={nonzero}")
