"""Load ROM and step to demo screen on new server"""
import urllib.request, json

BASE = "http://localhost:8115/api/v1"

def api_post(path, data):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req)
    return json.loads(r.read().decode())

def api_get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read().decode())

# Load ROM
print("Loading ROM...")
result = api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
print(f"Load ROM: {result}")

# Step 2700 frames to get to demo
print("Stepping 2700 frames...")
result = api_post("/emulator/step", {"frames": 2700})
print(f"Step: {result}")

# Check state
regs = api_get("/vdp/registers")["registers"]
print(f"\nR0=0x{regs[0]:02X} R1=0x{regs[1]:02X} R0xB=0x{regs[0xB]:02X} R0xC=0x{regs[0xC]:02X}")
print(f"Display enabled: {(regs[1]&0x40)!=0}")
print(f"Frame: {regs}")
