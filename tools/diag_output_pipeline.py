#!/usr/bin/env python3
"""Trace output pipeline: FM ticks vs output buffer."""
import urllib.request, json

BASE = "http://localhost:8095/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

def show_debug(label):
    apu = get("/apu/state")
    print(f"\n{label}:")
    for k in ["debug_fm_ticks", "debug_fm_nonzero", "debug_output_total", 
              "debug_output_nonzero", "last_fm_left", "last_fm_right",
              "ym_write_log_len", "vdp_frame", "audio_buffer_len"]:
        if k in apu:
            print(f"  {k}: {apu[k]}")

# Load ROM
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
show_debug("After load")

# Title screen
post("/emulator/step", {"frames": 100})
show_debug("After 100 frames")

# Press Start
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})

# Music should start
post("/emulator/step", {"frames": 50})
show_debug("After Start + 55 frames")

# More frames
post("/emulator/step", {"frames": 100})
show_debug("After Start + 155 frames")

# Check channel panning
apu = get("/apu/state")
print("\nChannel panning (B4-B6):")
print(f"  Port0: {apu.get('regs_port0_b4_b6', '?')}")
print(f"  Port1: {apu.get('regs_port1_b4_b6', '?')}")

# Check which channels are active
channels = apu.get("channels", [])
if isinstance(channels, list):
    for i, ch in enumerate(channels):
        if isinstance(ch, dict):
            pan_l = ch.get("pan_left", False)
            pan_r = ch.get("pan_right", False)
            algo = ch.get("algorithm", 0)
            fnum = ch.get("fnum", 0)
            key_info = "key=[" + ",".join(
                ("ON" if op.get("key_on", False) else "off") 
                for op in ch.get("operators", [])
            ) + "]"
            att_info = "[" + ",".join(
                str(op.get("attenuation", 0))
                for op in ch.get("operators", [])
            ) + "]"
            phase = ch.get("operators", [{}])[0].get("env_phase", "?")
            print(f"  Ch{i}: L={pan_l} R={pan_r} algo={algo} fnum={fnum} {key_info} att={att_info} ph={phase}")

print("\nDone.")
