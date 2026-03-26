#!/usr/bin/env python3
"""Check M68K exception trace to find crash cause."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("Loading puyo.bin...")
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})

# Check ROM vectors
rom_sp = get(f"/cpu/memory?addr=0&len=4")
rom_pc = get(f"/cpu/memory?addr=4&len=4")
sp_bytes = rom_sp.get("data", [])
pc_bytes = rom_pc.get("data", [])
initial_sp = (sp_bytes[0] << 24) | (sp_bytes[1] << 16) | (sp_bytes[2] << 8) | sp_bytes[3]
initial_pc = (pc_bytes[0] << 24) | (pc_bytes[1] << 16) | (pc_bytes[2] << 8) | pc_bytes[3]
print(f"ROM initial SP=0x{initial_sp:08X} PC=0x{initial_pc:08X}")

# Check exception vectors
vectors = get(f"/cpu/memory?addr=0&len=256")
v = vectors.get("data", [])
def read_long(data, offset):
    return (data[offset]<<24)|(data[offset+1]<<16)|(data[offset+2]<<8)|data[offset+3]

print(f"\nException vectors:")
names = {
    0: "Reset SP", 4: "Reset PC", 8: "Bus Error", 12: "Address Error",
    16: "Illegal Instruction", 20: "Zero Divide", 24: "CHK", 28: "TRAPV",
    32: "Privilege Violation", 36: "Trace", 40: "Line-A", 44: "Line-F",
    96: "Spurious", 100: "Auto L1", 104: "Auto L2", 108: "Auto L3",
    112: "Auto L4 (HInt)", 116: "Auto L5", 120: "Auto L6 (VInt)", 124: "Auto L7",
}
for offset, name in sorted(names.items()):
    val = read_long(v, offset)
    print(f"  [{offset:3d}] {name}: 0x{val:08X}")

# Run just 1 frame and check
cpu0 = get("/cpu/state")
cpu_data = cpu0.get("cpu", {})
m68k0 = cpu_data.get("m68k", {})
print(f"\nBefore any step: M68K PC=0x{m68k0.get('pc',0):06X} SR=0x{m68k0.get('sr',0):04X}")
print(f"  A7/SP=0x{m68k0.get('a', [0]*8)[7]:08X}")

post("/emulator/step", {"frames": 1})
cpu1 = get("/cpu/state")
cpu1_data = cpu1.get("cpu", {})
m68k1 = cpu1_data.get("m68k", {})
print(f"\nAfter 1 frame: M68K PC=0x{m68k1.get('pc',0):06X} SR=0x{m68k1.get('sr',0):04X}")
print(f"  A7/SP=0x{m68k1.get('a', [0]*8)[7]:08X}")

# Check CPU trace 
trace = get("/cpu/trace")
exc_trace = trace.get("exception_trace", [])
ring_trace = trace.get("trace_ring", [])
print(f"\nException trace entries: {len(exc_trace)}")
for t in exc_trace[:20]:
    print(f"  PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t.get('mnemonic','?')} cycles={t['cycles']}")

print(f"\nTrace ring entries: {len(ring_trace)}")
for t in ring_trace[-20:]:
    print(f"  PC=0x{t['pc']:06X} op=0x{t['opcode']:04X} {t.get('mnemonic','?')} cycles={t['cycles']}")
