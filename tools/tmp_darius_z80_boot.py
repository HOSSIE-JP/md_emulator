import json
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"
ROM = "/Users/hossie/development/md_emulator/roms/darius.bin"


def req(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as resp:
        return json.loads(resp.read().decode())


def top_trace_entries(state):
    return state.get("z80_trace_ring", [])[:8]


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})

previous = None
for frame in range(1, 241):
    req("POST", "/emulator/step", {"frames": 1})
    state = req("GET", "/apu/state")
    top = top_trace_entries(state)
    interesting = any("Ei" in entry or "Di" in entry or "INT" in entry for entry in top)
    signature = (state.get("z80_pc"), state.get("z80_iff1"), state.get("z80_int_pending"), tuple(top[:4]))
    if frame <= 8 or frame % 20 == 0 or interesting:
        if signature != previous:
            print(
                f"frame={frame} pc=${state.get('z80_pc', 0):04X} iff1={state.get('z80_iff1')} "
                f"pending={state.get('z80_int_pending')} vint={state.get('vint_delivered')}"
            )
            for entry in top:
                print(f"  {entry}")
            previous = signature