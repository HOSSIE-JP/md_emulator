use std::collections::{HashSet, VecDeque};
use std::path::Path;

use md_apu::Apu;
use md_bus::{BusDevice, SystemBus};
use md_cpu_m68k::{InstructionTrace, M68k, M68kBus, M68kState};
use md_cpu_z80::{Z80Bus, Z80};
use md_vdp::{SpriteDebugInfo, Vdp, FRAME_HEIGHT, FRAME_WIDTH};
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub const NTSC_FRAME_CYCLES_68K: u32 = 488 * 262;
const VDP_DATA_PORT: u32 = 0xC0_0000;
const VDP_CONTROL_PORT: u32 = 0xC0_0004;
const VDP_HV_COUNTER: u32 = 0xC0_0008;

#[derive(Debug, Error)]
pub enum EmulatorError {
    #[error("rom file read failed: {0}")]
    RomReadError(String),
    #[error("rom is empty")]
    EmptyRom,
    #[error("state serialize failed: {0}")]
    StateSerializeError(String),
    #[error("state deserialize failed: {0}")]
    StateDeserializeError(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CpuState {
    pub m68k: M68kState,
    pub z80_pc: u16,
    pub z80_cycles: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RomInfo {
    pub console_name: String,
    pub domestic_name: String,
    pub overseas_name: String,
    pub serial: String,
    pub region: String,
    pub rom_start: u32,
    pub rom_end: u32,
    pub checksum: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Emulator {
    m68k: M68k,
    z80: Z80,
    vdp: Vdp,
    apu: Apu,
    bus: SystemBus,
    breakpoints: HashSet<u32>,
    trace: VecDeque<InstructionTrace>,
    paused: bool,
    pub hint_delivered_count: u64,
    pub vint_delivered_count: u64,
}

impl Default for Emulator {
    fn default() -> Self {
        Self {
            m68k: M68k::default(),
            z80: Z80::default(),
            vdp: Vdp::default(),
            apu: Apu::default(),
            bus: SystemBus::default(),
            breakpoints: HashSet::new(),
            trace: VecDeque::with_capacity(512),
            paused: false,
            hint_delivered_count: 0,
            vint_delivered_count: 0,
        }
    }
}

impl Emulator {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn load_rom(&mut self, path: impl AsRef<Path>) -> Result<(), EmulatorError> {
        let data = std::fs::read(path).map_err(|e| EmulatorError::RomReadError(e.to_string()))?;
        self.load_rom_bytes(&data)
    }

    pub fn load_rom_bytes(&mut self, bytes: &[u8]) -> Result<(), EmulatorError> {
        if bytes.is_empty() {
            return Err(EmulatorError::EmptyRom);
        }
        self.bus.load_rom(bytes.to_vec());
        self.reset();
        Ok(())
    }

    pub fn reset(&mut self) {
        self.m68k.reset();
        self.z80.reset();
        self.vdp.reset();
        self.apu.reset();
        self.paused = false;
        self.trace.clear();

        if self.bus.has_rom() {
            let initial_sp = self.read_long_bus(0x0000_0000);
            let initial_pc = self.read_long_bus(0x0000_0004);
            self.m68k.state.a[7] = initial_sp;
            self.m68k.set_pc(initial_pc);
        }
    }

    pub fn step(&mut self, cycles: u32) {
        if self.paused {
            return;
        }
        let m68k_done = {
            let mut m68k_bus = CoreM68kBus {
                bus: &mut self.bus,
                vdp: &mut self.vdp,
            };
            self.m68k.step_cycles(&mut m68k_bus, cycles)
        };
        if m68k_done == 0 {
            return;
        }
        let z80_budget = m68k_done / 2;
        let mut z80_bus = CoreZ80Bus { bus: &mut self.bus };
        self.z80.step_cycles(&mut z80_bus, z80_budget);
        self.flush_sound_writes();
        self.apu.step_cycles(m68k_done);
        self.process_vdp_dma();

        let scanlines = (m68k_done / 488).max(1);
        for _ in 0..scanlines {
            self.vdp.step_scanline();
            self.deliver_vdp_interrupts();
        }
    }

    pub fn run_frame(&mut self) {
        if self.paused {
            return;
        }
        let cycles_per_line: u32 = 488;
        for _ in 0..262 {
            // Run M68K for one scanline
            {
                let mut m68k_bus = CoreM68kBus {
                    bus: &mut self.bus,
                    vdp: &mut self.vdp,
                };
                self.m68k.step_cycles(&mut m68k_bus, cycles_per_line);
            }
            // Run Z80 for half the cycles
            {
                let mut z80_bus = CoreZ80Bus { bus: &mut self.bus };
                self.z80.step_cycles(&mut z80_bus, cycles_per_line / 2);
            }
            self.flush_sound_writes();
            self.apu.step_cycles(cycles_per_line);
            self.process_vdp_dma();
            self.vdp.step_scanline();
            self.deliver_vdp_interrupts();
        }
    }

    pub fn pause(&mut self) {
        self.paused = true;
    }

    pub fn resume(&mut self) {
        self.paused = false;
    }

    pub fn get_registers(&self) -> M68kState {
        self.m68k.state.clone()
    }

    pub fn get_cpu_state(&self) -> CpuState {
        CpuState {
            m68k: self.m68k.state.clone(),
            z80_pc: self.z80.state.pc,
            z80_cycles: self.z80.state.total_cycles,
        }
    }

    pub fn get_memory(&self, address: u32, length: usize) -> Vec<u8> {
        self.bus.get_memory(address, length)
    }

    pub fn get_vram(&self) -> &[u8] {
        &self.vdp.vram
    }

    pub fn get_cram(&self) -> &[u8] {
        &self.vdp.cram
    }

    pub fn get_vdp_registers(&self) -> Vec<u8> {
        self.vdp.registers.to_vec()
    }

    pub fn get_vdp_debug(&self) -> (u8, u16, u16, u64, u64, u64) {
        (self.vdp.code, self.vdp.address, self.vdp.status, self.vdp.frame,
         self.vdp.data_write_count, self.vdp.ctrl_write_count)
    }

    pub fn get_vdp_dma_debug(&self) -> (u64, u64, u64, u64, u16, u32, u16) {
        (self.vdp.dma_68k_count, self.vdp.dma_68k_total_words,
         self.vdp.dma_fill_count, self.vdp.dma_copy_count,
         self.vdp.last_dma_target_addr, self.vdp.last_dma_source,
         self.vdp.last_dma_length)
    }

    pub fn get_framebuffer_argb(&self) -> &[u32] {
        &self.vdp.framebuffer
    }

    pub fn debug_render_plane(&self, plane: char) -> (usize, usize, Vec<u32>) {
        self.vdp.debug_render_plane(plane)
    }

    pub fn debug_render_tiles(&self, palette: u8) -> (usize, usize, Vec<u32>) {
        self.vdp.debug_render_tiles(palette)
    }

    pub fn debug_cram_colors(&self) -> Vec<u32> {
        self.vdp.debug_cram_colors()
    }

    pub fn debug_sprites(&self) -> Vec<SpriteDebugInfo> {
        self.vdp.debug_sprites()
    }

    pub fn get_vsram(&self) -> &[u8] {
        &self.vdp.vsram
    }

    pub fn get_scanline_vsram_a(&self) -> &[u16] {
        &self.vdp.debug_scanline_vsram_a
    }

    pub fn set_breakpoint(&mut self, address: u32) {
        self.breakpoints.insert(address);
    }

    pub fn step_instruction(&mut self) {
        if self.paused {
            return;
        }
        let trace = {
            let mut m68k_bus = CoreM68kBus {
                bus: &mut self.bus,
                vdp: &mut self.vdp,
            };
            self.m68k.step_instruction(&mut m68k_bus)
        };
        if trace.cycles == 0 {
            return;
        }
        if self.trace.len() == 512 {
            self.trace.pop_front();
        }
        self.trace.push_back(trace.clone());
        if self.breakpoints.contains(&trace.pc) {
            self.paused = true;
        }
        self.apu.step_cycles(trace.cycles);
        let mut z80_bus = CoreZ80Bus { bus: &mut self.bus };
        self.z80.step_cycles(&mut z80_bus, trace.cycles / 2);
        self.vdp.step_scanline();
        self.process_vdp_dma();
    }

    pub fn trace_execution(&self) -> Vec<InstructionTrace> {
        self.trace.iter().cloned().collect()
    }

    pub fn trace_ring(&self) -> Vec<InstructionTrace> {
        self.m68k.trace_ring.iter().cloned().collect()
    }

    pub fn exception_trace(&self) -> Vec<InstructionTrace> {
        self.m68k.exception_trace.clone()
    }

    pub fn set_controller_state(&mut self, player: u8, buttons: u16) {
        self.bus.set_controller(player, buttons);
    }

    pub fn take_audio_samples(&mut self, frames: usize) -> Vec<f32> {
        self.apu.take_samples(frames)
    }

    pub fn frame_dimensions(&self) -> (usize, usize) {
        (FRAME_WIDTH, FRAME_HEIGHT)
    }

    pub fn rom_loaded(&self) -> bool {
        self.bus.has_rom()
    }

    pub fn get_rom_info(&self) -> Option<RomInfo> {
        if self.bus.rom_len() < 0x200 {
            return None;
        }

        Some(RomInfo {
            console_name: self.read_header_string(0x100, 0x110),
            domestic_name: self.read_header_string(0x120, 0x150),
            overseas_name: self.read_header_string(0x150, 0x180),
            serial: self.read_header_string(0x180, 0x18E),
            region: self.read_header_string(0x1F0, 0x200),
            rom_start: self.read_long_bus(0x1A0),
            rom_end: self.read_long_bus(0x1A4),
            checksum: self.read_word_bus(0x18E),
        })
    }

    pub fn save_state(&self) -> Result<Vec<u8>, EmulatorError> {
        serde_json::to_vec(self).map_err(|e| EmulatorError::StateSerializeError(e.to_string()))
    }

    pub fn load_state(&mut self, data: &[u8]) -> Result<(), EmulatorError> {
        let restored: Emulator =
            serde_json::from_slice(data).map_err(|e| EmulatorError::StateDeserializeError(e.to_string()))?;
        *self = restored;
        Ok(())
    }

    fn process_vdp_dma(&mut self) {
        if let Some(req) = self.vdp.consume_dma_request() {
            self.vdp.execute_dma_from_memory(req, |addr| BusDevice::read8(&self.bus, addr));
        }
    }

    fn flush_sound_writes(&mut self) {
        for (port, addr, data) in self.bus.ym_write_queue.drain(..) {
            self.apu.write_ym2612(port, addr, data);
        }
        for data in self.bus.psg_write_queue.drain(..) {
            self.apu.write_psg(data);
        }
    }

    fn deliver_vdp_interrupts(&mut self) {
        // VBlank = level 6, HBlank = level 4
        // Edge-triggered: clear flag on delivery (mimics 68K IACK auto-acknowledge).
        if self.vdp.vblank_flag {
            self.vdp.vblank_flag = false;
            self.m68k.state.pending_ipl = 6;
            self.vint_delivered_count += 1;
        } else if self.vdp.hblank_flag {
            self.vdp.hblank_flag = false;
            self.m68k.state.pending_ipl = 4;
            self.hint_delivered_count += 1;
        }
    }

    fn read_word_bus(&self, addr: u32) -> u16 {
        let hi = BusDevice::read8(&self.bus, addr) as u16;
        let lo = BusDevice::read8(&self.bus, addr.wrapping_add(1)) as u16;
        (hi << 8) | lo
    }

    fn read_long_bus(&self, addr: u32) -> u32 {
        let hi = self.read_word_bus(addr) as u32;
        let lo = self.read_word_bus(addr.wrapping_add(2)) as u32;
        (hi << 16) | lo
    }

    fn read_header_string(&self, start: u32, end: u32) -> String {
        let len = end.saturating_sub(start) as usize;
        let bytes = self.bus.get_memory(start, len);
        let text = String::from_utf8_lossy(&bytes).to_string();
        text.trim_matches(char::from(0)).trim().to_string()
    }
}

struct CoreM68kBus<'a> {
    bus: &'a mut SystemBus,
    vdp: &'a mut Vdp,
}

impl M68kBus for CoreM68kBus<'_> {
    fn read16(&mut self, addr: u32) -> u16 {
        let addr = addr & 0x00FFFFFF;
        if addr >= 0xC00000 && addr < 0xE00000 {
            let reg = addr & 0x1F;
            return match reg {
                0x00 | 0x02 => self.vdp.read_data_port(),
                0x04 | 0x06 => self.vdp.read_status(),
                0x08 | 0x0A => self.vdp.read_hv_counter(),
                _ => 0,
            };
        }
        let hi = BusDevice::read8(self.bus, addr) as u16;
        let lo = BusDevice::read8(self.bus, addr.wrapping_add(1)) as u16;
        (hi << 8) | lo
    }

    fn write16(&mut self, addr: u32, value: u16) {
        let addr = addr & 0x00FFFFFF;
        if addr >= 0xC00000 && addr < 0xE00000 {
            let reg = addr & 0x1F;
            match reg {
                0x00 | 0x02 => self.vdp.write_data_port(value),
                0x04 | 0x06 => {
                    self.vdp.write_control_port(value);
                    // Execute 68K→VDP DMA immediately (hardware halts CPU until done)
                    if let Some(req) = self.vdp.consume_dma_request() {
                        self.vdp.execute_dma_from_memory(req, |a| BusDevice::read8(self.bus, a));
                    }
                },
                0x10 | 0x12 => {
                    // PSG write (only low byte matters)
                    self.bus.psg_write_queue.push((value & 0xFF) as u8);
                },
                _ => {},
            }
            return;
        }
        BusDevice::write8(self.bus, addr, (value >> 8) as u8);
        BusDevice::write8(self.bus, addr.wrapping_add(1), (value & 0xFF) as u8);
    }

    fn read8(&mut self, addr: u32) -> u8 {
        let addr = addr & 0x00FFFFFF;
        if addr >= 0xC00000 && addr < 0xE00000 {
            let reg = addr & 0x1F;
            return match reg {
                // VDP data port: do a full word read, return selected byte
                0x00..=0x03 => {
                    let w = self.vdp.read_data_port();
                    if (addr & 1) == 0 { (w >> 8) as u8 } else { (w & 0xFF) as u8 }
                }
                // VDP status (read-only, 16-bit)
                0x04..=0x07 => {
                    let w = self.vdp.read_status();
                    if (addr & 1) == 0 { (w >> 8) as u8 } else { (w & 0xFF) as u8 }
                }
                // HV counter
                0x08..=0x0B => {
                    let w = self.vdp.read_hv_counter();
                    if (addr & 1) == 0 { (w >> 8) as u8 } else { (w & 0xFF) as u8 }
                }
                _ => 0,
            };
        }
        BusDevice::read8(self.bus, addr)
    }

    fn write8(&mut self, addr: u32, value: u8) {
        let addr = addr & 0x00FFFFFF;
        if addr >= 0xC00000 && addr < 0xE00000 {
            let reg = addr & 0x1F;
            match reg {
                // VDP data port: byte write duplicates byte to both halves
                0x00..=0x03 => {
                    self.vdp.write_data_port(((value as u16) << 8) | value as u16);
                }
                // VDP control port: byte write
                0x04..=0x07 => {
                    self.vdp.write_control_port(((value as u16) << 8) | value as u16);
                    if let Some(req) = self.vdp.consume_dma_request() {
                        self.vdp.execute_dma_from_memory(req, |a| BusDevice::read8(self.bus, a));
                    }
                }
                // PSG (byte addressable, odd byte port)
                0x11 | 0x13 => {
                    self.bus.psg_write_queue.push(value);
                }
                _ => {}
            }
            return;
        }
        BusDevice::write8(self.bus, addr, value);
    }
}

struct CoreZ80Bus<'a> {
    bus: &'a mut SystemBus,
}

impl Z80Bus for CoreZ80Bus<'_> {
    fn read8(&self, addr: u16) -> u8 {
        BusDevice::read8(self.bus, addr as u32)
    }

