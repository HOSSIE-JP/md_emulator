#!/usr/bin/env python3
"""Compare audio/driver behavior between Puyo and Darius on the same metrics."""

import json
import math
import urllib.request

BASE = "http://127.0.0.1:8080/api/v1"


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=60) as resp:
        return json.loads(resp.read())


def post(path, payload=None):
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def drain_audio_samples():
    data = get("/audio/samples")
    samples = data.get("samples", [])
    if not samples:
        return {
            "count": 0,
            "nonzero": 0,
            "max_abs": 0.0,
            "rms": 0.0,
            "zc": 0,
        }

    nonzero = sum(1 for s in samples if abs(s) > 1e-6)
    max_abs = max(abs(s) for s in samples)
    rms = math.sqrt(sum((s * s) for s in samples) / len(samples))

    zc = 0
    prev = samples[0]
    for s in samples[1:]:
        if (prev < 0 <= s) or (prev > 0 >= s):
            zc += 1
        prev = s

    return {
        "count": len(samples),
        "nonzero": nonzero,
        "max_abs": max_abs,
        "rms": rms,
        "zc": zc,
    }


def snapshot(label):
    apu = get("/apu/state")
    audio = drain_audio_samples()
    trace = apu.get("z80_trace_ring", [])
    high_pc_hits = [t for t in trace[:128] if ": " in t and t.startswith("$") and int(t[1:5], 16) >= 0x4000]

    hist0 = apu.get("ym_histogram_port0_nonzero", [])
    hist1 = apu.get("ym_histogram_port1_nonzero", [])

    print(f"[{label}]")
    print(
        "  "
        f"frame={apu.get('vdp_frame')} "
        f"z80_pc=0x{apu.get('z80_pc', 0):04X} "
        f"iff1={apu.get('z80_iff1')} int_pending={apu.get('z80_int_pending')} "
        f"ym_writes={apu.get('ym_write_total')}"
    )
    print(
        "  "
        f"audio: count={audio['count']} nonzero={audio['nonzero']} "
        f"max={audio['max_abs']:.5f} rms={audio['rms']:.5f} zc={audio['zc']}"
    )
    print(
        "  "
        f"fm_nonzero={apu.get('debug_fm_nonzero')} "
        f"output_nonzero={apu.get('debug_output_nonzero')} "
        f"dac_enabled={apu.get('dac_enabled')}"
    )
    print(
        "  "
        f"hist_regs: p0={len(hist0)} p1={len(hist1)} "
        f"high_pc_hits_recent={len(high_pc_hits)}"
    )
    if high_pc_hits:
        print("  high_pc_sample:")
        for line in high_pc_hits[:5]:
            print(f"    {line}")


def run_puyo():
    print("=== PUYO ===")
    post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
    snapshot("load")

    for _ in range(120):
        post("/emulator/step", {"frames": 1})
    snapshot("title_120f")

    # Start press to enter mode where music should clearly begin.
    post("/input/controller", {"player": 1, "buttons": 0x80})
    for _ in range(8):
        post("/emulator/step", {"frames": 1})
    post("/input/controller", {"player": 1, "buttons": 0})

    for _ in range(180):
        post("/emulator/step", {"frames": 1})
    snapshot("after_start_300f")

    for _ in range(300):
        post("/emulator/step", {"frames": 1})
    snapshot("after_start_600f")


def run_darius():
    print("=== DARIUS ===")
    post("/emulator/load-rom-path", {"path": "roms/s_a_t_d.smd"})
    snapshot("load")

    for _ in range(180):
        post("/emulator/step", {"frames": 1})
    snapshot("180f")

    for _ in range(420):
        post("/emulator/step", {"frames": 1})
    snapshot("600f")


if __name__ == "__main__":
    run_puyo()
    run_darius()
