use std::cell::RefCell;

use serde::{Deserialize, Serialize};

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
    /// Debug: count M68K writes to Z80 space
    #[serde(skip)]
    pub z80_m68k_write_count: u32,
    /// Debug: recent Z80 banked 68K reads
    #[serde(skip)]
    pub z80_banked_read_log: RefCell<Vec<(u32, u8)>>,
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
            z80_m68k_write_count: 0,
            z80_banked_read_log: RefCell::new(Vec::new()),
        }
    }
}

impl SystemBus {
    pub fn load_rom(&mut self, rom: Vec<u8>) {
        self.rom = rom;
    }

    /// Reset all mutable state (keeping ROM). Matches power-on behavior.
    pub fn reset(&mut self) {
        self.work_ram.fill(0);
        self.z80_ram.fill(0);
        self.z80_bus_requested = false;
        self.z80_reset = true;
        self.ym_write_queue.clear();
        self.psg_write_queue.clear();
        self.ym_addr_latch = [0; 2];
        self.ym_status = 0;
        self.z80_m68k_write_count = 0;
        self.z80_banked_read_log.borrow_mut().clear();
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
}

impl BusDevice for SystemBus {
    fn read8(&self, addr: u32) -> u8 {
        let addr = addr & 0x00FFFFFF;
        match addr {
            ROM_START..=ROM_END => self.rom.get(addr as usize).copied().unwrap_or(0xFF),
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
        match addr {
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
                let index = (addr as usize - Z80_SPACE_START as usize) & 0x1FFF;
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
                    _ => {
                        let index = (addr as usize - IO_START as usize) & 0xFF;
                        self.io_ports[index] = value;
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
