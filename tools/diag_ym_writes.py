#!/usr/bin/env python3
"""Check YM2612 write log and channel state in detail."""
import urllib.request, json

BASE = "http://localhost:8093/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Fresh load
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
post("/emulator/step", {"frames": 30})

# Get full APU state
apu = get("/apu/state")

# Print YM write log
if "ym_write_log_first100" in apu:
    log = apu["ym_write_log_first100"]
    print(f"YM write log ({len(log)} entries):")
    for i, entry in enumerate(log[:50]):
        if isinstance(entry, dict):
            print(f"  #{i}: {entry}")
        elif isinstance(entry, list):
            print(f"  #{i}: port={entry[0]} addr={entry[1]:02X} data={entry[2]:02X}" if len(entry) >= 3 else f"  #{i}: {entry}")
        else:
            print(f"  #{i}: {entry}")

# Print all channel parameters
for port_name in ["regs_port0_freq", "regs_port0_tl", "regs_port0_algo", "regs_port0_b4_b6",
                   "regs_port1_freq", "regs_port1_tl", "regs_port1_algo", "regs_port1_b4_b6"]:
    if port_name in apu:
        print(f"\n{port_name}: {apu[port_name]}")

# Key on/off state
if "regs_port0_key" in apu:
    print(f"\nKey register ($28): {apu['regs_port0_key']}")

# Channel details
if "channels" in apu:
    channels = apu["channels"]
    if isinstance(channels, list):
        for i, ch in enumerate(channels):
            if isinstance(ch, dict):
                print(f"\nChannel {i}:")
                for k, v in ch.items():
                    print(f"  {k}: {v}")
    elif isinstance(channels, dict):
        for ch_name, ch in channels.items():
            print(f"\nChannel {ch_name}:")
            if isinstance(ch, dict):
                for k, v in ch.items():
                    print(f"  {k}: {v}")

# Write histogram
for hname in ["ym_histogram_port0_nonzero", "ym_histogram_port1_nonzero"]:
    if hname in apu:
        h = apu[hname]
        if h:
            print(f"\n{hname}: {h}")

# Check vint counts
print(f"\nvint_delivered: {apu.get('vint_delivered', '?')}")
print(f"vdp_frame: {apu.get('vdp_frame', '?')}")
print(f"z80_total_cycles: {apu.get('z80_total_cycles', '?')}")
print(f"ym_write_total: {apu.get('ym_write_total', '?')}")
print(f"debug_fm_ticks: {apu.get('debug_fm_ticks', '?')}")
print(f"debug_fm_nonzero: {apu.get('debug_fm_nonzero', '?')}")

# PSG state
if "psg_periods" in apu:
    print(f"\nPSG periods: {apu['psg_periods']}")
if "psg_volumes" in apu:
    print(f"PSG volumes: {apu['psg_volumes']}")

print("\nDone.")
