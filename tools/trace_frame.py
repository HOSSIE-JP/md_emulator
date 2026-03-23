"""Check: is VDP write_data_port being called with VSRAM code during HInt?
The key question: does VSRAM[0] change during mid-frame rendering?

We'll add a VSRAM write counter to track this. But first, let's try
stepping one scanline at a time using the step API with cycles.
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

# Now step 1 scanline worth of cycles (488) and check VSRAM
# But the step endpoint takes "frames" not "cycles"... 
# Let me check if it supports cycles too

# Check the step handler
# From the API code, step takes {"frames": N}
# Let me check if there's a cycles endpoint

# Actually let us just check what's at VSRAM[0] by stepping 1 frame 
# but also reading VSRAM[1] which is at byte offset 2

# Actually the real fix here is to check if the HInt handler is actually 
# executing. Let me look at the trace ring during one frame at the title screen.

# Step just 1 frame and check trace ring
print("=== Check trace ring for INT4 during title screen ===")
api_post("/emulator/step", {"frames": 1})
trace = api_get("/cpu/trace")
ring = trace.get("trace_ring", [])
print(f"Trace ring has {len(ring)} entries")

# Count unique PCs
pc_counts = {}
for t in ring:
    pc = t["pc"]
    m = t["mnemonic"]
    key = f"0x{pc:08X} {m}"
    pc_counts[key] = pc_counts.get(key, 0) + 1

for k, v in sorted(pc_counts.items()):
    if v > 1 or "INT" in k or "RTE" in k or "RTR" in k:
        print(f"  {k}: {v}x")

# Show all entries
print("\nFull trace ring:")
for i, t in enumerate(ring):
    print(f"  [{i:2d}] PC=0x{t['pc']:08X} cyc={t['cycles']:3d} {t['mnemonic']}")
