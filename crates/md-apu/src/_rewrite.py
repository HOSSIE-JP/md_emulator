#!/usr/bin/env python3
import os

content = '''use serde::{Deserialize, Serialize};

// Hardware constants
const YM2612_MASTER_CLOCK_HZ: u64 = 7_670_454;
const PSG_MASTER_CLOCK_HZ: f32 = 3_579_545.0;

// Operator address offsets within a channel (hardware slot order)
const YM_OPERATOR_OFFSETS: [usize; 4] = [0x0, 0x8, 0x4, 0xC];

// Bit widths matching real hardware
const PHASE_COUNTER_BITS: u32 = 20;
const PHASE_OUTPUT_BITS: u32 = 10;
const ATTENUATION_BITS: u32 = 10;
const OPERATOR_OUTPUT_BITS: u32 = 14;
const ACCUMULATOR_OUTPUT_BITS: u32 = 16;
const SIN_TABLE_BITS: u32 = 8;
const POW_TABLE_BITS: u32 = 8;
const POW_TABLE_OUTPUT_BITS: u32 = 11;
const CHANNEL_COUNT: usize = 6;
const OPERATOR_COUNT: usize = 4;
const SIN_TABLE_SIZE: usize = 1 << SIN_TABLE_BITS;
const POW_TABLE_SIZE: usize = 1 << POW_TABLE_BITS;

// Max attenuation value (10-bit)
const MAX_ATTENUATION: u32 = (1 << ATTENUATION_BITS) - 1; // 0x3FF

// Envelope counter shift table (64 entries, from hardware analysis)
const COUNTER_SHIFT_TABLE: [u32; 64] = [
    11, 11, 11, 11,  10, 10, 10, 10,   9,  9,  9,  9,   8,  8,  8,  8,
     7,  7,  7,  7,   6,  6,  6,  6,   5,  5,  5,  5,   4,  4,  4,  4,
     3,  3,  3,  3,   2,  2,  2,  2,   1,  1,  1,  1,   0,  0,  0,  0,
     0,  0,  0,  0,   0,  0,  0,  0,   0,  0,  0,  0,   0,  0,  0,  0,
];

// Attenuation increment table (64 rates x 8 cycle positions)
const ATTENUATION_INCREMENT_TABLE: [[u32; 8]; 64] = [
    [0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,0], [0,1,0,1,0,1,0,1], [0,1,0,1,0,1,0,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,0,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,0,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [0,1,0,1,0,1,0,1], [0,1,0,1,1,1,0,1], [0,1,1,1,0,1,1,1], [0,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1], [1,1,1,2,1,1,1,2], [1,2,1,2,1,2,1,2], [1,2,2,2,1,2,2,2],
    [2,2,2,2,2,2,2,2], [2,2,2,4,2,2,2,4], [2,4,2,4,2,4,2,4], [2,4,4,4,2,4,4,4],
    [4,4,4,4,4,4,4,4], [4,4,4,8,4,4,4,8], [4,8,4,8,4,8,4,8], [4,8,8,8,4,8,8,8],
    [8,8,8,8,8,8,8,8], [8,8,8,8,8,8,8,8], [8,8,8,8,8,8,8,8], [8,8,8,8,8,8,8,8],
];

// Detune phase increment table (32 key-codes x 4 detune indices)
const DETUNE_TABLE: [[u32; 4]; 32] = [
    [0, 0, 1, 2], [0, 0, 1, 2], [0, 0, 1, 2], [0, 0, 1, 2],
    [0, 1, 2, 2], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3],
    [0, 1, 2, 4], [0, 1, 3, 4], [0, 1, 3, 4], [0, 1, 3, 5],
    [0, 2, 4, 5], [0, 2, 4, 6], [0, 2, 4, 6], [0, 2, 5, 7],
    [0, 2, 5, 8], [0, 3, 6, 8], [0, 3, 6, 9], [0, 3, 7,10],
    [0, 4, 8,11], [0, 4, 8,12], [0, 4, 9,13], [0, 5,10,14],
    [0, 5,11,16], [0, 6,12,17], [0, 6,13,19], [0, 7,14,20],
    [0, 8,16,22], [0, 8,16,22], [0, 8,16,22], [0, 8,16,22],
];

// LFO period table
const LFO_PERIOD_TABLE: [u32; 8] = [108, 77, 71, 67, 62, 44, 8, 5];

// ADSR phase
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum YmEnvelopePhase {
    Attack,
    Decay,
    Sustain,
    Release,
}

// Operator state (per-operator, integer-based)
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct YmOperator {
    /// 20-bit phase counter
    pub phase_counter: u32,
    /// 10-bit EG attenuation (0 = max volume, 0x3FF = silent)
    pub attenuation: u32,
    /// Previous operator output (14-bit signed, for self-feedback)
    pub prev_output: i32,
    /// ADSR phase
    pub env_phase: YmEnvelopePhase,
    /// Key-on state (current)
    pub key_on: bool,
    /// Key-on state (previous sample, for edge detection)
    pub prev_key_on: bool,
    /// SSG-EG output inversion flag
    pub ssg_output_inverted: bool,
}

impl Default for YmOperator {
    fn default() -> Self {
        Self {
            phase_counter: 0,
            attenuation: MAX_ATTENUATION,
            prev_output: 0,
            env_phase: YmEnvelopePhase::Release,
            key_on: false,
            prev_key_on: false,
            ssg_output_inverted: false,
        }
    }
}

// Channel state
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct YmChannel {
    pub operators: [YmOperator; 4],
    /// Operator outputs from last sample (14-bit signed)
    pub operator_output: [i32; 4],
    /// Self-feedback buffer for operator 1 (two samples)
    pub feedback_buffer: [i32; 2],
    /// L/R panning
    pub pan_left: bool,
    pub pan_right: bool,
}

impl Default for YmChannel {
    fn default() -> Self {
        Self {
            operators: [YmOperator::default(); 4],
            operator_output: [0; 4],
            feedback_buffer: [0; 2],
            pan_left: true,
            pan_right: true,
        }
    }
}

// YM2612 state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Ym2612 {
    pub regs_port0: Vec<u8>,
    pub regs_port1: Vec<u8>,
    pub channels: [YmChannel; 6],
    pub dac_enabled: bool,
    pub dac_data: u8,
    /// Envelope generator cycle counter (global)
    pub envelope_cycle_counter: u32,
    /// LFO counter
    pub lfo_counter: u32,
    /// Cycles until next LFO increment
    pub lfo_cycles_remaining: u32,
    /// Hardware lookup tables (computed at init)
    pub sin_table: Vec<u32>,
    pub pow_table: Vec<u32>,
}

impl Default for Ym2612 {
    fn default() -> Self {
        let (sin_table, pow_table) = build_lookup_tables();
        Self {
            regs_port0: vec![0; 0x100],
            regs_port1: vec![0; 0x100],
            channels: [YmChannel::default(); 6],
            dac_enabled: false,
            dac_data: 0x80,
            envelope_cycle_counter: 0,
            lfo_counter: 0,
            lfo_cycles_remaining: LFO_PERIOD_TABLE[0],
            sin_table,
            pow_table,
        }
    }
}

/// Build sin/pow lookup tables matching hardware
fn build_lookup_tables() -> (Vec<u32>, Vec<u32>) {
    let mut sin_table = vec![0u32; SIN_TABLE_SIZE];
    let mut pow_table = vec![0u32; POW_TABLE_SIZE];

    // Sin table: 256 entries, 4.8 fixed-point attenuation
    for i in 0..SIN_TABLE_SIZE {
        let phase_normalized = ((i << 1) + 1) as f64 / (1 << (SIN_TABLE_BITS + 1)) as f64;
        let sin_result = (phase_normalized * std::f64::consts::FRAC_PI_2).sin();
        let sin_as_attenuation = -(sin_result.log2());
        let fixed_bits = 8u32;
        sin_table[i] = ((sin_as_attenuation * (1u64 << fixed_bits) as f64) + 0.5) as u32;
    }

    // Pow table: 256 entries, 11-bit result
    for i in 0..POW_TABLE_SIZE {
        let entry_normalized = (i + 1) as f64 / (1 << POW_TABLE_BITS) as f64;
        let result_normalized = 2.0_f64.powf(-entry_normalized);
        pow_table[i] = ((result_normalized * (1u64 << POW_TABLE_OUTPUT_BITS) as f64) + 0.5) as u32;
    }

    (sin_table, pow_table)
}

// PSG (SN76489)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Psg {
    pub tone_period: [u16; 3],
    pub noise_control: u8,
    pub volume: [u8; 4],
    pub phase: [f32; 3],
    pub noise_phase: f32,
    pub noise_lfsr: u16,
    pub noise_output: f32,
    pub latched_channel: usize,
    pub latched_is_volume: bool,
}

impl Default for Psg {
    fn default() -> Self {
        Self {
            tone_period: [0x200, 0x200, 0x200],
            noise_control: 0,
            volume: [0x0F, 0x0F, 0x0F, 0x0F],
            phase: [0.0; 3],
            noise_phase: 0.0,
            noise_lfsr: 0x8000,
            noise_output: 1.0,
            latched_channel: 0,
            latched_is_volume: false,
        }
    }
}

// APU (top-level)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Apu {
    pub sample_rate: u32,
    pub audio_buffer: Vec<f32>,
    pub ym2612: Ym2612,
    pub psg: Psg,
    pub cycle_accumulator: u64,
}

impl Default for Apu {
    fn default() -> Self {
        Self {
            sample_rate: 48_000,
            audio_buffer: Vec::new(),
            ym2612: Ym2612::default(),
            psg: Psg::default(),
            cycle_accumulator: 0,
        }
    }
}

// ============================================================================
// Pure functions: KeyCode, Rate, Attenuation conversions
// ============================================================================

/// Calculate 5-bit KeyCode from block and fnum
fn calculate_key_code(block: u32, fnum: u32) -> u32 {
    let f11 = (fnum >> 10) & 1;
    let f10 = (fnum >> 9) & 1;
    let f9 = (fnum >> 8) & 1;
    let f8 = (fnum >> 7) & 1;
    let n4 = f11;
    let n3 = (f11 & (f10 | f9 | f8)) | ((f11 ^ 1) & f10 & f9 & f8);
    (block << 2) | (n4 << 1) | n3
}

/// Calculate effective rate (6-bit) from rate data and key-scale
fn calculate_rate(rate_data: u32, rate_key_scale: u32) -> u32 {
    if rate_data == 0 {
        return 0;
    }
    let rate = (2 * rate_data) + rate_key_scale;
    rate.min(63)
}

/// Calculate rate key-scale from KS data (2-bit) and key code (5-bit)
fn calculate_rate_key_scale(key_scale: u32, key_code: u32) -> u32 {
    key_code >> (3 - key_scale)
}

/// Convert TL (7-bit) to 10-bit attenuation
fn convert_tl_to_attenuation(tl: u32) -> u32 {
    tl << 3
}

/// Convert SL (4-bit) to 10-bit attenuation
fn convert_sl_to_attenuation(sl: u32) -> u32 {
    let sl = if sl == 0x0F { sl | 0x10 } else { sl };
    sl << 5
}

/// InversePow2: convert 5.8 fixed-point log attenuation to linear power
fn inverse_pow2(pow_table: &[u32], num: u32) -> u32 {
    let shift_count = num >> POW_TABLE_BITS;
    let table_index = (num & ((1 << POW_TABLE_BITS) - 1)) as usize;
    let table_index = table_index.min(pow_table.len() - 1);
    let table_entry = pow_table[table_index];
    (table_entry << 2) >> shift_count
}

/// Calculate operator output: phase (10-bit) + phase modulation -> 14-bit signed output
fn calculate_operator(sin_table: &[u32], pow_table: &[u32], phase: u32, phase_modulation: i32, attenuation: u32) -> i32 {
    // If fully attenuated, output is zero
    if attenuation >= MAX_ATTENUATION {
        return 0;
    }

    // Combine phase and modulation (10-bit wrap)
    let combined_phase = ((phase as i32 + phase_modulation) as u32) & ((1 << PHASE_OUTPUT_BITS) - 1);

    // Extract sign bit (bit 9) and slope bit (bit 8)
    let sign_bit = (combined_phase >> (PHASE_OUTPUT_BITS - 1)) & 1;
    let slope_bit = (combined_phase >> (PHASE_OUTPUT_BITS - 2)) & 1;

    // Quarter phase (lower 8 bits)
    let mut quarter_phase = combined_phase & ((1 << (PHASE_OUTPUT_BITS - 2)) - 1);
    if slope_bit != 0 {
        quarter_phase = (!quarter_phase) & ((1 << (PHASE_OUTPUT_BITS - 2)) - 1);
    }

    // Lookup sin value (4.8 fixed-point attenuation)
    let sin_value = sin_table[quarter_phase as usize];

    // Convert envelope attenuation from 4.6 to 4.8 fixed-point
    let converted_attenuation = attenuation << 2;

    // Combined attenuation (5.8 fixed-point)
    let combined_attenuation = sin_value + converted_attenuation;

    // Clamp before pow lookup to avoid shift overflow
    if combined_attenuation >= (1 << 13) {
        return 0;
    }

    // Convert log attenuation to linear power
    let mut pow_result = inverse_pow2(pow_table, combined_attenuation) as i32;

    // Apply sign
    if sign_bit != 0 {
        pow_result = -pow_result;
    }

    pow_result
}

// ============================================================================
// Register accessors
// ============================================================================

impl Ym2612 {
    fn regs(&self, channel: usize) -> (&[u8], usize) {
        if channel < 3 {
            (&self.regs_port0, channel)
        } else {
            (&self.regs_port1, channel - 3)
        }
    }

    fn op_reg(&self, channel: usize, operator: usize, base: u8) -> u8 {
        let (regs, slot) = self.regs(channel);
        regs[(base as usize) + YM_OPERATOR_OFFSETS[operator] + slot]
    }

    fn ch_reg(&self, channel: usize, base: u8) -> u8 {
        let (regs, slot) = self.regs(channel);
        regs[base as usize + slot]
    }

    fn get_detune(&self, ch: usize, op: usize) -> u32 {
        ((self.op_reg(ch, op, 0x30) >> 4) & 0x07) as u32
    }
    fn get_multiple(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x30) & 0x0F) as u32
    }
    fn get_total_level(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x40) & 0x7F) as u32
    }
    fn get_key_scale(&self, ch: usize, op: usize) -> u32 {
        ((self.op_reg(ch, op, 0x50) >> 6) & 0x03) as u32
    }
    fn get_attack_rate(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x50) & 0x1F) as u32
    }
    fn get_am_enabled(&self, ch: usize, op: usize) -> bool {
        (self.op_reg(ch, op, 0x60) & 0x80) != 0
    }
    fn get_decay_rate(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x60) & 0x1F) as u32
    }
    fn get_sustain_rate(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x70) & 0x1F) as u32
    }
    fn get_sustain_level(&self, ch: usize, op: usize) -> u32 {
        ((self.op_reg(ch, op, 0x80) >> 4) & 0x0F) as u32
    }
    fn get_release_rate(&self, ch: usize, op: usize) -> u32 {
        (self.op_reg(ch, op, 0x80) & 0x0F) as u32
    }
    fn get_ssg_enabled(&self, ch: usize, op: usize) -> bool {
        (self.op_reg(ch, op, 0x90) & 0x08) != 0
    }
    fn get_ssg_attack(&self, ch: usize, op: usize) -> bool {
        (self.op_reg(ch, op, 0x90) & 0x04) != 0
    }
    fn get_ssg_alternate(&self, ch: usize, op: usize) -> bool {
        (self.op_reg(ch, op, 0x90) & 0x02) != 0
    }
    fn get_ssg_hold(&self, ch: usize, op: usize) -> bool {
        (self.op_reg(ch, op, 0x90) & 0x01) != 0
    }

    fn get_fnum(&self, ch: usize) -> u32 {
        let (regs, slot) = self.regs(ch);
        let low = regs[0xA0 + slot] as u32;
        let high = regs[0xA4 + slot] as u32;
        ((high & 0x07) << 8) | low
    }
    fn get_block(&self, ch: usize) -> u32 {
        let (regs, slot) = self.regs(ch);
        ((regs[0xA4 + slot] >> 3) & 0x07) as u32
    }
    fn get_algorithm(&self, ch: usize) -> u32 {
        (self.ch_reg(ch, 0xB0) & 0x07) as u32
    }
    fn get_feedback(&self, ch: usize) -> u32 {
        ((self.ch_reg(ch, 0xB0) >> 3) & 0x07) as u32
    }
    fn get_output_left(&self, ch: usize) -> bool {
        (self.ch_reg(ch, 0xB4) & 0x80) != 0
    }
    fn get_output_right(&self, ch: usize) -> bool {
        (self.ch_reg(ch, 0xB4) & 0x40) != 0
    }
    fn get_ams(&self, ch: usize) -> u32 {
        ((self.ch_reg(ch, 0xB4) >> 4) & 0x03) as u32
    }
    fn get_lfo_enabled(&self) -> bool {
        (self.regs_port0[0x22] & 0x08) != 0
    }
    fn get_lfo_freq(&self) -> u32 {
        (self.regs_port0[0x22] & 0x07) as u32
    }
}

// ============================================================================
// APU implementation
// ============================================================================

impl Apu {
    pub fn reset(&mut self) {
        *self = Self::default();
    }

    pub fn step_cycles(&mut self, cycles: u32) {
        if cycles == 0 {
            return;
        }
        self.cycle_accumulator += cycles as u64 * self.sample_rate as u64;
        let sample_count = (self.cycle_accumulator / YM2612_MASTER_CLOCK_HZ) as usize;
        self.cycle_accumulator %= YM2612_MASTER_CLOCK_HZ;
        if sample_count == 0 {
            return;
        }

        for _ in 0..sample_count {
            let (fm_left, fm_right) = self.next_fm_sample();
            let (psg_left, psg_right) = self.next_psg_sample();
            self.audio_buffer.push((fm_left + psg_left).clamp(-1.0, 1.0));
            self.audio_buffer.push((fm_right + psg_right).clamp(-1.0, 1.0));
        }
    }

    pub fn write_ym2612(&mut self, port: u8, address: u8, data: u8) {
        let regs = match port {
            0 => &mut self.ym2612.regs_port0,
            1 => &mut self.ym2612.regs_port1,
            _ => return,
        };
        regs[address as usize] = data;

        // Key-on/off (register 0x28, always port 0)
        if address == 0x28 {
            let ch_bits = data & 0x07;
            let channel = match ch_bits & 0x03 {
                0 => 0usize,
                1 => 1,
                2 => 2,
                _ => return, // 3 is invalid
            };
            let channel = if (ch_bits & 0x04) != 0 { channel + 3 } else { channel };

            let channel_ref = &mut self.ym2612.channels[channel];
            for op in 0..4 {
                let key_on = (data & (0x10 << op)) != 0;
                let operator = &mut channel_ref.operators[op];
                if key_on && !operator.key_on {
                    // Key on: reset phase, set attack phase
                    operator.phase_counter = 0;
                    operator.ssg_output_inverted = false;
                    operator.env_phase = YmEnvelopePhase::Attack;
                    operator.attenuation = MAX_ATTENUATION;
                } else if !key_on && operator.key_on {
                    // Key off: transition to release
                    operator.env_phase = YmEnvelopePhase::Release;
                }
                operator.key_on = key_on;
            }
            return;
        }

        // DAC enable
        if address == 0x2B {
            self.ym2612.dac_enabled = (data & 0x80) != 0;
            return;
        }
        // DAC data
        if address == 0x2A {
            self.ym2612.dac_data = data;
            return;
        }

        // LFO register
        if address == 0x22 {
            if !self.ym2612.get_lfo_enabled() {
                self.ym2612.lfo_counter = 0;
            }
            return;
        }

        // Panning update
        if (0xB4..=0xB6).contains(&address) {
            let channel = port as usize * 3 + (address - 0xB4) as usize;
            if channel < 6 {
                let left = (data & 0x80) != 0;
                let right = (data & 0x40) != 0;
                let ch = &mut self.ym2612.channels[channel];
                ch.pan_left = left || !right;
                ch.pan_right = right || !left;
            }
        }
    }

    pub fn write_psg(&mut self, data: u8) {
        if (data & 0x80) != 0 {
            self.psg.latched_channel = ((data >> 5) & 0x03) as usize;
            self.psg.latched_is_volume = (data & 0x10) != 0;

            if self.psg.latched_is_volume {
                self.psg.volume[self.psg.latched_channel] = data & 0x0F;
            } else if self.psg.latched_channel < 3 {
                let current = self.psg.tone_period[self.psg.latched_channel] & 0x3F0;
                self.psg.tone_period[self.psg.latched_channel] = current | (data as u16 & 0x0F);
            } else {
                self.psg.noise_control = data & 0x07;
                if (self.psg.noise_control & 0x04) == 0 {
                    self.psg.noise_lfsr = 0x8000;
                }
            }
        } else if self.psg.latched_is_volume {
            self.psg.volume[self.psg.latched_channel] = data & 0x0F;
        } else if self.psg.latched_channel < 3 {
            let low = self.psg.tone_period[self.psg.latched_channel] & 0x0F;
            self.psg.tone_period[self.psg.latched_channel] = low | (((data & 0x3F) as u16) << 4);
        }
    }

    pub fn take_samples(&mut self, count_stereo_frames: usize) -> Vec<f32> {
        let sample_count = count_stereo_frames * 2;
        let n = sample_count.min(self.audio_buffer.len());
        self.audio_buffer.drain(..n).collect()
    }

    // ========================================================================
    // FM synthesis (hardware-accurate integer pipeline)
    // ========================================================================

    fn next_fm_sample(&mut self) -> (f32, f32) {
        // Advance LFO
        if self.ym2612.get_lfo_enabled() {
            if self.ym2612.lfo_cycles_remaining == 0 {
                self.ym2612.lfo_counter = (self.ym2612.lfo_counter + 1) & 0x7F;
                self.ym2612.lfo_cycles_remaining = LFO_PERIOD_TABLE[self.ym2612.get_lfo_freq() as usize];
            } else {
                self.ym2612.lfo_cycles_remaining -= 1;
            }
        } else {
            self.ym2612.lfo_counter = 0;
        }

        // Advance envelope cycle counter (3 samples per EG update)
        let update_eg = (self.ym2612.envelope_cycle_counter % 3) == 0;
        self.ym2612.envelope_cycle_counter = self.ym2612.envelope_cycle_counter.wrapping_add(1);

        let mut total_left: i32 = 0;
        let mut total_right: i32 = 0;

        // Copy tables to avoid borrow issues
        let sin_table = self.ym2612.sin_table.clone();
        let pow_table = self.ym2612.pow_table.clone();
        let lfo_counter = self.ym2612.lfo_counter;
        let eg_counter = self.ym2612.envelope_cycle_counter;

        for ch_idx in 0..CHANNEL_COUNT {
            let fnum = self.ym2612.get_fnum(ch_idx);
            let block = self.ym2612.get_block(ch_idx);
            let algorithm = self.ym2612.get_algorithm(ch_idx);
            let feedback = self.ym2612.get_feedback(ch_idx);
            let key_code = calculate_key_code(block, fnum);

            // Update all 4 operators: phase + envelope
            for op_idx in 0..OPERATOR_COUNT {
                // --- Phase generator ---
                let detune_raw = self.ym2612.get_detune(ch_idx, op_idx);
                let mul = self.ym2612.get_multiple(ch_idx, op_idx);

                let mut phase_increment = if block == 0 {
                    fnum >> 1
                } else {
                    fnum << (block - 1)
                };

                // Apply detune (before multiplier)
                let detune_index = detune_raw & 0x03;
                let detune_negative = (detune_raw >> 2) != 0;
                let detune_increment = DETUNE_TABLE[key_code.min(31) as usize][detune_index as usize];
                if detune_negative {
                    phase_increment = phase_increment.wrapping_sub(detune_increment);
                } else {
                    phase_increment = phase_increment.wrapping_add(detune_increment);
                }
                phase_increment &= (1 << 17) - 1;

                // Apply multiplier
                if mul == 0 {
                    phase_increment >>= 1;
                } else {
                    phase_increment *= mul;
                }
                phase_increment &= (1 << PHASE_COUNTER_BITS) - 1;

                // Advance phase counter
                let operator = &mut self.ym2612.channels[ch_idx].operators[op_idx];
                operator.phase_counter = (operator.phase_counter + phase_increment) & ((1 << PHASE_COUNTER_BITS) - 1);

                // --- Envelope generator ---
                if update_eg {
                    let ks = self.ym2612.get_key_scale(ch_idx, op_idx);
                    let rks = calculate_rate_key_scale(ks, key_code);
                    self.update_envelope(ch_idx, op_idx, rks, eg_counter);
                }

                // Update prev_key_on
                let operator = &mut self.ym2612.channels[ch_idx].operators[op_idx];
                operator.prev_key_on = operator.key_on;
            }

            // --- Compute operator outputs ---
            let phases: [u32; 4] = std::array::from_fn(|op| {
                self.ym2612.channels[ch_idx].operators[op].phase_counter >> (PHASE_COUNTER_BITS - PHASE_OUTPUT_BITS)
            });

            let attenuations: [u32; 4] = std::array::from_fn(|op| {
                self.get_output_attenuation(ch_idx, op, lfo_counter)
            });

            let fb = feedback;

            // Operator 1 (with self-feedback)
            let fb_buf = self.ym2612.channels[ch_idx].feedback_buffer;
            let pm_op1 = if fb > 0 {
                let raw = fb_buf[0].wrapping_add(fb_buf[1]);
                raw >> (10 - fb as i32)
            } else {
                0
            };
            let out1 = calculate_operator(&sin_table, &pow_table, phases[0], pm_op1, attenuations[0]);

            // Store feedback buffer
            self.ym2612.channels[ch_idx].feedback_buffer[0] = self.ym2612.channels[ch_idx].feedback_buffer[1];
            self.ym2612.channels[ch_idx].feedback_buffer[1] = out1;

            // Operator 2
            let pm_op2 = match algorithm {
                0 | 3 | 4 | 5 | 6 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out2 = calculate_operator(&sin_table, &pow_table, phases[1], pm_op2, attenuations[1]);

            // Operator 3
            let pm_op3 = match algorithm {
                0 | 2 => Self::op_to_pm(out2),
                1 => Self::op_to_pm(out1.wrapping_add(out2)),
                5 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out3 = calculate_operator(&sin_table, &pow_table, phases[2], pm_op3, attenuations[2]);

            // Operator 4
            let pm_op4 = match algorithm {
                0 | 1 | 4 => Self::op_to_pm(out3),
                2 => Self::op_to_pm(out1.wrapping_add(out3)),
                3 => Self::op_to_pm(out2.wrapping_add(out3)),
                5 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out4 = calculate_operator(&sin_table, &pow_table, phases[3], pm_op4, attenuations[3]);

            // Store operator outputs
            self.ym2612.channels[ch_idx].operator_output = [out1, out2, out3, out4];

            // --- Accumulator: sum carrier operators ---
            let mut combined: i32 = match algorithm {
                0 | 1 | 2 | 3 => out4,
                4 => out2 + out4,
                5 | 6 => out2 + out3 + out4,
                7 => out1 + out2 + out3 + out4,
                _ => out4,
            };

            // DAC: channel 6 replaced when enabled
            if ch_idx == 5 && self.ym2612.dac_enabled {
                let dac_signed = self.ym2612.dac_data as i32 - 0x80;
                combined = dac_signed << (OPERATOR_OUTPUT_BITS - 8);
            }

            // Shift 14-bit to 16-bit
            combined <<= 2;

            // Clamp to 16-bit signed
            let max_acc = (1i32 << (ACCUMULATOR_OUTPUT_BITS - 1)) - 1;
            combined = combined.clamp(-max_acc, max_acc);

            // Apply L/R panning
            let ch = &self.ym2612.channels[ch_idx];
            if ch.pan_left {
                total_left += combined;
            }
            if ch.pan_right {
                total_right += combined;
            }
        }

        // Normalize
        let norm = ((1i32 << (ACCUMULATOR_OUTPUT_BITS - 1)) - 1) as f32;
        let left = (total_left as f32 / norm / CHANNEL_COUNT as f32).clamp(-1.0, 1.0);
        let right = (total_right as f32 / norm / CHANNEL_COUNT as f32).clamp(-1.0, 1.0);

        (left, right)
    }

    /// Convert 14-bit operator output to 10-bit phase modulation input
    #[inline]
    fn op_to_pm(op_output: i32) -> i32 {
        (op_output >> 1) & ((1 << PHASE_OUTPUT_BITS) - 1) as i32
    }

    /// Get output attenuation for an operator, combining EG + SSG + TL + AM
    fn get_output_attenuation(&self, ch: usize, op: usize, lfo_counter: u32) -> u32 {
        let state = &self.ym2612.channels[ch].operators[op];
        let mut attenuation = state.attenuation;

        // SSG-EG output inversion
        if self.ym2612.get_ssg_enabled(ch, op)
            && state.env_phase != YmEnvelopePhase::Release
            && (state.ssg_output_inverted ^ self.ym2612.get_ssg_attack(ch, op))
        {
            attenuation = (0x200u32.wrapping_sub(attenuation)) & 0x3FF;
        }

        // Add TL
        attenuation += convert_tl_to_attenuation(self.ym2612.get_total_level(ch, op));

        // Amplitude modulation
        if self.ym2612.get_am_enabled(ch, op) {
            let inverted = (lfo_counter & 0x40) == 0;
            let mut am_value = lfo_counter & 0x3F;
            if inverted {
                am_value = (!am_value) & 0x3F;
            }
            let am_shift_values: [u32; 4] = [8, 3, 1, 0];
            let ams = self.ym2612.get_ams(ch) as usize;
            am_value = ((am_value << 1) >> am_shift_values[ams.min(3)]) & 0x7F;
            attenuation += am_value;
        }

        // Clamp to 10-bit
        attenuation.min(MAX_ATTENUATION)
    }

    /// Update envelope generator for one operator
    fn update_envelope(&mut self, ch: usize, op: usize, rks: u32, eg_counter: u32) {
        let state = &self.ym2612.channels[ch].operators[op];

        // Check phase transitions
        match state.env_phase {
            YmEnvelopePhase::Attack => {
                if state.attenuation == 0 {
                    self.ym2612.channels[ch].operators[op].env_phase = YmEnvelopePhase::Decay;
                }
            }
            YmEnvelopePhase::Decay => {
                let sl_attn = convert_sl_to_attenuation(self.ym2612.get_sustain_level(ch, op));
                if self.ym2612.channels[ch].operators[op].attenuation >= sl_attn {
                    self.ym2612.channels[ch].operators[op].env_phase = YmEnvelopePhase::Sustain;
                }
            }
            _ => {}
        }

        // Calculate rate for current phase
        let rate_data = match self.ym2612.channels[ch].operators[op].env_phase {
            YmEnvelopePhase::Attack => self.ym2612.get_attack_rate(ch, op),
            YmEnvelopePhase::Decay => self.ym2612.get_decay_rate(ch, op),
            YmEnvelopePhase::Sustain => self.ym2612.get_sustain_rate(ch, op),
            YmEnvelopePhase::Release => {
                let rr = self.ym2612.get_release_rate(ch, op);
                (rr << 1) | 1
            }
        };
        let rate = calculate_rate(rate_data, rks);

        if rate == 0 {
            return;
        }

        // Check counter shift to see if we update on this cycle
        let counter_shift = COUNTER_SHIFT_TABLE[rate as usize];
        if counter_shift > 0 && (eg_counter & ((1 << counter_shift) - 1)) != 0 {
            return;
        }

        // Get attenuation increment from table
        let update_cycle = if counter_shift > 0 {
            ((eg_counter >> counter_shift) & 0x07) as usize
        } else {
            (eg_counter & 0x07) as usize
        };
        let attenuation_increment = ATTENUATION_INCREMENT_TABLE[rate as usize][update_cycle];

        if attenuation_increment == 0 {
            return;
        }

        let state = &mut self.ym2612.channels[ch].operators[op];
        let current = state.attenuation;

        if state.env_phase == YmEnvelopePhase::Attack {
            if rate >= 62 {
                // Instant attack
                state.attenuation = 0;
            } else {
                // Attack curve: newAtt += (~att * increment) >> 4
                let inverted = (!current) & MAX_ATTENUATION;
                let adjustment = (inverted * attenuation_increment) >> 4;
                if adjustment > current {
                    state.attenuation = 0;
                } else {
                    state.attenuation = current - adjustment;
                }
            }
        } else {
            // Decay/Sustain/Release: linear increment
            let mut new_att = current;
            if self.ym2612.get_ssg_enabled(ch, op) && state.env_phase != YmEnvelopePhase::Release {
                // SSG-EG: 4x speed for decay phases
                if new_att < 0x200 {
                    new_att += 4 * attenuation_increment;
                }
            } else {
                new_att += attenuation_increment;
            }
            state.attenuation = new_att.min(MAX_ATTENUATION);
        }
    }

    // ========================================================================
    // PSG synthesis
    // ========================================================================

    fn psg_volume(level: u8) -> f32 {
        let attenuation = level.min(15);
        if attenuation == 15 {
            0.0
        } else {
            10.0_f32.powf(-(attenuation as f32) * 2.0 / 20.0)
        }
    }

    fn psg_effective_period(raw: u16) -> u16 {
        if raw == 0 { 0x400 } else { raw }
    }

    fn next_psg_sample(&mut self) -> (f32, f32) {
        let mut left = 0.0;
        let mut right = 0.0;

        for ch in 0..3 {
            let tone = Self::psg_effective_period(self.psg.tone_period[ch]) as f32;
            let freq = (PSG_MASTER_CLOCK_HZ / 32.0) / tone;
            let step = (freq / self.sample_rate as f32).clamp(0.0, 0.49);
            self.psg.phase[ch] = (self.psg.phase[ch] + step).fract();
            let square = if self.psg.phase[ch] < 0.5 { 1.0 } else { -1.0 };
            let amp = Self::psg_volume(self.psg.volume[ch]) * 0.10;
            let sample = square * amp;

            match ch {
                0 => {
                    left += sample * 0.85;
                    right += sample * 0.35;
                }
                1 => {
                    left += sample * 0.6;
                    right += sample * 0.6;
                }
                _ => {
                    left += sample * 0.35;
                    right += sample * 0.85;
                }
            }
        }

        let noise_freq = match self.psg.noise_control & 0x03 {
            0 => PSG_MASTER_CLOCK_HZ / 512.0,
            1 => PSG_MASTER_CLOCK_HZ / 1024.0,
            2 => PSG_MASTER_CLOCK_HZ / 2048.0,
            _ => {
                let tone = Self::psg_effective_period(self.psg.tone_period[2]) as f32;
                (PSG_MASTER_CLOCK_HZ / 32.0) / tone
            }
        };
        let noise_step = (noise_freq / self.sample_rate as f32).clamp(0.0, 0.49);
        let previous_phase = self.psg.noise_phase;
        self.psg.noise_phase = (self.psg.noise_phase + noise_step).fract();
        if self.psg.noise_phase < previous_phase {
            let feedback_bit = if (self.psg.noise_control & 0x04) != 0 {
                (self.psg.noise_lfsr ^ (self.psg.noise_lfsr >> 3)) & 1
            } else {
                self.psg.noise_lfsr & 1
            };
            self.psg.noise_lfsr = (self.psg.noise_lfsr >> 1) | (feedback_bit << 15);
            if self.psg.noise_lfsr == 0 {
                self.psg.noise_lfsr = 0x8000;
            }
            self.psg.noise_output = if (self.psg.noise_lfsr & 1) == 0 { 1.0 } else { -1.0 };
        }

        let noise_amp = Self::psg_volume(self.psg.volume[3]) * 0.08;
        let noise_sample = self.psg.noise_output * noise_amp;
        left += noise_sample * 0.65;
        right += noise_sample * 0.65;

        (left.clamp(-1.0, 1.0), right.clamp(-1.0, 1.0))
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generates_stereo_samples() {
        let mut apu = Apu::default();
        apu.step_cycles(1_024);
        assert!(apu.audio_buffer.len() >= 4);
        assert_eq!(apu.audio_buffer.len() % 2, 0);
    }

    #[test]
    fn ym_write_updates_registers() {
        let mut apu = Apu::default();
        apu.write_ym2612(0, 0xA0, 0x40);
        apu.write_ym2612(0, 0xA4, 0x02);
        assert_eq!(apu.ym2612.regs_port0[0xA0], 0x40);
        assert_eq!(apu.ym2612.regs_port0[0xA4], 0x02);
        assert_eq!(apu.ym2612.get_fnum(0), 0x240);
        assert_eq!(apu.ym2612.get_block(0), 0);
    }

    #[test]
    fn take_samples_drains_buffer() {
        let mut apu = Apu::default();
        apu.step_cycles(1_024);
        let before = apu.audio_buffer.len();
        let out = apu.take_samples(1);
        assert_eq!(out.len(), 2);
        assert_eq!(apu.audio_buffer.len(), before - 2);
    }

    #[test]
    fn psg_latch_updates_high_bits() {
        let mut apu = Apu::default();
        apu.write_psg(0x80 | 0x05);
        apu.write_psg(0x1A);
        assert_eq!(apu.psg.tone_period[0], 0x1A5);
    }

    #[test]
    fn reset_state_is_silent() {
        let mut apu = Apu::default();
        apu.step_cycles(5_000);
        assert!(apu.audio_buffer.iter().all(|s| s.abs() < 1.0e-6));
    }

    #[test]
    fn ym_key_on_is_per_operator() {
        let mut apu = Apu::default();
        apu.write_ym2612(0, 0x28, 0x10); // OP1 only on channel 0
        assert!(apu.ym2612.channels[0].operators[0].key_on);
        assert!(!apu.ym2612.channels[0].operators[1].key_on);
        assert!(!apu.ym2612.channels[0].operators[2].key_on);
        assert!(!apu.ym2612.channels[0].operators[3].key_on);
    }

    #[test]
    fn ym_operator_registers_use_hardware_slot_layout() {
        let mut apu = Apu::default();
        apu.write_ym2612(0, 0x38, 0x07); // DT/MUL to slot 0x08
        apu.write_ym2612(0, 0x4C, 0x20); // TL to slot 0x0C
        assert_eq!(apu.ym2612.get_multiple(0, 1), 7);
        assert_eq!(apu.ym2612.get_total_level(0, 3), 0x20);
    }

    #[test]
    fn key_code_calculation() {
        assert_eq!(calculate_key_code(4, 0x400), 19);
        assert_eq!(calculate_key_code(0, 0), 0);
        assert_eq!(calculate_key_code(7, 0x7FF), 31);
    }

    #[test]
    fn rate_calculation() {
        assert_eq!(calculate_rate(0, 15), 0);
        assert_eq!(calculate_rate(31, 0), 62);
        assert_eq!(calculate_rate(31, 31), 63);
    }

    #[test]
    fn sustain_level_conversion() {
        assert_eq!(convert_sl_to_attenuation(0), 0);
        assert_eq!(convert_sl_to_attenuation(1), 0x20);
        assert_eq!(convert_sl_to_attenuation(0x0F), 0x3E0);
    }

    #[test]
    fn sin_table_is_populated() {
        let ym = Ym2612::default();
        assert!(ym.sin_table[0] > 0);
        assert!(ym.sin_table[SIN_TABLE_SIZE - 1] < ym.sin_table[0]);
    }

    #[test]
    fn pow_table_is_populated() {
        let ym = Ym2612::default();
        assert!(ym.pow_table[0] > 0);
        assert!(ym.pow_table[0] > ym.pow_table[POW_TABLE_SIZE - 1]);
    }

    #[test]
    fn dac_replaces_channel6() {
        let mut apu = Apu::default();
        apu.write_ym2612(0, 0x2B, 0x80);
        apu.write_ym2612(0, 0x2A, 0xFF);
        apu.step_cycles(1_024);
        let has_nonzero = apu.audio_buffer.iter().any(|s| s.abs() > 1.0e-6);
        assert!(has_nonzero);
    }

    #[test]
    fn initial_attenuation_is_max() {
        let apu = Apu::default();
        for ch in &apu.ym2612.channels {
            for op in &ch.operators {
                assert_eq!(op.attenuation, MAX_ATTENUATION);
                assert_eq!(op.env_phase, YmEnvelopePhase::Release);
            }
        }
    }
}
'''

path = '/Users/hossie/development/md_emulator/crates/md-apu/src/lib.rs'
with open(path, 'w', newline='\n') as f:
    f.write(content)
print(f"Written {len(content)} bytes to {path}")
