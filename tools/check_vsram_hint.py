"""Test: Is VSRAM being updated mid-frame by HInt handler?
Approach: Add a logging mechanism to track VSRAM writes per scanline.
Since we can't easily do that without code changes, let's check VSRAM at the
end of a frame during the title screen when the wave flag is set.
"""
import urllib.request, json

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
api_post("/emulator/step", {"frames": 900})

# Check flag
flag = api_get("/cpu/memory?addr=16711994&len=8")["data"]
print(f"$FF013A = {flag[0]} (wave flag)")
ptr = (flag[2] << 24) | (flag[3] << 16) | (flag[4] << 8) | flag[5]
print(f"$FF013C-D = data ptr 0x{ptr:08X}")
# Wait $FF013C is a long, so it needs 4 bytes from offset 2
ptr = api_get(f"/cpu/memory?addr={0xFF013C}&len=4")["data"]
ptr_val = (ptr[0] << 24) | (ptr[1] << 16) | (ptr[2] << 8) | ptr[3]
print(f"$FF013C pointer = 0x{ptr_val:08X}")
offset = api_get(f"/cpu/memory?addr={0xFF013E}&len=2")["data"]
offset_val = (offset[0] << 8) | offset[1]
print(f"$FF013E offset = {offset_val}")
counter = api_get(f"/cpu/memory?addr={0xFF0140}&len=2")["data"]
counter_val = (counter[0] << 8) | counter[1]
print(f"$FF0140 counter = {counter_val}")

# Read VSRAM
vsram = api_get("/vdp/vsram")["vsram"]
print(f"\nVSRAM after frame 900:")
for i in range(min(10, len(vsram))):
    v = vsram[i]
    print(f"  VSRAM[{i}] = 0x{v:04X} ({v})")

# Read the data table that the HInt handler uses
if ptr_val > 0 and ptr_val < 0x01000000:
    table_data = api_get(f"/cpu/memory?addr={ptr_val}&len=448")["data"]  # 224 words
    print(f"\nData table at 0x{ptr_val:08X} (first 20 words):")
    for i in range(0, min(40, len(table_data)), 2):
        w = (table_data[i] << 8) | table_data[i+1]
        ws = w if w < 0x8000 else w - 0x10000
        print(f"  [{i//2:3d}] = 0x{w:04X} ({ws})")

# Step 1 frame and check again
api_post("/emulator/step", {"frames": 1})
vsram2 = api_get("/vdp/vsram")["vsram"]
print(f"\nVSRAM after frame 901:")
for i in range(min(10, len(vsram2))):
    v = vsram2[i]
    print(f"  VSRAM[{i}] = 0x{v:04X} ({v})")

flag2 = api_get(f"/cpu/memory?addr={0xFF013A}&len=1")["data"][0]
counter2_data = api_get(f"/cpu/memory?addr={0xFF0140}&len=2")["data"]
counter2 = (counter2_data[0] << 8) | counter2_data[1]
print(f"After +1 frame: flag={flag2} counter={counter2}")
