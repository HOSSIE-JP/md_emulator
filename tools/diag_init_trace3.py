#!/usr/bin/env python3
"""Trace M68K frame-by-frame during init to understand scene controller freeze."""
import json, struct, sys, urllib.request, base64

API = "http://127.0.0.1:8080/api/v1"
ROM = "frontend/roms/北へPM 鮎.bin"


def api_get(path):
    r = urllib.request.urlopen(API + path)
    return json.loads(r.read())


def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(
        API + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    r = urllib.request.urlopen(req)
    raw = r.read()
    return json.loads(raw) if raw else None


def load_rom():
    api_post("/emulator/load-rom-path", {"path": ROM})


def step_frame():
    api_post("/emulator/step", {"frames": 1})


def get_mem(addr, length):
    d = api_get("/cpu/memory?addr=%d&len=%d" % (addr, length))
    return bytes(d["data"])


def mem_word(addr):
    return struct.unpack(">H", get_mem(addr, 2))[0]


def mem_long(addr):
    return struct.unpack(">I", get_mem(addr, 4))[0]


def main():
    api_post("/emulator/reset")
    load_rom()

    hdr = "%4s %10s %4s %4s %10s %8s %8s %8s %8s %10s %10s" % (
        "Frm", "M68K_PC", "R1", "VINT", "scene@5E",
        "dly@42", "flg@66", "snd@67", "Z80_PC", "D0", "D3",
    )
    print(hdr)
    print("-" * 120)

    prev_scene = 0
    vint_off_frame = None

    for frame in range(300):
        step_frame()

        regs = api_get("/cpu/state")
        m68k = regs.get("cpu", {}).get("m68k", regs)
        pc = m68k.get("pc", 0)
        d_regs = m68k.get("d", [0] * 8)
        d0 = d_regs[0]
        d3 = d_regs[3]

        vdp = api_get("/vdp/registers")
        regs_list = vdp.get("registers", [0] * 32)
        r1 = regs_list[1] if len(regs_list) > 1 else 0
        vint_en = bool(r1 & 0x20)

        sc = mem_word(0xFF005E)
        dly = mem_word(0xFF0042)
        flg = mem_word(0xFF0066)
        snd = mem_word(0xFF0067)

        z80st = api_get("/apu/state")
        z80_pc = z80st.get("z80_pc", 0)

        if not vint_en and vint_off_frame is None and frame > 5:
            vint_off_frame = frame

        changed = sc != prev_scene
        prev_scene = sc

        show = (
            frame < 20
            or (frame < 150 and frame % 5 == 0)
            or frame % 25 == 0
            or changed
        )

        if show:
            mark = " <-- SCENE CHANGED" if changed and frame > 0 else ""
            vstr = " ON" if vint_en else "OFF"
            print(
                "%4d 0x%08X 0x%02X %s 0x%04X   0x%04X   0x%04X   0x%04X   0x%04X 0x%08X 0x%08X%s"
                % (frame, pc, r1, vstr, sc, dly, flg, snd, z80_pc, d0, d3, mark)
            )

    print()
    if vint_off_frame is not None:
        print("VINT disabled at frame: %d" % vint_off_frame)
    print("Final scene@FF005E = 0x%04X" % mem_word(0xFF005E))
    print("Final @FF005C(long) = 0x%08X" % mem_long(0xFF005C))

    for label, addr, size in [
        ("Scene transition @9240", 0x9240, 128),
        ("Code @1C2E (scene ctrl)", 0x1C2E, 32),
        ("Code @1CCE (Phase 1)", 0x1CCE, 64),
        ("Main loop @7A42", 0x7A40, 64),
    ]:
        print("\n--- %s ---" % label)
        bs = get_mem(addr, size)
        for i in range(0, len(bs), 16):
            h = " ".join("%02X" % b for b in bs[i : i + 16])
            print("  $%06X: %s" % (addr + i, h))


if __name__ == "__main__":
    main()
