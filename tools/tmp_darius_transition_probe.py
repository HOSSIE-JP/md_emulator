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


def pulse(buttons, on_frames, off_frames, repeats):
    for _ in range(repeats):
        set_buttons(buttons)
        for _ in range(on_frames):
            step_one()
        set_buttons(0)
        for _ in range(off_frames):
            step_one()


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
pulse(BTN_C, 10, 10, 20)

history = []
for index in range(1, 121):
    step_one()
    cpu = req("GET", "/cpu/state")["cpu"]
    apu = req("GET", "/apu/state")
    snapshot = {
        "index": index,
        "pc": cpu["z80_pc"],
        "sp": cpu["z80"]["sp"],
        "a": cpu["z80"]["a"],
        "f": cpu["z80"]["f"],
        "bc": (cpu["z80"]["b"] << 8) | cpu["z80"]["c"],
        "de": (cpu["z80"]["d"] << 8) | cpu["z80"]["e"],
        "hl": (cpu["z80"]["h"] << 8) | cpu["z80"]["l"],
        "z80_reset": apu.get("z80_reset"),
        "z80_bus_requested": apu.get("z80_bus_requested"),
        "trace": apu.get("z80_trace_ring", [])[:24],
    }
    history.append(snapshot)
    if cpu["z80_pc"] < 0x0200:
        for item in history[-6:]:
            print(
                f"step={item['index']} pc=${item['pc']:04X} sp=${item['sp']:04X} "
                f"a=${item['a']:02X} f=${item['f']:02X} bc=${item['bc']:04X} de=${item['de']:04X} hl=${item['hl']:04X}"
                f" reset={item['z80_reset']} busreq={item['z80_bus_requested']}"
            )
            for entry in item["trace"][:12]:
                print(f"  {entry}")
        break