use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Ym2612 {
    pub regs_port0: Vec<u8>,
    pub regs_port1: Vec<u8>,
    pub phase: f32,
    pub frequency_hz: f32,
    pub level: f32,
}

impl Default for Ym2612 {
    fn default() -> Self {
        Self {
            regs_port0: vec![0; 0x100],
            regs_port1: vec![0; 0x100],
            phase: 0.0,
            frequency_hz: 440.0,
            level: 0.08,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Psg {
    pub latched_tone: [u16; 4],
    pub volume: [u8; 4],
    pub phase: [f32; 4],
}

impl Default for Psg {
    fn default() -> Self {
        Self {
            latched_tone: [0x200, 0x200, 0x200, 0x200],
            volume: [0x08, 0x08, 0x08, 0x0F],
            phase: [0.0; 4],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Apu {
    pub sample_rate: u32,
    pub audio_buffer: Vec<f32>,
    pub ym2612: Ym2612,
    pub psg: Psg,
}

impl Default for Apu {
    fn default() -> Self {
        Self {
            sample_rate: 48_000,
            audio_buffer: Vec::new(),
            ym2612: Ym2612::default(),
            psg: Psg::default(),
        }
    }
}

impl Apu {
    pub fn reset(&mut self) {
        *self = Self::default();
    }

    pub fn step_cycles(&mut self, cycles: u32) {
        if cycles == 0 {
            return;
        }
        let sample_count = (cycles / 96).max(1);
        for i in 0..sample_count {
            let _frame_pos = i as f32 / sample_count as f32;
            let fm = self.next_fm_sample();
            let psg = self.next_psg_sample();
            let mono = (fm + psg).clamp(-1.0, 1.0);
            self.audio_buffer.push(mono);
            self.audio_buffer.push(mono);
        }
    }

    pub fn write_ym2612(&mut self, port: u8, address: u8, data: u8) {
        match port {
            0 => self.ym2612.regs_port0[address as usize] = data,
            1 => self.ym2612.regs_port1[address as usize] = data,
            _ => return,
        }

        if address == 0xA4 || address == 0xA0 {
            let low = self.ym2612.regs_port0[0xA0] as u16;
            let high = (self.ym2612.regs_port0[0xA4] as u16) & 0x07;
            let fnum = (high << 8) | low;
            let hz = 55.0 + fnum as f32 * 0.15;
            self.ym2612.frequency_hz = hz.clamp(10.0, 8000.0);
        }
        if address == 0x4C {
            let att = (data & 0x7F) as f32;
            self.ym2612.level = ((127.0 - att) / 127.0) * 0.12;
        }
    }

    pub fn write_psg(&mut self, data: u8) {
        let channel = ((data >> 5) & 0x03) as usize;
        let is_volume = (data & 0x10) != 0;
        if is_volume {
            self.psg.volume[channel] = data & 0x0F;
        } else {
            let low = (data & 0x0F) as u16;
            let current = self.psg.latched_tone[channel] & 0x3F0;
            self.psg.latched_tone[channel] = current | low;
        }
    }

    pub fn take_samples(&mut self, count_stereo_frames: usize) -> Vec<f32> {
        let sample_count = count_stereo_frames * 2;
        let n = sample_count.min(self.audio_buffer.len());
        self.audio_buffer.drain(..n).collect()
    }

    fn next_fm_sample(&mut self) -> f32 {
        let step = self.ym2612.frequency_hz / self.sample_rate as f32;
        self.ym2612.phase = (self.ym2612.phase + step).fract();
        let theta = self.ym2612.phase * std::f32::consts::TAU;
        theta.sin() * self.ym2612.level
    }

    fn next_psg_sample(&mut self) -> f32 {
        let mut sum = 0.0;
        for ch in 0..3 {
            let tone = self.psg.latched_tone[ch].max(1) as f32;
            let freq = (3_579_545.0 / 32.0) / tone;
            let step = (freq / self.sample_rate as f32).clamp(0.0, 0.49);
            self.psg.phase[ch] = (self.psg.phase[ch] + step).fract();
            let amp = (15 - self.psg.volume[ch].min(15)) as f32 / 15.0;
            let square = if self.psg.phase[ch] < 0.5 { 1.0 } else { -1.0 };
            sum += square * amp * 0.03;
        }
        sum
    }
}

#[cfg(test)]
mod tests {
    use super::Apu;

    #[test]
    fn generates_stereo_samples() {
        let mut apu = Apu::default();
        apu.step_cycles(192);
        assert!(apu.audio_buffer.len() >= 4);
        assert_eq!(apu.audio_buffer.len() % 2, 0);
    }

    #[test]
    fn ym_write_updates_frequency() {
        let mut apu = Apu::default();
        apu.write_ym2612(0, 0xA0, 0x40);
        apu.write_ym2612(0, 0xA4, 0x02);
        assert!(apu.ym2612.frequency_hz > 55.0);
    }

    #[test]
    fn take_samples_drains_buffer() {
        let mut apu = Apu::default();
        apu.step_cycles(192);
        let before = apu.audio_buffer.len();
        let out = apu.take_samples(1);
        assert_eq!(out.len(), 2);
        assert_eq!(apu.audio_buffer.len(), before - 2);
    }
}
