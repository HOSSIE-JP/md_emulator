"""Compare two consecutive frames to see what changes in the background.
This will help identify if the wave effect is visible or not."""
import urllib.request, json, struct, zlib

BASE = "http://localhost:8117/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

# Get frame 1
f1 = api_get("/video/frame")
pixels1 = f1["pixels_argb"]
w, h = f1["width"], f1["height"]

# Step 1 frame
api_post("/emulator/step", {"frames": 1})

# Get frame 2
f2 = api_get("/video/frame")
pixels2 = f2["pixels_argb"]

# Compare
diff_count = 0
diff_lines = set()
for y in range(h):
    for x in range(w):
        idx = y * w + x
        if pixels1[idx] != pixels2[idx]:
            diff_count += 1
            diff_lines.add(y)

print(f"Pixels that differ between frames: {diff_count} / {w*h}")
print(f"Lines with differences: {len(diff_lines)} / {h}")
if diff_lines:
    sorted_lines = sorted(diff_lines)
    print(f"First 20 different lines: {sorted_lines[:20]}")
    print(f"Last 20 different lines: {sorted_lines[-20:]}")

# Also check: render just Plane B (with no vscroll wave)
# by looking at column 160 in both frames
print(f"\nColumn 160 comparison (first 20 differing lines):")
shown = 0
for y in sorted(diff_lines):
    if shown >= 20: break
    idx = y * w + 160
    p1 = pixels1[idx]
    p2 = pixels2[idx]
    if p1 != p2:
        print(f"  Line {y:3d}: frame1=0x{p1:08X} frame2=0x{p2:08X}")
        shown += 1
