#!/usr/bin/env python3
"""Check Z80 status byte and M68K sound flags after N frames."""
import json, struct, urllib.request, base64

API = "http://127.0.0.1:8080/api/v1"
ROM = "frontend/roms/北へPM 鮎.bin"


def api_get(path):
    r = urllib.request.urlopen(API + path)
    return json.loads(r.read())


def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(
        API + path, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    r = urllib.request.urlopen(req)
    raw = r.read()
    return json.loads(raw) if raw else None


def mem_bytes(addr, length):
    d = api_get("/cpu/memory?addr=%d&len=%d" % (addr, length))
    return bytes(d["data"])


def mem_byte(addr):
    return mem_bytes(addr, 1)[0]


def mem_word(addr):
    return struct.unpack(">H", mem_bytes(addr, 2))[0]


def main():
    api_post("/emulator/reset")
    api_post("/emulator/load-rom-path", {"path": ROM})

    checkpoints = [5, 10, 15, 20, 30, 40, 50, 75, 100, 125, 150, 200, 300]
    prev = 0

    print("%5s %6s %6s %6s %6s %6s %6s %8s" % (
        "Frame", "Z80102", "FF0066", "FF0067", "FF019E", "FFA820", "FF019C", "Z80_PC"))
    print("-" * 70)

    for target in checkpoints:
        frames_to_run = target - prev
        if frames_to_run > 0:
            api_post("/emulator/step", {"frames": frames_to_run})
        prev = target

        # Z80[$0102] via M68K bus ($A00102 = 10486018)
        z80_0102 = mem_byte(0xA00102)
        ff0066 = mem_word(0xFF0066)
        ff0067 = mem_byte(0xFF0067)
        ff019e = mem_byte(0xFF019E)
        ffa820 = mem_word(0xFFA820)
        ff019c = mem_word(0xFF019C)

        z80st = api_get("/apu/state")
        z80_pc = z80st.get("z80_pc", 0)

        print("%5d   0x%02X   0x%04X   0x%02X     0x%02X   0x%04X   0x%04X   0x%04X" % (
            target, z80_0102, ff0066, ff0067, ff019e, ffa820, ff019c, z80_pc))

    # After 300 frames, also dump Z80 RAM $0100-$010F directly
    print("\nZ80 RAM $0100-$010F (via $A00100):")
    data = mem_bytes(0xA00100, 16)
    print("  " + " ".join("%02X" % b for b in data))

    # Check if Z80 bus is requested
    apu = api_get("/apu/state")
    print("\nZ80 bus_requested:", apu.get("z80_bus_requested"))
    print("Z80 reset:", apu.get("z80_reset"))
    print("Z80 PC:", "0x%04X" % apu.get("z80_pc", 0))


if __name__ == "__main__":
    main()
