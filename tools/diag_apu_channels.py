#!/usr/bin/env python3
"""Check APU channel state after YM2612 writes are happening."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Run 120 frames
for i in range(120):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")

print(f"ym_write_total: {apu.get('ym_write_total')}")
print(f"z80_pc: 0x{apu.get('z80_pc', 0):04X}")
print(f"z80_cycles: {apu.get('z80_cycles')}")
print(f"dac_enabled: {apu.get('dac_enabled')}")

print("\n=== FM Channels ===")
for ch in apu.get("channels", []):
    ch_idx = ch["channel"]
    fnum = ch.get("fnum", 0)
    block = ch.get("block", 0)
    algo = ch.get("algorithm", 0)
    fb = ch.get("feedback", 0)
    pan_l = ch.get("pan_left", False)
    pan_r = ch.get("pan_right", False)
    
    ops_info = []
    for op in ch.get("operators", []):
        phase = op["eg_phase"]
        atten = op["attenuation"]
        tl = op.get("total_level", "?")
        ar = op.get("attack_rate", "?")
        ops_info.append(f"({phase} atn={atten} TL={tl} AR={ar})")
    
    print(f"  CH{ch_idx}: fnum={fnum} block={block} algo={algo} fb={fb} pan=({'L' if pan_l else '-'}{'R' if pan_r else '-'}) ops={' '.join(ops_info)}")

print("\n=== PSG ===")
print(f"PSG volumes: {apu.get('psg_volumes')}")
print(f"PSG tones: {apu.get('psg_tones')}")
