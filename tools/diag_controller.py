"""Check controller input: does game toggle TH and read START?"""
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

def safe_int(v):
    return int(v, 16) if isinstance(v, str) else int(v)

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

# Load ROM fresh
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})

# Step to game running state (past init)
api("POST", "/emulator/step", {"frames": 200})

# Read I/O port values
io_data = read_mem(0xA10001, 16)
print(f"I/O ports $A10001-$A10010: {[f'{b:02X}' for b in io_data]}")
print(f"  $A10001 (version): 0x{io_data[0]:02X}")
print(f"  $A10003 (PAD1 data): 0x{io_data[2]:02X}")
print(f"  $A10005 (PAD2 data): 0x{io_data[4]:02X}")
print(f"  $A10007 (EXP data): 0x{io_data[6]:02X}")
print(f"  $A10009 (PAD1 ctrl): 0x{io_data[8]:02X}")
print(f"  $A1000B (PAD2 ctrl): 0x{io_data[10]:02X}")

# Check what the game sees when reading with TH=1 (no buttons pressed)
pad1_data = io_data[2]
th_bit = (pad1_data >> 6) & 1
print(f"\nPAD1 TH bit: {th_bit}")
print(f"PAD1 data bits: {pad1_data:08b}")

# Now set START and re-read
api("POST", "/input/controller", {"player": 1, "buttons": 0x0080})
api("POST", "/emulator/step", {"frames": 5})
io_data2 = read_mem(0xA10001, 16)
print(f"\nAfter START press:")
print(f"  $A10003: 0x{io_data2[2]:02X} ({io_data2[2]:08b})")

# The game might read controller via RAM - search for controller state variable
# Read work RAM for any controller-related values
# Common locations: $FF0000-$FFFF (game variables)

# Check the ROM code that reads controller
# Look at $A10003 references in the code
ROM_PATH_LOCAL = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"
with open(ROM_PATH_LOCAL, "rb") as f:
    rom = f.read()

# Search for reads from $A10003: MOVE.B ($A10003).l, Dn
# Pattern: 1030 xx39 00A1 0003 (read from $A10003)
# Actually, BTST and MOVE patterns vary. Search for $A10003 address
target_bytes = bytes([0x00, 0xA1, 0x00, 0x03])
count = 0
for i in range(len(rom) - 4):
    if rom[i:i+4] == target_bytes:
        count += 1
        if count <= 15:
            ctx = rom[max(0,i-4):min(len(rom),i+8)]
            print(f"  $A10003 ref at ${i:06X}: {ctx.hex(' ')}")
print(f"Total $A10003 references: {count}")

# Also search for $A10002 (word read of controller)
target_bytes_w = bytes([0x00, 0xA1, 0x00, 0x02])
count2 = 0
for i in range(len(rom) - 4):
    if rom[i:i+4] == target_bytes_w:
        count2 += 1
        if count2 <= 5:
            ctx = rom[max(0,i-4):min(len(rom),i+8)]
            print(f"  $A10002 ref at ${i:06X}: {ctx.hex(' ')}")
print(f"Total $A10002 references: {count2}")

# Read the game's $FF0000 area for controller state in RAM
ram_state = read_mem(0xFF0060, 32)
print(f"\nRAM $FF0060-$FF007F: {[f'{b:02X}' for b in ram_state]}")

# Some games store button state at specific RAM locations
# Check common locations
for addr in [0xFF0008, 0xFF0012, 0xFF0062, 0xFF0064, 0xFF0066, 0xFF0068]:
    val = read_mem(addr, 2)
    print(f"  RAM ${addr:06X}: {[f'{b:02X}' for b in val]}")

# Check version register ($A10001)
version = read_mem(0xA10001, 1)
print(f"\nVersion register ($A10001): 0x{version[0]:02X}")
print(f"  Region: {'JP' if (version[0] & 0x80) == 0 else 'US/EU'}")
print(f"  Model: {'MD1' if (version[0] & 0x40) == 0 else 'MD2'}")
print(f"  NTSC/PAL: {'NTSC' if (version[0] & 0x40) == 0 else 'PAL'}")

# Release controller
api("POST", "/input/controller", {"player": 1, "buttons": 0})
