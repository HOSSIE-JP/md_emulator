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
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def read(addr, length):
    return req("GET", f"/cpu/memory?addr={0xA00000 + addr}&len={length}")["data"]


def show(tag):
    d1600 = read(0x1600, 0x20)
    d1680 = read(0x1680, 0x40)
    print(tag)
    print("1600", " ".join(f"{v:02X}" for v in d1600[:16]))
    print("1610", " ".join(f"{v:02X}" for v in d1600[16:32]))
    print("1680", " ".join(f"{v:02X}" for v in d1680[:16]))
    print("1690", " ".join(f"{v:02X}" for v in d1680[16:32]))
    print("16A0", " ".join(f"{v:02X}" for v in d1680[32:48]))
    apu = req("GET", "/apu/state")
    log = apu.get("z80_banked_read_log", [])
    print("banked_read_log_recent", len(log))
    for line in log[:16]:
        print(line)


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})
show("after_load")

for n in (30, 120, 240):
    req("POST", "/emulator/step", {"frames": n})
    show(f"after_plus_{n}_frames")