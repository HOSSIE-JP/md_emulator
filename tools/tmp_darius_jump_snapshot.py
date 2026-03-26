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


def z80_state():
    cpu = req("GET", "/cpu/state")["cpu"]
    z80 = cpu["z80"]
    return {
        "pc": cpu["z80_pc"],
        "sp": z80["sp"],
        "a": z80["a"],
        "f": z80["f"],
        "bc": (z80["b"] << 8) | z80["c"],
        "de": (z80["d"] << 8) | z80["e"],
        "hl": (z80["h"] << 8) | z80["l"],
    }


def dump(addr, length):
    data = req("GET", f"/cpu/memory?addr={0xA00000 + addr}&len={length}")["data"]
    print(f"mem[{addr:04X}..{addr + length - 1:04X}]")
    for i in range(0, len(data), 16):
        line = data[i:i + 16]
        print(f"${addr + i:04X}: " + " ".join(f"{v:02X}" for v in line))


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    req("POST", "/emulator/step", {"frames": 1})
req("POST", "/input/controller", {"player": 1, "buttons": BTN_C})
for _ in range(67):
    req("POST", "/emulator/step", {"frames": 1})

print("start", json.dumps(z80_state(), ensure_ascii=False))
for step in range(1, 1601):
    req("POST", "/emulator/step", {"cycles": 256})
    cur = z80_state()
    if step % 20 == 0:
        print(step, json.dumps(cur, ensure_ascii=False))
    if cur["pc"] >= 0x4000:
        print("hit", step, json.dumps(cur, ensure_ascii=False))
        trace = req("GET", "/apu/state").get("z80_trace_ring", [])
        print("trace_tail")
        for item in trace[:100]:
            print(item)
        dump(0x1600, 0x20)
        dump(0x1680, 0x40)
        dump(0x0700, 0x80)
        dump(0x0800, 0x40)
        break