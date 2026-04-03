"""Trace game initialization: when and why does sound NOT get enabled?
Focus on $FF0066 (word write to $0066 affects $0067) and init flow."""
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

# Key finding: $E0FF0066 references at:
# $005314:  ... MOVE.W ($FF0066), D0; ORI.W #$0004, D0; MOVE.W D0, ($FF0066) → sets bit 2!
# $00B23E:  ... MOVE.W #$0000, ($FF0066) → clears!
# $007A80:  ... MOVE.W ($FF0066), D2; BTST #2, D2 ...
# $007AA4:  ... MOVE.W D2, ($FF0066) 
# $007B4A:  ... ANDI.W #$FFDF, D2; MOVE.W D2, ($FF0066) → clears bit 5

# Check the ORI at $5314 - this sets bit 2 of $FF0066
# But bit 3 of $FF0067 = bit 11 of the WORD at $FF0066
# Word at $FF0066: high byte = $FF0066, low byte = $FF0067
# So bit 3 of $FF0067 = bit 3 of the WORD low byte
# To set bit 3 of $FF0067 via WORD write: ORI.W #$0008, ($FF0066) would set it

# Let me check all modifications to $FF0066 and decode what bits they affect
print("=== Decoding all $FF0066 write sites ===\n")

sites = [0x004E88, 0x004E92, 0x005314, 0x00531E, 0x007A80, 0x007AA4, 
         0x007B4A, 0x0083EC, 0x0083F6, 0x00B23E]

for site in sites:
    # Read 24 bytes around each site  
    start = max(0, site - 8)
    end = min(len(rom), site + 16)
    data = rom[start:end]
    print(f"--- ${site:06X} ---")
    for i in range(0, len(data), 16):
        line = data[i:min(i+16, len(data))]
        addr = start + i
        print(f"  ${addr:06X}: {' '.join(f'{b:02X}' for b in line)}")
    print()

# Now let me check $53xx more carefully - the ORI.W #$0004, ($FF0066) sets bit 2 of $FF0066 (high byte)
# But we need bit 3 of $FF0067 (LOW byte of the WORD at $FF0066)
# Actually: in big-endian M68K, $FF0066 = high byte, $FF0067 = low byte
# WORD at $FF0066: upper byte at $FF0066, lower byte at $FF0067
# ORI.W #$0004, ($FF0066) sets bit 2 of the WORD = bit 2 of $FF0067 (low byte)
# ORI.W #$0008, ($FF0066) would set bit 3 of the WORD = bit 3 of $FF0067  
# Let me check: $FF0067 = 0x04 → bit 2 is set in low byte
# WORD at $FF0066 = 0x0004 = bit 2 of low byte (= $FF0067) is set
# This matches ORI.W #$0004 at ~$5314

# So bit 3 of $FF0067 = bit 3 of the WORD = 0x0008
# Let me search for ORI.W #$0008 or MOVE.W patterns that set bit 3

# What about $B23E? It clears $FF0066 to 0x0000
# Let me decode the full flow:

# Fresh load and trace $FF0066 frame by frame during init
api("POST", "/emulator/load-rom-path", {"path": ROM_PATH})
print("\n=== Frame-by-frame $FF0066 tracking during init ===")

prev_val = None
for f in range(1, 55):
    api("POST", "/emulator/step", {"frames": 1})
    data = read_mem(0xFF0066, 2)
    val = (data[0] << 8) | data[1]
    cpu = api("GET", "/cpu/state")
    m68k = cpu["cpu"]["m68k"]
    if val != prev_val:
        print(f"  F{f:3d}: $FF0066=0x{val:04X} (high=0x{data[0]:02X} low=0x{data[1]:02X} "
              f"bit2={'Y' if val&4 else 'N'} bit3={'Y' if val&8 else 'N'}) PC=${m68k['pc']:06X}")
        prev_val = val

# Check: is there code at $B23E that INITIALIZES sound and THEN enables flags?
print(f"\n=== Code around $B23E (sound system init?) ===")
for off in range(0, 128, 16):
    data = rom[0xB200+off:0xB200+off+16]
    print(f"  ${0xB200+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Check $5310 area (ORI.W #$0004)
print(f"\n=== Code around $5310 (sets bit 2 of $FF0066) ===")  
for off in range(0, 64, 16):
    data = rom[0x5300+off:0x5300+off+16]
    print(f"  ${0x5300+off:06X}: {' '.join(f'{b:02X}' for b in data)}")

# Now the BIG question: what sets bit 3?
# Search for ORI.W #$0008 or #$000C or #$000E or #$000F near E0FF0066
print(f"\n=== Searching for ORI/MOVE patterns that set bit 3 of WORD at $FF0066 ===")
target_addr = bytes([0xE0, 0xFF, 0x00, 0x66])

# ORI.W #imm, ($E0FF0066).l = 0079 xxxx E0FF 0066
for i in range(len(rom) - 8):
    if rom[i:i+2] == bytes([0x00, 0x79]) and rom[i+4:i+8] == target_addr:
        imm = (rom[i+2] << 8) | rom[i+3]
        if imm & 0x08:  # bit 3 would be set
            print(f"  ORI.W #${imm:04X}, ($FF0066) at ${i:06X}")

# MOVE.W #imm, ($E0FF0066).l where imm has bit 3 set
# 33FC xxxx E0FF 0066
for i in range(len(rom) - 8):
    if rom[i:i+2] == bytes([0x33, 0xFC]) and rom[i+4:i+8] == target_addr:
        imm = (rom[i+2] << 8) | rom[i+3]
        if imm & 0x08:
            print(f"  MOVE.W #${imm:04X}, ($FF0066) at ${i:06X}")
        else:
            print(f"  MOVE.W #${imm:04X}, ($FF0066) at ${i:06X} (bit3 NOT set)")

# BSET #3, ($E0FF0067) or through $E0FF0066 word
bset_67 = bytes([0x08, 0xF9, 0x00, 0x03, 0xE0, 0xFF, 0x00, 0x67])
for i in range(len(rom) - 8):
    if rom[i:i+8] == bset_67:
        print(f"  BSET #3, ($FF0067) at ${i:06X}")

# Check if bit 3 is set through $83EC area
print(f"\n=== Code around $83EC (ORI.W #$0008?) ===")
for off in range(0, 48, 16):
    data = rom[0x83E0+off:0x83E0+off+16]
    print(f"  ${0x83E0+off:06X}: {' '.join(f'{b:02X}' for b in data)}")
