use serde::{Deserialize, Serialize};

// Hardware constants
const YM2612_MASTER_CLOCK_HZ: u64 = 7_670_454;
const PSG_CLOCK_HZ_INT: u64 = 3_579_545;
/// PSG internal divider (master clock / 16 = ~223.7 kHz tick rate)
const PSG_DIVIDER: u64 = 16;

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

// Phase modulation increment table (from Exodus hardware tests)
// [PMS value 0-7][quarter phase 0-7]
const PHASE_MOD_INCREMENT_TABLE: [[u32; 8]; 8] = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 1, 1, 1],
    [0, 0, 0, 1, 1, 1, 2, 2],
    [0, 0, 1, 1, 2, 2, 3, 3],
    [0, 0, 1, 2, 2, 2, 3, 4],
    [0, 0, 2, 3, 4, 4, 5, 6],
    [0, 0, 4, 6, 8, 8,10,12],
    [0, 0, 8,12,16,16,20,24],
];

// CH3 special mode: per-operator frequency register addresses (port0 only)
// [operator] -> (fnum_lsb_addr, block_fnum_msb_addr)
const CH3_OP_FREQ_REGS: [(usize, usize); 4] = [
    (0xA9, 0xAD),  // Operator 1
    (0xAA, 0xAE),  // Operator 2
    (0xA8, 0xAC),  // Operator 3
    (0xA2, 0xA6),  // Operator 4 (same as normal CH3 registers)
];

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
            pan_left: false,
            pan_right: false,
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
    /// Envelope generator cycle counter (global, incremented only on EG update ticks)
    pub envelope_cycle_counter: u32,
    /// EG divider timer (counts down from 2, triggers EG update at 0)
    pub eg_timer: u32,
    /// LFO counter
    pub lfo_counter: u32,
    /// Cycles until next LFO increment
    pub lfo_cycles_remaining: u32,
    /// Hardware lookup tables (computed at init)
    pub sin_table: Vec<u32>,
    pub pow_table: Vec<u32>,
    /// Timer A counter (counts in FM clocks)
    pub timer_a_counter: u32,
    /// Timer B sub-counter (counts in FM clocks)
    pub timer_b_subcounter: u32,
    /// YM2612 status register (bit 0: Timer A overflow, bit 1: Timer B overflow)
    pub status: u8,
    /// Latched frequency data (written on A4-A6, applied on A0-A2)
    /// Per-channel latch: one byte holding the upper frequency/block data
    pub latched_freq_data: [u8; 6],
    pub latched_freq_pending: [bool; 6],
    /// CH3 special mode operator frequency latches (operators 0-2; op3 uses normal channel regs)
    pub latched_freq_ch3: [u8; 3],
    pub latched_freq_ch3_pending: [bool; 3],
    /// Previous timer A/B load bits for edge detection (Exodus: reload on 0→1 transition)
    pub prev_timer_a_load: bool,
    pub prev_timer_b_load: bool,
    /// Debug: write log (first N writes as (port, addr, data))
    #[serde(skip)]
    pub write_log: Vec<(u8, u8, u8)>,
    /// Debug: per-register write count [port*256+addr]
    #[serde(skip)]
    pub write_histogram: Vec<u32>,
}

