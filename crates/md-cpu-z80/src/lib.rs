use serde::{Deserialize, Serialize};

mod decoder;
mod executor;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Z80State {
    pub a: u8,
    pub f: u8,
    pub b: u8,
    pub c: u8,
    pub d: u8,
    pub e: u8,
    pub h: u8,
    pub l: u8,
    pub a_: u8,
    pub f_: u8,
    pub b_: u8,
    pub c_: u8,
    pub d_: u8,
    pub e_: u8,
    pub h_: u8,
    pub l_: u8,
    pub ix: u16,
    pub iy: u16,
    pub sp: u16,
    pub pc: u16,
    pub i: u8,
    pub r: u8,
    pub im: u8,
    pub total_cycles: u64,
    pub halted: bool,
    pub iff1: bool,
    pub iff2: bool,
    pub int_pending: bool,
    pub ei_delay: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Z80Trace {
    pub pc: u16,
    pub opcode: u8,
    pub cycles: u32,
    pub mnemonic: String,
}

pub trait Z80Bus {
    fn read8(&self, addr: u16) -> u8;
    fn write8(&mut self, addr: u16, value: u8);
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Z80 {
    pub state: Z80State,
}

impl Z80 {
    pub fn reset(&mut self) {
        self.state = Z80State::default();
    }

    /// Signal a maskable interrupt (active low INT pin).
    pub fn signal_int(&mut self) {
        self.state.int_pending = true;
    }

    pub fn step_instruction<B: Z80Bus>(&mut self, bus: &mut B) -> Z80Trace {
        // Process delayed EI before checking interrupts. EI enables IFF1/IFF2
        // immediately but defers interrupt acceptance until after one more instruction.
        if self.state.ei_delay > 0 {
            self.state.ei_delay -= 1;
        } else if self.state.int_pending && self.state.iff1 {
            // Handle pending interrupt before executing next instruction
            self.state.int_pending = false;
            self.state.iff1 = false;
            // Un-halt if HALT'd
            if self.state.halted {
                self.state.halted = false;
                self.state.pc = self.state.pc.wrapping_add(1);
            }
            // IM 1: CALL $0038 — push PC and jump to $0038
            let pc = self.state.pc;
            self.state.sp = self.state.sp.wrapping_sub(1);
            bus.write8(self.state.sp, (pc >> 8) as u8);
            self.state.sp = self.state.sp.wrapping_sub(1);
            bus.write8(self.state.sp, (pc & 0xFF) as u8);
            self.state.pc = 0x0038;
            let cycles = 13;
            self.state.total_cycles += cycles as u64;
            return Z80Trace {
                pc,
                opcode: 0xFF, // RST $38 opcode equivalent
                cycles,
                mnemonic: "INT".to_string(),
            };
        }
        executor::execute_next(self, bus)
    }

    pub fn step_cycles<B: Z80Bus>(&mut self, bus: &mut B, budget: u32) -> u32 {
        let mut consumed = 0;
        while consumed < budget {
            let trace = self.step_instruction(bus);
            if trace.cycles == 0 {
                break;
            }
            consumed = consumed.saturating_add(trace.cycles);
        }
        consumed
    }
}

#[cfg(test)]
mod tests {
    use super::{Z80Bus, Z80};

    struct MockBus {
        mem: Vec<u8>,
    }

    impl MockBus {
        fn new(size: usize) -> Self {
            Self { mem: vec![0; size] }
        }

        fn load(&mut self, at: u16, bytes: &[u8]) {
            let start = at as usize;
            self.mem[start..start + bytes.len()].copy_from_slice(bytes);
        }
    }

    impl Z80Bus for MockBus {
        fn read8(&self, addr: u16) -> u8 {
            self.mem[addr as usize]
        }

        fn write8(&mut self, addr: u16, value: u8) {
            self.mem[addr as usize] = value;
        }
    }

    #[test]
    fn maskable_interrupt_preserves_iff2_until_reti() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);

        cpu.state.pc = 0x1234;
        cpu.state.sp = 0xFFFE;
        cpu.state.iff1 = true;
        cpu.state.iff2 = true;
        cpu.state.int_pending = true;

        bus.load(0x0038, &[0xED, 0x4D]);

        let interrupt = cpu.step_instruction(&mut bus);
        assert_eq!(interrupt.mnemonic, "INT");
        assert_eq!(cpu.state.pc, 0x0038);
        assert!(!cpu.state.iff1);
        assert!(cpu.state.iff2);
        let reti = cpu.step_instruction(&mut bus);
        assert_eq!(reti.mnemonic, "RETI");
        assert_eq!(cpu.state.pc, 0x1234);
        assert!(cpu.state.iff1);
        assert!(cpu.state.iff2);
    }