    fn write8(&mut self, addr: u16, value: u8) {
        BusDevice::write8(self.bus, addr as u32, value);
    }
}

#[cfg(test)]
mod tests {
    use super::Emulator;

    fn write_be32(buffer: &mut [u8], addr: usize, value: u32) {
        buffer[addr] = (value >> 24) as u8;
        buffer[addr + 1] = (value >> 16) as u8;
        buffer[addr + 2] = (value >> 8) as u8;
        buffer[addr + 3] = value as u8;
    }

    #[test]
    fn state_roundtrip_preserves_cpu_state() {
        let mut emu = Emulator::new();
        emu.m68k.state.a[7] = 0xFF00;
        emu.step(1024);
        let before = emu.get_cpu_state();

        let snapshot = emu.save_state().expect("save_state failed");

        let mut restored = Emulator::new();
        restored
            .load_state(&snapshot)
            .expect("load_state failed");
        let after = restored.get_cpu_state();

        assert_eq!(before.m68k.pc, after.m68k.pc);
        assert_eq!(before.z80_pc, after.z80_pc);
        assert_eq!(before.z80_cycles, after.z80_cycles);
    }

    #[test]
    fn paused_state_blocks_stepping() {
        let mut emu = Emulator::new();
        emu.pause();
        let before = emu.get_cpu_state();
        emu.step(512);
        let after = emu.get_cpu_state();
        assert_eq!(before.m68k.pc, after.m68k.pc);
        assert_eq!(before.z80_pc, after.z80_pc);
    }

