"""Check per-scanline VSRAM[0] values during title screen rendering.
This will show if the HInt handler is actually changing VSRAM[0] per line."""
import urllib.request, json, time

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

time.sleep(1)

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step to title screen
api_post("/emulator/step", {"frames": 900})

# Check wave flag
flag = api_get("/cpu/memory?addr=16711994&len=1")  # $FF013A = 0xFF013A = 16711994
flag_val = flag["data"][0]
print(f"Wave flag ($FF013A) = {flag_val}")

# Get per-scanline VSRAM[0]
sv = api_get("/vdp/scanline-vsram")
data = sv["scanline_vsram_a"]
print(f"\nPer-scanline VSRAM[0] (first 40 lines):")
for i in range(min(40, len(data))):
    print(f"  Line {i:3d}: VSRAM[0] = {data[i]:5d} (0x{data[i]:04X})")

# Count unique values
unique = set(data)
print(f"\nTotal unique VSRAM[0] values: {len(unique)}")
nonzero = [d for d in data if d != 0]
print(f"Non-zero VSRAM[0] count: {len(nonzero)} out of {len(data)}")

# Show distribution
if len(unique) <= 20:
    for v in sorted(unique):
        cnt = data.count(v)
        print(f"  value={v:5d} (0x{v:04X}): {cnt} lines")
else:
    print("  (too many unique values to list all)")
    for i in range(0, len(data), 10):
        print(f"  Lines {i:3d}-{min(i+9,len(data)-1):3d}: {data[i:i+10]}")