    #[test]
    fn ei_defers_interrupt_until_after_next_instruction() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);

        bus.load(0x0000, &[0xFB, 0x00, 0xF3]);
        bus.load(0x0038, &[0xED, 0x4D]);

        cpu.state.sp = 0xFFFE;
        cpu.state.int_pending = true;

        let ei = cpu.step_instruction(&mut bus);
        assert_eq!(ei.mnemonic, "Ei");
        assert_eq!(cpu.state.pc, 0x0001);
        assert!(cpu.state.iff1);
        assert!(cpu.state.iff2);
        assert_eq!(cpu.state.ei_delay, 1);

        let nop = cpu.step_instruction(&mut bus);
        assert_eq!(nop.mnemonic, "Nop");
        assert_eq!(cpu.state.pc, 0x0002);
        assert_eq!(cpu.state.ei_delay, 0);

        let interrupt = cpu.step_instruction(&mut bus);
        assert_eq!(interrupt.mnemonic, "INT");
        assert_eq!(cpu.state.pc, 0x0038);
        assert!(!cpu.state.iff1);
        assert!(cpu.state.iff2);
    }

    #[test]
    fn executes_ld_a_imm() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0x3E, 0x42]);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "LdR8Imm(A)");
        assert_eq!(cpu.state.a, 0x42);
        assert_eq!(cpu.state.pc, 2);
    }

    #[test]
    fn executes_jr_relative() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0x18, 0x02, 0x00, 0x00, 0x3E, 0x99]);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.pc, 4);
        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.a, 0x99);
    }

    #[test]
    fn step_cycles_consumes_budget() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0x00, 0x00, 0x00, 0x00]);

        let consumed = cpu.step_cycles(&mut bus, 8);
        assert_eq!(consumed, 8);
        assert_eq!(cpu.state.pc, 2);
    }

    #[test]
    fn cb_prefix_increments_r_twice() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xCB, 0x40]);

        let _ = cpu.step_instruction(&mut bus);

        assert_eq!(cpu.state.r & 0x7F, 2);
    }

    #[test]
    fn ld_r_a_preserves_high_bit() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xED, 0x4F]);
        cpu.state.a = 0x55;
        cpu.state.r = 0x80;

        let _ = cpu.step_instruction(&mut bus);

        assert_eq!(cpu.state.r, 0xD5);
    }

    #[test]
    fn executes_absolute_jump() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xC3, 0x34, 0x12]);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "Jp");
        assert_eq!(cpu.state.pc, 0x1234);
    }

    #[test]
    fn fd_ld_a_iyh_and_iyl_use_index_register_halves() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0x7C, 0xFD, 0x7D]);
        cpu.state.iy = 0x1234;

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.a, 0x12);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.a, 0x34);
    }

    #[test]
    fn fd_ld_iyh_iyl_from_a_updates_iy() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0x67, 0xFD, 0x6F]);
        cpu.state.iy = 0x0000;
        cpu.state.a = 0x56;

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.iy, 0x5600);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.iy, 0x5656);
    }

    #[test]
    fn fd_dec_iyl_and_ld_c_iyh_work() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0x2D, 0xFD, 0x4C, 0xFD, 0x26, 0x9A]);
        cpu.state.iy = 0x1201;

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.iy, 0x1200);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.c, 0x12);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.iy, 0x9A00);
    }

    #[test]
    fn fd_indexed_memory_ld_still_uses_displacement() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0x66, 0x02, 0xFD, 0x74, 0x03]);
        cpu.state.iy = 0x2000;
        cpu.state.h = 0x11;
        bus.write8(0x2002, 0xAB);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.h, 0xAB);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(bus.read8(0x2003), 0xAB);
    }

    #[test]
    fn ed_in_returns_ff_and_out_is_noop_on_md() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xED, 0x50, 0xED, 0x79]);
        cpu.state.b = 0x40;
        cpu.state.c = 0x01;
        cpu.state.a = 0x5A;
        bus.write8(0x4001, 0xA7);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.d, 0xFF);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(bus.read8(0x4001), 0xA7);
    }

    #[test]
    fn edir_family_uses_ff_input_and_noop_output_on_md() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xED, 0xA2, 0xED, 0xA3]);
        cpu.state.b = 0x20;
        cpu.state.c = 0x10;
        cpu.state.h = 0x30;
        cpu.state.l = 0x00;
        bus.write8(0x2010, 0x3C);
        bus.write8(0x3001, 0x77);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(bus.read8(0x3000), 0xFF);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(bus.read8(0x1F10), 0x00);
    }

    #[test]
    fn fd_prefix_executes_non_hl_instruction_in_one_step() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0x3E, 0x56, 0xFD, 0xC3, 0x34, 0x12]);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.a, 0x56);
        assert_eq!(cpu.state.pc, 3);

        let _ = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.pc, 0x1234);
    }

    #[test]
    fn fd_ed_sequence_executes_ed_opcode_without_extra_step() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xFD, 0xED, 0x4F]);
        cpu.state.a = 0x55;
        cpu.state.r = 0x80;

        let _ = cpu.step_instruction(&mut bus);

        assert_eq!(cpu.state.pc, 3);
        assert_eq!(cpu.state.r, 0xD5);
    }
}
