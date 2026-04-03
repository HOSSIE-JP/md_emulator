"""Check APU channel state for 北へPM"""
import requests
BASE = "http://localhost:8080/api/v1"
apu = requests.get(f"{BASE}/apu/state").json()

channels = apu.get("channels", [])
for i, ch in enumerate(channels):
    ops = ch.get("operators", [])
    print(f"CH{i+1}: algo={ch.get('algorithm')} fb={ch.get('feedback')} "
          f"fnum={ch.get('fnum')} block={ch.get('block')} "
          f"L={ch.get('pan_left')} R={ch.get('pan_right')}")
    for j, op in enumerate(ops):
        print(f"  OP{j+1}: atten={op.get('attenuation')} env={op.get('env_phase')} "
              f"key={op.get('key_on')} phase={op.get('phase_counter')}")

print()
print(f"DAC enabled: {apu.get('dac_enabled')}")
print(f"DAC data: {apu.get('dac_data')}")
print(f"Bank: {apu.get('z80_bank_68k_addr')}")
print(f"reg27: {apu.get('reg27')}")
print(f"regs_port0_2b: {apu.get('regs_port0_2b')}")
print(f"Status: {apu.get('status')}")

hist0 = apu.get("ym_histogram_port0_nonzero", [])
print(f"Port0 hist ({len(hist0)}): {hist0[:30]}")
hist1 = apu.get("ym_histogram_port1_nonzero", [])
print(f"Port1 hist ({len(hist1)}): {hist1[:30]}")

print(f"Port0 TL: {apu.get('regs_port0_tl')}")
print(f"Port1 TL: {apu.get('regs_port1_tl')}")
print(f"Port0 freq: {apu.get('regs_port0_freq')}")
print(f"Port1 freq: {apu.get('regs_port1_freq')}")
print(f"Port0 algo: {apu.get('regs_port0_algo')}")
print(f"Port1 algo: {apu.get('regs_port1_algo')}")
print(f"Port0 key: {apu.get('regs_port0_key')}")
print(f"Port0 B4-B6: {apu.get('regs_port0_b4_b6')}")
print(f"Port1 B4-B6: {apu.get('regs_port1_b4_b6')}")

first = apu.get("ym_write_log_first100", [])
print(f"\nFirst writes ({len(first)}):")
for w in first[:30]:
    print(f"  {w}")

recent = apu.get("ym_write_log_recent_non_dac", [])
print(f"\nRecent non-DAC ({len(recent)}):")
for w in recent[:30]:
    print(f"  {w}")
