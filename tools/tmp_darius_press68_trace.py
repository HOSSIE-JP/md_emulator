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


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
for _ in range(240):
    req("POST", "/emulator/step", {"frames": 1})
req("POST", "/input/controller", {"player": 1, "buttons": BTN_C})
for _ in range(68):
    req("POST", "/emulator/step", {"frames": 1})

cpu = req("GET", "/cpu/state")["cpu"]
apu = req("GET", "/apu/state")
trace = apu.get("z80_trace_ring", [])

print(json.dumps({
    "pc": cpu["z80_pc"],
    "sp": cpu["z80"]["sp"],
    "a": cpu["z80"]["a"],
    "hl": (cpu["z80"]["h"] << 8) | cpu["z80"]["l"],
    "i": cpu["z80"]["i"],
    "r": cpu["z80"]["r"],
    "im": cpu["z80"]["im"],
    "iff1": cpu["z80"]["iff1"],
    "int_pending": cpu["z80"]["int_pending"],
    "trace_len": len(trace),
}, ensure_ascii=False, indent=2))
for item in trace:
    print(item)