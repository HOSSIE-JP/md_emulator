use std::cell::RefCell;

use serde::{Deserialize, Serialize};

/// Flash ROM chip read mode
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
enum FlashMode {
    #[default]
    Normal,
    CfiQuery, // After CFI query command (0x98 to 0xAB): reads return CFI table data
}

/// Flash ROM chip command state machine
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
enum FlashState {
    #[default]
    Idle,
    Unlock1,        // Got 0xAA to 0xAAB; waiting for 0x55 to 0x555
    Unlock2,        // Got both unlock bytes; waiting for command byte
    Program,        // Got program command; next even-byte write to flash area
    ProgramHigh,    // Got high byte of word; waiting for low byte
    EraseUnlock,    // Got 0x80 after main unlock; need second full unlock
    EraseUnlock2,   // Got 0xAA of second unlock
    EraseUnlock3,   // Got full second unlock; waiting for sector erase confirm (0x30)
}

pub const ROM_START: u32 = 0x000000;
pub const ROM_END: u32 = 0x3F_FFFF;
pub const Z80_SPACE_START: u32 = 0xA0_0000;
pub const Z80_SPACE_END: u32 = 0xA0_FFFF;
pub const YM2612_START: u32 = 0xA0_4000;
pub const YM2612_END: u32 = 0xA0_4003;
pub const IO_START: u32 = 0xA1_0000;
pub const IO_END: u32 = 0xA1_FFFF;
pub const PAD1_DATA_PORT: u32 = 0xA1_0003;
pub const PAD2_DATA_PORT: u32 = 0xA1_0005;
pub const PAD1_CTRL_PORT: u32 = 0xA1_0009;
pub const PAD2_CTRL_PORT: u32 = 0xA1_000B;
pub const Z80_BUS_REQ: u32 = 0xA1_1100;
pub const Z80_RESET: u32 = 0xA1_1200;
pub const SRAM_CTRL_REG: u32 = 0xA1_30F1;
const SSF2_BANK_REGS: [u32; 7] = [
    0xA1_30F3,
    0xA1_30F5,
    0xA1_30F7,
    0xA1_30F9,
    0xA1_30FB,
    0xA1_30FD,
    0xA1_30FF,
];
const SSF2_WINDOW_START: u32 = 0x08_0000;
const SSF2_WINDOW_SIZE: u32 = 0x08_0000;
const SSF2_WINDOW_END: u32 = 0x3F_FFFF;
pub const VDP_START: u32 = 0xC0_0000;
pub const VDP_END: u32 = 0xC0_001F;
pub const WORK_RAM_START: u32 = 0xE0_0000;
pub const WORK_RAM_END: u32 = 0xE0_FFFF;
pub const WORK_RAM_MIRROR_START: u32 = 0xFF_0000;
pub const WORK_RAM_MIRROR_END: u32 = 0xFF_FFFF;

pub const BTN_UP: u16 = 1 << 0;
pub const BTN_DOWN: u16 = 1 << 1;
pub const BTN_LEFT: u16 = 1 << 2;
pub const BTN_RIGHT: u16 = 1 << 3;
pub const BTN_B: u16 = 1 << 4;
pub const BTN_C: u16 = 1 << 5;
pub const BTN_A: u16 = 1 << 6;
pub const BTN_START: u16 = 1 << 7;

pub trait BusDevice {
    fn read8(&self, addr: u32) -> u8;
    fn write8(&mut self, addr: u32, value: u8);
}

pub trait CpuBus {
    fn read8(&mut self, addr: u32) -> (u8, u32);
    fn write8(&mut self, addr: u32, value: u8) -> u32;
}

