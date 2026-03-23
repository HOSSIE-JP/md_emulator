"""Check HInt handler behavior: flag at $FF013A and code at branch target."""
import urllib.request, json

BASE = "http://localhost:8116/api/v1"

def api_post(p, d):
    r = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r).read().decode())

def api_get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read().decode())

api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})

# Check flag at different frame counts
for fc in [10, 100, 300, 600, 900, 1050, 1200, 1350, 1500]:
    if fc == 10:
        api_post("/emulator/step", {"frames": fc})
    else:
        # Already at previous checkpoint, just step the difference
        pass
    flag = api_get("/cpu/memory?addr=16711994&len=1")["data"][0]  # $FF013A
    regs = api_get("/vdp/registers")["registers"]
    hint_en = (regs[0] >> 4) & 1
    frame = api_get("/vdp/registers").get("frame", "?")
    print(f"Frame ~{frame}: $FF013A={flag} HInt_en={hint_en}")

# Reset and step progressively
api_post("/emulator/reset", {})
api_post("/emulator/load-rom-path", {"path": "D:/homebrew/puyo.bin"})
print("\n--- Progressive check ---")
prev = 0
for target in [10, 100, 300, 600, 900, 1050, 1200]:
    api_post("/emulator/step", {"frames": target - prev})
    prev = target
    flag = api_get("/cpu/memory?addr=16711994&len=1")["data"][0]
    regs = api_get("/vdp/registers")["registers"]
    hint_en = (regs[0] >> 4) & 1
    frame = api_get("/vdp/registers").get("frame", "?")
    print(f"Frame {frame:>5}: $FF013A={flag} HInt_en={hint_en}")

# Read the "else" branch at 0x706
# The BEQ at 0x6B6: 6700 004E -> branches to 0x6B6+4+0x4E = 0x6B6+0x52 = 0x708
# Wait: 6700 004E -> BEQ.W $+0x004E
# PC at time of branch = 0x6B6+2 = 0x6B8 (+2 for the extension word)  
# Actually: at 0x6B6 the opcode is 0x6700 (BEQ.W), followed by displacement 0x004E
# Branch target = PC + 2 + disp = 0x6B6 + 2 + 0x004E = 0x706
# Wait, for BEQ.W the PC is at the next word after the opcode: 0x6B6 + 2 = 0x6B8
# displacement from 0x6B8 + 0x004E = 0x706  

# Read code at 0x706
code_706 = api_get(f"/cpu/memory?addr={0x706}&len=64")["data"]
print(f"\nCode at 0x0706:")
print(f"Bytes: {' '.join(f'{b:02X}' for b in code_706[:64])}")

# The full handler disassembly based on bytes:
print("\n--- Manual disassembly of HInt handler ---")
handler = api_get(f"/cpu/memory?addr={0x6AC}&len=128")["data"]
# 0x6AC: 00 7C 07 00 -> ORI #$0700, SR
print("0x06AC: ORI.W   #$0700,SR           ; mask all interrupts")
# 0x6B0: 4A 39 00 FF 01 3A -> TST.B $FF013A
print("0x06B0: TST.B   ($FF013A).L          ; test wave enable flag")
# 0x6B6: 67 00 00 4E -> BEQ.W *+$50 (to 0x706)
print("0x06B6: BEQ.W   $0706                ; skip if wave not enabled")
# 0x6BA: 48 E7 00 80 -> MOVEM.L A0, -(SP)
print("0x06BA: MOVEM.L A0,-(SP)")
# 0x6BE: 23 FC 40 00 00 10 00 C0 00 04 -> MOVE.L #$40000010, $C00004
print("0x06BE: MOVE.L  #$40000010,($C00004).L ; set VDP VRAM write addr=0x0000")
# 0x6C8: 20 79 00 FF 01 3C -> MOVEA.L ($FF013C).L, A0
print("0x06C8: MOVEA.L ($FF013C).L,A0       ; load data pointer")
# 0x6CE: 33 D0 00 C0 00 00 -> MOVE.W (A0), $C00000
print("0x06CE: MOVE.W  (A0),($C00000).L     ; write to VDP data port")
# 0x6D4: 54 79 00 FF 01 3E -> ADDQ.W #2, ($FF013E).L
print("0x06D4: ADDQ.W  #2,($FF013E).L       ; advance pointer offset")
# 0x6DA: 53 79 00 FF 01 40 -> SUBQ.W #1, ($FF0140).L
print("0x06DA: SUBQ.W  #1,($FF0140).L       ; decrement counter")
# 0x6E0: 66 00 00 20 -> BNE.W *+$22 (to 0x702)
# Actually: from 0x6E0 + 2 + 0x20 = 0x702
print("0x06E0: BNE.W   $0702                ; if counter>0, branch")
# The "counter==0" path:
# 0x6E4: 48 E7 80 00 -> MOVEM.L D0, -(SP)
print("0x06E4: MOVEM.L D0,-(SP)")
# 0x6E8: 61 00 00 22 -> BSR.W *+$24 (to 0x070C)
print("0x06E8: BSR.W   $070C                ; call subroutine")
# 0x6EC: 4C DF 00 01 -> MOVEM.L (SP)+, D0
print("0x06EC: MOVEM.L (SP)+,D0")
# 0x6F0: 23 FC 40 00 00 10 00 C0 00 04 -> MOVE.L #$40000010, $C00004
print("0x06F0: MOVE.L  #$40000010,($C00004).L ; re-set VDP address")
# 0x6FA: 33 FC 00 00 00 C0 00 00 -> MOVE.W #$0000, $C00000
print("0x06FA: MOVE.W  #$0000,($C00000).L   ; write 0 to VDP")
# 0x702: 4C DF 01 00 -> MOVEM.L (SP)+, A0
print("0x0702: MOVEM.L (SP)+,A0             ; restore A0")
# 0x706: 02 7C F8 FF -> ANDI #$F8FF, SR
print("0x0706: ANDI.W  #$F8FF,SR            ; unmask interrupts")
# 0x70A: 4E 77 -> RTR
print("0x070A: RTR                           ; return from handler")
