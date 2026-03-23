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
    pub sp: u16,
    pub pc: u16,
    pub total_cycles: u64,
    pub halted: bool,
    pub iff1: bool,
    pub iff2: bool,
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

    pub fn step_instruction<B: Z80Bus>(&mut self, bus: &mut B) -> Z80Trace {
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
    fn executes_absolute_jump() {
        let mut cpu = Z80::default();
        let mut bus = MockBus::new(0x10000);
        bus.load(0, &[0xC3, 0x34, 0x12]);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "Jp");
        assert_eq!(cpu.state.pc, 0x1234);
    }
}