pub trait Clockable {
    fn tick(&mut self, cycles: u32);
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
pub struct ControllerState {
    pub buttons: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemBus {
    rom: Vec<u8>,
    work_ram: Vec<u8>,
    z80_ram: Vec<u8>,
    io_ports: Vec<u8>,
    controller_1: ControllerState,
    controller_2: ControllerState,
    pub z80_bus_requested: bool,
    pub z80_reset: bool,
    /// Buffered YM2612 writes: (port, address, data)
    pub ym_write_queue: Vec<(u8, u8, u8)>,
    /// Buffered PSG writes
    pub psg_write_queue: Vec<u8>,
    /// YM2612 address latch per port
    ym_addr_latch: [u8; 2],
    /// YM2612 status register (updated from APU)
    pub ym_status: u8,
    /// Cartridge SRAM (battery-backed)
    sram: Vec<u8>,
    /// SRAM mapped address range start
    sram_start: u32,
    /// SRAM mapped address range end (inclusive)
    sram_end: u32,
    /// SRAM type flags from ROM header (bit 5 = odd-only, bit 6 = even-only)
    sram_flags: u8,
    /// Whether SRAM is enabled / mapped (controlled by $A130F1 bit 0)
    sram_enabled: bool,
    /// Whether SRAM is write-protected (controlled by $A130F1 bit 1)
    sram_write_protect: bool,
    /// Flash ROM chip read mode (Normal or CfiQuery)
    #[serde(skip)]
    flash_mode: FlashMode,
    /// Flash ROM chip command state machine
    #[serde(skip)]
    flash_state: FlashState,
    /// Flash overlay: full-byte writable storage for the save area (size = sram_end - sram_start + 1)
    /// Initialized to 0xFF (erased) when RA marker is detected in ROM header.
    flash_overlay: Vec<u8>,
    /// Base address of flash_overlay in M68K address space (= sram_start when active)
    flash_overlay_base: u32,
    /// Sparse cache for flash writes to ROM addresses outside flash_overlay.
    /// Enables data_poll to succeed after word_program to any ROM address.
    #[serde(default)]
    flash_rom_cache: std::collections::HashMap<u32, u8>,
    /// Z80 bank register: bits 15-23 of 68K address for banked window
    pub z80_bank_68k_addr: u32,
    /// Debug: count M68K writes to Z80 space
    #[serde(skip)]
    pub z80_m68k_write_count: u32,
    /// Debug: recent Z80 banked 68K reads
    #[serde(skip)]
    pub z80_banked_read_log: RefCell<Vec<(u32, u8)>>,
    /// Debug: count Z80 bank register writes
    #[serde(skip)]
    pub z80_bank_write_count: u32,
    /// Debug: max bank value seen
    #[serde(skip)]
    pub z80_bank_max_value: u32,
    /// Debug: ring buffer of last 20 bank register write values (value, resulting_bank)
    #[serde(skip)]
    pub z80_bank_write_log: Vec<(u8, u32)>,
    /// Enable SSF2-style mapper when ROM is larger than 4MB.
    ssf2_mapper_enabled: bool,
    /// SSF2 bank registers for 0x080000-0x3FFFFF (7 windows).
    ssf2_bank_regs: [u8; 7],
}

impl Default for SystemBus {
    fn default() -> Self {
        let mut io_ports = vec![0; 0x100];
        io_ports[(PAD1_DATA_PORT - IO_START) as usize] = 0x40;
        io_ports[(PAD2_DATA_PORT - IO_START) as usize] = 0x40;
        io_ports[(PAD1_CTRL_PORT - IO_START) as usize] = 0x00;
        io_ports[(PAD2_CTRL_PORT - IO_START) as usize] = 0x00;

        Self {
            rom: Vec::new(),
            work_ram: vec![0; 0x10000],
            z80_ram: vec![0; 0x2000],
            io_ports,
            controller_1: ControllerState::default(),
            controller_2: ControllerState::default(),
            z80_bus_requested: false,
            z80_reset: true,
            ym_write_queue: Vec::new(),
            psg_write_queue: Vec::new(),
            ym_addr_latch: [0; 2],
            ym_status: 0,
            sram: Vec::new(),
            sram_start: 0,
            sram_end: 0,
            sram_flags: 0,
            sram_enabled: false,
            sram_write_protect: false,
            flash_mode: FlashMode::Normal,
            flash_state: FlashState::Idle,
            flash_overlay: Vec::new(),
            flash_overlay_base: 0,
            flash_rom_cache: std::collections::HashMap::new(),
            z80_bank_68k_addr: 0,
            z80_m68k_write_count: 0,
            z80_banked_read_log: RefCell::new(Vec::new()),
            z80_bank_write_count: 0,
            z80_bank_max_value: 0,
            z80_bank_write_log: Vec::new(),
            ssf2_mapper_enabled: false,
            ssf2_bank_regs: [1, 2, 3, 4, 5, 6, 7],
        }
    }
}

impl SystemBus {
    pub fn load_rom(&mut self, rom: Vec<u8>) {
        // Parse SRAM info from ROM header ($1B0-$1BB)
        if rom.len() > 0x1BC {
            let marker = [rom[0x1B0], rom[0x1B1]];
            if marker == [0x52, 0x41] {
                // "RA" marker → SRAM/Flash present
                // Header layout: [0x1B0-0x1B1]=RA, [0x1B2]=type/flags, [0x1B3]=reserved(0x20),
                // [0x1B4-0x1B7]=start, [0x1B8-0x1BB]=end
                let flags = rom[0x1B2];
                let start = u32::from_be_bytes([rom[0x1B4], rom[0x1B5], rom[0x1B6], rom[0x1B7]]);
                let end = u32::from_be_bytes([rom[0x1B8], rom[0x1B9], rom[0x1BA], rom[0x1BB]]);
                if end >= start {
                    let sram_size = (end - start + 1) as usize;
                    // For odd-only or even-only SRAM, effective size is half
                    let effective_size = if (flags & 0x60) != 0 {
                        sram_size / 2
                    } else {
                        sram_size
                    };
                    self.sram = vec![0xFF; effective_size]; // uninitialized SRAM reads 0xFF
                    self.sram_start = start;
                    self.sram_end = end;
                    self.sram_flags = flags;
                    self.sram_enabled = true;
                    // Flash overlay: full-byte access to the save area (bypasses odd/even restriction)
                    // Used by Flash ROM chip state machine for program/erase operations
                    self.flash_overlay = vec![0xFF; sram_size];
                    self.flash_overlay_base = start;
                }
            }
        }
        self.ssf2_mapper_enabled = rom.len() > (SSF2_WINDOW_END as usize + 1);
        self.ssf2_bank_regs = [1, 2, 3, 4, 5, 6, 7];
        self.rom = rom;
    }

