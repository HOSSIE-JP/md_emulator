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


def dump(title, start, data):
    print(title)
    for offset in range(0, len(data), 16):
        addr = start + offset
        chunk = data[offset:offset + 16]
        print(f"${addr:04X}: " + " ".join(f"{value:02X}" for value in chunk))


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
step(240)
set_buttons(BTN_C)
step(120)
set_buttons(0)
step(30)
pulse(BTN_C, 10, 10, 20)
step(60)

for frame in range(1, 16):
    step(1)
    cpu = req("GET", "/cpu/state")["cpu"]
    apu = req("GET", "/apu/state")
    pc = cpu["z80_pc"]
    print(f"frame+{frame} pc=${pc:04X} sp=${cpu['z80']['sp']:04X} a=${cpu['z80']['a']:02X} f=${cpu['z80']['f']:02X}")
    if pc < 0x0200 or pc >= 0x6100:
        low = req("GET", "/cpu/memory?addr=10486016&len=64")
        stack_addr = 0xA00000 + cpu["z80"]["sp"]
        stack = req("GET", f"/cpu/memory?addr={stack_addr}&len=32")
        dump("ram[0100..013F]", 0x0100, low["data"])
        dump(f"stack[${cpu['z80']['sp']:04X}..]", cpu["z80"]["sp"], stack["data"])
        for entry in apu.get("z80_trace_ring", [])[:24]:
            print(f"  {entry}")
        break