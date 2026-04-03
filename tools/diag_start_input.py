#!/usr/bin/env python3
"""
Test with START button press to see if game needs input to progress.
Also check VINT state after START is pressed.
"""
import requests, time

API = "http://localhost:8080/api/v1"
FRAME_CYCLES = 128056
BTN_START = 0x80

# Load ROM and reset
r = requests.post(f"{API}/emulator/load-rom-path", json={"path": "frontend/roms/北へPM 鮎.bin"})
print(f"Load: {r.status_code}")
requests.post(f"{API}/emulator/reset")

def get_state():
    cpu = requests.get(f"{API}/cpu/state").json()["cpu"]
    vdp = requests.get(f"{API}/vdp/registers").json()
    return cpu, vdp

def check_audio():
    """Check YM2612 and audio state."""
    # Read some Z80 RAM to check XGM2 status
    r = requests.get(f"{API}/cpu/memory", params={"addr": 0xA00100, "len": 16})
    z80_comm = r.json().get("data", [])
    return z80_comm

# Run 200 frames (startup + title screen)
print("Running 200 frames to reach title screen...")
for i in range(200):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

cpu, vdp = get_state()
regs = vdp["registers"]
print(f"Frame 200: PC=0x{cpu['m68k']['pc']:06X} VDP_reg1=0x{regs[1]:02X} "
      f"VINT={'ON' if regs[1] & 0x20 else 'OFF'}")
z80 = check_audio()
print(f"  Z80 comm: {' '.join(f'{b:02X}' for b in z80)}")

# Press START for 5 frames
print("\nPressing START...")
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
for i in range(5):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

# Release START
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Run 100 more frames
for i in range(100):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

cpu, vdp = get_state()
regs = vdp["registers"]
print(f"Frame 305: PC=0x{cpu['m68k']['pc']:06X} VDP_reg1=0x{regs[1]:02X} "
      f"VINT={'ON' if regs[1] & 0x20 else 'OFF'}")
z80 = check_audio()
print(f"  Z80 comm: {' '.join(f'{b:02X}' for b in z80)}")

# Press START again  
print("\nPressing START again...")
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": BTN_START})
for i in range(5):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})
requests.post(f"{API}/input/controller", json={"player": 1, "buttons": 0})

# Run 500 more frames
print("Running 500 more frames...")
for i in range(500):
    requests.post(f"{API}/emulator/step", json={"cycles": FRAME_CYCLES})

cpu, vdp = get_state()
regs = vdp["registers"]
print(f"Frame 810: PC=0x{cpu['m68k']['pc']:06X} VDP_reg1=0x{regs[1]:02X} "
      f"VINT={'ON' if regs[1] & 0x20 else 'OFF'}")
z80 = check_audio()
print(f"  Z80 comm: {' '.join(f'{b:02X}' for b in z80)}")

# Check DAC state
print(f"  Z80 PC: {cpu['z80']['pc']:04X}")
print(f"  Z80 alt regs: H'={cpu['z80']['h_']}, L'={cpu['z80']['l_']}, D'={cpu['z80']['d_']}, E'={cpu['z80']['e_']}")

# Check YM write queue status via VDP debug
vint_count = vdp.get("vint_delivered", 0)
print(f"  VINT delivered: {vint_count}")
print(f"  VDP frame: {vdp.get('frame', 0)}")
