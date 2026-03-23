"""Quick CPU state check on port 8113"""
import requests

BASE = "http://127.0.0.1:8113/api/v1"

def api(method, path, **kw):
    r = getattr(requests, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

# Check CPU state
cpu = api("get", "/cpu/state")
print("CPU state:", cpu)

# Check VDP regs
vdp = api("get", "/vdp/registers")
print("VDP regs:", vdp)
