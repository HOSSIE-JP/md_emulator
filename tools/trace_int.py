"""Step through a single frame one scanline at a time, checking interrupts."""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step to title screen (frame 899)
api_post("/emulator/step", {"frames": 899})

m68k = api_get("/cpu/state")["cpu"]["m68k"]
print(f"Before frame 900: PC=0x{m68k['pc']:08X} SR=0x{m68k['sr']:04X}")

# Now step 1 frame using the step endpoint with cycles
# Each scanline = 488 cycles, total frame = 262 scanlines = 127856 cycles
# But step endpoint only takes "frames", not "cycles"
# Let's use the step endpoint: {"cycles": N} 
# First check what step accepts

# Actually step with 1 frame and look at int counts in exception_trace
api_post("/emulator/step", {"frames": 1})

m68k2 = api_get("/cpu/state")["cpu"]["m68k"]
print(f"After frame 900: PC=0x{m68k2['pc']:08X} SR=0x{m68k2['sr']:04X}")

trace = api_get("/cpu/trace")
ring = trace.get("trace_ring", [])
exc = trace.get("exception_trace", [])

print(f"Trace ring: {len(ring)}")
print(f"Exception trace: {len(exc)}")

# Count INTs in exception trace
if exc:
    int4_exc = sum(1 for t in exc if "INT4" in t.get("mnemonic", ""))
    int6_exc = sum(1 for t in exc if "INT6" in t.get("mnemonic", ""))
    print(f"Exception trace INT4={int4_exc} INT6={int6_exc}")
    for t in exc[:30]:
        print(f"  0x{t['pc']:08X} {t['mnemonic']}")

# Count INTs in trace ring
int4_ring = sum(1 for t in ring if "INT4" in t.get("mnemonic", ""))
int6_ring = sum(1 for t in ring if "INT6" in t.get("mnemonic", ""))
rte_ring = sum(1 for t in ring if "RTE" in t.get("mnemonic", ""))
print(f"Trace ring INT4={int4_ring} INT6={int6_ring} RTE={rte_ring}")

# Show all trace entries (only 64)
for i, t in enumerate(ring):
    m = t.get("mnemonic", "")
    if "INT" in m or "RTE" in m or "ORI" in m:
        print(f"  [{i:2d}] 0x{t['pc']:08X} cyc={t['cycles']:3d} {m}")
