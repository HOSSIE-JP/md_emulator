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


def step(frames):
    for _ in range(frames):
        req("POST", "/emulator/step", {"frames": 1})


def set_buttons(buttons):
    req("POST", "/input/controller", {"player": 1, "buttons": buttons})


def pulse(buttons, on_frames, off_frames, repeats):
    for _ in range(repeats):
        set_buttons(buttons)
        step(on_frames)
        set_buttons(0)
        step(off_frames)


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
step(240)
set_buttons(BTN_C)
step(120)
set_buttons(0)
step(30)
pulse(BTN_C, 10, 10, 20)
step(60)

for frame in range(1, 1201):
    step(1)
    cpu = req("GET", "/cpu/state")["cpu"]
    apu = req("GET", "/apu/state")
    pc = cpu["z80_pc"]
    bad = 0x6100 <= pc <= 0x7FFF and pc != 0x7F11
    if frame <= 10 or frame % 60 == 0 or bad or pc == 0x0038:
        print(
            f"frame+{frame} pc=${pc:04X} iff1={cpu['z80']['iff1']} pending={cpu['z80']['int_pending']} "
            f"sp=${cpu['z80']['sp']:04X} a=${cpu['z80']['a']:02X} bc=${cpu['z80']['b']:02X}{cpu['z80']['c']:02X} "
            f"de=${cpu['z80']['d']:02X}{cpu['z80']['e']:02X} hl=${cpu['z80']['h']:02X}{cpu['z80']['l']:02X}"
        )
        for entry in apu.get("z80_trace_ring", [])[:12]:
            print(f"  {entry}")
    if bad:
        break