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


def dump_block(start, data):
    for offset in range(0, len(data), 16):
        addr = start + offset
        chunk = data[offset:offset + 16]
        print(f"${addr:04X}: " + " ".join(f"{value:02X}" for value in chunk))


req("POST", "/emulator/reset", {})
req("POST", "/emulator/load-rom-path", {"path": ROM})

stepped = 0
for frame in (1, 20, 40, 80, 120, 240):
    req("POST", "/emulator/step", {"frames": frame - stepped})
    stepped = frame
    cpu = req("GET", "/cpu/state")["cpu"]
    ram0 = req("GET", "/cpu/memory?addr=10485760&len=128")
    ram38 = req("GET", "/cpu/memory?addr=10485816&len=64")
    print(f"frame={frame} pc=${cpu['z80_pc']:04X}")
    print("ram[0000..007F]")
    dump_block(0x0000, ram0["data"])
    print("ram[0038..0077]")
    dump_block(0x0038, ram38["data"])