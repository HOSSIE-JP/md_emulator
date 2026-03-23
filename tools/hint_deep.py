"""Detailed per-scanline HInt analysis during title screen.
Check: Are HInt interrupts actually firing? Is the hscroll table being updated mid-frame?
"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read().decode())

# Reset and step to title screen
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

# Read current state
regs = api_get("/vdp/registers")["registers"]
hint_en = (regs[0] >> 4) & 1
hs_mode = regs[0xB] & 3
hint_counter_reg = regs[0xA]
hs_addr = (regs[0xD] & 0x3F) << 10
print(f"HInt enabled={hint_en}, HScroll mode={hs_mode}, HInt counter reg=R0xA={hint_counter_reg}")
print(f"HScroll addr=0x{hs_addr:04X}")

# Get the HBlank vector
hint_vector_addr = 0x70  # (24+4)*4 = 112 = 0x70
rom_data = api_get(f"/emulator/memory?addr=0x70&len=4")
if "data" in rom_data:
    handler_addr = (rom_data["data"][0] << 24) | (rom_data["data"][1] << 16) | (rom_data["data"][2] << 8) | rom_data["data"][3]
    print(f"HBlank handler at 0x{handler_addr:08X}")

    # Read a few instructions at the handler
    handler_data = api_get(f"/emulator/memory?addr={handler_addr}&len=32")
    if "data" in handler_data:
        data = handler_data["data"]
        print(f"Handler bytes: {' '.join(f'{b:02X}' for b in data[:32])}")
else:
    print(f"Memory API response: {list(rom_data.keys())}")
    
# Also check VBlank handler
vbl_vector_addr = 0x78  # (24+6)*4 = 120 = 0x78
rom_data2 = api_get(f"/emulator/memory?addr=0x78&len=4")
if "data" in rom_data2:
    vbl_handler = (rom_data2["data"][0] << 24) | (rom_data2["data"][1] << 16) | (rom_data2["data"][2] << 8) | rom_data2["data"][3]
    print(f"VBlank handler at 0x{vbl_handler:08X}")
else:
    print(f"VBlank vector API: {list(rom_data2.keys())}")

# Now read the hscroll table
vram_data = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero_a = 0
nonzero_b = 0
for line in range(224):
    offset = line * 4
    if offset + 3 < len(vram_data):
        hs_a = (vram_data[offset] << 8) | vram_data[offset + 1]
        hs_b = (vram_data[offset + 2] << 8) | vram_data[offset + 3]
        if hs_a != 0: nonzero_a += 1
        if hs_b != 0: nonzero_b += 1
        
print(f"\nHScroll table: nonzero_A={nonzero_a} nonzero_B={nonzero_b}")

# Check the execution trace after stepping 1 more frame
# to see if INT4 appears (HInt)
api_post("/emulator/step", {"frames": 1})
trace = api_get("/emulator/trace")
if "traces" in trace:
    traces = trace["traces"]
    int4_count = sum(1 for t in traces if "INT4" in t.get("mnemonic", ""))
    int6_count = sum(1 for t in traces if "INT6" in t.get("mnemonic", ""))
    print(f"\nAfter 1 frame: trace has {len(traces)} entries, INT4={int4_count}, INT6={int6_count}")
    
    # Show first few INT4 traces
    for t in traces:
        if "INT" in t.get("mnemonic", ""):
            print(f"  {t['mnemonic']} at PC=0x{t['pc']:08X}")
elif "ring" in trace:
    traces = trace["ring"]
    int4_count = sum(1 for t in traces if "INT4" in t.get("mnemonic", ""))
    print(f"\nTrace ring: {len(traces)} entries, INT4={int4_count}")
    for t in traces:
        if "INT" in t.get("mnemonic", ""):
            print(f"  {t['mnemonic']} at PC=0x{t['pc']:08X}")

# Re-check hscroll after running 1 frame
vram_data2 = api_get(f"/vdp/vram?addr={hs_addr}&len=896")["data"]
nonzero_a2 = 0
for line in range(224):
    offset = line * 4
    if offset + 3 < len(vram_data2):
        hs_a = (vram_data2[offset] << 8) | vram_data2[offset + 1]
        if hs_a != 0:
            nonzero_a2 += 1
            if nonzero_a2 <= 10:
                hs_a_s = hs_a if hs_a < 0x8000 else hs_a - 0x10000
                print(f"  line {line}: hs_A={hs_a_s}")
                
print(f"\nAfter +1 frame: nonzero_A={nonzero_a2}")
