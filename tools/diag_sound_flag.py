"""Find the sound update call path: VBlank handler checks $FF0067 bit 3 → calls $D5B0"""
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

# Check $FF0067 at various stages
print("=== $FF0067 (sound enable flag) tracking ===")
for target in [1, 10, 50, 100, 120, 125, 130, 150, 200, 500, 1000]:
    prev = 0
    api("POST", "/emulator/step", {"frames": target - prev if target == 1 else 1})
    if target > 1:
        api("POST", "/emulator/step", {"frames": target - 1 - (1 if target == 10 else 0)})
    flag = read_mem(0xFF0067, 1)[0]
    counter_42 = read_mem(0xFF0042, 2)
    counter_42_val = (counter_42[0] << 8) | counter_42[1]
    vblank_flag = read_mem(0xFF0064, 2)
    frame_ctr = read_mem(0xFF004C, 4)
    frame_val = (frame_ctr[0]<<24) | (frame_ctr[1]<<16) | (frame_ctr[2]<<8) | frame_ctr[3]
    
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    
    print(f"  F{target:4d}: $FF0067=0x{flag:02X} (bit3={'SET' if flag & 8 else 'clr'}) "
          f"$FF0042={counter_42_val:04X} frame_ctr={frame_val} PC=${m68k['pc']:06X}")

# Let's specifically check after loading - step frame by frame around VINT disable
print("\n=== Frame-by-frame during VINT enabled period ===")
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 50})

for f in range(50, 135):
    api("POST", "/emulator/step", {"frames": 1})
    flag = read_mem(0xFF0067, 1)[0]
    if flag != 0:
        cpu = api("GET", "/cpu/state")
        m68k = cpu["cpu"]["m68k"]
        print(f"  F{f+1}: $FF0067=0x{flag:02X} (bit3={'SET' if flag & 8 else 'clr'}, "
              f"bit1={'SET' if flag & 2 else 'clr'}) PC=${m68k['pc']:06X}")

# Check if $D5B0 has been called by looking at what happens there
print("\n=== Sound update routine at $D5B0 ===")
rom_data = read_mem(0xD5B0, 64)
print(f"$D5B0: {' '.join(f'{b:02X}' for b in rom_data[:16])}")
print(f"$D5C0: {' '.join(f'{b:02X}' for b in rom_data[16:32])}")
print(f"$D5D0: {' '.join(f'{b:02X}' for b in rom_data[32:48])}")
print(f"$D5E0: {' '.join(f'{b:02X}' for b in rom_data[48:64])}")

# Also check the indirect call target at $FF005E
print("\n=== Indirect VBlank routine ($FF005E) ===")
indirect = read_mem(0xFF005E, 4)
indirect_addr = (indirect[0]<<24) | (indirect[1]<<16) | (indirect[2]<<8) | indirect[3]
print(f"$FF005E (indirect JSR target): 0x{indirect_addr:06X}")

# Check what the return address is when M68K is in VBlank poll
print("\n=== Main loop analysis ===")
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
api("POST", "/emulator/step", {"frames": 200})
cpu = api("GET", "/cpu/state")
m68k = cpu["cpu"]["m68k"]
a7 = m68k['a'][7]
print(f"At F200: PC=0x{m68k['pc']:06X} A7(SP)=0x{a7:06X}")

# Stack layout at the VBlank poll:
# MOVEM.W saves D2,D3,D4,A2 (4 words = 8 bytes) pushed before entering
# ADDQ.L #4 discards 4 more bytes
# Then RTS pops return address
# So return addr is at A7 + saved_regs + extra
# Actually, let me just read the stack
stack = read_mem(a7, 32)
print(f"Stack at A7:")
for i in range(0, 32, 4):
    val = (stack[i]<<24) | (stack[i+1]<<16) | (stack[i+2]<<8) | stack[i+3]
    print(f"  A7+{i:2d} (${a7+i:06X}): {stack[i]:02X} {stack[i+1]:02X} {stack[i+2]:02X} {stack[i+3]:02X} = 0x{val:08X}")

# Check M68K D/A registers for context
print(f"\nD regs: {[f'0x{d:08X}' for d in m68k['d']]}")
print(f"A regs: {[f'0x{a:08X}' for a in m68k['a']]}")