    /// Reset all mutable state (keeping ROM and SRAM). Matches power-on behavior.
    pub fn reset(&mut self) {
        self.work_ram.fill(0);
        self.z80_ram.fill(0);
        self.z80_bus_requested = false;
        self.z80_reset = true;
        self.ym_write_queue.clear();
        self.psg_write_queue.clear();
        self.ym_addr_latch = [0; 2];
        self.ym_status = 0;
        // SRAM is battery-backed; keep contents but re-enable mapping
        if !self.sram.is_empty() {
            self.sram_enabled = true;
            self.sram_write_protect = false;
        }
        // Reset flash state machine (keep flash_overlay data)
        self.flash_mode = FlashMode::Normal;
        self.flash_state = FlashState::Idle;
        self.flash_rom_cache.clear();
        self.z80_bank_68k_addr = 0;
        self.z80_m68k_write_count = 0;
        self.z80_banked_read_log.borrow_mut().clear();
        self.z80_bank_write_count = 0;
        self.z80_bank_max_value = 0;
        self.z80_bank_write_log.clear();
        self.ssf2_bank_regs = [1, 2, 3, 4, 5, 6, 7];
        // Re-initialize IO ports with default values
        self.io_ports.fill(0);
        self.io_ports[(PAD1_DATA_PORT - IO_START) as usize] = 0x40;
        self.io_ports[(PAD2_DATA_PORT - IO_START) as usize] = 0x40;
        self.io_ports[(PAD1_CTRL_PORT - IO_START) as usize] = 0x00;
        self.io_ports[(PAD2_CTRL_PORT - IO_START) as usize] = 0x00;
    }

    pub fn set_controller(&mut self, player: u8, buttons: u16) {
        let state = ControllerState { buttons };
        match player {
            1 => self.controller_1 = state,
            2 => self.controller_2 = state,
            _ => {}
        }
    }

    pub fn has_rom(&self) -> bool {
        !self.rom.is_empty()
    }

    pub fn rom_len(&self) -> usize {
        self.rom.len()
    }

    pub fn get_memory(&self, address: u32, length: usize) -> Vec<u8> {
        (0..length)
            .map(|offset| self.read8(address.wrapping_add(offset as u32)))
            .collect()
    }

    fn ssf2_page_count(&self) -> u8 {
        ((self.rom.len() as u32 + SSF2_WINDOW_SIZE - 1) / SSF2_WINDOW_SIZE)
            .max(1)
            .min(64) as u8
    }

    fn normalize_ssf2_bank_value(&self, value: u8) -> u8 {
        let page_count = self.ssf2_page_count();
        if page_count == 0 {
            0
        } else {
            (value & 0x3F) % page_count
        }
    }

    fn mapped_rom_addr(&self, addr: u32) -> u32 {
        if !self.ssf2_mapper_enabled {
            return addr;
        }
        if !(SSF2_WINDOW_START..=SSF2_WINDOW_END).contains(&addr) {
            return addr;
        }
        let window = ((addr - SSF2_WINDOW_START) / SSF2_WINDOW_SIZE) as usize;
        if window >= self.ssf2_bank_regs.len() {
            return addr;
        }
        let page = self.ssf2_bank_regs[window] as u32;
        let offset = (addr - SSF2_WINDOW_START) & (SSF2_WINDOW_SIZE - 1);
        (page * SSF2_WINDOW_SIZE) | offset
    }

