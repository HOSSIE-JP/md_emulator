use std::collections::{HashSet, VecDeque};

const Z80_TRACE_RING_CAPACITY: usize = 32768;
use std::path::Path;

use md_apu::Apu;
use md_bus::{BusDevice, SystemBus, Z80_SPACE_START, Z80_SPACE_END, YM2612_START, YM2612_END};
use md_cpu_m68k::{InstructionTrace, M68k, M68kBus, M68kState};
use md_cpu_z80::{Z80Bus, Z80State, Z80Trace, Z80};
use md_vdp::{SpriteDebugInfo, Vdp, FRAME_HEIGHT, FRAME_WIDTH};
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub const NTSC_FRAME_CYCLES_68K: u32 = 488 * 262;
const M68K_CLOCK_HZ: i64 = 7_670_454;
const Z80_CLOCK_HZ: i64 = 3_579_545;
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
    pub z80: Z80State,
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
    #[serde(skip)]
    z80_trace_ring: VecDeque<Z80Trace>,
    paused: bool,
    pub hint_delivered_count: u64,
    pub vint_delivered_count: u64,
    /// Total YM2612 writes flushed to APU
    pub ym_write_total: u64,
    /// Previous z80_reset state (for edge detection)
    prev_z80_reset: bool,
    #[serde(default)]
    vdp_cycle_accumulator: u32,
    #[serde(default)]
    z80_cycle_balance: i64,
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
            z80_trace_ring: VecDeque::with_capacity(Z80_TRACE_RING_CAPACITY),
            paused: false,
            hint_delivered_count: 0,
            vint_delivered_count: 0,
            ym_write_total: 0,
            prev_z80_reset: true,
            vdp_cycle_accumulator: 0,
            z80_cycle_balance: 0,
        }
    }
}

impl Emulator {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn build_version() -> String {
        let base = env!("CARGO_PKG_VERSION");
        let timestamp = option_env!("BUILD_TIMESTAMP").unwrap_or("unknown");
        let git_sha = option_env!("BUILD_GIT_SHA").unwrap_or("nogit");
        let git_dirty = option_env!("BUILD_GIT_DIRTY").unwrap_or("unknown");
        if git_dirty == "dirty" {
            format!("{base}+{timestamp}.{git_sha}.dirty")
        } else {
            format!("{base}+{timestamp}.{git_sha}")
        }
    }

    pub fn load_rom(&mut self, path: impl AsRef<Path>) -> Result<(), EmulatorError> {
        let data = std::fs::read(path).map_err(|e| EmulatorError::RomReadError(e.to_string()))?;
        self.load_rom_bytes(&data)
    }

    pub fn load_rom_bytes(&mut self, bytes: &[u8]) -> Result<(), EmulatorError> {
        if bytes.is_empty() {
            return Err(EmulatorError::EmptyRom);
        }
        let rom = if Self::is_smd_format(bytes) {
            Self::deinterleave_smd(bytes)
        } else {
            bytes.to_vec()
        };
        self.bus.load_rom(rom);
        self.reset();
        Ok(())
    }

    /// Detect SMD (Super Magic Drive) interleaved ROM format.
    /// SMD files have a 512-byte header followed by 16KB interleaved blocks.
    fn is_smd_format(bytes: &[u8]) -> bool {
        const SMD_HEADER_SIZE: usize = 512;
        const SMD_BLOCK_SIZE: usize = 16384;
        if bytes.len() <= SMD_HEADER_SIZE {
            return false;
        }
        // SMD files: (total_size - 512) is a multiple of 16384
        if (bytes.len() - SMD_HEADER_SIZE) % SMD_BLOCK_SIZE != 0 {
            return false;
        }
        // Verify by deinterleaving first block and checking for "SEGA" at offset 0x100
        let block = &bytes[SMD_HEADER_SIZE..SMD_HEADER_SIZE + SMD_BLOCK_SIZE];
        let odd = &block[..SMD_BLOCK_SIZE / 2];
        let even = &block[SMD_BLOCK_SIZE / 2..];
        // Offset 0x100 in deinterleaved data: even byte at index 0x80, odd byte at index 0x80
        // deinterleaved[0x100] = even[0x80], deinterleaved[0x101] = odd[0x80], ...
        let sig: Vec<u8> = (0..4)
            .flat_map(|i| [even[0x80 + i], odd[0x80 + i]])
            .collect();
        // "SEGA" = [0x53, 0x45, 0x47, 0x41]
        sig.len() >= 4 && sig[0] == 0x53 && sig[1] == 0x45 && sig[2] == 0x47 && sig[3] == 0x41
    }

