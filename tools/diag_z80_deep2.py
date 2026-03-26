#!/usr/bin/env python3
"""Deep investigation of Z80 state after interrupt fix."""
import urllib.request, json

BASE = "http://localhost:8093/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Load ROM and step to stable state
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
post("/emulator/step", {"frames": 5})

# Check Z80 state
cpu = get("/cpu/state")
z80_pc = cpu["cpu"]["z80_pc"]
print(f"After 5 frames: Z80 PC=${z80_pc:04X}")

# Read Z80 memory: command area + stack area
z80_lo = get("/cpu/memory", {"addr": 0xA00000, "len": 0x40})
d = bytes(z80_lo["data"])
print(f"Z80 [0x20-0x2F]: {' '.join(f'{d[i]:02X}' for i in range(0x20, 0x30))}")
print(f"Z80 [0x27]={d[0x27]:02X} [0x22]={d[0x22]:02X}")

# Read Z80 memory near PC to see what code is executing
if z80_pc >= 16:
    z80_pc_area = get("/cpu/memory", {"addr": 0xA00000 + (z80_pc - 16), "len": 48})
    pc_d = bytes(z80_pc_area["data"])
    print(f"\nZ80 code near PC=${z80_pc:04X}:")
    for i in range(0, len(pc_d), 16):
        addr = z80_pc - 16 + i
        hex_str = ' '.join(f'{pc_d[i+j]:02X}' for j in range(min(16, len(pc_d)-i)))
        marker = " <-- PC" if addr <= z80_pc < addr + 16 else ""
        print(f"  ${addr:04X}: {hex_str}{marker}")

# Read interrupt handler area $0038
z80_int = get("/cpu/memory", {"addr": 0xA00038, "len": 32})
int_d = bytes(z80_int["data"])
print(f"\nZ80 IM1 handler at $0038: {' '.join(f'{b:02X}' for b in int_d)}")

# Check the area around $0B0E (where Z80 was stuck)
z80_0b = get("/cpu/memory", {"addr": 0xA00B00, "len": 32})
ob_d = bytes(z80_0b["data"])
print(f"\nZ80 code around $0B00-$0B1F: {' '.join(f'{b:02X}' for b in ob_d)}")

# Check stack area (Z80 stack typically at $1FFF going down)
z80_stack = get("/cpu/memory", {"addr": 0xA01F80, "len": 128})
stk = bytes(z80_stack["data"])
nonzero_stk = [(0x1F80 + i, stk[i]) for i in range(len(stk)) if stk[i] != 0]
if nonzero_stk:
    print(f"\nZ80 stack area (non-zero $1F80-$1FFF):")
    for addr, val in nonzero_stk[-20:]:
        print(f"  ${addr:04X}: ${val:02X}")

# Step one frame at a time and track Z80 PC changes
print("\nStepping 1 frame at a time, tracking Z80 PC:")
pcs = []
for i in range(20):
    post("/emulator/step", {"frames": 1})
    cpu = get("/cpu/state")
    z80_pc = cpu["cpu"]["z80_pc"]
    pcs.append(z80_pc)
    if i < 10 or (len(pcs) > 1 and z80_pc != pcs[-2]):
        print(f"  Frame {i+1}: Z80 PC=${z80_pc:04X}")

# Check unique PCs
unique_pcs = set(pcs)
print(f"  Unique Z80 PCs: {', '.join(f'${p:04X}' for p in sorted(unique_pcs))}")

# Check M68K work RAM for GEMS commands
gems = get("/cpu/memory", {"addr": 0xFF012C, "len": 16})
gd = bytes(gems["data"])
print(f"\nM68K work RAM $FF012C-$FF013B: {' '.join(f'{b:02X}' for b in gd)}")

# Get APU details
apu = get("/apu/state")
print(f"\nAPU state keys: {list(apu.keys()) if isinstance(apu, dict) else type(apu)}")
if isinstance(apu, dict):
    for k, v in apu.items():
        if isinstance(v, (int, float, str, bool)):
            print(f"  {k}: {v}")
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, (int, float, str, bool)):
                    print(f"  {k}.{k2}: {v2}")

print("\nDone.")