    fn ssf2_bank_reg_index(addr: u32) -> Option<usize> {
        SSF2_BANK_REGS.iter().position(|&reg| reg == addr)
    }

    fn read_pad_data(&self, player: u8) -> u8 {
        let (state, port_addr) = match player {
            1 => (&self.controller_1, PAD1_DATA_PORT),
            2 => (&self.controller_2, PAD2_DATA_PORT),
            _ => (&self.controller_1, PAD1_DATA_PORT),
        };

        let idx = (port_addr - IO_START) as usize;
        let port_value = self.io_ports[idx];
        let th_high = (port_value & 0x40) != 0;

        let mut data = port_value & 0xC0;
        if th_high {
            if (state.buttons & BTN_UP) == 0 {
                data |= 1 << 0;
            }
            if (state.buttons & BTN_DOWN) == 0 {
                data |= 1 << 1;
            }
            if (state.buttons & BTN_LEFT) == 0 {
                data |= 1 << 2;
            }
            if (state.buttons & BTN_RIGHT) == 0 {
                data |= 1 << 3;
            }
            if (state.buttons & BTN_B) == 0 {
                data |= 1 << 4;
            }
            if (state.buttons & BTN_C) == 0 {
                data |= 1 << 5;
            }
        } else {
            if (state.buttons & BTN_UP) == 0 {
                data |= 1 << 0;
            }
            if (state.buttons & BTN_DOWN) == 0 {
                data |= 1 << 1;
            }
            if (state.buttons & BTN_A) == 0 {
                data |= 1 << 4;
            }
            if (state.buttons & BTN_START) == 0 {
                data |= 1 << 5;
            }
        }
        data
    }

    /// Returns the raw SRAM bytes (effective size, already halved for odd/even-only).
    pub fn get_sram(&self) -> &[u8] {
        &self.sram
    }

    /// Overwrites SRAM contents from an external buffer (e.g., loaded from a save file).
    /// Silently clips to the allocated SRAM size.
    pub fn load_sram(&mut self, data: &[u8]) {
        let len = data.len().min(self.sram.len());
        self.sram[..len].copy_from_slice(&data[..len]);
    }

    /// Returns true if the ROM has battery-backed SRAM.
    pub fn has_sram(&self) -> bool {
        !self.sram.is_empty()
    }

    /// Returns (start_addr, end_addr, effective_size_bytes, flags).
    pub fn sram_info(&self) -> (u32, u32, usize, u8) {
        (self.sram_start, self.sram_end, self.sram.len(), self.sram_flags)
    }

    /// Calculate SRAM byte offset from M68K address, respecting odd/even-only flags.
    /// Returns None if the address doesn't match the SRAM byte type.
    fn sram_offset(&self, addr: u32) -> Option<usize> {
        let odd_only = (self.sram_flags & 0x20) != 0;
        let even_only = (self.sram_flags & 0x40) != 0;
        let is_odd = (addr & 1) != 0;
        if odd_only && !is_odd {
            return None; // even address on odd-only SRAM
        }
        if even_only && is_odd {
            return None; // odd address on even-only SRAM
        }
        let byte_addr = addr - self.sram_start;
        if odd_only || even_only {
            Some((byte_addr / 2) as usize)
        } else {
            Some(byte_addr as usize)
        }
    }

