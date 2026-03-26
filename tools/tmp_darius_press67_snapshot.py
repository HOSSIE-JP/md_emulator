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


def dump(title, start, data):
    print(title)
    for offset in range(0, len(data), 16):
        addr = start + offset
        chunk = data[offset:offset + 16]
        print(f"${addr:04X}: " + " ".join(f"{value:02X}" for value in chunk))


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    step_one()
set_buttons(BTN_C)
for frame in range(67):
    step_one()

cpu = req("GET", "/cpu/state")["cpu"]
apu = req("GET", "/apu/state")

print(json.dumps({
    "pc": cpu["z80_pc"],
    "sp": cpu["z80"]["sp"],
    "a": cpu["z80"]["a"],
    "bc": (cpu["z80"]["b"] << 8) | cpu["z80"]["c"],
    "de": (cpu["z80"]["d"] << 8) | cpu["z80"]["e"],
    "hl": (cpu["z80"]["h"] << 8) | cpu["z80"]["l"],
    "trace": apu.get("z80_trace_ring", [])[:24],
}, ensure_ascii=False, indent=2))

pc_mem = req("GET", f"/cpu/memory?addr={0xA00000 + 0x07A0}&len=352")
stack_mem = req("GET", f"/cpu/memory?addr={0xA00000 + cpu['z80']['sp'] - 32}&len=96")
ptr_1600 = req("GET", f"/cpu/memory?addr={0xA00000 + 0x1600}&len=32")
ptr_1700 = req("GET", f"/cpu/memory?addr={0xA00000 + 0x1700}&len=32")
ptr_0100 = req("GET", f"/cpu/memory?addr={0xA00000 + 0x0100}&len=32")
dump("code[07A0..08FF]", 0x07A0, pc_mem["data"])
dump(f"stack[${cpu['z80']['sp']-32:04X}..]", cpu["z80"]["sp"] - 32, stack_mem["data"])
dump("ptr[1600..161F]", 0x1600, ptr_1600["data"])
dump("ptr[1700..171F]", 0x1700, ptr_1700["data"])
dump("ram[0100..011F]", 0x0100, ptr_0100["data"])