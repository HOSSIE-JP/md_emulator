"""Check why CPU is at PC=0 after 900 frames"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def api_get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read().decode())

# Reset and step to title 
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Step just a few frames first
api_post("/emulator/step", {"frames": 10})
cpu = api_get("/cpu/state")["cpu"]
print(f"After 10 frames: PC=0x{cpu['pc']:08X} SR=0x{cpu['sr']:04X}")

# Check trace ring
trace = api_get("/cpu/trace")
ring = trace.get("trace_ring", [])
exc = trace.get("exception_trace", [])
print(f"Trace ring: {len(ring)} entries")
print(f"Exception trace: {len(exc)} entries")

# Show last 20 trace entries
for t in ring[-20:]:
    m = t.get("mnemonic", "")
    pc = t.get("pc", 0)
    print(f"  PC=0x{pc:08X} {m}")

if exc:
    print("\nException trace:")
    for t in exc[:10]:
        print(f"  PC=0x{t.get('pc',0):08X} {t.get('mnemonic','')}")

# Step more
api_post("/emulator/step", {"frames": 90})
cpu2 = api_get("/cpu/state")["cpu"]
print(f"\nAfter 100 frames: PC=0x{cpu2['pc']:08X} SR=0x{cpu2['sr']:04X}")

# Check if stopped
print(f"  stopped={cpu2.get('stopped', 'N/A')}")
print(f"  last_exception={cpu2.get('last_exception', 'N/A')}")

# Check trace again
trace2 = api_get("/cpu/trace")
ring2 = trace2.get("trace_ring", [])
for t in ring2[-10:]:
    m = t.get("mnemonic", "")
    pc = t.get("pc", 0)
    cyc = t.get("cycles", 0)
    print(f"  PC=0x{pc:08X} cyc={cyc} {m}")