    /// Read from the flash overlay (full-byte save area).
    /// Returns Some(byte) if the address is within the overlay, None otherwise.
    /// Return the CFI response byte for the given M68K address in CFI Query mode.
    /// The SGDK flash library reads odd byte addresses 0x21, 0x23, 0x25 ... (step +2).
    /// Each odd byte at address `a` maps to CFI buffer index `(a - 0x21) / 2`.
    /// Even bytes return 0x00 in CFI mode.
    fn cfi_response_byte(addr: u32) -> u8 {
        if (addr & 1) == 0 {
            return 0x00; // even bytes return 0 in CFI mode
        }
        if addr < 0x21 {
            return 0x00;
        }
        let idx = ((addr - 0x21) / 2) as usize;
        if idx >= 64 {
            return 0x00;
        }
        // CFI response for AMD-compatible 4MB flash chip, 128 sectors of 32KB each.
        // This satisfies the SGDK flash_init() checks:
        //   cfi[0..=6] = {0x51, 0x52, 0x59, 0x02, 0x01, 0x40, 0x00}
        //     cfi[4]=0x01: old SGDK flash-save lib uses this as max_slots (standard AMD is 0x00)
        //   cfi[23] = 0x16 → chip size 2^22 = 4MB
        //   cfi[28] = 0x01 → 1 erase region
        //   cfi[29..32] = {0x7F, 0x00, 0x80, 0x00} → 128 sectors × 32KB
        //   cfi[63] = 0x02 → bottom-boot/regular sectors (metadata_populate_bot path)
        const CFI: [u8; 64] = [
            0x51, 0x52, 0x59, // [0..2]  "QRY"
            0x02, 0x00,       // [3..4]  AMD cmd-set (primary cmd set 0x0002: LSB=0x02, MSB=0x00)
            0x40, 0x00,       // [5..6]  extended query table at flash word 0x40
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // [7..14]
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // [15..22]
            0x16,             // [23]    device size: 2^22 = 4MB
            0x00, 0x00, 0x00, 0x00, // [24..27]
            0x01,             // [28]    number of erase regions = 1
            0x7F, 0x00,       // [29..30] num_sectors - 1 = 127  (128 sectors)
            0x80, 0x00,       // [31..32] sector_len = 0x80 × 256 = 32768 bytes
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // [33..39]
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // [40..47]
            // AMD primary extension table "PRI" at word address 0x40 (idx 48 = chip addr 0x81).
            // SGDK flash_init reads this table and checks for the "PRI" magic before
            // computing max_slots and writing it to the device_table.
            0x50, 0x52, 0x49, // [48..50] "PRI" signature
            0x31, 0x33,       // [51..52] version "1.3"
            0x00, 0x02, 0x04, // [53..55] addr_unlock / erase_suspend / sector_protect
            0x01, 0x04, 0x00, 0x00, 0x00, // [56..60] temp_unprotect / protect_scheme / simult / burst / page
            0x85, 0x95,       // [61..62] V_PP min=8.5V / max=9.5V
            0x02,             // [63]    boot sector type: regular (bottom-boot)
        ];
        CFI[idx]
    }

