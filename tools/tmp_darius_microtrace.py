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


def z80():
    cpu = req("GET", "/cpu/state")["cpu"]["z80"]
    return {
        "pc": cpu["pc"],
        "sp": cpu["sp"],
        "a": cpu["a"],
        "f": cpu["f"],
        "bc": (cpu["b"] << 8) | cpu["c"],
        "de": (cpu["d"] << 8) | cpu["e"],
        "hl": (cpu["h"] << 8) | cpu["l"],
    }


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    req("POST", "/emulator/step", {"frames": 1})
req("POST", "/input/controller", {"player": 1, "buttons": BTN_C})
for _ in range(67):
    req("POST", "/emulator/step", {"frames": 1})

# coarse seek
s = z80()
for _ in range(1200):
    req("POST", "/emulator/step", {"cycles": 128})
    s = z80()
    if 0x07F0 <= s["pc"] <= 0x0815:
        break

print("enter", json.dumps(s, ensure_ascii=False))

# micro trace around critical sequence
for i in range(600):
    req("POST", "/emulator/step", {"cycles": 4})
    s = z80()
    if 0x07F0 <= s["pc"] <= 0x0820 or s["pc"] >= 0x4000 or (i % 50 == 0):
        print(i, json.dumps(s, ensure_ascii=False))
    if s["pc"] >= 0x4000:
        trace = req("GET", "/apu/state").get("z80_trace_ring", [])
        print("trace_head")
        for item in trace[:40]:
            print(item)
        break