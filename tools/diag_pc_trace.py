"""Check if M68K ever executes the sound init code at $82B0-$8420"""
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

# Fresh load 
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})

# Use cycle-level stepping to sample PC at high frequency during init
# The Z80 driver loading happens around frames 10-50
# Let's step a few cycles at a time and check PC
print("=== High-frequency PC sampling during init ===")
pc_ranges_hit = {}

for frame in range(55):
    # Step 1 frame at a time but check PC
    api("POST", "/emulator/step", {"frames": 1})
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    pc = m68k['pc']
    
    # Track which 256-byte range the PC is in
    pc_range = pc & 0xFFFF00
    key = f"${pc_range:06X}"
    pc_ranges_hit[key] = pc_ranges_hit.get(key, 0) + 1
    
    # Check specific ranges
    if 0x82B0 <= pc <= 0x8420:
        data19a = read_mem(0xFF019A, 2) 
        val19a = (data19a[0] << 8) | data19a[1]
        data66 = read_mem(0xFF0066, 2)
        val66 = (data66[0] << 8) | data66[1]
        print(f"  F{frame}: PC=${pc:06X} *** IN SOUND INIT! *** $FF019A={val19a:04X} $FF0066={val66:04X}")
    elif 0x6600 <= pc <= 0x6800:
        print(f"  F{frame}: PC=${pc:06X} (in first busreq area)")
    elif 0x8500 <= pc <= 0x8D00:
        print(f"  F{frame}: PC=${pc:06X} (in other busreq area)")

# Report most visited PC ranges
print("\n=== PC range heatmap (top 15) ===")
sorted_ranges = sorted(pc_ranges_hit.items(), key=lambda x: x[1], reverse=True)
for key, count in sorted_ranges[:15]:
    print(f"  {key}: {count} hits")

# Final state check  
data19a = read_mem(0xFF019A, 2)
val19a = (data19a[0] << 8) | data19a[1]
data66 = read_mem(0xFF0066, 2)
val66 = (data66[0] << 8) | data66[1]
print(f"\nFinal: $FF019A={val19a:04X}, $FF0066={val66:04X}")

# Check Z80 handshake byte
z80_102 = read_mem(0xA00102, 1)
print(f"Z80[$0102] = 0x{z80_102[0]:02X}")

# Check which BUSREQ functions were called
# The sound init functions are at $66E8, $67BA, $82C8, $852C, $86F2, $889A, etc.
# Check Z80 RAM to see what happened 
z80_1c00 = read_mem(0xA01C00, 4)
print(f"Z80[$1C00-1C03] = {[f'{b:02X}' for b in z80_1c00]}")

# Check the subroutine at $04A4 
with open(ROM_PATH, "rb") as f:
    rom = f.read()

print(f"\n=== Subroutine at $04A4 ===")
for off in range(0, 32, 16):
    data = rom[0x04A4+off:0x04A4+off+16]
    print(f"  ${0x04A4+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

print(f"\n=== Subroutine at $048C ===")
for off in range(0, 32, 16):
    data = rom[0x048C+off:0x048C+off+16]
    print(f"  ${0x048C+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Track more specific areas: check if game calls $82C8 area at all
# by looking at callers: BSR/JSR to $82B0+ range
# Search ROM for JSR $82C8 etc.
print(f"\n=== Callers of $82xx range ===")
# JSR $00xxxx = 4EB9 0000 xxxx
for target in range(0x82B0, 0x8420, 2):
    pattern = bytes([0x4E, 0xB9, (target >> 16) & 0xFF, (target >> 8) & 0xFF, target & 0xFF])
    # This won't work - need proper 4-byte absolute
    pass

# More practical: search for 4EB9 + address matching $0082xx
for i in range(len(rom) - 6):
    if rom[i] == 0x4E and rom[i+1] == 0xB9:
        addr = (rom[i+2]<<24) | (rom[i+3]<<16) | (rom[i+4]<<8) | rom[i+5]
        if 0x82B0 <= addr <= 0x8420:
            print(f"  JSR ${addr:06X} at ${i:06X}")