    /// Process a write to ROM address space as a flash chip command.
    /// Handles the AMD/CFI command state machine.
    fn handle_flash_command(&mut self, addr: u32, value: u8) {
        // Reset command: 0xF0 to any address exits all modes
        if value == 0xF0 {
            self.flash_mode = FlashMode::Normal;
            self.flash_state = FlashState::Idle;
            return;
        }
        // CFI Query command: 0x98 to byte address 0xAB (no unlock required)
        if addr == 0xAB && value == 0x98 {
            self.flash_mode = FlashMode::CfiQuery;
            return;
        }
        // In Program/ProgramHigh state, ROM-space writes that are NOT unlock commands
        // are flash data writes to ROM chip addresses (e.g., flash_copy copies data
        // to arbitrary ROM addresses). Store them in the ROM cache so data_poll succeeds.
        match &self.flash_state {
            FlashState::Program => {
                if addr != 0xAAB {
                    // Flash data write to this ROM address; cache it for data_poll
                    self.flash_rom_cache.insert(addr, value);
                    if (addr & 1) == 0 {
                        // Even byte (high): stay in Program for the following odd byte
                        self.flash_state = FlashState::ProgramHigh;
                    } else {
                        self.flash_state = FlashState::Idle;
                    }
                    return;
                }
            }
            FlashState::ProgramHigh => {
                // Low byte of a ROM-space word program
                self.flash_rom_cache.insert(addr, value);
                self.flash_state = FlashState::Idle;
                return;
            }
            _ => {}
        }
        // AMD flash chip commands are only conveyed on ODD byte addresses.
        // Even-address writes are the high bytes of M68K word writes (always 0x00 for SGDK
        // command sequences). Ignoring them prevents spurious state machine resets.
        if (addr & 1) == 0 {
            return;
        }
        // Main command state machine (ODD addresses only)
        match &self.flash_state {
            FlashState::Idle | FlashState::Program | FlashState::ProgramHigh => {
                // Only unlock start is accepted from Idle
                if addr == 0xAAB && value == 0xAA {
                    self.flash_state = FlashState::Unlock1;
                } else {
                    self.flash_state = FlashState::Idle;
                }
            }
            FlashState::Unlock1 => {
                if addr == 0x555 && value == 0x55 {
                    self.flash_state = FlashState::Unlock2;
                } else {
                    self.flash_state = FlashState::Idle;
                }
            }
            FlashState::Unlock2 => {
                match (addr, value) {
                    (0xAAB, 0xA0) => {
                        // Program command: next write to flash area programs data
                        self.flash_state = FlashState::Program;
                    }
                    (0xAAB, 0x80) => {
                        // Erase setup: need a second full unlock
                        self.flash_state = FlashState::EraseUnlock;
                    }
                    _ => {
                        self.flash_state = FlashState::Idle;
                    }
                }
            }
            FlashState::EraseUnlock => {
                if addr == 0xAAB && value == 0xAA {
                    self.flash_state = FlashState::EraseUnlock2;
                } else {
                    self.flash_state = FlashState::Idle;
                }
            }
            FlashState::EraseUnlock2 => {
                if addr == 0x555 && value == 0x55 {
                    self.flash_state = FlashState::EraseUnlock3;
                } else {
                    self.flash_state = FlashState::Idle;
                }
            }
            FlashState::EraseUnlock3 => {
                // Sector erase: addr is the odd byte of the sector start.
                // Clear any cached ROM bytes in the 32KB sector so reads return 0xFF.
                if (addr & 1) != 0 && value == 0x30 {
                    let sector_base = addr & !1;  // even byte = sector start
                    const SECTOR_SIZE: u32 = 0x8000; // 32KB
                    self.flash_rom_cache.retain(|&k, _| k < sector_base || k >= sector_base + SECTOR_SIZE);
                }
                self.flash_state = FlashState::Idle;
            }
        }
    }
} // end impl SystemBus

impl BusDevice for SystemBus {
    fn read8(&self, addr: u32) -> u8 {
        let addr = addr & 0x00FFFFFF;
        // Flash overlay range: handle CfiQuery mode and normal data reads.
        // This check runs before SRAM so the flash chip takes priority.
        if !self.flash_overlay.is_empty()
            && addr >= self.flash_overlay_base
            && addr < self.flash_overlay_base + self.flash_overlay.len() as u32
        {
            let rel_addr = addr - self.flash_overlay_base;
            if self.flash_mode == FlashMode::CfiQuery {
                // Return CFI table data using chip-relative address
                return Self::cfi_response_byte(rel_addr);
            }
            // Normal read: return programmed data (or 0xFF if erased)
            return self.flash_overlay.get(rel_addr as usize).copied().unwrap_or(0xFF);
        }
        // SRAM read: intercept before ROM
        if self.sram_enabled && addr >= self.sram_start && addr <= self.sram_end {
            if let Some(offset) = self.sram_offset(addr) {
                return self.sram.get(offset).copied().unwrap_or(0xFF);
            }
            // Address not matching odd/even filter → fall through to ROM
        }
        match addr {
            ROM_START..=ROM_END => {
                // In CFI Query mode, odd-byte reads return CFI table data
                if self.flash_mode == FlashMode::CfiQuery {
                    return Self::cfi_response_byte(addr);
                }
                let mapped = self.mapped_rom_addr(addr);
                // Check flash ROM cache (stores bytes programmed to ROM-space addresses
                // outside flash_overlay, e.g. during flash_copy operations).
                if let Some(&cached) = self.flash_rom_cache.get(&mapped) {
                    return cached;
                }
                self.rom.get(mapped as usize).copied().unwrap_or(0xFF)
            }
            Z80_SPACE_START..=Z80_SPACE_END => {
                if addr >= YM2612_START && addr <= YM2612_END {
                    return self.ym_status; // YM2612 status register
                }
                let index = (addr as usize - Z80_SPACE_START as usize) & 0x1FFF;
                self.z80_ram[index]
            }
            IO_START..=IO_END => {
                match addr {
                    Z80_BUS_REQ => {
                        // Bit 0: 0 = bus granted (Z80 halted), 1 = Z80 still running
                        if self.z80_bus_requested { 0x00 } else { 0x01 }
                    }
                    0xA1_1101 | Z80_RESET | 0xA1_1201 => 0x00,
                    PAD1_DATA_PORT => self.read_pad_data(1),
                    PAD2_DATA_PORT => self.read_pad_data(2),
                    // SRAM control register ($A130F1): read returns current state
                    // bit 0 (MD): 1 = RAM mapped, 0 = ROM
                    // bit 1 (WP): 1 = write-protected, 0 = writable
                    SRAM_CTRL_REG => {
                        let mut ctrl = 0u8;
                        if self.sram_enabled { ctrl |= 0x01; }
                        if self.sram_write_protect { ctrl |= 0x02; }
                        ctrl
                    }
                    reg if Self::ssf2_bank_reg_index(reg).is_some() => {
                        if self.ssf2_mapper_enabled {
                            let idx = Self::ssf2_bank_reg_index(reg).unwrap();
                            self.ssf2_bank_regs[idx]
                        } else {
                            0xFF
                        }
                    }
                    _ => {
                        let index = (addr as usize - IO_START as usize) & 0xFF;
                        self.io_ports[index]
                    }
                }
            }
            WORK_RAM_START..=WORK_RAM_END => {
                let index = (addr as usize - WORK_RAM_START as usize) & 0xFFFF;
                self.work_ram[index]
            }
            WORK_RAM_MIRROR_START..=WORK_RAM_MIRROR_END => {
                let index = (addr as usize - WORK_RAM_MIRROR_START as usize) & 0xFFFF;
                self.work_ram[index]
            }
            _ => 0xFF,
        }
    }

