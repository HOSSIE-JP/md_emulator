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
        "total": z80["total_cycles"],
    }


def dump_mem(addr, length):
    data = req("GET", f"/cpu/memory?addr={0xA00000 + addr}&len={length}")["data"]
    print(f"mem[{addr:04X}..{addr+length-1:04X}]")
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        print(f"${addr + i:04X}: " + " ".join(f"{value:02X}" for value in chunk))


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    req("POST", "/emulator/step", {"frames": 1})
req("POST", "/input/controller", {"player": 1, "buttons": BTN_C})
for _ in range(67):
    req("POST", "/emulator/step", {"frames": 1})

print("start", json.dumps(z80_state(), ensure_ascii=False))
last = z80_state()
for chunk in range(1, 257):
    req("POST", "/emulator/step", {"cycles": 512})
    cur = z80_state()
    print(chunk, json.dumps(cur, ensure_ascii=False))
    if cur["pc"] >= 0x5000 or cur["pc"] < 0x0200:
        print("hit", chunk, json.dumps({"prev": last, "cur": cur}, ensure_ascii=False, indent=2))
        trace = req("GET", "/apu/state").get("z80_trace_ring", [])
        print("trace_len", len(trace))
        for item in trace[:256]:
            print(item)
        dump_mem(0x1600, 0x20)
        dump_mem(0x0700, 0x80)
        break
    if cur["pc"] >= 0x4000:
        print("hit_high", chunk, json.dumps({"prev": last, "cur": cur}, ensure_ascii=False, indent=2))
        trace = req("GET", "/apu/state").get("z80_trace_ring", [])
        print("trace_len", len(trace))
        for item in trace[:512]:
            print(item)
        dump_mem(0x1600, 0x20)
        dump_mem(0x0700, 0x80)
        break
    last = cur