    /// Deinterleave SMD format ROM into standard binary format.
    fn deinterleave_smd(bytes: &[u8]) -> Vec<u8> {
        const SMD_HEADER_SIZE: usize = 512;
        const SMD_BLOCK_SIZE: usize = 16384;
        const HALF_BLOCK: usize = SMD_BLOCK_SIZE / 2;

        let data = &bytes[SMD_HEADER_SIZE..];
        let num_blocks = data.len() / SMD_BLOCK_SIZE;
        let mut rom = vec![0u8; num_blocks * SMD_BLOCK_SIZE];

        for b in 0..num_blocks {
            let block = &data[b * SMD_BLOCK_SIZE..(b + 1) * SMD_BLOCK_SIZE];
            let odd = &block[..HALF_BLOCK];
            let even = &block[HALF_BLOCK..];
            let out = &mut rom[b * SMD_BLOCK_SIZE..(b + 1) * SMD_BLOCK_SIZE];
            for i in 0..HALF_BLOCK {
                out[i * 2] = even[i];
                out[i * 2 + 1] = odd[i];
            }
        }
        rom
    }

    pub fn reset(&mut self) {
        self.bus.reset();
        self.m68k.reset();
        self.z80.reset();
        self.vdp.reset();
        self.apu.reset();
        self.paused = false;
        self.trace.clear();
        self.z80_trace_ring.clear();
        self.vdp_cycle_accumulator = 0;
        self.z80_cycle_balance = 0;

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
        let mut consumed = 0u32;
        while consumed < cycles {
            let trace = {
                let mut m68k_bus = CoreM68kBus {
                    bus: &mut self.bus,
                    vdp: &mut self.vdp,
                };
                self.m68k.step_instruction(&mut m68k_bus)
            };
            if trace.cycles == 0 {
                break;
            }
            consumed = consumed.saturating_add(trace.cycles);
            self.advance_subsystems(trace.cycles);
        }
    }