    fn write8(&mut self, addr: u32, value: u8) {
        let addr = addr & 0x00FFFFFF;

        // Flash data area writes: intercept BEFORE SRAM check when flash state machine is active.
        // Program mode: write byte to flash overlay (full-byte, no odd/even restriction)
        // EraseUnlock3: sector erase confirmation arrives at the flash area address+1
        if !self.flash_overlay.is_empty()
            && addr >= self.flash_overlay_base
            && addr < self.flash_overlay_base + self.flash_overlay.len() as u32
        {
            let offset = (addr - self.flash_overlay_base) as usize;
            match &self.flash_state {
                FlashState::Program => {
                    // Write high byte of word; wait for low byte
                    self.flash_overlay[offset] = value;
                    if (addr & 1) == 0 {
                        // Even byte (high): stay in program state for the following odd byte
                        self.flash_state = FlashState::ProgramHigh;
                    } else {
                        // Odd byte only (unusual) or standalone byte write: done
                        self.flash_state = FlashState::Idle;
                    }
                    return;
                }
                FlashState::ProgramHigh => {
                    // Write low byte of word; word program complete
                    self.flash_overlay[offset] = value;
                    self.flash_state = FlashState::Idle;
                    return;
                }
                FlashState::EraseUnlock3 => {
                    // Sector erase: 0x30 written to odd byte of sector start address.
                    // Even-byte writes (high byte of word) are ignored; only the odd byte
                    // (low byte = 0x30) triggers the erase so the state is not prematurely reset.
                    if (addr & 1) == 0 {
                        return; // ignore high byte; wait for odd byte with 0x30
                    }
                    if value == 0x30 {
                        // Sector start = even byte before this odd address
                        let sector_start_addr = addr - 1;
                        let sector_start = (sector_start_addr - self.flash_overlay_base) as usize;
                        const SECTOR_SIZE: usize = 0x8000; // 32KB per CFI table
                        let sector_end = (sector_start + SECTOR_SIZE).min(self.flash_overlay.len());
                        self.flash_overlay[sector_start..sector_end].fill(0xFF);
                    }
                    self.flash_state = FlashState::Idle;
                    return;
                }
                _ => {
                    // Flash command write in the flash address range.
                    // Use address relative to flash base for the state machine.
                    let rel_addr = addr - self.flash_overlay_base;
                    self.handle_flash_command(rel_addr, value);
                    return;
                }
            }
        }

        // SRAM write: intercept before other handlers
        if self.sram_enabled && addr >= self.sram_start && addr <= self.sram_end {
            if let Some(offset) = self.sram_offset(addr) {
                // Write-protect (bit 1 of $A130F1) blocks writes but not reads
                if !self.sram_write_protect && offset < self.sram.len() {
                    self.sram[offset] = value;
                }
                return;
            }
        }
        match addr {
            // ROM space: process as flash chip commands
            ROM_START..=ROM_END => {
                self.handle_flash_command(addr, value);
            }
            Z80_SPACE_START..=Z80_SPACE_END => {
                if addr >= YM2612_START && addr <= YM2612_END {
                    // YM2612 writes: buffer for APU processing
                    let port = if addr <= 0xA04001 { 0u8 } else { 1u8 };
                    let is_addr = (addr & 1) == 0; // even = address, odd = data
                    if is_addr {
                        self.ym_addr_latch[port as usize] = value;
                    } else {
                        let addr_reg = self.ym_addr_latch[port as usize];
                        self.ym_write_queue.push((port, addr_reg, value));
                    }
                    return;
                }
                // Z80 bank register (Z80 addr 0x6000-0x60FF)
                let z80_local = (addr as usize - Z80_SPACE_START as usize) & 0xFFFF;
                if z80_local >= 0x6000 && z80_local <= 0x60FF {
                    let incoming = ((value as u32) & 0x01) << 23;
                    self.z80_bank_68k_addr =
                        ((self.z80_bank_68k_addr >> 1) | incoming) & 0x00FF_8000;
                    self.z80_bank_write_count = self.z80_bank_write_count.saturating_add(1);
                    if self.z80_bank_68k_addr > self.z80_bank_max_value {
                        self.z80_bank_max_value = self.z80_bank_68k_addr;
                    }
                    if self.z80_bank_write_log.len() >= 40 {
                        self.z80_bank_write_log.remove(0);
                    }
                    self.z80_bank_write_log.push((value, self.z80_bank_68k_addr));
                    return;
                }
                // PSG write port (Z80 addr 0x7F11)
                if z80_local == 0x7F11 {
                    self.psg_write_queue.push(value);
                    return;
                }
                let index = z80_local & 0x1FFF;
                self.z80_ram[index] = value;
            }
            IO_START..=IO_END => {
                match addr {
                    Z80_BUS_REQ => {
                        self.z80_bus_requested = (value & 0x01) != 0;
                    }
                    Z80_RESET => {
                        self.z80_reset = (value & 0x01) == 0;
                    }
                    0xA1_1101 | 0xA1_1201 => { /* odd byte - ignore */ }
                    // SRAM control register ($A130F1): bit 0 = mode (1=RAM), bit 1 = write-protect
                    SRAM_CTRL_REG => {
                        if !self.sram.is_empty() {
                            self.sram_enabled = (value & 0x01) != 0;
                            self.sram_write_protect = (value & 0x02) != 0;
                        }
                    }
                    reg => {
                        if let Some(idx) = Self::ssf2_bank_reg_index(reg) {
                            if self.ssf2_mapper_enabled {
                                self.ssf2_bank_regs[idx] = self.normalize_ssf2_bank_value(value);
                            }
                        } else {
                            let index = (addr as usize - IO_START as usize) & 0xFF;
                            self.io_ports[index] = value;
                        }
                    }
                }
            }
            WORK_RAM_START..=WORK_RAM_END => {
                let index = (addr as usize - WORK_RAM_START as usize) & 0xFFFF;
                self.work_ram[index] = value;
            }
            WORK_RAM_MIRROR_START..=WORK_RAM_MIRROR_END => {
                let index = (addr as usize - WORK_RAM_MIRROR_START as usize) & 0xFFFF;
                self.work_ram[index] = value;
            }
            _ => {}
        }
    }
}

impl CpuBus for SystemBus {
    fn read8(&mut self, addr: u32) -> (u8, u32) {
        (BusDevice::read8(self, addr), 4)
    }

