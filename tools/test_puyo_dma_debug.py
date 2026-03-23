"""Check DMA counters to verify SAT DMA is being executed"""
import urllib.request
import json
import time

BASE = "http://127.0.0.1:8112"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

time.sleep(2)

# Load ROM
api("POST", "/api/v1/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

for target_frame in [100, 300, 500, 600, 700, 900]:
    delta = {100:100, 300:200, 500:200, 600:100, 700:100, 900:200}
    for _ in range(delta[target_frame]):
        api("POST", "/api/v1/emulator/step", {"cycles": 488 * 262})
    
    r = api("GET", "/api/v1/vdp/registers")
    print(f"\nFrame ~{target_frame}:")
    print(f"  dma_68k_count={r.get('dma_68k_count')} total_words={r.get('dma_68k_total_words')}")
    print(f"  dma_fill_count={r.get('dma_fill_count')} dma_copy_count={r.get('dma_copy_count')}")
    print(f"  last_dma: target=0x{r.get('last_dma_target_addr', 0):04X} "
          f"source=0x{r.get('last_dma_source', 0):06X} length={r.get('last_dma_length', 0)}")
    print(f"  data_writes={r.get('data_writes')} ctrl_writes={r.get('ctrl_writes')}")
    
    # Check SAT
    r_vram = api("GET", f"/api/v1/vdp/vram?addr={0xBC00}&len=16")
    vram_sat = r_vram.get("data", [])
    vram_hex = ' '.join(f'{b:02X}' for b in vram_sat[:16])
    
    r_ram = api("GET", f"/api/v1/cpu/memory?addr={0xFF0E86}&len=16")
    ram_sat = r_ram.get("data", [])
    ram_hex = ' '.join(f'{b:02X}' for b in ram_sat[:16])
    
    r_frame = api("GET", "/api/v1/video/frame")
    pixels = r_frame["pixels_argb"]
    nb = sum(1 for p in pixels if (p & 0xFFFFFF) != 0)
    unique = len(set(pixels))
    
    print(f"  Frame: {unique} colors, {nb} non-black")
    print(f"  RAM  SAT: {ram_hex}")
    print(f"  VRAM SAT: {vram_hex}")
