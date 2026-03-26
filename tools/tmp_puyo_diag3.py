#!/usr/bin/env python3
"""Diagnose freq latching issue - check raw register values and write log."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def main():
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})

    # Step to frame 420
    for f in range(420):
        api("/emulator/step", "POST", {"cycles": 896040})

    apu = api("/apu/state")
    print("regs_port0_freq (A0-A6):", apu.get("regs_port0_freq"))
    print("regs_port1_freq (A0-A6):", apu.get("regs_port1_freq"))
    print("ym_write_total:", apu.get("ym_write_total"))
    print("ym_write_log_len:", apu.get("ym_write_log_len"))

    # Non-DAC log
    log = apu.get("ym_write_log_recent_non_dac", [])
    print(f"\nNon-DAC log entries: {len(log)}")
    # Filter for freq writes (A0-AE)
    freq_writes = [e for e in log if ":$A" in e.upper()]
    print(f"Freq-related entries: {len(freq_writes)}")
    for entry in freq_writes[:50]:
        print(f"  {entry}")

    # Show all non-DAC log in order
    print(f"\nAll non-DAC log (last 50):")
    for entry in log[:50]:
        print(f"  {entry}")

    # Channel info
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        print(f"\nCH{i+1}: fnum={ch.get('fnum',0)} block={ch.get('block',0)} algo={ch.get('algorithm',0)}")
        for j, op in enumerate(ch.get("operators", [])):
            print(f"  OP{j+1}: key={op.get('key_on')} att={op.get('attenuation')} env={op.get('env_phase')}")

    # Show DAC state
    print(f"\nDAC enabled: {apu.get('dac_enabled')}")
    print(f"DAC data: {apu.get('dac_data')}")
    print(f"last_fm_left: {apu.get('last_fm_left')}")
    print(f"last_fm_right: {apu.get('last_fm_right')}")

if __name__ == "__main__":
    main()