    fn write8(&mut self, addr: u32, value: u8) -> u32 {
        BusDevice::write8(self, addr, value);
        4
    }
}

#[cfg(test)]
mod tests {
    use super::{BusDevice, SystemBus};

    fn build_paged_rom(page_count: usize, page_size: usize) -> Vec<u8> {
        let mut rom = vec![0u8; page_count * page_size];
        for page in 0..page_count {
            rom[page * page_size] = page as u8;
        }
        rom
    }

    #[test]
    fn ssf2_mapper_register_remaps_window_reads() {
        const PAGE_SIZE: usize = 0x080000;
        let mut bus = SystemBus::default();
        let rom = build_paged_rom(10, PAGE_SIZE);
        bus.load_rom(rom);

        // Default mapping: window #0 (0x080000) points to page 1.
        assert_eq!(BusDevice::read8(&bus, 0x080000), 0x01);

        // Write bank register $A130F3 -> page 3.
        BusDevice::write8(&mut bus, 0xA1_30F3, 0x03);
        assert_eq!(BusDevice::read8(&bus, 0xA1_30F3), 0x03);
        assert_eq!(BusDevice::read8(&bus, 0x080000), 0x03);
    }

    #[test]
    fn ssf2_mapper_disabled_for_small_rom() {
        const PAGE_SIZE: usize = 0x080000;
        let mut bus = SystemBus::default();
        let rom = build_paged_rom(8, PAGE_SIZE);
        bus.load_rom(rom);

        // Register access returns unmapped default when mapper is disabled.
        assert_eq!(BusDevice::read8(&bus, 0xA1_30F3), 0xFF);

        // Writing the register must not alter 0x080000 fixed mapping.
        let before = BusDevice::read8(&bus, 0x080000);
        BusDevice::write8(&mut bus, 0xA1_30F3, 0x07);
        let after = BusDevice::read8(&bus, 0x080000);
        assert_eq!(before, after);
    }
}