    #[test]
    fn reset_uses_rom_vectors() {
        let mut rom = vec![0u8; 0x400];
        write_be32(&mut rom, 0x00, 0x00FF_0000);
        write_be32(&mut rom, 0x04, 0x0000_0200);

        let mut emu = Emulator::new();
        emu.load_rom_bytes(&rom).expect("load_rom_bytes failed");
        let cpu = emu.get_cpu_state();

        assert_eq!(cpu.m68k.a[7], 0x00FF_0000);
        assert_eq!(cpu.m68k.pc, 0x0000_0200);
    }

    #[test]
    fn parses_rom_header_info() {
        let mut rom = vec![0u8; 0x400];
        write_be32(&mut rom, 0x00, 0x00FF_0000);
        write_be32(&mut rom, 0x04, 0x0000_0200);
        write_be32(&mut rom, 0x1A0, 0x0000_0000);
        write_be32(&mut rom, 0x1A4, 0x0003_FFFF);
        rom[0x18E] = 0x12;
        rom[0x18F] = 0x34;
        rom[0x100..0x10F].copy_from_slice(b"SEGA MEGA DRIVE");
        rom[0x120..0x12D].copy_from_slice(b"TEST DOMESTIC");
        rom[0x150..0x15D].copy_from_slice(b"TEST OVERSEAS");
        rom[0x180..0x189].copy_from_slice(b"GM 000001");
        rom[0x1F0..0x1F3].copy_from_slice(b"JUE");

        let mut emu = Emulator::new();
        emu.load_rom_bytes(&rom).expect("load_rom_bytes failed");
        let info = emu.get_rom_info().expect("rom info missing");

        assert_eq!(info.console_name, "SEGA MEGA DRIVE");
        assert_eq!(info.checksum, 0x1234);
        assert_eq!(info.region, "JUE");
    }
}
