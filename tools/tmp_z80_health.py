#!/usr/bin/env python3
"""Full Z80 health check after byte access fix."""
import urllib.request
import json

BASE = "http://localhost:8080/api/v1"

def api(path, method="GET", data=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def main():
    print("Loading ROM...")
    api("/emulator/load-rom-path", "POST", {"path": "roms/puyo.bin"})
    
    # Step to frame 5
    api("/emulator/step", "POST", {"cycles": 896040 * 5})
    
    # Check Z80 RAM
    mem = api("/cpu/memory?addr=10485760&len=64")["data"]
    print(f"Z80 RAM $0000: {' '.join(f'{b:02X}' for b in mem[:16])}")
    print(f"Z80 RAM $0010: {' '.join(f'{b:02X}' for b in mem[16:32])}")
    print(f"Z80 RAM $0030: {' '.join(f'{b:02X}' for b in mem[48:64])}")
    
    # Decode first instruction
    if mem[0] == 0xF3:
        print(f"\n$0000: F3 = DI ✓")
    if mem[1] == 0xC3:
        target = mem[2] | (mem[3] << 8)
        print(f"$0001: C3 {mem[2]:02X} {mem[3]:02X} = JP ${target:04X} ✓")
    
    # Check Z80 state
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    z80_sp = apu.get("z80_sp", 0xFFFF)
    iff1 = apu.get("iff1", False)
    halted = apu.get("z80_halted", False)
    ym_writes = apu.get("ym_write_total", 0)
    print(f"\nFrame 5: Z80 PC=0x{z80_pc:04X}, SP=0x{z80_sp:04X}, iff1={iff1}, halted={halted}")
    print(f"YM write total: {ym_writes}")
    
    # Step to frame 10
    api("/emulator/step", "POST", {"cycles": 896040 * 5})
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    ym_writes = apu.get("ym_write_total", 0)
    print(f"\nFrame 10: Z80 PC=0x{z80_pc:04X}, YM writes={ym_writes}")
    
    # Check trace ring for recent non-crash instructions
    trace = apu.get("z80_trace_ring", [])
    if trace:
        print(f"\nRecent Z80 trace (newest first):")
        for i in range(min(20, len(trace))):
            print(f"  {trace[i]}")
    
    # Step to frame 300 and check  
    api("/emulator/step", "POST", {"cycles": 896040 * 290})
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    iff1 = apu.get("iff1", False)
    halted = apu.get("z80_halted", False)
    ym_writes = apu.get("ym_write_total", 0)
    print(f"\nFrame 300: Z80 PC=0x{z80_pc:04X}, iff1={iff1}, halted={halted}, YM writes={ym_writes}")
    
    if z80_pc >= 0x2000:
        print(f"  Z80 PC is OUTSIDE RAM - possible crash!")
    else:
        print(f"  Z80 PC is in RAM range - looks healthy!")
    
    # Check FM channels
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        ops = ch.get("operators", [])
        if fnum > 0:
            print(f"  CH{i+1}: fnum={fnum} block={block}")
    
    # Step to frame 600
    api("/emulator/step", "POST", {"cycles": 896040 * 300})
    apu = api("/apu/state")
    z80_pc = apu.get("z80_pc", 0)
    ym_writes = apu.get("ym_write_total", 0)
    print(f"\nFrame 600: Z80 PC=0x{z80_pc:04X}, YM writes={ym_writes}")
    
    channels = apu.get("channels", [])
    for i, ch in enumerate(channels):
        fnum = ch.get("fnum", 0)
        block = ch.get("block", 0)
        if fnum > 0:
            print(f"  CH{i+1}: fnum={fnum} block={block}")
    
    # Get write histogram
    hist0 = apu.get("ym_histogram_port0_nonzero", [])
    hist1 = apu.get("ym_histogram_port1_nonzero", [])
    print(f"\nYM write histogram (port0): {hist0[:20]}")
    print(f"YM write histogram (port1): {hist1[:20]}")
    
    # Check audio
    audio = api("/audio/samples", "POST", {"max_samples": 4096})
    samples = audio.get("samples", [])
    if samples:
        max_amp = max(abs(s) for s in samples)
        print(f"\nAudio: {len(samples)} samples, max amplitude={max_amp:.4f}")
    else:
        print("\nAudio: No samples")

if __name__ == "__main__":
    main()
