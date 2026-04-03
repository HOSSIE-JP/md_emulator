#!/usr/bin/env python3
"""Trace M68K frame-by-frame during init to understand scene controller freeze."""
import json, struct, sys, urllib.request

API = "http://127.0.0.1:8080/api/v1"
ROM = "frontend/roms/北へPM 鮎.bin"

def api_get(path):
    r = urllib.request.urlopen(f"{API}{path}")
    return json.loads(r.read())

def api_post(path, data=None):
    body = json.dumps(data).encode() if data else b""
    req = urllib.request.Request(f"{API}{path}", data=body,
                                 headers={"Content-Type": "application/json"} if data else {},
                                 method="POST")
    r = urllib.request.urlopen(req)
    return json.loads(r.read()) if r.length else None

def load_rom():
    import base64
    with open(ROM, "rb") as f:
        data = f.read()
    api_post("/rom/load", {"rom_base64": base64.b64encode(data).decode()})

def get_mem(addr, length):
    d = api_get(f"/debug/memory?address={addr}&length={length}")
    return bytes(d["data"])

def mem_word(addr):
    return struct.unpack(">H", get_mem(addr, 2))[0]

def mem_long(addr):
    return struct.unpack(">I", get_mem(addr, 4))[0]

def main():
    api_post("/emulator/reset")
    load_rom()

    print(f"{'Frm':>4} {'M68K_PC':>10} {'R1':>4} {'VINT':>4} {'scene@5E':>10} "
          f"{'dly@42':>8} {'flg@66':>8} {'snd@67':>8} {'Z80_PC':>8} {'D0':>10} {'D3':>10}")
    print("-" * 120)

    prev_scene = 0
    vint_off_frame = None

    for frame in range(300):
        api_post("/emulator/step_frame")

        regs = api_get("/debug/cpu")
        pc = regs.get("pc", 0)
        d0 = regs.get("d", [0]*8)[0]
        d3 = regs.get("d", [0]*8)[3]

        vdp = api_get("/debug/vdp_state")
        r1 = vdp.get("registers", [0]*32)[1]
        vint_en = bool(r1 & 0x20)

        sc = mem_word(0xFF005E)
        dly = mem_word(0xFF0042)
        flg = mem_word(0xFF0066)
        snd = mem_word(0xFF0067)

        z80 = api_get("/debug/z80_state")
        z80_pc = z80.get("pc", 0)

        if not vint_en and vint_off_frame is None and frame > 5:
            vint_off_frame = frame

        changed = (sc != prev_scene)
        prev_scene = sc

        show = (frame < 20 or
                (frame < 150 and frame % 5 == 0) or
                frame % 25 == 0 or
                changed)

        if show:
            mark = " <-- scene changed!" if changed and frame > 0 else ""
            print(f"{frame:4d} 0x{pc:08X} 0x{r1:02X} {'ON':>4 if vint_en else 'OFF':>4} "
                  f"0x{sc:04X}     0x{dly:04X}   0x{flg:04X}   0x{snd:04X}   "
                  f"0x{z80_pc:04X}   0x{d0:08X} 0x{d3:08X}{mark}")

    print()
    if vint_off_frame is not None:
        print(f"VINT disabled at frame: {vint_off_frame}")

    print(f"\nFinal scene@$FF005E = 0x{mem_word(0xFF005E):04X}")
    print(f"Final $FF005C(long) = 0x{mem_long(0xFF005C):08X}")

    # Dump the scene transition code at $9240+
    print("\n--- Scene transition code @$9240 ---")
    bs = get_mem(0x9240, 128)
    for i in range(0, len(bs), 16):
        h = " ".join(f"{b:02X}" for b in bs[i:i+16])
        print(f"  ${0x9240+i:06X}: {h}")

    # Dump code at $1C2E (the RTS scene controller)
    print("\n--- Code @$1C2E ---")
    bs = get_mem(0x1C2E, 32)
    for i in range(0, len(bs), 16):
        h = " ".join(f"{b:02X}" for b in bs[i:i+16])
        print(f"  ${0x1C2E+i:06X}: {h}")

    # Also check $1CCE (Phase 1 re-enable path)
    print("\n--- Code @$1CCE ---")
    bs = get_mem(0x1CCE, 64)
    for i in range(0, len(bs), 16):
        h = " ".join(f"{b:02X}" for b in bs[i:i+16])
        print(f"  ${0x1CCE+i:06X}: {h}")

    # Main loop around $7A42 (the D3≠0 path)
    print("\n--- Main loop @$7A42 ---")
    bs = get_mem(0x7A40, 64)
    for i in range(0, len(bs), 16):
        h = " ".join(f"{b:02X}" for b in bs[i:i+16])
        print(f"  ${0x7A40+i:06X}: {h}")

if __name__ == "__main__":
    main()
