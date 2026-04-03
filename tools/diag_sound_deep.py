"""Deep trace of sound update function $D5B0 and Z80 bus state"""
import urllib.request, json, time

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

# Dump full sound function at $D5B0
print("=== Sound function $D5B0-$D680 (208 bytes) ===")
for off in range(0, 208, 16):
    data = read_mem(0xD5B0 + off, 16)
    print(f"  ${0xD5B0+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Check sound-related RAM variables
print("\n=== Sound RAM variables ===")
vars_to_check = [
    (0xFF0116, 2, "timer/counter"),
    (0xFF0198, 2, "reference value"),
    (0xFF019A, 2, "sub value"),
    (0xFF0067, 1, "sound flags"),
    (0xFF0064, 2, "VBlank flag"),
    (0xFF004C, 4, "frame counter"),
    (0xFF005E, 4, "indirect VBlank ptr"),
    (0xFF0042, 2, "VBlank countdown"),
]
for addr, size, desc in vars_to_check:
    data = read_mem(addr, size)
    if size == 1:
        print(f"  ${addr:06X} ({desc}): 0x{data[0]:02X}")
    elif size == 2:
        val = (data[0] << 8) | data[1]
        print(f"  ${addr:06X} ({desc}): 0x{val:04X} ({val})")
    elif size == 4:
        val = (data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]
        print(f"  ${addr:06X} ({desc}): 0x{val:08X} ({val})")

# Check M68K SR and interrupt mask
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
sr = m68k['sr']
int_mask = (sr >> 8) & 7
print(f"\n=== CPU State ===")
print(f"  PC=0x{m68k['pc']:06X}")
print(f"  SR=0x{sr:04X} (I={int_mask}, S={'Y' if sr & 0x2000 else 'N'})")
print(f"  A0=0x{m68k['a'][0]:08X}")
print(f"  A7=0x{m68k['a'][7]:08X}")

# Check Z80 bus request state
print(f"\n=== Z80 Bus State ===")
bus_status = read_mem(0xA11100, 2)
print(f"  $A11100 = 0x{bus_status[0]:02X} (bus {'granted' if bus_status[0]==0 else 'Z80 running'})")

# NOW: let's try a different approach
# Instead of enabling VINT and letting the VBlank handler call $D5B0,
# let's understand what NORMALLY enables sound
# Let's look at WHAT writes to $FF0067

# The VBlank handler at $02B0 is the "simple" path (from supervisor mode interrupt)
# The complex path at $026C-$02AC is for NON-supervisor interrupts
# Let's check: could $FF0067 be written through the save/restore mechanism?

# Check if $FF0067 is near the register save area
# $029A: MOVEM.W ..., -(A0) where A0 = $FF0042
# Saves 14 words = 28 bytes from $FF0042 downward = $FF0026 to $FF0041
# $FF0067 is NOT in this range ($0067 > $0042)

# Let me look for writes to $FF0067 via register indirect
# First, let me search for $0067 offset patterns
ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"
with open(ROM_PATH, "rb") as f:
    rom = f.read()

# Search for MOVE.B #xx, xx(An) where displacement = $0067 from base $FF0000
# That would be: MOVE.B #xx, $0067(A5) if A5 = $FF0000, etc.
# Also: any BSET/BCLR with absolute short addressing $0067
# $FF0067 as absolute short = $0067 sign-extended = $FF0067 since $0067 < $7FFF it's positive... 
# Wait, $0067 as absolute short ($xxx.W) sign-extends: $0067 → $00000067 (positive, ROM area!)
# So $FF0067 can ONLY be addressed as absolute long ($E0FF0067 or $00FF0067)

# But I already searched for those and found nothing.
# The game must be writing through a register-indirect or data table approach.

# Let me search for what initializes $FF0060-$FF006F range
# Check for any reference to $E0FF0060
target60 = bytes([0xE0, 0xFF, 0x00, 0x60])
print(f"\n=== References to $E0FF0060 ===")
found = []
for i in range(len(rom) - 4):
    if rom[i:i+4] == target60:
        found.append(i)
        ctx = rom[max(0,i-4):min(len(rom),i+8)]
        print(f"  ${i:06X}: {ctx.hex(' ')}")
print(f"  Total: {len(found)}")

# Also check $E0FF0066 (maybe word write to $0066 writes byte to $0067)
target66 = bytes([0xE0, 0xFF, 0x00, 0x66])
print(f"\n=== References to $E0FF0066 ===")
found66 = []
for i in range(len(rom) - 4):
    if rom[i:i+4] == target66:
        found66.append(i)
        ctx = rom[max(0,i-6):min(len(rom),i+10)]
        print(f"  ${i:06X}: {ctx.hex(' ')}")
print(f"  Total: {len(found66)}")
