"""Check controller processing results and game flow dispatcher"""
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

# Load fresh
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 200})

# Check controller-related areas
print("=== Controller RAM areas ===")
for base in [0xFFA040, 0xFFA060, 0xFFA068, 0xFFA078]:
    data = read_mem(base, 16)
    print(f"  ${base:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Check the game's dispatch tables and function pointers
print("\n=== Game state / function pointers ===")
for addr in [0xFF0048, 0xFF004C, 0xFF0050, 0xFF0054, 0xFF0058, 0xFF005E, 
             0xFF0060, 0xFF0064, 0xFF0066, 0xFF0306, 0xFF030A]:
    data = read_mem(addr, 4)
    val = (data[0]<<24)|(data[1]<<16)|(data[2]<<8)|data[3]
    print(f"  ${addr:06X} = 0x{val:08X}")

# Now press START and check $FFA068
print("\n=== Before START ===")
pre_data = read_mem(0xFFA060, 32)
print(f"  $FFA060: {' '.join(f'{b:02X}' for b in pre_data)}")

api("POST", "/input/controller", {"player": 1, "buttons": 0x0080})
api("POST", "/emulator/step", {"frames": 5})

print("\n=== After START (5 frames) ===")
post_data = read_mem(0xFFA060, 32)
print(f"  $FFA060: {' '.join(f'{b:02X}' for b in post_data)}")

# Check what changed
changes = [(i, pre_data[i], post_data[i]) for i in range(32) if pre_data[i] != post_data[i]]
if changes:
    for offset, old, new in changes:
        print(f"  Changed: $FFA0{0x60+offset:02X}: 0x{old:02X} -> 0x{new:02X}")
else:
    print("  No changes in $FFA060-$FFA07F!")

# Release START
api("POST", "/input/controller", {"player": 1, "buttons": 0})
api("POST", "/emulator/step", {"frames": 5})
    
# Check game's button processing specifically
# The controller read writes to $FFA068 and $FFA078
# Let me also check if the controller READ function is even being called
# by checking if $FFA068 has changed from its initial value (0)
init_data = [0] * 32
print("\n=== Checking if controller read runs at all ===")
test_data = read_mem(0xFFA068, 16)
print(f"  $FFA068: {' '.join(f'{b:02X}' for b in test_data)}")

# Also check the controller CTRL register ($A10009)
ctrl = read_mem(0xA10009, 1)
print(f"  PAD1 CTRL ($A10009): 0x{ctrl[0]:02X}")
data_port = read_mem(0xA10003, 1)
print(f"  PAD1 DATA ($A10003): 0x{data_port[0]:02X}")

# Check $FFA040 (function pointer used by controller handler)
fptr = read_mem(0xFFA040, 4)
fptr_val = (fptr[0]<<24)|(fptr[1]<<16)|(fptr[2]<<8)|fptr[3]
print(f"  $FFA040 (ctrl handler): 0x{fptr_val:08X}")

# Check game state variables more broadly
print("\n=== Wider RAM scan for game state ===")
for base_addr in [0xFF0300, 0xFF0A00, 0xFF0A40, 0xFF0A80]:
    data = read_mem(base_addr, 32)
    nonzero = any(b != 0 for b in data)
    if nonzero:
        print(f"  ${base_addr:06X}: {' '.join(f'{b:02X}' for b in data)}")
    else:
        print(f"  ${base_addr:06X}: all zeros")

# Also check: does the game use SR lower than IPL 6?
# This determines if VBlank can fire
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
sr = m68k['sr']
ipl = (sr >> 8) & 7
print(f"\n=== CPU State ===")
print(f"  PC=0x{m68k['pc']:06X} SR=0x{sr:04X} IPL={ipl}")

# Check: how is the VBlank poll loop called?
# The return address on the stack tells us the caller
a7 = m68k['a'][7]  
stack_data = read_mem(a7, 24)
print(f"  SP=0x{a7:08X}")
print(f"  Stack: {' '.join(f'{b:02X}' for b in stack_data)}")
