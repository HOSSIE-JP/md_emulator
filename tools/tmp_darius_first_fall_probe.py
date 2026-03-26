import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/roms/darius.bin"
BTN_C = 1 << 5


def req(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def step_one():
    req("POST", "/emulator/step", {"frames": 1})


def set_buttons(buttons):
    req("POST", "/input/controller", {"player": 1, "buttons": buttons})


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})

seen_high = False
history = []

def record(label):
    global seen_high
    cpu = req("GET", "/cpu/state")["cpu"]
    apu = req("GET", "/apu/state")
    pc = cpu["z80_pc"]
    if pc >= 0x0200:
        seen_high = True
    snap = {
        "label": label,
        "pc": pc,
        "sp": cpu["z80"]["sp"],
        "trace": apu.get("z80_trace_ring", [])[:16],
    }
    history.append(snap)
    if seen_high and pc < 0x0200:
        for item in history[-10:]:
            print(f"{item['label']} pc=${item['pc']:04X} sp=${item['sp']:04X}")
            for entry in item["trace"][:8]:
                print(f"  {entry}")
        raise SystemExit


for frame in range(240):
    step_one()
    record(f"boot-{frame+1}")

set_buttons(BTN_C)
for frame in range(120):
    step_one()
    record(f"press-{frame+1}")

set_buttons(0)
for frame in range(30):
    step_one()
    record(f"settle-{frame+1}")

for repeat in range(20):
    set_buttons(BTN_C)
    for frame in range(10):
        step_one()
        record(f"pulse-on-{repeat+1}-{frame+1}")
    set_buttons(0)
    for frame in range(10):
        step_one()
        record(f"pulse-off-{repeat+1}-{frame+1}")

print("no fall observed")