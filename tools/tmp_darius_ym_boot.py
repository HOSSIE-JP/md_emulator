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


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})

for frame in range(1, 401):
    req("POST", "/emulator/step", {"frames": 1})
    state = req("GET", "/apu/state")
    writes = state.get("ym_write_log_first100", [])
    filtered = [entry for entry in writes if any(token in entry for token in ("$28=", "$2B=", "$B4=", "$B5=", "$B6="))]
    if filtered and (frame <= 10 or frame % 20 == 0 or any("$2B=" in entry for entry in filtered)):
        print(
            f"frame={frame} pc=${state.get('z80_pc', 0):04X} iff1={state.get('z80_iff1')} "
            f"pending={state.get('z80_int_pending')}"
        )
        for entry in filtered[:20]:
            print(f"  {entry}")