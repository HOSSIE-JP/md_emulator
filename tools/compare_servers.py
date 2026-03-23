"""Compare old vs new server - check display status"""
import urllib.request, json

def check_server(port, name):
    BASE = f"http://127.0.0.1:{port}/api/v1"
    
    def get(path):
        r = urllib.request.urlopen(f"{BASE}{path}")
        return json.loads(r.read())
    
    def post(path, data=None):
        d = json.dumps(data or {}).encode()
        req = urllib.request.Request(f"{BASE}{path}", data=d,
                                    headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(req)
        return json.loads(r.read())
    
    print(f"=== Server {name} (port {port}) ===")
    
    # Reset
    post("/emulator/reset")
    # Step just 10 frames
    post("/emulator/step", {"frames": 10})
    
    regs = get("/vdp/registers")
    rdata = regs.get("registers") or regs.get("data")
    r01 = rdata[0x01]
    display_en = (r01 & 0x40) != 0
    print(f"  After 10 frames: R01=0x{r01:02X} display={'ON' if display_en else 'OFF'}")
    
    # Step more
    post("/emulator/step", {"frames": 90})
    regs = get("/vdp/registers")
    rdata = regs.get("registers") or regs.get("data")
    r01 = rdata[0x01]
    display_en = (r01 & 0x40) != 0
    print(f"  After 100 frames: R01=0x{r01:02X} display={'ON' if display_en else 'OFF'}")
    
    # Check CPU state
    cpu = get("/cpu/state")
    m68k = cpu.get("m68k") or cpu.get("cpu")
    pc = m68k.get("pc", 0)
    print(f"  PC: 0x{pc:06X}")
    
    # More frames
    post("/emulator/step", {"frames": 800})
    regs = get("/vdp/registers")
    rdata = regs.get("registers") or regs.get("data")
    r01 = rdata[0x01]
    display_en = (r01 & 0x40) != 0
    print(f"  After 900 frames: R01=0x{r01:02X} display={'ON' if display_en else 'OFF'}")
    
    fdata = get("/video/frame")
    pixels = fdata["pixels_argb"]
    non_black = sum(1 for p in pixels if (p & 0x00FFFFFF) != 0)
    print(f"  Non-black pixels: {non_black}/{len(pixels)}")

check_server(8117, "old (target33)")
print()
check_server(8118, "new (target34)")
