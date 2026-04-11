#!/usr/bin/env python3
"""Deep analysis of step5 handler and related functions."""
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
    ('$8540 step5 handler (full)', 0x8540, 288),
    ('$8864 step1 handler (full)', 0x8864, 256),
    ('$8A0C step3 handler (full)', 0x8A0C, 256),
    ('$86BC step2 handler', 0x86BC, 256),
    ('$8292 step4 handler', 0x8292, 256),
    ('$66BE (load/decompress?)', 0x66BE, 64),
    ('$78B4 vblank_wait?', 0x78B4, 128),
    ('$8C82 dispatch step5-special', 0x8C82, 32),
    ('$8C8A dispatch step4-special', 0x8C8A, 16),
    ('$8C92 dispatch error', 0x8C92, 16),
]

for name, addr, length in areas:
    data = fetch(addr, length)
    print('\n=== %s ===' % name)
    hexdump(data, addr)
