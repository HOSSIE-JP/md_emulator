"""Track $FF019E bit 0 which prevents sound enable at $83F0"""
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

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

with open(ROM_PATH, "rb") as f:
    rom = f.read()

# Search for ALL references to $E0FF019E
target = bytes([0xE0, 0xFF, 0x01, 0x9E])
print("=== ALL references to $E0FF019E ===")
refs_19e = []
for i in range(len(rom) - 4):
    if rom[i:i+4] == target:
        refs_19e.append(i)
        ctx_start = max(0, i - 6)
        ctx_end = min(len(rom), i + 10)
        ctx = rom[ctx_start:ctx_end]
        print(f"  ${i:06X}: {ctx.hex(' ')}")
print(f"Total: {len(refs_19e)}")

# Track $FF019E during init
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("\n=== Frame-by-frame $FF019E tracking ===")
prev_val = None
for f in range(1, 55):
    api("POST", "/emulator/step", {"frames": 1})
    data19e = read_mem(0xFF019E, 2)
    val = (data19e[0] << 8) | data19e[1]
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    if val != prev_val:
        data66 = read_mem(0xFF0066, 2)
        val66 = (data66[0] << 8) | data66[1]
        print(f"  F{f:3d}: $FF019E=0x{val:04X} (bit0={'SET' if val&1 else 'clr'}) "
              f"$FF0066=0x{val66:04X} PC=${m68k['pc']:06X}")
        prev_val = val

# Check if $FF019E bit 0 is set before $83F0 is reached
# The function at $82C8+ loads the Z80 driver
# Let me decode the full function from $82C8 to $8400
print(f"\n=== Full sound init function $82B0-$8420 ===")
for off in range(0, 0x170, 16):
    data = rom[0x82B0+off:0x82B0+off+16]
    print(f"  ${0x82B0+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Also: look at what's at the BUSREQ area at $66E8 (first BUSREQ)
# This might be the first sound init call
print(f"\n=== First sound init at $66C0-$6740 ===")
for off in range(0, 128, 16):
    data = rom[0x66C0+off:0x66C0+off+16]
    print(f"  ${0x66C0+off:06X}: {' '.join(f'{b:02X}' for b in data)}")
