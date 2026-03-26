import json
import math
import struct
import urllib.request
import zlib

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
    with urllib.request.urlopen(request, timeout=120) as resp:
        return json.loads(resp.read().decode())


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


def audio_stats():
    samples = req("GET", "/api/v1/audio/samples?frames=800")["samples"]
    mono = []
    for index in range(0, len(samples), 2):
        left = samples[index]
        right = samples[index + 1] if index + 1 < len(samples) else 0.0
        mono.append((left + right) * 0.5)
    nonzero = [value for value in mono if abs(value) > 1e-9]
    rms = math.sqrt(sum(value * value for value in mono) / len(mono)) if mono else 0.0
    peak = max((abs(value) for value in mono), default=0.0)
    return {
        "nonzero": len(nonzero),
        "rms": rms,
        "peak": peak,
        "first_nonzero": nonzero[:16],
    }


def write_png(path, width, height, pixels_argb):
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        row_start = y * width
        for pixel in pixels_argb[row_start:row_start + width]:
            raw.extend(((pixel >> 16) & 0xFF, (pixel >> 8) & 0xFF, pixel & 0xFF, (pixel >> 24) & 0xFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(data)


req("POST", "/api/v1/emulator/reset", {})
req("POST", "/api/v1/emulator/load-rom-path", {"path": ROM})
step(240)
set_buttons(BTN_C)
step(120)
set_buttons(0)
step(30)
pulse(BTN_C, 10, 10, 20)
step(60)
print("after_entry", json.dumps(audio_stats(), ensure_ascii=False))
step(600)
print("after_600_more", json.dumps(audio_stats(), ensure_ascii=False))
state = req("GET", "/api/v1/apu/state")
print("apu", json.dumps({
    "dac_enabled": state.get("dac_enabled"),
    "dac_data": state.get("dac_data"),
    "debug_dac_nonzero": state.get("debug_dac_nonzero"),
    "debug_output_nonzero": state.get("debug_output_nonzero"),
    "regs_port0_2b": state.get("regs_port0_2b"),
    "z80_total_cycles": state.get("z80_total_cycles"),
    "ym_write_total": state.get("ym_write_total"),
    "recent_non_dac": state.get("ym_write_log_recent_non_dac", [])[:12],
    "recent_writes": state.get("ym_write_log_first100", [])[:12],
}, ensure_ascii=False))
frame = req("GET", "/api/v1/video/frame")
png_path = "/tmp/darius_audio_check.png"
write_png(png_path, frame["width"], frame["height"], frame["pixels_argb"])
print("frame_png", png_path)
