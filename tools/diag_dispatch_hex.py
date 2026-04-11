#!/usr/bin/env python3
"""Fetch additional hex dumps for dispatch analysis."""
import json
import urllib.request

def fetch(addr, length):
    url = f'http://localhost:8080/api/v1/cpu/memory?addr={addr}&len={length}'
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())['data']

def hexdump(data, base):
    for i in range(0, len(data), 16):
        h = ' '.join('%02X' % data[i+j] for j in range(min(16, len(data)-i)))
        print('  $%06X: %s' % (base+i, h))

areas = [
    ('$78B4 (called from main loop)', 0x78B4, 64),
    ('$8DFC full (chain handler)', 0x8DFC, 128),
    ('$7B12 (bit5 handler in main loop)', 0x7B12, 96),
    ('$7B66 (bit0 handler)', 0x7B66, 32),
    ('$7B7E (bit4 handler)', 0x7B7E, 64),
    ('$7C3C (bit2 handler)', 0x7C3C, 128),
    ('$601A (jumped from $7B0E)', 0x601A, 64),
    ('$8540 (step5 handler)', 0x8540, 80),
    ('$8864 (step1 handler)', 0x8864, 64),
    ('$8A0C (step3 handler)', 0x8A0C, 64),
    ('$7DCC (bit0 of $0064 handler)', 0x7DCC, 32),
    ('$7DE0 (from $7B24)', 0x7DE0, 64),
]

for name, addr, length in areas:
    data = fetch(addr, length)
    print('\n=== %s ===' % name)
    hexdump(data, addr)
