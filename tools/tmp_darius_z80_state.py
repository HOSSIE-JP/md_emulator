import json
import urllib.request

BASE = "http://127.0.0.1:8080"
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


def set_buttons(buttons):
    req("POST", "/api/v1/input/controller", {"player": 1, "buttons": buttons})


def step(frames):
    for _ in range(frames):
        req("POST", "/api/v1/emulator/step", {"frames": 1})


def pulse(buttons, on_frames, off_frames, repeats):
    for _ in range(repeats):
        set_buttons(buttons)
        step(on_frames)
        set_buttons(0)
        step(off_frames)


req("POST", "/api/v1/emulator/reset", {})
req("POST", "/api/v1/emulator/load-rom-path", {"path": ROM})
step(240)
print("after_boot")
set_buttons(BTN_C)
step(120)
print("after_press")
set_buttons(0)
step(30)
pulse(BTN_C, 10, 10, 20)
print("after_pulse")
step(60)
step(600)
print("after_gameplay")

cpu = req("GET", "/api/v1/cpu/state")["cpu"]
apu = req("GET", "/api/v1/apu/state")
print(json.dumps({
    "z80": cpu["z80"],
    "z80_pc": cpu["z80_pc"],
    "z80_cycles": cpu["z80_cycles"],
    "mem": {
        "hl": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['h'] << 8) | cpu['z80']['l'])}&len=16"),
        "de": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['d'] << 8) | cpu['z80']['e'])}&len=16"),
        "bc": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['b'] << 8) | cpu['z80']['c'])}&len=16"),
        "hl_alt": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['h_'] << 8) | cpu['z80']['l_'])}&len=16"),
        "de_alt": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['d_'] << 8) | cpu['z80']['e_'])}&len=16"),
        "bc_alt": req("GET", f"/api/v1/cpu/memory?addr={0xA00000 + ((cpu['z80']['b_'] << 8) | cpu['z80']['c_'])}&len=16"),
    },
    "apu": {
        "regs_port0_2b": apu.get("regs_port0_2b"),
        "dac_enabled": apu.get("dac_enabled"),
        "dac_data": apu.get("dac_data"),
        "recent_non_dac": apu.get("ym_write_log_recent_non_dac", [])[:12],
        "recent_writes": apu.get("ym_write_log_first100", [])[:20],
        "trace": apu.get("z80_trace_ring", [])[-64:],
    },
}, ensure_ascii=False, indent=2))