    pub fn run_frame(&mut self) {
        if self.paused {
            return;
        }
        self.step(NTSC_FRAME_CYCLES_68K);
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
            z80: self.z80.state.clone(),
        }
    }

    pub fn get_memory(&self, address: u32, length: usize) -> Vec<u8> {
        self.bus.get_memory(address, length)
    }

    pub fn set_memory(&mut self, address: u32, data: &[u8]) {
        for (i, &byte) in data.iter().enumerate() {
            BusDevice::write8(&mut self.bus, address.wrapping_add(i as u32), byte);
        }
    }

    pub fn set_vdp_register(&mut self, reg: u8, value: u8) {
        self.vdp.write_control_port(0x8000 | ((reg as u16) << 8) | value as u16);
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

    /// Debug: return APU internal state for diagnostics
    pub fn get_apu_debug(&self) -> serde_json::Value {
        let ym = &self.apu.ym2612;
        let channels: Vec<serde_json::Value> = (0..6).map(|ch| {
            let ops: Vec<serde_json::Value> = (0..4).map(|op| {
                let o = &ym.channels[ch].operators[op];
                serde_json::json!({
                    "key_on": o.key_on,
                    "attenuation": o.attenuation,
                    "env_phase": format!("{:?}", o.env_phase),
                    "phase_counter": o.phase_counter,
                })
            }).collect();
            serde_json::json!({
                "pan_left": ym.get_output_left(ch),
                "pan_right": ym.get_output_right(ch),
                "fnum": ym.get_fnum(ch),
                "block": ym.get_block(ch),
                "algorithm": ym.get_algorithm(ch),
                "feedback": ym.get_feedback(ch),
                "operators": ops,
            })
        }).collect();

        let psg = &self.apu.psg;
        let mut obj = serde_json::json!({
            "audio_buffer_len": self.apu.audio_buffer.len(),
            "fm_tick_accumulator": self.apu.fm_tick_accumulator,
            "dac_enabled": ym.dac_enabled,
            "dac_data": ym.dac_data,
            "lfo_counter": ym.lfo_counter,
            "eg_counter": ym.envelope_cycle_counter,
            "status": ym.status,
            "reg27": ym.regs_port0[0x27],
            "timer_a_value": ((ym.regs_port0[0x24] as u32) << 2) | ((ym.regs_port0[0x25] as u32) & 0x03),
            "timer_a_counter": ym.timer_a_counter,
            "timer_a_period": 1024u32.saturating_sub(((ym.regs_port0[0x24] as u32) << 2) | ((ym.regs_port0[0x25] as u32) & 0x03)).max(1),
            "timer_a_load": (ym.regs_port0[0x27] & 0x01) != 0,
            "timer_a_enabled": (ym.regs_port0[0x27] & 0x04) != 0,
            "timer_preadvanced_ticks": self.apu.timer_preadvanced_ticks,
            "timer_only_accumulator": self.apu.timer_only_accumulator,
            "reg24": ym.regs_port0[0x24],
            "reg25": ym.regs_port0[0x25],
            "timer_a_overflow_count": self.apu.debug_timer_a_overflow_count,
            "timer_a_clear_count": self.apu.debug_timer_a_clear_count,
            "channels": channels,
            "psg_volumes": psg.volume,
            "psg_periods": psg.tone_period,
        });

        // Add register dumps and debug data separately to avoid recursion limit
        let m = obj.as_object_mut().unwrap();
        m.insert("regs_port0_freq".into(), serde_json::json!(&ym.regs_port0[0xA0..0xA7]));
        m.insert("regs_port1_freq".into(), serde_json::json!(&ym.regs_port1[0xA0..0xA7]));
        m.insert("regs_port0_algo".into(), serde_json::json!([ym.regs_port0[0xB0], ym.regs_port0[0xB1], ym.regs_port0[0xB2]]));
        m.insert("regs_port1_algo".into(), serde_json::json!([ym.regs_port1[0xB0], ym.regs_port1[0xB1], ym.regs_port1[0xB2]]));
        m.insert("regs_port0_tl".into(), serde_json::json!(&ym.regs_port0[0x40..0x50]));
        m.insert("regs_port1_tl".into(), serde_json::json!(&ym.regs_port1[0x40..0x50]));
        m.insert("regs_port0_b4_b6".into(), serde_json::json!([ym.regs_port0[0xB4], ym.regs_port0[0xB5], ym.regs_port0[0xB6]]));
        m.insert("regs_port1_b4_b6".into(), serde_json::json!([ym.regs_port1[0xB4], ym.regs_port1[0xB5], ym.regs_port1[0xB6]]));
        m.insert("regs_port0_key".into(), serde_json::json!(ym.regs_port0[0x28]));
        m.insert("regs_port0_22".into(), serde_json::json!(ym.regs_port0[0x22]));
        m.insert("regs_port0_2b".into(), serde_json::json!(ym.regs_port0[0x2B]));
        m.insert("z80_bus_requested".into(), serde_json::json!(self.bus.z80_bus_requested));
        m.insert("z80_reset".into(), serde_json::json!(self.bus.z80_reset));
        m.insert("z80_m68k_write_count".into(), serde_json::json!(self.bus.z80_m68k_write_count));
        m.insert("ym_write_total".into(), serde_json::json!(self.ym_write_total));
        m.insert("z80_pc".into(), serde_json::json!(self.z80.state.pc));
        m.insert("z80_total_cycles".into(), serde_json::json!(self.z80.state.total_cycles));
        m.insert("z80_halted".into(), serde_json::json!(self.z80.state.halted));
        m.insert("z80_iff1".into(), serde_json::json!(self.z80.state.iff1));
        m.insert("z80_int_pending".into(), serde_json::json!(self.z80.state.int_pending));
        m.insert("z80_bank_68k_addr".into(), serde_json::json!(format!("{:#010X}", self.bus.z80_bank_68k_addr)));
        m.insert("z80_bank_write_count".into(), serde_json::json!(self.bus.z80_bank_write_count));
        m.insert("z80_bank_max_value".into(), serde_json::json!(format!("{:#010X}", self.bus.z80_bank_max_value)));
        m.insert("z80_bank_write_log".into(), serde_json::json!(
            self.bus.z80_bank_write_log.iter()
                .map(|(v, bank)| format!("val=0x{:02X}(b0={}) -> bank={:#010X}", v, v & 1, bank))
                .collect::<Vec<_>>()
        ));
        m.insert("z80_int_count".into(), serde_json::json!(self.z80.state.total_cycles)); // proxy
        m.insert("vint_delivered".into(), serde_json::json!(self.vint_delivered_count));
        m.insert("vdp_frame".into(), serde_json::json!(self.vdp.frame));
        m.insert("vdp_vint_enabled".into(), serde_json::json!((self.vdp.registers[1] & 0x20) != 0));
        m.insert("vdp_scanline".into(), serde_json::json!(self.vdp.scanline));
        m.insert("vdp_status".into(), serde_json::json!(format!("0x{:04X}", self.vdp.status)));
        m.insert("vdp_read_status_total".into(), serde_json::json!(self.vdp.debug_read_status_total));
        m.insert("vdp_read_status_vblank_count".into(), serde_json::json!(self.vdp.debug_read_status_vblank_count));

        // DAC/FM debug counters
        m.insert("debug_dac_samples".into(), serde_json::json!(self.apu.debug_dac_samples));
        m.insert("debug_dac_nonzero".into(), serde_json::json!(self.apu.debug_dac_nonzero));
        m.insert("debug_fm_nonzero".into(), serde_json::json!(self.apu.debug_fm_nonzero));
        m.insert("debug_fm_ticks".into(), serde_json::json!(self.apu.debug_fm_ticks));
        m.insert("debug_output_nonzero".into(), serde_json::json!(self.apu.debug_output_nonzero));
        m.insert("debug_output_total".into(), serde_json::json!(self.apu.debug_output_total));
        m.insert("last_fm_left".into(), serde_json::json!(self.apu.last_fm_left));
        m.insert("last_fm_right".into(), serde_json::json!(self.apu.last_fm_right));

        // Write log and histogram
        let log: Vec<String> = self.apu.ym2612.write_log.iter().rev().take(100)
            .map(|(p,a,d)| format!("P{}:${:02X}=${:02X}", p, a, d))
            .collect();
        let non_dac_log: Vec<String> = self
            .apu
            .ym2612
            .write_log
            .iter()
            .rev()
            .filter(|(_, a, _)| *a != 0x2A)
            .take(100)
            .map(|(p, a, d)| format!("P{}:${:02X}=${:02X}", p, a, d))
            .collect();
        m.insert("ym_write_log_first100".into(), serde_json::json!(log));
        m.insert("ym_write_log_recent_non_dac".into(), serde_json::json!(non_dac_log));
        m.insert("ym_write_log_len".into(), serde_json::json!(self.apu.ym2612.write_log.len()));
        let banked_reads: Vec<String> = self
            .bus
            .z80_banked_read_log
            .borrow()
            .iter()
            .rev()
            .take(64)
            .map(|(addr, value)| format!("${:06X}=${:02X}", addr, value))
            .collect();
        m.insert("z80_banked_read_log".into(), serde_json::json!(banked_reads));
        let z80_trace_ring: Vec<String> = self
            .z80_trace_ring
            .iter()
            .rev()
            .take(Z80_TRACE_RING_CAPACITY)
            .map(|trace| format!("${:04X}: {:02X} {}", trace.pc, trace.opcode, trace.mnemonic))
            .collect();
        m.insert("z80_trace_ring".into(), serde_json::json!(z80_trace_ring));

        let hist0: Vec<String> = (0..=255u16)
            .filter(|&a| self.apu.ym2612.write_histogram[a as usize] > 0)
            .map(|a| format!("${:02X}:{}", a, self.apu.ym2612.write_histogram[a as usize]))
            .collect();
        let hist1: Vec<String> = (0..=255u16)
            .filter(|&a| self.apu.ym2612.write_histogram[256 + a as usize] > 0)
            .map(|a| format!("${:02X}:{}", a, self.apu.ym2612.write_histogram[256 + a as usize]))
            .collect();
        m.insert("ym_histogram_port0_nonzero".into(), serde_json::json!(hist0));
        m.insert("ym_histogram_port1_nonzero".into(), serde_json::json!(hist1));

        obj
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
        self.advance_subsystems(trace.cycles);
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

    fn advance_subsystems(&mut self, m68k_cycles: u32) {
        if m68k_cycles == 0 {
            return;
        }

        self.check_z80_reset_edge();

        self.z80_cycle_balance += i64::from(m68k_cycles) * Z80_CLOCK_HZ;

        // Track Z80 cycles for lightweight timer interleaving
        let mut z80_cycles_run: u32 = 0;

        if !self.bus.z80_reset && !self.bus.z80_bus_requested {
            while self.z80_cycle_balance > 0 {
                let trace_cycles = {
                    let mut z80_bus = CoreZ80Bus {
                        bus: &mut self.bus,
                    };
                    let trace = self.z80.step_instruction(&mut z80_bus);
                    if self.z80_trace_ring.len() == Z80_TRACE_RING_CAPACITY {
                        self.z80_trace_ring.pop_front();
                    }
                    self.z80_trace_ring.push_back(trace.clone());
                    trace.cycles
                };
                if trace_cycles == 0 {
                    break;
                }
                self.z80_cycle_balance -= i64::from(trace_cycles) * M68K_CLOCK_HZ;
                z80_cycles_run += trace_cycles;
                self.flush_sound_writes();

                // Lightweight timer advance: convert Z80 cycles to master clocks
                // and advance only timer counters (no FM synthesis).
                // Z80 clock = M68K clock * Z80_HZ / M68K_HZ ≈ 0.4667x
                // Master clock and M68K clock are the same for timer purposes.
                // Z80 cycles → M68K equiv: z80_cycles * M68K_HZ / Z80_HZ
                // But we need master clocks for timer accumulator (144 per FM tick).
                // Approximate: pass Z80 cycles scaled to M68K domain.
                let m68k_equiv = ((trace_cycles as u64 * M68K_CLOCK_HZ as u64) / Z80_CLOCK_HZ as u64) as u32;
                if m68k_equiv > 0 {
                    self.apu.advance_timers(m68k_equiv);
                    self.bus.ym_status = self.apu.ym2612.status;
                }
            }
        } else {
            self.z80_cycle_balance = 0;
        }

        self.flush_sound_writes();
        // Full APU step for audio generation (timers will advance again but
        // advance_timers already handled them — next_fm_sample will re-advance,
        // which is harmless as the counter just continues from where it is)
        self.apu.step_cycles(m68k_cycles);
        // APU step_cycles advances timers — update status for next Z80 read
        self.bus.ym_status = self.apu.ym2612.status;
        self.process_vdp_dma();

        self.vdp_cycle_accumulator = self.vdp_cycle_accumulator.saturating_add(m68k_cycles);
        while self.vdp_cycle_accumulator >= 488 {
            self.vdp_cycle_accumulator -= 488;
            self.vdp.step_scanline();
            self.deliver_vdp_interrupts();
        }
    }

    /// Detect Z80 reset deassertion edge and restart Z80 from PC=0
    fn check_z80_reset_edge(&mut self) {
        let current_reset = self.bus.z80_reset;
        if self.prev_z80_reset && !current_reset {
            // Reset deasserted: Z80 starts from address 0
            self.z80.reset();
        }
        self.prev_z80_reset = current_reset;
    }

    fn flush_sound_writes(&mut self) {
        for (port, addr, data) in self.bus.ym_write_queue.drain(..) {
            self.apu.write_ym2612(port, addr, data);
        }
        for data in self.bus.psg_write_queue.drain(..) {
            self.apu.write_psg(data);
        }
        // Update YM2612 status register in bus for CPU reads
        self.bus.ym_status = self.apu.ym2612.status;
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

        // Z80 /INT is connected directly to VBlank, independent of M68K VINT_EN.
        // On real hardware, Z80 always receives VBlank interrupts regardless of R1 bit 5.
        if self.vdp.z80_vblank_flag {
            self.vdp.z80_vblank_flag = false;
            self.z80.signal_int();
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

fn m68k_to_z80_bus_addr(addr: u32) -> u32 {
    Z80_SPACE_START + ((addr - Z80_SPACE_START) & 0x7FFF)
}

impl M68kBus for CoreM68kBus<'_> {
    fn read16(&mut self, addr: u32) -> u16 {
        let addr = addr & 0x00FFFFFF;
        if addr >= Z80_SPACE_START as u32 && addr <= Z80_SPACE_END as u32 {
            // Z80 bus is 8-bit: word reads return byte on D8-D15.
            // YM2612 uses direct address decode; RAM uses M68K A1..A15 → Z80 A0..A14.
            let bus_addr = if addr >= YM2612_START && addr <= YM2612_END {
                addr
            } else {
                m68k_to_z80_bus_addr(addr)
            };
            let value = BusDevice::read8(self.bus, bus_addr) as u16;
            return value << 8;
        }
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
        if addr >= Z80_SPACE_START as u32 && addr <= Z80_SPACE_END as u32 {
            // Z80 bus is 8-bit: word writes send high byte (D8-D15) to Z80.
            // YM2612 uses direct address decode; RAM uses >>1 mapping.
            let bus_addr = if addr >= YM2612_START && addr <= YM2612_END {
                addr
            } else {
                m68k_to_z80_bus_addr(addr)
            };
            self.bus.z80_m68k_write_count = self.bus.z80_m68k_write_count.saturating_add(1);
            BusDevice::write8(self.bus, bus_addr, (value >> 8) as u8);
            return;
        }
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
        if addr >= Z80_SPACE_START as u32 && addr <= Z80_SPACE_END as u32 {
            // M68K byte access to Z80 space: A1..A15 → Z80 A0..A14 (>>1 mapping).
            let bus_addr = if addr >= YM2612_START && addr <= YM2612_END {
                addr
            } else {
                m68k_to_z80_bus_addr(addr)
            };
            return BusDevice::read8(self.bus, bus_addr);
        }
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
        if addr >= Z80_SPACE_START as u32 && addr <= Z80_SPACE_END as u32 {
            // M68K byte access to Z80 space: use same address mapping as word access.
            self.bus.z80_m68k_write_count = self.bus.z80_m68k_write_count.saturating_add(1);
            let bus_addr = if addr >= YM2612_START && addr <= YM2612_END {
                addr
            } else {
                m68k_to_z80_bus_addr(addr)
            };
            BusDevice::write8(self.bus, bus_addr, value);
            return;
        }
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
        let addr32 = addr as u32;
        match addr32 {
            // Z80 RAM + mirror
            0x0000..=0x3FFF => {
                let z80_addr = 0xA0_0000 | (addr32 & 0x1FFF);
                BusDevice::read8(self.bus, z80_addr)
            }
            // YM2612 (0x4000-0x5FFF, mirrored; hardware only decodes A0-A1)
            0x4000..=0x5FFF => {
                let ym_addr = 0xA0_4000 | (addr32 & 0x03);
                BusDevice::read8(self.bus, ym_addr)
            }
            // Banked 68K window
            0x8000..=0xFFFF => {
                let bank_base = self.bus.z80_bank_68k_addr & 0x00FF_8000;
                let m68k_addr = bank_base | (addr32 & 0x7FFF);
                let value = BusDevice::read8(self.bus, m68k_addr);
                let mut banked_read_log = self.bus.z80_banked_read_log.borrow_mut();
                if banked_read_log.len() >= 256 {
                    banked_read_log.remove(0);
                }
                banked_read_log.push((m68k_addr, value));
                value
            }
            _ => 0xFF,
        }
    }

    fn write8(&mut self, addr: u16, value: u8) {
        let addr32 = addr as u32;
        match addr32 {
            // Z80 RAM + mirror
            0x0000..=0x3FFF => {
                let z80_addr = 0xA0_0000 | (addr32 & 0x1FFF);
                BusDevice::write8(self.bus, z80_addr, value);
            }
            // YM2612 (0x4000-0x5FFF, mirrored; hardware only decodes A0-A1)
            0x4000..=0x5FFF => {
                let ym_addr = 0xA0_4000 | (addr32 & 0x03);
                BusDevice::write8(self.bus, ym_addr, value);
            }
            // Z80 bank register (serial, bit0 shifted in per write).
            0x6000..=0x60FF => {
                let incoming = ((value as u32) & 0x01) << 23;
                self.bus.z80_bank_68k_addr =
                    ((self.bus.z80_bank_68k_addr >> 1) | incoming) & 0x00FF_8000;
                self.bus.z80_bank_write_count = self.bus.z80_bank_write_count.saturating_add(1);
                if self.bus.z80_bank_68k_addr > self.bus.z80_bank_max_value {
                    self.bus.z80_bank_max_value = self.bus.z80_bank_68k_addr;
                }
                if self.bus.z80_bank_write_log.len() >= 40 {
                    self.bus.z80_bank_write_log.remove(0);
                }
                self.bus.z80_bank_write_log.push((value, self.bus.z80_bank_68k_addr));
            }
            // PSG write port
            0x7F11 => {
                self.bus.psg_write_queue.push(value);
            }
            // Banked 68K window write
            0x8000..=0xFFFF => {
                let bank_base = self.bus.z80_bank_68k_addr & 0x00FF_8000;
                let m68k_addr = bank_base | (addr32 & 0x7FFF);
                BusDevice::write8(self.bus, m68k_addr, value);
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{CoreM68kBus, CoreZ80Bus, Emulator};
    use md_cpu_m68k::M68kBus;
    use md_cpu_z80::Z80Bus;

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

    #[test]
    fn z80_bus_maps_ym_and_psg_writes() {
        let mut emu = Emulator::new();
        {
            let mut z80_bus = CoreZ80Bus {
                bus: &mut emu.bus,
            };

            // YM: address then data on port 0
            z80_bus.write8(0x4000, 0x28);
            z80_bus.write8(0x4001, 0xF0);
            // PSG data port
            z80_bus.write8(0x7F11, 0x90);
        }

        assert_eq!(emu.bus.ym_write_queue.len(), 1);
        assert_eq!(emu.bus.ym_write_queue[0], (0, 0x28, 0xF0));
        assert_eq!(emu.bus.psg_write_queue, vec![0x90]);
    }

    #[test]
    fn z80_bus_uses_z80_ram_not_rom_at_zero_page() {
        let mut emu = Emulator::new();
        {
            let mut z80_bus = CoreZ80Bus {
                bus: &mut emu.bus,
            };
            z80_bus.write8(0x0000, 0x5A);
            assert_eq!(z80_bus.read8(0x0000), 0x5A);
        }
    }

    #[test]
    fn z80_banked_window_maps_z80_addr_to_68k_linear() {
        let mut rom = vec![0u8; 0x20010];
        rom[0x0000] = 0x11;
        rom[0x0001] = 0x22;
        rom[0x0002] = 0x33;
        rom[0x0003] = 0x44;

        let mut emu = Emulator::new();
        emu.load_rom_bytes(&rom).expect("load_rom_bytes failed");

        {
            let z80_bus = CoreZ80Bus {
                bus: &mut emu.bus,
            };

            // Z80 banked window maps linearly: Z80 $8000+n → M68K bank_base+n
            assert_eq!(z80_bus.read8(0x8000), 0x11);
            assert_eq!(z80_bus.read8(0x8001), 0x22);
            assert_eq!(z80_bus.read8(0x8002), 0x33);
            assert_eq!(z80_bus.read8(0x8003), 0x44);
        }
    }

    #[test]
    fn m68k_word_writes_send_high_byte_to_z80() {
        let mut emu = Emulator::new();
        {
            let mut m68k_bus = CoreM68kBus {
                bus: &mut emu.bus,
                vdp: &mut emu.vdp,
            };
            // Word writes send only the high byte (D8-D15) to the Z80 bus.
            // M68K address maps 1:1 to Z80 address (& 0x7FFF).
            m68k_bus.write16(0xA0_0000, 0x1122);
            m68k_bus.write16(0xA0_0002, 0x3344);
            m68k_bus.write16(0xA0_0004, 0x5566);
        }
        {
            let z80_bus = CoreZ80Bus {
                bus: &mut emu.bus,
            };
            // Each word write goes to the corresponding Z80 addr (1:1).
            assert_eq!(z80_bus.read8(0x0000), 0x11); // high byte of 0x1122
            assert_eq!(z80_bus.read8(0x0002), 0x33); // high byte of 0x3344
            assert_eq!(z80_bus.read8(0x0004), 0x55); // high byte of 0x5566
            // Odd Z80 addresses are untouched.
            assert_eq!(z80_bus.read8(0x0001), 0x00);
            assert_eq!(z80_bus.read8(0x0003), 0x00);
        }
    }

    #[test]
    fn m68k_byte_accesses_use_direct_z80_mapping() {
        let mut emu = Emulator::new();
        {
            let mut m68k_bus = CoreM68kBus {
                bus: &mut emu.bus,
                vdp: &mut emu.vdp,
            };
            // M68K byte access uses 1:1 mapping (& 0x7FFF).
            // Consecutive M68K addresses map to consecutive Z80 addresses.
            m68k_bus.write8(0xA0_0000, 0xAA); // Z80 addr 0
            m68k_bus.write8(0xA0_0001, 0xBB); // Z80 addr 1
            m68k_bus.write8(0xA0_0002, 0xCC); // Z80 addr 2
            assert_eq!(m68k_bus.read8(0xA0_0000), 0xAA);
            assert_eq!(m68k_bus.read8(0xA0_0001), 0xBB);
            assert_eq!(m68k_bus.read8(0xA0_0002), 0xCC);
        }
    }
}
