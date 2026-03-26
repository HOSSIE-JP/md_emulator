#!/usr/bin/env python3
"""Dump raw APU state JSON."""
import urllib.request, json

BASE = "http://127.0.0.1:8080/api/v1"

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

post("/emulator/load-rom-path", {"path": "roms/puyo.bin"})
for i in range(60):
    post("/emulator/step", {"frames": 1})

apu = get("/apu/state")
# Pretty print the JSON
print(json.dumps(apu, indent=2)[:5000])
