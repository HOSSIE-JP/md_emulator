"""Check RAM flag $FF013A at various frame points."""
import urllib.request, json

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

prev = 0
for target in [10, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200]:
    api_post("/emulator/step", {"frames": target - prev})
    prev = target
    flag = api_get("/cpu/memory?addr=16711994&len=8")["data"]  # $FF013A
    regs = api_get("/vdp/registers")["registers"]
    hint_en = (regs[0] >> 4) & 1
    hint_del = api_get("/vdp/registers").get("hint_delivered", "?")
    print(f"Frame {target:5d}: $FF013A={flag[0]} HInt_en={hint_en} hint_del={hint_del} "
          f"$013B={flag[1]} $013C-D={flag[2]:02X}{flag[3]:02X} $013E-F={flag[4]:02X}{flag[5]:02X} $0140-1={flag[6]:02X}{flag[7]:02X}")
