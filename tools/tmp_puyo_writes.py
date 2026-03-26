#!/usr/bin/env python3
"""Quick check: are YM writes happening? What does the write log show?"""
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
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    # Step to frame 10 and check write counter
    for f in range(10):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    writes_10 = apu.get("ym_write_total", 0)
    print(f"Frame 10: ym_writes={writes_10}")
    
    # Check the first few writes in the log
    write_log = apu.get("write_log", [])
    print(f"  Write log entries: {len(write_log)}")
    
    # Check for freq register writes specifically
    freq_writes = [w for w in write_log if len(w) >= 3 and 0xA0 <= w[1] <= 0xA6]
    print(f"  Freq register (A0-A6) writes: {len(freq_writes)}")
    if freq_writes[:20]:
        print(f"  First 20 freq writes:")
        for port, addr, data in freq_writes[:20]:
            reg_type = "MSB" if addr >= 0xA4 else "LSB"
            ch = addr - (0xA4 if addr >= 0xA4 else 0xA0) + port * 3
            print(f"    Port{port} R0x{addr:02X} = 0x{data:02X} (CH{ch+1} {reg_type})")
    
    # Step to frame 360 (BGM command)
    for f in range(350):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    writes_360 = apu.get("ym_write_total", 0)
    print(f"\nFrame 360: ym_writes={writes_360} (delta={writes_360-writes_10})")
    
    # Check latch state
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        if fnum > 0:
            print(f"  CH{i+1}: fnum={fnum} block={block}")
    
    # Check raw reg values inline
    port0_regs = apu.get("regs_port0", [])
    port1_regs = apu.get("regs_port1", [])
    if port0_regs:
        print(f"\n  Port0 A0-A6: {[f'0x{port0_regs[a]:02X}' for a in range(0xA0, 0xA7)]}")
    if port1_regs:
        print(f"  Port1 A0-A6: {[f'0x{port1_regs[a]:02X}' for a in range(0xA0, 0xA7)]}")
    
    # Step to frame 420
    for f in range(60):
        api("/emulator/step", "POST", {"cycles": 896040})
    apu = api("/apu/state")
    writes_420 = apu.get("ym_write_total", 0)
    print(f"\nFrame 420: ym_writes={writes_420} (delta from 360={writes_420-writes_360})")
    
    write_log = apu.get("write_log", [])
    freq_writes_420 = [w for w in write_log if len(w) >= 3 and 0xA0 <= w[1] <= 0xA6]
    print(f"  Recent freq writes in log: {len(freq_writes_420)}")
    if freq_writes_420[-30:]:
        print(f"  Last 30 freq writes:")
        for port, addr, data in freq_writes_420[-30:]:
            reg_type = "MSB" if addr >= 0xA4 else "LSB"
            ch_base = addr - (0xA4 if addr >= 0xA4 else 0xA0) 
            ch = ch_base + port * 3
            print(f"    Port{port} R0x{addr:02X} = 0x{data:02X} (CH{ch+1} {reg_type})")

    port0_regs = apu.get("regs_port0", [])
    port1_regs = apu.get("regs_port1", [])
    if port0_regs:
        print(f"\n  Port0 A0-A6: {[f'0x{port0_regs[a]:02X}' for a in range(0xA0, 0xA7)]}")
    if port1_regs:
        print(f"  Port1 A0-A6: {[f'0x{port1_regs[a]:02X}' for a in range(0xA0, 0xA7)]}")

if __name__ == "__main__":
    main()
