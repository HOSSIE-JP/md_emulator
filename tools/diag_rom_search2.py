"""Search ROM for Z80 bus request and Z80 RAM write patterns"""
import os

ROM_PATH = "/Users/hossie/development/md_emulator/frontend/roms/北へPM 鮎.bin"

with open(ROM_PATH, "rb") as f:
    rom = f.read()

print(f"ROM size: {len(rom)} bytes ({len(rom)/1024:.0f} KB)")
print(f"ROM header rom_end: ${(rom[0x1A4]<<24|rom[0x1A5]<<16|rom[0x1A6]<<8|rom[0x1A7]):08X}")

# Search for Z80 bus request: MOVE.W #$0100, ($A11100).l
# = 33FC 0100 00A1 1100
pattern_busreq = bytes([0x33, 0xFC, 0x01, 0x00, 0x00, 0xA1, 0x11, 0x00])
busreq_addrs = []
for i in range(len(rom) - len(pattern_busreq)):
    if rom[i:i+len(pattern_busreq)] == pattern_busreq:
        busreq_addrs.append(i)
        if len(busreq_addrs) <= 30:
            print(f"  Z80 BUSREQ at ROM ${i:06X}")
print(f"Total Z80 BUSREQ patterns: {len(busreq_addrs)}")

# Search for Z80 bus release: MOVE.W #$0000, ($A11100).l
# = 33FC 0000 00A1 1100  
pattern_busrel = bytes([0x33, 0xFC, 0x00, 0x00, 0x00, 0xA1, 0x11, 0x00])
busrel_addrs = []
for i in range(len(rom) - len(pattern_busrel)):
    if rom[i:i+len(pattern_busrel)] == pattern_busrel:
        busrel_addrs.append(i)
        if len(busrel_addrs) <= 10:
            print(f"  Z80 BUSREL at ROM ${i:06X}")
print(f"Total Z80 BUSREL patterns: {len(busrel_addrs)}")

print()

# Check what's at the VBlank vector (address 0x78 in ROM)
vblank_vec = (rom[0x78] << 24) | (rom[0x79] << 16) | (rom[0x7A] << 8) | rom[0x7B]
print(f"VBlank vector (ROM $78): 0x{vblank_vec:06X}")

# Read the VBlank handler code
print(f"VBlank handler at 0x{vblank_vec:06X}:")
start = vblank_vec
for i in range(0, 128, 16):
    data = rom[start+i:start+i+16]
    hex_str = ' '.join(f'{b:02X}' for b in data)
    print(f"  ${start+i:06X}: {hex_str}")

# Read M68K code around PC=0x798E (where M68K was stuck polling)
print(f"\nCode around VBlank poll (PC=0x798E, ±128 bytes):")
for i in range(0x7900, 0x7A40, 16):
    data = rom[i:i+16]
    hex_str = ' '.join(f'{b:02X}' for b in data)
    print(f"  ${i:06X}: {hex_str}")

# HBlank vector
hblank_vec = (rom[0x70] << 24) | (rom[0x71] << 16) | (rom[0x72] << 8) | rom[0x73]
print(f"\nHBlank vector (ROM $70): 0x{hblank_vec:06X}")

# Entry point
entry = (rom[0x4] << 24) | (rom[0x5] << 16) | (rom[0x6] << 8) | rom[0x7]
print(f"Entry point (ROM $4): 0x{entry:06X}")

# Show all exception vectors
print("\nException vectors:")
for off, name in [(0x08, "Bus Error"), (0x0C, "Address Error"), 
                   (0x10, "Illegal Insn"), (0x14, "Div Zero"),
                   (0x18, "CHK"), (0x1C, "TRAPV"),
                   (0x20, "Privilege"), (0x24, "Trace"),
                   (0x60, "IRQ1"), (0x64, "IRQ2/Ext"),
                   (0x68, "IRQ3"), (0x6C, "IRQ4/HInt"),
                   (0x70, "IRQ5"), (0x74, "IRQ6/VInt"),
                   (0x78, "IRQ7/NMI")]:
    vec = (rom[off] << 24) | (rom[off+1] << 16) | (rom[off+2] << 8) | rom[off+3]
    print(f"  ${off:02X} {name:20s}: ${vec:06X}")

# Show code at busreq locations (show what's around each Z80 bus request)
print(f"\n== Z80 Bus Request code context ==")
for addr in busreq_addrs[:15]:
    # Show 32 bytes before and 64 bytes after
    start = max(0, addr - 16)
    end = min(len(rom), addr + 48)
    print(f"\n--- BUSREQ at ${addr:06X} ---")
    for i in range(start, end, 16):
        data = rom[i:min(i+16, end)]
        hex_str = ' '.join(f'{b:02X}' for b in data)
        marker = " <<< BUSREQ" if i <= addr < i + 16 else ""
        print(f"  ${i:06X}: {hex_str}{marker}")