impl Default for Ym2612 {
    fn default() -> Self {
        let (sin_table, pow_table) = build_lookup_tables();
        let mut regs_port0 = vec![0; 0x100];
        let mut regs_port1 = vec![0; 0x100];
        regs_port0[0xB4] = 0xC0;
        regs_port0[0xB5] = 0xC0;
        regs_port0[0xB6] = 0xC0;
        regs_port1[0xB4] = 0xC0;
        regs_port1[0xB5] = 0xC0;
        regs_port1[0xB6] = 0xC0;
        Self {
            regs_port0,
            regs_port1,
            channels: [YmChannel::default(); 6],
            dac_enabled: false,
            dac_data: 0x80,
            envelope_cycle_counter: 0,
            eg_timer: 0,
            lfo_counter: 0,
            lfo_cycles_remaining: LFO_PERIOD_TABLE[0],
            sin_table,
            pow_table,
            timer_a_counter: 0,
            timer_b_subcounter: 0,
            status: 0,
            latched_freq_data: [0; 6],
            latched_freq_pending: [false; 6],
            latched_freq_ch3: [0; 3],
            latched_freq_ch3_pending: [false; 3],
            prev_timer_a_load: false,
            prev_timer_b_load: false,
            write_log: Vec::new(),
            write_histogram: vec![0; 512],
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

// PSG (SN76489) — integer counter model matching hardware
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Psg {
    pub tone_period: [u16; 3],
    pub noise_control: u8,
    pub volume: [u8; 4],
    /// Tone channel down-counters (hardware: count down from period, toggle on zero)
    pub counter: [u16; 3],
    /// Tone channel output polarity (+1 or -1)
    pub polarity: [i8; 3],
    /// Noise channel down-counter
    pub noise_counter: u16,
    /// Noise LFSR (16-bit, seeded with 0x8000)
    pub noise_lfsr: u16,
    /// Noise output polarity
    pub noise_polarity: i8,
    pub latched_channel: usize,
    pub latched_is_volume: bool,
    /// Fractional accumulator for PSG tick tracking (in Z80 clock units × sample_rate)
    pub tick_accumulator: u64,
}

impl Default for Psg {
    fn default() -> Self {
        Self {
            tone_period: [0x200, 0x200, 0x200],
            noise_control: 0,
            volume: [0x0F, 0x0F, 0x0F, 0x0F],
            counter: [0x200, 0x200, 0x200],
            polarity: [1, 1, 1],
            noise_counter: 0x10,
            noise_lfsr: 0x8000,
            noise_polarity: 1,
            latched_channel: 0,
            latched_is_volume: false,
            tick_accumulator: 0,
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
    /// FM internal tick accumulator (ticks every 144 master clocks)
    pub fm_tick_accumulator: u64,
    /// Timer-only tick accumulator for lightweight Z80-interleaved timer advance
    pub timer_only_accumulator: u64,
    /// FM ticks already advanced by advance_timers() (to avoid double-counting)
    pub timer_preadvanced_ticks: u64,
    /// Last computed FM output (sample-and-hold between ticks)
    pub last_fm_left: f32,
    pub last_fm_right: f32,
    /// Debug: DAC sample count
    #[serde(skip)]
    pub debug_dac_samples: u64,
    /// Debug: DAC nonzero output count
    #[serde(skip)]
    pub debug_dac_nonzero: u64,
    /// Debug: FM nonzero output count
    #[serde(skip)]
    pub debug_fm_nonzero: u64,
    /// Debug: total FM ticks
    #[serde(skip)]
    pub debug_fm_ticks: u64,
    /// Debug: output buffer non-zero count
    #[serde(skip)]
    pub debug_output_nonzero: u64,
    /// Debug: total output samples pushed
    #[serde(skip)]
    pub debug_output_total: u64,
    /// Debug: Timer A overflow count
    #[serde(skip)]
    pub debug_timer_a_overflow_count: u64,
    /// Debug: Timer A flag clear count (reg27 bit4 writes)
    #[serde(skip)]
    pub debug_timer_a_clear_count: u64,
}

impl Default for Apu {
    fn default() -> Self {
        Self {
            sample_rate: 48_000,
            audio_buffer: Vec::new(),
            ym2612: Ym2612::default(),
            psg: Psg::default(),
            cycle_accumulator: 0,
            fm_tick_accumulator: 0,
            timer_only_accumulator: 0,
            timer_preadvanced_ticks: 0,
            last_fm_left: 0.0,
            last_fm_right: 0.0,
            debug_dac_samples: 0,
            debug_dac_nonzero: 0,
            debug_fm_nonzero: 0,
            debug_fm_ticks: 0,
            debug_output_nonzero: 0,
            debug_output_total: 0,
            debug_timer_a_overflow_count: 0,
            debug_timer_a_clear_count: 0,
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

    pub fn get_fnum(&self, ch: usize) -> u32 {
        let (regs, slot) = self.regs(ch);
        let low = regs[0xA0 + slot] as u32;
        let high = regs[0xA4 + slot] as u32;
        ((high & 0x07) << 8) | low
    }
    pub fn get_block(&self, ch: usize) -> u32 {
        let (regs, slot) = self.regs(ch);
        ((regs[0xA4 + slot] >> 3) & 0x07) as u32
    }
    pub fn get_algorithm(&self, ch: usize) -> u32 {
        (self.ch_reg(ch, 0xB0) & 0x07) as u32
    }
    pub fn get_feedback(&self, ch: usize) -> u32 {
        ((self.ch_reg(ch, 0xB0) >> 3) & 0x07) as u32
    }
    pub fn get_output_left(&self, ch: usize) -> bool {
        (self.ch_reg(ch, 0xB4) & 0x80) != 0
    }
    pub fn get_output_right(&self, ch: usize) -> bool {
        (self.ch_reg(ch, 0xB4) & 0x40) != 0
    }
    fn get_ams(&self, ch: usize) -> u32 {
        ((self.ch_reg(ch, 0xB4) >> 4) & 0x03) as u32
    }
    fn get_pms(&self, ch: usize) -> u32 {
        (self.ch_reg(ch, 0xB4) & 0x07) as u32
    }
    fn get_ch3_mode(&self) -> u32 {
        ((self.regs_port0[0x27] >> 6) & 0x03) as u32
    }
    fn get_ch3_op_fnum(&self, op: usize) -> u32 {
        let (lsb_addr, msb_addr) = CH3_OP_FREQ_REGS[op];
        let low = self.regs_port0[lsb_addr] as u32;
        let high = self.regs_port0[msb_addr] as u32;
        ((high & 0x07) << 8) | low
    }
    fn get_ch3_op_block(&self, op: usize) -> u32 {
        let (_, msb_addr) = CH3_OP_FREQ_REGS[op];
        ((self.regs_port0[msb_addr] >> 3) & 0x07) as u32
    }
    fn get_timer_a_value(&self) -> u32 {
        let msb = (self.regs_port0[0x24] as u32) << 2;
        let lsb = (self.regs_port0[0x25] as u32) & 0x03;
        msb | lsb
    }
    fn get_timer_b_value(&self) -> u32 {
        self.regs_port0[0x26] as u32
    }
    fn get_timer_a_load(&self) -> bool {
        (self.regs_port0[0x27] & 0x01) != 0
    }
    fn get_timer_b_load(&self) -> bool {
        (self.regs_port0[0x27] & 0x02) != 0
    }
    fn get_timer_a_enabled(&self) -> bool {
        (self.regs_port0[0x27] & 0x04) != 0
    }
    fn get_timer_b_enabled(&self) -> bool {
        (self.regs_port0[0x27] & 0x08) != 0
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
        // Advance FM internal ticks (every 144 master clocks = one FM sample period)
        self.fm_tick_accumulator += cycles as u64;
        while self.fm_tick_accumulator >= 144 {
            self.fm_tick_accumulator -= 144;
            let (l, r) = self.next_fm_sample();
            self.last_fm_left = l;
            self.last_fm_right = r;
        }
        // Generate output samples at the configured sample rate
        self.cycle_accumulator += cycles as u64 * self.sample_rate as u64;
        let sample_count = (self.cycle_accumulator / YM2612_MASTER_CLOCK_HZ) as usize;
        self.cycle_accumulator %= YM2612_MASTER_CLOCK_HZ;
        for _ in 0..sample_count {
            let (psg_left, psg_right) = self.next_psg_sample();
            let out_l = (self.last_fm_left + psg_left).clamp(-1.0, 1.0);
            let out_r = (self.last_fm_right + psg_right).clamp(-1.0, 1.0);
            self.debug_output_total += 1;
            if out_l != 0.0 || out_r != 0.0 {
                self.debug_output_nonzero += 1;
            }
            self.audio_buffer.push(out_l);
            self.audio_buffer.push(out_r);
        }
    }

    /// Lightweight timer-only advance for use during Z80 interleaving.
    /// Advances timer counters without doing FM synthesis or audio output.
    /// This keeps Timer A/B status fresh for Z80 polling.
    pub fn advance_timers(&mut self, cycles: u32) {
        if cycles == 0 {
            return;
        }
        self.timer_only_accumulator += cycles as u64;
        while self.timer_only_accumulator >= 144 {
            self.timer_only_accumulator -= 144;
            self.timer_preadvanced_ticks += 1;
            // Timer A
            if self.ym2612.get_timer_a_load() {
                self.ym2612.timer_a_counter += 1;
                let period = 1024u32.saturating_sub(self.ym2612.get_timer_a_value()).max(1);
                while self.ym2612.timer_a_counter >= period {
                    self.ym2612.timer_a_counter -= period;
                    if self.ym2612.get_timer_a_enabled() {
                        self.ym2612.status |= 0x01;
                        self.debug_timer_a_overflow_count += 1;
                    }
                }
            }
            // Timer B
            if self.ym2612.get_timer_b_load() {
                self.ym2612.timer_b_subcounter += 1;
                let period = (16u32 * 256u32.saturating_sub(self.ym2612.get_timer_b_value())).max(1);
                while self.ym2612.timer_b_subcounter >= period {
                    self.ym2612.timer_b_subcounter -= period;
                    if self.ym2612.get_timer_b_enabled() {
                        self.ym2612.status |= 0x02;
                    }
                }
            }
        }
    }

    pub fn write_ym2612(&mut self, port: u8, address: u8, data: u8) {
        // Debug logging
        if self.ym2612.write_log.len() >= 4096 {
            self.ym2612.write_log.remove(0);
        }
        self.ym2612.write_log.push((port, address, data));
        self.ym2612.write_histogram[(port as usize & 1) * 256 + address as usize] += 1;

        // ────────────────────────────────────────────────────────────────────
        // Frequency data latching (Exodus-accurate):
        //   Writing to A4-A6 / AC-AE does NOT write to real registers.
        //   Instead, data is latched and applied atomically when A0-A2 / A8-AA
        //   is subsequently written. This must be handled BEFORE the generic
        //   register store to prevent premature frequency changes.
        // ────────────────────────────────────────────────────────────────────

        // A4-A6: Latch fnum MSB / block (per-channel) — do NOT store to regs
        if (0xA4..=0xA6).contains(&address) {
            let slot = (address - 0xA4) as usize;
            let ch = port as usize * 3 + slot;
            if ch < 6 {
                self.ym2612.latched_freq_data[ch] = data;
                self.ym2612.latched_freq_pending[ch] = true;
            }
            return;
        }

        // AC-AE: CH3 special mode operator frequency latch (port 0 only)
        if port == 0 && (0xAC..=0xAE).contains(&address) {
            let idx = (address - 0xAC) as usize;
            self.ym2612.latched_freq_ch3[idx] = data;
            self.ym2612.latched_freq_ch3_pending[idx] = true;
            return;
        }

        // Generic register store for all non-latched registers
        let regs = match port {
            0 => &mut self.ym2612.regs_port0,
            1 => &mut self.ym2612.regs_port1,
            _ => return,
        };
        regs[address as usize] = data;

        // A0-A2: Apply latched MSB + new LSB atomically
        if (0xA0..=0xA2).contains(&address) {
            let slot = (address - 0xA0) as usize;
            let ch = port as usize * 3 + slot;
            if ch < 6 {
                if self.ym2612.latched_freq_pending[ch] {
                    let regs = if ch < 3 {
                        &mut self.ym2612.regs_port0
                    } else {
                        &mut self.ym2612.regs_port1
                    };
                    let reg_slot = if ch < 3 { ch } else { ch - 3 };
                    regs[0xA4 + reg_slot] = self.ym2612.latched_freq_data[ch];
                    self.ym2612.latched_freq_pending[ch] = false;
                }
            }
            return;
        }

        // A8-AA: CH3 special mode — apply latched MSB + new LSB (port 0 only)
        if port == 0 && (0xA8..=0xAA).contains(&address) {
            let idx = (address - 0xA8) as usize;
            if self.ym2612.latched_freq_ch3_pending[idx] {
                self.ym2612.regs_port0[0xAC + idx] = self.ym2612.latched_freq_ch3[idx];
                self.ym2612.latched_freq_ch3_pending[idx] = false;
            }
            return;
        }

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

            for op in 0..4 {
                let key_on = (data & (0x10 << op)) != 0;
                let prev_key_on = self.ym2612.channels[channel].operators[op].key_on;

                if key_on && !prev_key_on {
                    // Calculate effective attack rate for instant attack check
                    let ar = self.ym2612.get_attack_rate(channel, op);
                    let ks = self.ym2612.get_key_scale(channel, op);
                    let (fnum, block) = if channel == 2 && self.ym2612.get_ch3_mode() != 0 {
                        (self.ym2612.get_ch3_op_fnum(op), self.ym2612.get_ch3_op_block(op))
                    } else {
                        (self.ym2612.get_fnum(channel), self.ym2612.get_block(channel))
                    };
                    let key_code = calculate_key_code(block, fnum);
                    let rks = calculate_rate_key_scale(ks, key_code);
                    let rate = calculate_rate(ar, rks);

                    let operator = &mut self.ym2612.channels[channel].operators[op];
                    operator.phase_counter = 0;
                    operator.ssg_output_inverted = false;
                    operator.env_phase = YmEnvelopePhase::Attack;
                    // Rate >= 62: instant attack (attenuation forced to 0)
                    // Exodus: do NOT reset attenuation for rate < 62.
                    // The attack curve works from the current attenuation.
                    if rate >= 62 {
                        operator.attenuation = 0;
                    }
                } else if !key_on && prev_key_on {
                    // Key off: transition to release
                    // SSG-EG: if output is currently inverted, convert to equivalent non-inverted value
                    let ssg_enabled = self.ym2612.get_ssg_enabled(channel, op);
                    let ssg_attack = self.ym2612.get_ssg_attack(channel, op);
                    let operator = &mut self.ym2612.channels[channel].operators[op];
                    if ssg_enabled && (operator.ssg_output_inverted ^ ssg_attack) {
                        operator.attenuation = (0x200u32.wrapping_sub(operator.attenuation)) & 0x3FF;
                    }
                    operator.env_phase = YmEnvelopePhase::Release;
                }
                self.ym2612.channels[channel].operators[op].key_on = key_on;
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

        // Timer/CH3 mode register (0x27)
        // Exodus: timer counter is reloaded only on load-bit 0→1 transition
        if address == 0x27 {
            // Detect load-bit edge transitions (0→1)
            let new_timer_a_load = (data & 0x01) != 0;
            let new_timer_b_load = (data & 0x02) != 0;

            if new_timer_a_load && !self.ym2612.prev_timer_a_load {
                // Edge 0→1: reload Timer A counter
                self.ym2612.timer_a_counter = 0;
            }
            if new_timer_b_load && !self.ym2612.prev_timer_b_load {
                // Edge 0→1: reload Timer B counter
                self.ym2612.timer_b_subcounter = 0;
            }

            self.ym2612.prev_timer_a_load = new_timer_a_load;
            self.ym2612.prev_timer_b_load = new_timer_b_load;

            // Timer A reset: clear overflow flag
            if (data & 0x10) != 0 {
                self.ym2612.status &= !0x01u8;
                self.debug_timer_a_clear_count += 1;
            }
            // Timer B reset: clear overflow flag
            if (data & 0x20) != 0 {
                self.ym2612.status &= !0x02u8;
            }
            return;
        }

        // Panning update
        if (0xB4..=0xB6).contains(&address) {
            let channel = port as usize * 3 + (address - 0xB4) as usize;
            if channel < 6 {
                let ch = &mut self.ym2612.channels[channel];
                ch.pan_left = (data & 0x80) != 0;
                ch.pan_right = (data & 0x40) != 0;
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
        // Cap buffer at 2× requested to keep latency under ~33ms.
        // Discard oldest samples when buffer exceeds this limit.
        let max_buffered = sample_count * 2;
        if self.audio_buffer.len() > max_buffered {
            let skip = self.audio_buffer.len() - max_buffered;
            // Ensure skip is even (stereo pairs)
            let skip = skip & !1;
            self.audio_buffer.drain(..skip);
        }
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

        // EG divider: update envelope generator every 3 FM ticks (matching hardware)
        let update_eg = self.ym2612.eg_timer == 0;
        if update_eg {
            self.ym2612.envelope_cycle_counter = self.ym2612.envelope_cycle_counter.wrapping_add(1);
        }
        self.ym2612.eg_timer = if update_eg { 2 } else { self.ym2612.eg_timer - 1 };

        // Timer A: increments once per FM output clock (timerAClockDivider=1)
        // Skip if this tick was already advanced by advance_timers()
        if self.timer_preadvanced_ticks > 0 {
            self.timer_preadvanced_ticks -= 1;
        } else {
            if self.ym2612.get_timer_a_load() {
                self.ym2612.timer_a_counter += 1;
                let period = 1024u32.saturating_sub(self.ym2612.get_timer_a_value()).max(1);
                while self.ym2612.timer_a_counter >= period {
                    self.ym2612.timer_a_counter -= period;
                    if self.ym2612.get_timer_a_enabled() {
                        self.ym2612.status |= 0x01;
                        self.debug_timer_a_overflow_count += 1;
                    }
                }
            }
            // Timer B: increments once per FM output clock, with ×16 prescaler (timerBClockDivider=16)
            if self.ym2612.get_timer_b_load() {
                self.ym2612.timer_b_subcounter += 1;
                let period = (16u32 * 256u32.saturating_sub(self.ym2612.get_timer_b_value())).max(1);
                while self.ym2612.timer_b_subcounter >= period {
                    self.ym2612.timer_b_subcounter -= period;
                    if self.ym2612.get_timer_b_enabled() {
                        self.ym2612.status |= 0x02;
                    }
                }
            }
        }

        let mut total_left: i32 = 0;
        let mut total_right: i32 = 0;
        let mut fm_left: i32 = 0;
        let mut fm_right: i32 = 0;

        let lfo_counter = self.ym2612.lfo_counter;
        let eg_counter = self.ym2612.envelope_cycle_counter;

        for ch_idx in 0..CHANNEL_COUNT {
            let ch_fnum = self.ym2612.get_fnum(ch_idx);
            let ch_block = self.ym2612.get_block(ch_idx);
            let algorithm = self.ym2612.get_algorithm(ch_idx);
            let feedback = self.ym2612.get_feedback(ch_idx);
            let ch3_mode = self.ym2612.get_ch3_mode();
            let pms = self.ym2612.get_pms(ch_idx);
            let pan_left = self.ym2612.get_output_left(ch_idx);
            let pan_right = self.ym2612.get_output_right(ch_idx);

            // Update all 4 operators: phase + envelope
            for op_idx in 0..OPERATOR_COUNT {
                // Get per-operator frequency (CH3 special mode)
                let (op_fnum, op_block) = if ch_idx == 2 && ch3_mode != 0 {
                    (self.ym2612.get_ch3_op_fnum(op_idx), self.ym2612.get_ch3_op_block(op_idx))
                } else {
                    (ch_fnum, ch_block)
                };

                // EG key code uses raw (non-PM) frequency
                let eg_key_code = calculate_key_code(op_block, op_fnum);

                // Apply LFO Phase Modulation to frequency data
                let mut freq_data = op_fnum;
                let pm_counter_raw = (lfo_counter >> 2) & 0x1F;
                if pm_counter_raw != 0 && pms != 0 {
                    let pm_inverted = (pm_counter_raw >> 4) != 0;
                    let pm_slope_negative = ((pm_counter_raw >> 3) & 1) != 0;
                    let mut quarter_phase = pm_counter_raw & 0x07;
                    if pm_slope_negative {
                        quarter_phase = (!quarter_phase) & 0x07;
                    }
                    let mut pm_increment: i32 = 0;
                    for i in 0..11u32 {
                        if (freq_data & (1 << i)) != 0 {
                            let pm_value = PHASE_MOD_INCREMENT_TABLE[pms as usize][quarter_phase as usize];
                            pm_increment += (pm_value as i32) << i;
                        }
                    }
                    pm_increment >>= 9;
                    if pm_inverted {
                        pm_increment = -pm_increment;
                    }
                    freq_data = ((freq_data as i32 + pm_increment) as u32) & 0x7FF;
                }

                // Phase key code uses PM'd frequency (affects detune)
                let phase_key_code = calculate_key_code(op_block, freq_data);

                // --- Phase generator ---
                let detune_raw = self.ym2612.get_detune(ch_idx, op_idx);
                let mul = self.ym2612.get_multiple(ch_idx, op_idx);

                let mut phase_increment = if op_block == 0 {
                    freq_data >> 1
                } else {
                    freq_data << (op_block - 1)
                };

                // Apply detune (before multiplier)
                let detune_index = detune_raw & 0x03;
                let detune_negative = (detune_raw >> 2) != 0;
                let detune_increment = DETUNE_TABLE[phase_key_code.min(31) as usize][detune_index as usize];
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

                // --- SSG-EG per-sample state machine (runs every sample, before EG update) ---
                let ssg_enabled = self.ym2612.get_ssg_enabled(ch_idx, op_idx);
                if ssg_enabled {
                    // Read SSG-EG register values before taking mutable borrow
                    let ssg_alternate = self.ym2612.get_ssg_alternate(ch_idx, op_idx);
                    let ssg_hold = self.ym2612.get_ssg_hold(ch_idx, op_idx);
                    let ssg_attack = self.ym2612.get_ssg_attack(ch_idx, op_idx);

                    let op_state = &mut self.ym2612.channels[ch_idx].operators[op_idx];
                    if op_state.attenuation >= 0x200 {
                        // Toggle inversion state for alternating patterns
                        if ssg_alternate && (!ssg_hold || !op_state.ssg_output_inverted) {
                            op_state.ssg_output_inverted = !op_state.ssg_output_inverted;
                        }

                        if op_state.env_phase != YmEnvelopePhase::Attack {
                            if op_state.env_phase != YmEnvelopePhase::Release && !ssg_hold {
                                // Loop back to attack phase
                                op_state.env_phase = YmEnvelopePhase::Attack;
                                // Check rate >= 62 for instant attack
                                let ar = self.ym2612.get_attack_rate(ch_idx, op_idx);
                                let ks = self.ym2612.get_key_scale(ch_idx, op_idx);
                                let rks = calculate_rate_key_scale(ks, eg_key_code);
                                let rate = calculate_rate(ar, rks);
                                if rate >= 62 {
                                    self.ym2612.channels[ch_idx].operators[op_idx].attenuation = 0;
                                }
                            } else if op_state.env_phase == YmEnvelopePhase::Release
                                || !(op_state.ssg_output_inverted ^ ssg_attack)
                            {
                                // Force attenuation to max
                                op_state.attenuation = 0x3FF;
                            }
                        }
                    }
                    // Hold phase counter at 0 when SSG non-alt, non-hold, att >= 0x200
                    let op_state = &mut self.ym2612.channels[ch_idx].operators[op_idx];
                    if !ssg_alternate && !ssg_hold && op_state.attenuation >= 0x200 {
                        op_state.phase_counter = 0;
                    }
                }

                // --- Envelope generator ---
                if update_eg {
                    let ks = self.ym2612.get_key_scale(ch_idx, op_idx);
                    let rks = calculate_rate_key_scale(ks, eg_key_code);
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
                // Exodus: shift then mask to PHASE_OUTPUT_BITS before use as phase modulation
                (raw >> (10 - fb as i32)) & ((1 << PHASE_OUTPUT_BITS) - 1) as i32
            } else {
                0
            };
            let out1 = calculate_operator(self.ym2612.sin_table.as_slice(), self.ym2612.pow_table.as_slice(), phases[0], pm_op1, attenuations[0]);

            // Store feedback buffer
            self.ym2612.channels[ch_idx].feedback_buffer[0] = self.ym2612.channels[ch_idx].feedback_buffer[1];
            self.ym2612.channels[ch_idx].feedback_buffer[1] = out1;

            // Operator 2
            let pm_op2 = match algorithm {
                0 | 3 | 4 | 5 | 6 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out2 = calculate_operator(self.ym2612.sin_table.as_slice(), self.ym2612.pow_table.as_slice(), phases[1], pm_op2, attenuations[1]);

            // Operator 3
            let pm_op3 = match algorithm {
                0 | 2 => Self::op_to_pm(out2),
                1 => Self::op_to_pm(out1.wrapping_add(out2)),
                5 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out3 = calculate_operator(self.ym2612.sin_table.as_slice(), self.ym2612.pow_table.as_slice(), phases[2], pm_op3, attenuations[2]);

            // Operator 4
            let pm_op4 = match algorithm {
                0 | 1 | 4 => Self::op_to_pm(out3),
                2 => Self::op_to_pm(out1.wrapping_add(out3)),
                3 => Self::op_to_pm(out2.wrapping_add(out3)),
                5 => Self::op_to_pm(out1),
                _ => 0,
            };
            let out4 = calculate_operator(self.ym2612.sin_table.as_slice(), self.ym2612.pow_table.as_slice(), phases[3], pm_op4, attenuations[3]);

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

            let is_dac_channel = ch_idx == 5 && self.ym2612.dac_enabled;
            if is_dac_channel {
                let dac_signed = self.ym2612.dac_data as i32 - 0x80;
                combined = dac_signed << (OPERATOR_OUTPUT_BITS - 8);
                self.debug_dac_samples += 1;
                if combined != 0 {
                    self.debug_dac_nonzero += 1;
                }
            }

            // Shift 14-bit to 16-bit
            combined <<= 2;

            // Clamp to 16-bit signed
            let max_acc = (1i32 << (ACCUMULATOR_OUTPUT_BITS - 1)) - 1;
            combined = combined.clamp(-max_acc, max_acc);

            // Apply L/R panning
            // Pan Left/Right: read directly from registers (matching hardware)
            if pan_left {
                total_left += combined;
                if !is_dac_channel {
                    fm_left += combined;
                }
            }
            if pan_right {
                total_right += combined;
                if !is_dac_channel {
                    fm_right += combined;
                }
            }
        }

        // Normalize
        let norm = ((1i32 << (ACCUMULATOR_OUTPUT_BITS - 1)) - 1) as f32;
        let left = (total_left as f32 / norm / CHANNEL_COUNT as f32).clamp(-1.0, 1.0);
        let right = (total_right as f32 / norm / CHANNEL_COUNT as f32).clamp(-1.0, 1.0);

        self.debug_fm_ticks += 1;
        if fm_left != 0 || fm_right != 0 {
            self.debug_fm_nonzero += 1;
        }

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

        // Check counter shift to decide if we update on this EG cycle.
        // Exodus: `if ((_envelopeCycleCounter % (1 << counterShiftValue)) == 0)`
        // The increment is only applied when the counter is divisible by (1 << shift).
        let counter_shift = COUNTER_SHIFT_TABLE[rate as usize];
        if (eg_counter % (1u32 << counter_shift)) != 0 {
            return;
        }
        let update_cycle = ((eg_counter >> counter_shift) & 0x07) as usize;
        let attenuation_increment = ATTENUATION_INCREMENT_TABLE[rate as usize][update_cycle];

        if attenuation_increment == 0 {
            return;
        }

        // Read SSG state before taking mutable borrow
        let ssg_enabled = self.ym2612.get_ssg_enabled(ch, op);

        let state = &mut self.ym2612.channels[ch].operators[op];
        let current = state.attenuation;

        if state.env_phase == YmEnvelopePhase::Attack {
            if rate < 62 {
                // Attack curve: att += (~att * increment) >> 4
                // Full 32-bit NOT produces a two's complement negative adjustment.
                // The result is masked to 10 bits, matching the hardware Data(10) register.
                let adjustment = (!current).wrapping_mul(attenuation_increment) >> 4;
                let new_att = current.wrapping_add(adjustment);
                state.attenuation = new_att & MAX_ATTENUATION;
            }
            // Rate >= 62 is handled at key-on time (instant attack to 0).
            // If rate changes to 62+ mid-attack, the curve stalls (matching hardware).
        } else {
            // Decay/Sustain/Release: linear increment
            let mut new_att = current;
            if ssg_enabled && state.env_phase != YmEnvelopePhase::Release {
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
        // Calculate how many PSG internal ticks to advance for this output sample.
        // PSG internal clock = Z80_clock / 16.
        // Accumulator tracks fractional ticks: accumulator += PSG_CLOCK_HZ_INT,
        // ticks = accumulator / (sample_rate * PSG_DIVIDER).
        let sr = self.sample_rate as u64;
        self.psg.tick_accumulator += PSG_CLOCK_HZ_INT;
        let ticks = self.psg.tick_accumulator / (sr * PSG_DIVIDER);
        self.psg.tick_accumulator %= sr * PSG_DIVIDER;

        // Determine noise period (in PSG ticks)
        let noise_period: u16 = match self.psg.noise_control & 0x03 {
            0 => 0x10,   // N/512 → period 16
            1 => 0x20,   // N/1024 → period 32
            2 => 0x40,   // N/2048 → period 64
            _ => Self::psg_effective_period(self.psg.tone_period[2]),  // Ch3 period
        };
        let white_noise = (self.psg.noise_control & 0x04) != 0;

        // Advance PSG counters by 'ticks' internal clocks
        for _ in 0..ticks {
            // Tone channels
            for ch in 0..3 {
                if self.psg.counter[ch] > 0 {
                    self.psg.counter[ch] -= 1;
                }
                if self.psg.counter[ch] == 0 {
                    let period = Self::psg_effective_period(self.psg.tone_period[ch]);
                    self.psg.counter[ch] = period;
                    self.psg.polarity[ch] = -self.psg.polarity[ch];
                }
            }
            // Noise channel
            if self.psg.noise_counter > 0 {
                self.psg.noise_counter -= 1;
            }
            if self.psg.noise_counter == 0 {
                self.psg.noise_counter = noise_period.max(1);
                // Advance LFSR on each period expiry
                let feedback_bit = if white_noise {
                    (self.psg.noise_lfsr ^ (self.psg.noise_lfsr >> 3)) & 1
                } else {
                    self.psg.noise_lfsr & 1
                };
                self.psg.noise_lfsr = (self.psg.noise_lfsr >> 1) | (feedback_bit << 15);
                if self.psg.noise_lfsr == 0 {
                    self.psg.noise_lfsr = 0x8000;
                }
                self.psg.noise_polarity = if (self.psg.noise_lfsr & 1) == 0 { 1 } else { -1 };
            }
        }

        // Mix output from current polarity states
        let mut left: f32 = 0.0;
        let mut right: f32 = 0.0;

        for ch in 0..3 {
            let amp = Self::psg_volume(self.psg.volume[ch]) * 0.10;
            // Period 0 or 1 produces a constant high output (hardware behavior)
            let out = if self.psg.tone_period[ch] <= 1 {
                amp
            } else {
                self.psg.polarity[ch] as f32 * amp
            };
            match ch {
                0 => { left += out * 0.85; right += out * 0.35; }
                1 => { left += out * 0.6; right += out * 0.6; }
                _ => { left += out * 0.35; right += out * 0.85; }
            }
        }

        let noise_amp = Self::psg_volume(self.psg.volume[3]) * 0.08;
        let noise_sample = self.psg.noise_polarity as f32 * noise_amp;
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
        // Write A4 first (MSB goes to latch, not to regs)
        apu.write_ym2612(0, 0xA4, 0x02);
        assert_eq!(apu.ym2612.regs_port0[0xA4], 0, "A4 should NOT be written to regs (latched)");
        // Write A0 (LSB) — this triggers atomic apply of latched A4
        apu.write_ym2612(0, 0xA0, 0x40);
        assert_eq!(apu.ym2612.regs_port0[0xA0], 0x40);
        assert_eq!(apu.ym2612.regs_port0[0xA4], 0x02, "A4 applied atomically on A0 write");
        assert_eq!(apu.ym2612.get_fnum(0), 0x240);
        assert_eq!(apu.ym2612.get_block(0), 0);
    }

    #[test]
    fn take_samples_drains_buffer() {
        let mut apu = Apu::default();
        apu.step_cycles(1_024);
        let before = apu.audio_buffer.len();
        // Request enough stereo frames to avoid buffer-skip logic
        let request = before / 2;
        let out = apu.take_samples(request);
        assert_eq!(out.len(), before);
        assert_eq!(apu.audio_buffer.len(), 0);
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
        // block=4, fnum=0x400: F11=1, F10=F9=F8=0 → N4=1, N3=0 → (4<<2)|2|0=18
        assert_eq!(calculate_key_code(4, 0x400), 18);
        assert_eq!(calculate_key_code(0, 0), 0);
        // block=7, fnum=0x7FF: F11=1, F10=F9=F8=1 → N4=1, N3=1 → (7<<2)|2|1=31
        assert_eq!(calculate_key_code(7, 0x7FF), 31);
        // block=4, fnum=0x600: F11=1, F10=1 → N3=1 → (4<<2)|2|1=19
        assert_eq!(calculate_key_code(4, 0x600), 19);
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
        // Enable panning for channel 6 (L+R)
        apu.write_ym2612(1, 0xB6, 0xC0);
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

    #[test]
    fn attack_curve_progresses_from_max() {
        let mut apu = Apu::default();
        // Set frequency/block for channel 0
        apu.write_ym2612(0, 0xA4, 0x22); // block=4
        apu.write_ym2612(0, 0xA0, 0x69); // fnum
        // Set AR=20 (slower than instant) for operator 0, channel 0
        apu.write_ym2612(0, 0x50, 0x54); // KS=1, AR=20
        // Set TL=0 (max volume)
        apu.write_ym2612(0, 0x40, 0x00);
        // Set DT/MUL
        apu.write_ym2612(0, 0x30, 0x01);
        // Key on operator 0
        apu.write_ym2612(0, 0x28, 0x10);
        assert_eq!(apu.ym2612.channels[0].operators[0].env_phase, YmEnvelopePhase::Attack);
        assert_eq!(apu.ym2612.channels[0].operators[0].attenuation, MAX_ATTENUATION);
        // Run enough cycles for several EG updates
        apu.step_cycles(50_000);
        // Attack must have progressed (attenuation decreased from MAX)
        assert!(apu.ym2612.channels[0].operators[0].attenuation < MAX_ATTENUATION,
            "Attack curve should progress from max attenuation, got {}",
            apu.ym2612.channels[0].operators[0].attenuation);
    }

    #[test]
    fn fm_produces_nonzero_output_with_instant_attack() {
        let mut apu = Apu::default();
        // Set frequency for channel 0 (A4 = 440Hz approx)
        apu.write_ym2612(0, 0xA4, 0x22); // block=4
        apu.write_ym2612(0, 0xA0, 0x69); // fnum
        // Set all 4 operators with instant attack (AR=31), TL=0
        for op_slot in [0x00, 0x08, 0x04, 0x0C] {
            apu.write_ym2612(0, 0x30 + op_slot, 0x01); // DT=0, MUL=1
            apu.write_ym2612(0, 0x40 + op_slot, 0x00); // TL=0
            apu.write_ym2612(0, 0x50 + op_slot, 0x1F); // KS=0, AR=31 (max)
            apu.write_ym2612(0, 0x60 + op_slot, 0x00); // D1R=0
            apu.write_ym2612(0, 0x70 + op_slot, 0x00); // D2R=0
            apu.write_ym2612(0, 0x80 + op_slot, 0x0F); // SL=0, RR=max
        }
        // Algorithm 7 (all carriers), panning L+R
        apu.write_ym2612(0, 0xB0, 0x07); // FB=0, ALG=7
        apu.write_ym2612(0, 0xB4, 0xC0); // Pan L+R

        // Key-on all 4 operators on channel 0
        apu.write_ym2612(0, 0x28, 0xF0);

        // Verify key-on and instant attack
        for op in 0..4 {
            assert!(apu.ym2612.channels[0].operators[op].key_on,
                "Operator {} should be key-on", op);
            assert_eq!(apu.ym2612.channels[0].operators[op].attenuation, 0,
                "Operator {} should have 0 attenuation (instant attack)", op);
        }

        // Run FM synthesis
        apu.step_cycles(10_000);

        // Check that some non-zero output was produced
        let has_nonzero = apu.audio_buffer.iter().any(|s| s.abs() > 1.0e-6);
        assert!(has_nonzero,
            "FM should produce non-zero output with instant attack, TL=0, ALG=7. \
             fm_nonzero={}, output_nonzero={}, fm_ticks={}, buffer_len={}",
            apu.debug_fm_nonzero, apu.debug_output_nonzero,
            apu.debug_fm_ticks, apu.audio_buffer.len());
    }
}
