"""Trace DMA transfers and SAT population for Puyo Puyo."""
import urllib.request, json, sys

BASE = "http://localhost:8114/api/v1"

def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

def get_vram(addr, length):
    return api_get(f"/vdp/vram?addr={addr}&len={length}")

def dump_sat_raw(label, sat_addr):
    """Print raw bytes at SAT address (first 10 sprites = 80 bytes)."""
    resp = get_vram(sat_addr, 80)
    data = resp.get('data', [])
    print(f"\n--- {label}: SAT raw at 0x{sat_addr:04X} ---")
    for i in range(min(10, len(data) // 8)):
        off = i * 8
        row = data[off:off+8]
        y_pos = ((row[0] << 8) | row[1]) & 0x3FF
        size = row[2]
        link = row[3] & 0x7F
        attr = (row[4] << 8) | row[5]
        x_pos = ((row[6] << 8) | row[7]) & 0x1FF
        hc = ((size >> 2) & 3) + 1
        vc = (size & 3) + 1
        tile = attr & 0x7FF
        print(f"  spr[{i:2d}]: y={y_pos:3d}(scr={y_pos-128:+4d}) x={x_pos:3d}(scr={x_pos-128:+4d}) "
              f"sz=0x{size:02X}({hc}x{vc}) link={link:2d} tile=0x{tile:03X} attr=0x{attr:04X} "
              f"raw={' '.join(f'{b:02X}' for b in row)}")
    # Check how many non-zero entries total
    resp2 = get_vram(sat_addr, 640)  # 80 sprites x 8 bytes
    data2 = resp2.get('data', [])
    nz_entries = 0
    for i in range(min(80, len(data2) // 8)):
        off = i * 8
        if any(data2[off:off+8]):
            nz_entries += 1
    print(f"  Non-zero SAT entries (out of 80): {nz_entries}")

def show_dma_stats(label):
    regs = api_get("/vdp/registers")
    r = regs['registers']
    sat_addr = (r[5] & 0x7F) << 9
    print(f"\n=== {label} ===")
    print(f"  SAT base: 0x{sat_addr:04X}")
    print(f"  DMA 68K count: {regs.get('dma_68k_count', 0)}")
    print(f"  DMA 68K total words: {regs.get('dma_68k_total_words', 0)}")
    print(f"  DMA fill count: {regs.get('dma_fill_count', 0)}")
    print(f"  DMA copy count: {regs.get('dma_copy_count', 0)}")
    print(f"  Last DMA target addr: 0x{regs.get('last_dma_target_addr', 0):04X}")
    print(f"  Last DMA source: 0x{regs.get('last_dma_source', 0):06X}")
    print(f"  Last DMA length: {regs.get('last_dma_length', 0)} words")
    print(f"  Data writes: {regs.get('data_writes', 0)}")
    print(f"  Ctrl writes: {regs.get('ctrl_writes', 0)}")
    print(f"  Code reg: 0x{regs.get('code', 0):02X}")
    print(f"  Addr reg: 0x{regs.get('address', 0):04X}")
    print(f"  Auto-increment (reg 0x0F): {r[0x0F]}")
    print(f"  DMA enable (reg 1 bit 4): {(r[1] & 0x10) != 0}")
    return r, sat_addr

# Reset and load ROM
print("=== Starting DMA trace analysis ===")
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Check DMA stats at various frame milestones
for frame_target in [1, 10, 50, 100, 300, 600, 900]:
    prev = api_get("/vdp/registers")
    prev_dma = prev.get('dma_68k_count', 0)
    prev_frame = prev.get('frame', 0)
    
    frames_to_step = frame_target - prev_frame
    if frames_to_step <= 0:
        continue
    
    api_post("/emulator/step", {"frames": frames_to_step})
    r, sat_addr = show_dma_stats(f"Frame {frame_target}")
    
    # At key frames, show SAT content
    if frame_target in [10, 100, 900]:
        dump_sat_raw(f"Frame {frame_target}", sat_addr)

# Now let's check what's at the SAT address in detailed hex
print("\n\n=== Detailed VRAM analysis at frame 900 ===")
regs = api_get("/vdp/registers")
r = regs['registers']
sat_addr = (r[5] & 0x7F) << 9

# Check work RAM around common sprite table source addresses
# Puyo Puyo likely DMAs sprite data from work RAM (0xFF0000-0xFFFFFF)
# Let's check what the 68K has in RAM near potential sprite buffer
print("\n--- Work RAM scan for potential sprite data ---")
resp_mem = api_get(f"/cpu/memory?addr=0xFF0000&len=256")
if 'data' in resp_mem:
    data = resp_mem['data']
    nz = sum(1 for b in data if b != 0)
    print(f"  0xFF0000-0xFF00FF: {nz}/256 non-zero")

# Check a wider range
for base in [0xFF0000, 0xFF1000, 0xFF2000, 0xFF8000, 0xFFC000, 0xFFD000, 0xFFE000]:
    resp_mem = api_get(f"/cpu/memory?addr={base}&len=256")
    if 'data' in resp_mem:
        data = resp_mem['data']
        nz = sum(1 for b in data if b != 0)
        if nz > 0:
            print(f"  0x{base:06X}-0x{base+0xFF:06X}: {nz}/256 non-zero")
            # If this looks like SAT data (8 bytes per sprite entry), show first few
            if nz > 10:
                for i in range(min(5, len(data) // 8)):
                    off = i * 8
                    row = data[off:off+8]
                    y_pos = ((row[0] << 8) | row[1]) & 0x3FF
                    if y_pos > 0 and y_pos < 0x200:  # Plausible Y coord
                        x_pos = ((row[6] << 8) | row[7]) & 0x1FF
                        print(f"    [{i}] y={y_pos}(scr={y_pos-128:+d}) x={x_pos}(scr={x_pos-128:+d}) "
                              f"raw={' '.join(f'{b:02X}' for b in row)}")

# Check VRAM content at SAT and nearby
print(f"\n--- VRAM at SAT (0x{sat_addr:04X}) and nearby ---")
for off in [sat_addr, sat_addr - 0x200, sat_addr + 0x200, sat_addr + 0x400]:
    if off < 0 or off >= 0x10000:
        continue
    resp = get_vram(off, 64)
    data = resp.get('data', [])
    nz = sum(1 for b in data if b != 0)
    print(f"  VRAM 0x{off:04X}: {nz}/64 non-zero | {' '.join(f'{b:02X}' for b in data[:32])}")

# Check VRAM data port write statistics
print(f"\n--- VRAM Non-zero regions (0x0000-0xFFFF by 0x400) ---")
for region_start in range(0, 0x10000, 0x400):
    resp = get_vram(region_start, 0x400)
    data = resp.get('data', [])
    nonzero = sum(1 for b in data if b != 0)
    if nonzero > 0:
        print(f"  0x{region_start:04X}-0x{region_start+0x3FF:04X}: {nonzero}/1024 non-zero")

print("\nDone!")
