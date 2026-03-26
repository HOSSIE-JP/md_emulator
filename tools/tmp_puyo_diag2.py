#!/usr/bin/env python3
"""Diagnose why YM2612 channels all show fnum=0 despite BGM playing."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    # Load ROM
    print("Loading Puyo Puyo ROM...")
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})

    # Advance to frame 300 (before BGM starts)
    print("Advancing to frame 300...")
    for f in range(300):
        api("/emulator/step", "POST", {"cycles": 896040})

    # Now advance frame-by-frame and check when channels get non-zero fnum
    print("\n=== Tracking channel frequencies frame 300-480 ===")
    for f in range(300, 480):
        api("/emulator/step", "POST", {"cycles": 896040})
        if f % 10 == 0:
            apu = api("/apu/state")
            channels = apu.get("channels", [])
            # Check fnum/block for all channels
            freq_info = []
            for i, ch in enumerate(channels):
                fnum = ch.get("fnum", 0)
                block = ch.get("block", 0)
                key_on = sum(1 for op in ch.get("operators", []) if op.get("key_on", False))
                att0 = ch.get("operators", [{}])[0].get("attenuation", 1023) if ch.get("operators") else 1023
                freq_info.append(f"CH{i+1}:f={fnum}b={block}k={key_on}a={att0}")
            
            # Also get write log
            write_count = apu.get("ym_write_total", 0)
            
            # Check raw register values for A0-A6
            reg_a0_a6 = []
            for addr in range(0xA0, 0xA7):
                val0 = api(f"/cpu/memory?addr={addr}&len=1&type=ym_reg_port0")
                val1 = api(f"/cpu/memory?addr={addr}&len=1&type=ym_reg_port1")
                # These endpoints might not exist, try alternative
            
            print(f"  F{f}: writes={write_count} | {' '.join(freq_info)}")
    
    # Check what freq registers actually contain by reading APU debug
    print("\n=== Raw register check at frame 480 ===")
    apu = api("/apu/state")
    
    # Check latch state
    latch_data = apu.get("latched_freq_data", [])
    latch_pending = apu.get("latched_freq_pending", [])
    print(f"  Latched freq data: {latch_data}")
    print(f"  Latched freq pending: {latch_pending}")
    
    # Check write histogram for frequency register addresses
    hist = apu.get("write_histogram", [])
    if hist:
        print(f"\n=== Write histogram for freq registers ===")
        for port in range(2):
            for addr in [0xA0, 0xA1, 0xA2, 0xA4, 0xA5, 0xA6, 0xA8, 0xA9, 0xAA, 0xAC, 0xAD, 0xAE]:
                idx = port * 256 + addr
                count = hist[idx] if idx < len(hist) else 0
                if count > 0:
                    print(f"  Port {port} Reg 0x{addr:02X}: {count} writes")
    
    # Check recent write log
    write_log = apu.get("write_log", [])
    if write_log:
        # Show last 50 writes
        print(f"\n=== Last 50 YM writes (of {len(write_log)} total) ===")
        for port, addr, data in write_log[-50:]:
            reg_name = ""
            if 0xA0 <= addr <= 0xA6:
                reg_name = f" (freq CH{addr-0xA0+1+port*3} {'MSB' if addr>=0xA4 else 'LSB'})"
            elif addr == 0x28:
                reg_name = f" (KEY ON/OFF)"
            elif 0x30 <= addr <= 0x9F:
                reg_name = f" (op reg)"
            print(f"  Port{port} R{addr:02X} = {data:02X}{reg_name}")

    print("\nDone!")

if __name__ == "__main__":
    main()
