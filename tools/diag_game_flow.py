"""Check game entry point and early init, trace to find sound init call path.
Also test: does the game detect START presses?"""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def read_mem(addr, length):
    r = api("GET", f"/cpu/memory?addr={addr}&len={length}")
    return r.get("data") or r.get("memory", [])

def write_mem(addr, data):
    return api("POST", "/cpu/memory", {"addr": addr, "data": data})

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"
with open(ROM_PATH, "rb") as f:
    rom = f.read()

# Check $D4E0-$D530 (early boot code)
print("=== Game boot code at $D4E0-$D540 ===")
for off in range(0, 96, 16):
    data = rom[0xD4E0+off:0xD4E0+off+16]
    print(f"  ${0xD4E0+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Also check: what is at $B200 (the game's "scene init" that clears $FF0066)  
# This was found earlier. Does the game call THIS function?
# Search for JSR/BSR to $B200
target_b200 = bytes([0x00, 0x00, 0xB2, 0x00])
print(f"\n=== JSR to $B200 area ===")
for i in range(len(rom) - 6):
    if rom[i] == 0x4E and rom[i+1] == 0xB9:
        addr = (rom[i+2]<<24) | (rom[i+3]<<16) | (rom[i+4]<<8) | rom[i+5]
        if 0xB200 <= addr <= 0xB280:
            print(f"  JSR ${addr:06X} at ${i:06X}")

# Look for BSR to $B200
for i in range(len(rom) - 4):
    if rom[i] == 0x61:
        if rom[i+1] == 0x00:
            disp = (rom[i+2] << 8) | rom[i+3]
            if disp >= 0x8000: disp -= 0x10000
            t = i + 2 + disp
            if 0xB200 <= t <= 0xB280:
                print(f"  BSR.W ${t:06X} at ${i:06X}")

# Check what function calls the sound COMMAND functions $82C8/$852C
# They might be called from a central "sound manager" 
# Search for any reference to $82C8 or $852C as addresses
# Check for LEA or 32-bit address patterns
for target in [0x82C8, 0x82B0, 0x852C, 0x66E8]:
    addr_bytes = bytes([(target >> 24) & 0xFF, (target >> 16) & 0xFF, 
                        (target >> 8) & 0xFF, target & 0xFF])
    for i in range(len(rom) - 4):
        if rom[i:i+4] == addr_bytes:
            ctx = rom[max(0,i-4):min(len(rom),i+8)]
            print(f"  ${target:04X} found as address at ${i:06X}: {ctx.hex(' ')}")

# NOW: Test controller input detection
# Fresh load, step to F200, then check controller-related RAM
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 200})

# Read some common controller state RAM locations
print("\n=== Controller state in RAM ===")
for addr in [0xFF0008, 0xFF000A, 0xFF000C, 0xFF000E, 0xFF0010, 0xFF0012]:
    v = read_mem(addr, 2)
    print(f"  ${addr:06X} = 0x{(v[0]<<8)|v[1]:04X}")

# Check $FF0062 (used in sound manager)
val_62 = read_mem(0xFF0062, 2)
print(f"  $FF0062 = 0x{(val_62[0]<<8)|val_62[1]:04X}")

# Press START and step some frames, check if RAM state changes
api("POST", "/input/controller", {"player": 1, "buttons": 0x0080})
api("POST", "/emulator/step", {"frames": 10})
api("POST", "/input/controller", {"player": 1, "buttons": 0})

print("\nAfter START press:")
for addr in [0xFF0008, 0xFF000A, 0xFF000C, 0xFF000E, 0xFF0010, 0xFF0012]:
    v = read_mem(addr, 2)
    print(f"  ${addr:06X} = 0x{(v[0]<<8)|v[1]:04X}")

# Check a wider range of RAM near $FF0060 for controller-related data
print("\nRAM $FF0000-$FF001F:")
ram = read_mem(0xFF0000, 32)
print(f"  {' '.join(f'{b:02X}' for b in ram)}")

# Look for what the game stores at its "button pressed" location
# The game's controller read code at $6098 writes results somewhere
# Let me search for what follows the controller read at $60xx
print(f"\n=== Controller read function $6080-$6120 ===")
for off in range(0, 160, 16):
    data = rom[0x6080+off:0x6080+off+16]
    print(f"  ${0x6080+off:06X}: {' '.join(f'{b:02X}' for b in data)}")
