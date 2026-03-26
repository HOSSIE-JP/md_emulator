#!/usr/bin/env python3
"""Quick test: load ROM, run 200 frames, check if GEMS commands are queued."""
import urllib.request, json, struct

BASE = "http://localhost:8091/api/v1"

def post(path, data=None):
    body = json.dumps(data).encode() if data else b"{}"
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(urllib.request.urlopen(url).read())

# Load ROM and run
post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
print("ROM loaded, running 200 frames...")

post("/emulator/step", {"frames": 200})
print("200 frames done")

# Check M68K PC and state
cpu = get("/cpu/state")
print(f"M68K PC: ${cpu.get('pc', 0):06X}, SR: ${cpu.get('sr', 0):04X}")
if 'd' in cpu:
    print(f"  D regs: {['${:08X}'.format(d) for d in cpu['d'][:4]]}")
if 'a' in cpu:
    print(f"  A regs: {['${:08X}'.format(a) for a in cpu['a'][:4]]}")

# Check work RAM GEMS area
mem = get("/cpu/memory", {"addr": 0xFF012C, "len": 20})
data = bytes(mem["data"])
print(f"\nGEMS area:")
print(f"  $FF012C={data[0]:02X} $FF012D={data[1]:02X} $FF012E={data[2]:02X}")
print(f"  $FF012F={data[3]:02X}")
print(f"  $FF0130-3: {' '.join(f'{b:02X}' for b in data[4:8])}")
print(f"  $FF013A={data[14]:02X}")

# Now press Start and run more
print("\nPressing Start (buttons=0x80)...")
post("/input/controller", {"player": 1, "buttons": 128})
post("/emulator/step", {"frames": 5})
post("/input/controller", {"player": 1, "buttons": 0})
post("/emulator/step", {"frames": 30})

# Check again
mem2 = get("/cpu/memory", {"addr": 0xFF012C, "len": 20})
data2 = bytes(mem2["data"])
print(f"\nAfter Start:")
print(f"  $FF012C={data2[0]:02X} $FF012D={data2[1]:02X} $FF012E={data2[2]:02X}")
print(f"  $FF012F={data2[3]:02X}")
print(f"  $FF013A={data2[14]:02X}")

# Run 200 more frames
post("/emulator/step", {"frames": 200})
mem3 = get("/cpu/memory", {"addr": 0xFF012C, "len": 20})
data3 = bytes(mem3["data"])
print(f"\nAfter 200 more frames:")
print(f"  $FF012C={data3[0]:02X} $FF012D={data3[1]:02X} $FF012E={data3[2]:02X}")
print(f"  $FF012F={data3[3]:02X}")
print(f"  $FF013A={data3[14]:02X}")

# Check Z80 comm
z80 = get("/cpu/memory", {"addr": 0xA00000, "len": 0x30})
z80d = bytes(z80["data"])
print(f"\nZ80 [0x22]={z80d[0x22]:02X} [0x24]={z80d[0x24]:02X} [0x25]={z80d[0x25]:02X} [0x26]={z80d[0x26]:02X} [0x27]={z80d[0x27]:02X}")

# Check audio
samples = get("/audio/samples")
sdata = bytes(samples["data"])
nonzero = sum(1 for i in range(0, len(sdata), 2) if struct.unpack_from('<h', sdata, i)[0] != 0)
print(f"\nAudio: {nonzero}/{len(sdata)//2} non-zero samples")

print("\nDone. Check server stderr for [GEMS-WRITE] traces.")
