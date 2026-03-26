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


def state():
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
        "iff1": z80["iff1"],
        "int_pending": z80["int_pending"],
        "total": z80["total_cycles"],
    }


def dump_mem(addr, length):
    return req("GET", f"/cpu/memory?addr={0xA00000 + addr}&len={length}")["data"]


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    req("POST", "/emulator/step", {"frames": 1})
req("POST", "/input/controller", {"player": 1, "buttons": BTN_C})
for _ in range(67):
    req("POST", "/emulator/step", {"frames": 1})

print("start", json.dumps(state(), ensure_ascii=False))
last = state()
for step in range(1, 201):
    req("POST", "/emulator/step", {"cycles": 488})
    cur = state()
    if cur["pc"] != last["pc"] or cur["sp"] != last["sp"]:
        print(step, json.dumps(cur, ensure_ascii=False))
    if cur["pc"] == 0x514D:
        print("hit514d", step, json.dumps(cur, ensure_ascii=False))
        trace = req("GET", "/apu/state").get("z80_trace_ring", [])
        print("trace")
        for item in trace:
            print(item)
        code = dump_mem(0x0800, 0x200)
        print("code0800")
        for offset in range(0, len(code), 16):
            chunk = code[offset:offset + 16]
            print(f"${0x0800 + offset:04X}: " + " ".join(f"{value:02X}" for value in chunk))
        stack_addr = max(cur["sp"] - 32, 0)
        stack = dump_mem(stack_addr, 96)
        print("stack")
        for offset in range(0, len(stack), 16):
            chunk = stack[offset:offset + 16]
            print(f"${stack_addr + offset:04X}: " + " ".join(f"{value:02X}" for value in chunk))
        break
    last = cur