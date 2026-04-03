#!/usr/bin/env python3
"""Check YM2612 timer state and why Timer A never overflows."""
import requests, json

BASE = 'http://localhost:8080/api/v1'
requests.post(BASE + '/emulator/load-rom-path', json={'path': 'frontend/roms/北へPM 鮎.bin'})
requests.post(BASE + '/emulator/step', json={'frames': 200})

apu = requests.get(BASE + '/apu/state').json()

# Check relevant timer fields
print('=== YM2612 Timer State ===')
print('status: 0x%02X' % apu.get('status', 0))
print('reg27: 0x%02X' % apu.get('reg27', 0))

# Decode reg27
r27 = apu.get('reg27', 0)
timer_a_enable = bool(r27 & 0x01)
timer_b_enable = bool(r27 & 0x02)
timer_a_load = bool(r27 & 0x04)
timer_b_load = bool(r27 & 0x08)
timer_a_flag = bool(r27 & 0x01)  # this is enable, not flag
timer_a_irq = bool(r27 & 0x04)

print('  Timer A enable: %s' % timer_a_enable)
print('  Timer B enable: %s' % timer_b_enable)
print('  Timer A load: %s' % timer_a_load)
print('  Timer B load: %s' % timer_b_load)
print('  CSM mode: %s' % bool(r27 & 0x80))

# Check Timer A period from regs
regs_p0 = apu.get('regs_port0_freq', [])
print('\nPort0 freq regs: %s' % regs_p0)

# Check ym_write_histogram for timer register writes
hist0 = apu.get('ym_histogram_port0_nonzero', [])
print('\nYM2612 Port0 write histogram (relevant):')
for item in hist0:
    reg_str, count = item.split(':')
    reg = int(reg_str.replace('$', ''), 16)
    if reg in [0x24, 0x25, 0x26, 0x27]:
        name = {0x24: 'TimerA_MSB', 0x25: 'TimerA_LSB', 0x26: 'TimerB', 0x27: 'TimerCtrl'}[reg]
        print('  %s ($%02X): %s writes' % (name, reg, count))

# Check bus ym_status directly
print('\nYM status from bus: 0x%02X' % apu.get('status', 0))
print('Bus z80_bus_requested: %s' % apu.get('z80_bus_requested', '?'))

# Check non-DAC writes to see if timers were configured
non_dac = apu.get('ym_write_log_recent_non_dac', [])
print('\nRecent non-DAC YM writes (last 20):')
for entry in non_dac[:20]:
    print('  %s' % entry)

# Check if M68K wrote to timer registers
print('\n=== Timer register writes ===')
for item in hist0:
    parts = item.split(':')
    if len(parts) == 2:
        reg_str, count = parts
        reg = int(reg_str.replace('$', ''), 16)
        if reg >= 0x24 and reg <= 0x27:
            print('  $%02X written %s times' % (reg, count))

# Also check total YM write count
print('\nTotal YM writes: %s' % apu.get('ym_write_log_len', '?'))
print('ym_write_total: %s' % apu.get('ym_write_total', '?'))
