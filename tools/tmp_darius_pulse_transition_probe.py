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
for _ in range(240):
    step_one()
set_buttons(BTN_C)
for _ in range(120):
    step_one()
set_buttons(0)
for _ in range(30):
    step_one()

history = []
for repeat in range(20):
    set_buttons(BTN_C)
    for frame in range(10):
        step_one()
        cpu = req("GET", "/cpu/state")["cpu"]
        apu = req("GET", "/apu/state")
        snap = {
            "phase": f"on-{repeat}-{frame+1}",
            "pc": cpu["z80_pc"],
            "sp": cpu["z80"]["sp"],
            "trace": apu.get("z80_trace_ring", [])[:16],
        }
        history.append(snap)
        if cpu["z80_pc"] < 0x0200:
            for item in history[-8:]:
                print(f"{item['phase']} pc=${item['pc']:04X} sp=${item['sp']:04X}")
                for entry in item["trace"][:8]:
                    print(f"  {entry}")
            raise SystemExit
    set_buttons(0)
    for frame in range(10):
        step_one()
        cpu = req("GET", "/cpu/state")["cpu"]
        apu = req("GET", "/apu/state")
        snap = {
            "phase": f"off-{repeat}-{frame+1}",
            "pc": cpu["z80_pc"],
            "sp": cpu["z80"]["sp"],
            "trace": apu.get("z80_trace_ring", [])[:16],
        }
        history.append(snap)
        if cpu["z80_pc"] < 0x0200:
            for item in history[-8:]:
                print(f"{item['phase']} pc=${item['pc']:04X} sp=${item['sp']:04X}")
                for entry in item["trace"][:8]:
                    print(f"  {entry}")
            raise SystemExit

print("no low transition during pulses")