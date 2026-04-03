"""Find how $82xx sound init connects to the game flow.
Check indirect calls, function pointer tables, and trace the actual init sequence."""
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

# The $82xx function isn't called directly (no JSR $82xx found).
# Check for BSR (relative branches) that could reach $82xx.
# BSR.W range: -32768 to +32767 from current PC
# Any code from $02C8 to $102C8 could BSR.W to $82C8

# Also check for function pointer tables containing $82C8 or nearby addresses
# as long words (00 00 82 C8 or 00 00 82 B0 etc.)

print("=== Searching for $0082C8 as function pointer in ROM ===")
target_ptr = bytes([0x00, 0x00, 0x82, 0xC8])
for i in range(len(rom) - 4):
    if rom[i:i+4] == target_ptr:
        ctx = rom[max(0,i-4):min(len(rom),i+12)]
        print(f"  ${i:06X}: {ctx.hex(' ')}")

# Also check $82B0 (potential function entry)
for addr_check in [0x82B0, 0x82B8, 0x82C0, 0x8310, 0x83E0]:
    target = bytes([0x00, 0x00, (addr_check >> 8) & 0xFF, addr_check & 0xFF])
    for i in range(len(rom) - 4):
        if rom[i:i+4] == target:
            ctx_start = max(0, i-4)
            ctx_end = min(len(rom), i+8)
            ctx = rom[ctx_start:ctx_end]
            print(f"  ${addr_check:04X} ref at ${i:06X}: {ctx.hex(' ')}")

# Check BSR to $82C8 from various points
print("\n=== BSR.W to $82C8 from nearby code ===")
# BSR.W = 6100 + 16-bit displacement
# BSR.B = 61xx (8-bit displacement)
for i in range(len(rom) - 4):
    if rom[i] == 0x61:
        # BSR.W: rom[i] = 0x61, rom[i+1] = 0x00, displacement = rom[i+2:i+4]
        if rom[i+1] == 0x00:
            disp = (rom[i+2] << 8) | rom[i+3]
            if disp >= 0x8000:
                disp -= 0x10000  # sign extend
            target_addr = i + 2 + disp
            if 0x82B0 <= target_addr <= 0x8420:
                print(f"  BSR.W at ${i:06X} -> ${target_addr:06X}")
        else:
            # BSR.B: displacement in rom[i+1]
            disp = rom[i+1]
            if disp >= 0x80:
                disp -= 0x100
            target_addr = i + 2 + disp
            if 0x82B0 <= target_addr <= 0x8420:
                print(f"  BSR.B at ${i:06X} -> ${target_addr:06X}")

# Check BRA to $82C8  
print("\n=== BRA to $82xx range ===")
for i in range(len(rom) - 4):
    if rom[i] == 0x60:
        if rom[i+1] == 0x00:
            disp = (rom[i+2] << 8) | rom[i+3]
            if disp >= 0x8000:
                disp -= 0x10000
            target_addr = i + 2 + disp
            if 0x82B0 <= target_addr <= 0x8420:
                print(f"  BRA.W at ${i:06X} -> ${target_addr:06X}")
        elif rom[i+1] != 0x00 and rom[i+1] != 0xFF:
            disp = rom[i+1]
            if disp >= 0x80:
                disp -= 0x100
            target_addr = i + 2 + disp
            if 0x82B0 <= target_addr <= 0x8420:
                print(f"  BRA.B at ${i:06X} -> ${target_addr:06X}")

# Look for the ACTUAL path the game takes during init
# Step cycle-by-cycle during frames 10-14 (when Z80 loading happens)
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 35})

# Now do cycle-level stepping through the driver loading
# Sample PC every 100 cycles
print("\n=== Cycle-level PC trace during Z80 loading (F35-F50) ===")
visited_pcs = set()
for i in range(3000):
    api("POST", "/emulator/step", {"cycles": 100})
    cpu = api("GET", "/cpu/state")
    pc = cpu["cpu"]["m68k"]["pc"]
    if pc not in visited_pcs:
        visited_pcs.add(pc)
        if 0x6500 <= pc <= 0x6800 or 0x8200 <= pc <= 0x8500 or 0xB200 <= pc <= 0xB300:
            print(f"  cycle {i*100}: PC=${pc:06X}")
            if len(visited_pcs) > 200:
                break
    if pc >= 0x7980 and pc <= 0x79A0:
        # VBlank poll - game is done with init
        print(f"  cycle {i*100}: PC=${pc:06X} (VBlank poll - init done)")
        break
