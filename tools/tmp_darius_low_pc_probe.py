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

for phase, frames in (("boot", 240), ("press", 120), ("settle", 30)):
    for frame in range(1, frames + 1):
        step(1)
        cpu = req("GET", "/cpu/state")["cpu"]
        apu = req("GET", "/apu/state")
        pc = cpu["z80_pc"]
        if pc < 0x0200 and frame > 1:
            print(f"phase={phase} frame={frame} pc=${pc:04X} sp=${cpu['z80']['sp']:04X}")
            for entry in apu.get("z80_trace_ring", [])[:16]:
                print(f"  {entry}")
            raise SystemExit

set_buttons(BTN_C)
for frame in range(1, 121):
    step(1)
    cpu = req("GET", "/cpu/state")["cpu"]
    apu = req("GET", "/apu/state")
    pc = cpu["z80_pc"]
    if pc < 0x0200:
        print(f"phase=title-c frame={frame} pc=${pc:04X} sp=${cpu['z80']['sp']:04X}")
        for entry in apu.get("z80_trace_ring", [])[:16]:
            print(f"  {entry}")
        raise SystemExit

set_buttons(0)
step(30)

for repeat in range(20):
    set_buttons(BTN_C)
    for frame in range(10):
        step(1)
        cpu = req("GET", "/cpu/state")["cpu"]
        apu = req("GET", "/apu/state")
        pc = cpu["z80_pc"]
        if pc < 0x0200:
            print(f"phase=pulse-on repeat={repeat} frame={frame+1} pc=${pc:04X} sp=${cpu['z80']['sp']:04X}")
            for entry in apu.get("z80_trace_ring", [])[:16]:
                print(f"  {entry}")
            raise SystemExit
    set_buttons(0)
    for frame in range(10):
        step(1)
        cpu = req("GET", "/cpu/state")["cpu"]
        apu = req("GET", "/apu/state")
        pc = cpu["z80_pc"]
        if pc < 0x0200:
            print(f"phase=pulse-off repeat={repeat} frame={frame+1} pc=${pc:04X} sp=${cpu['z80']['sp']:04X}")
            for entry in apu.get("z80_trace_ring", [])[:16]:
                print(f"  {entry}")
            raise SystemExit

print("no low-pc transition observed")