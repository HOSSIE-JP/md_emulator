pub mod addressing;
pub mod decoder;
pub mod executor;
pub mod timing;

use std::collections::VecDeque;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum M68kException {
    IllegalInstruction { opcode: u16 },
    AddressError { address: u32 },
    ZeroDivide,
    TrapV,
    Trap { vector: u8 },
    LineA { opcode: u16 },
    LineF { opcode: u16 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct M68kState {
    pub d: [u32; 8],
    pub a: [u32; 8],
    pub pc: u32,
    pub sr: u16,
    pub usp: u32,
    pub pending_ipl: u8,
    pub total_cycles: u64,
    pub stopped: bool,
    pub last_exception: Option<M68kException>,
    pub last_exception_pc: u32,
}

impl Default for M68kState {
    fn default() -> Self {
        Self {
            d: [0; 8],
            a: [0; 8],
            pc: 0,
            sr: 0x2700,
            usp: 0,
            pending_ipl: 0,
            total_cycles: 0,
            stopped: false,
            last_exception: None,
            last_exception_pc: 0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstructionTrace {
    pub pc: u32,
    pub opcode: u16,
    pub cycles: u32,
    pub mnemonic: String,
}

pub trait M68kBus {
    fn read16(&mut self, addr: u32) -> u16;
    fn write16(&mut self, addr: u32, value: u16);

    fn read8(&mut self, addr: u32) -> u8 {
        let w = self.read16(addr & !1);
        if (addr & 1) == 0 { (w >> 8) as u8 } else { (w & 0xFF) as u8 }
    }

    fn write8(&mut self, addr: u32, value: u8) {
        let aligned = addr & !1;
        let cur = self.read16(aligned);
        let merged = if (addr & 1) == 0 {
            ((value as u16) << 8) | (cur & 0xFF)
        } else {
            (cur & 0xFF00) | value as u16
        };
        self.write16(aligned, merged);
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct M68k {
    pub state: M68kState,
    #[serde(skip)]
    pub trace_ring: VecDeque<InstructionTrace>,
    #[serde(skip)]
    pub exception_trace: Vec<InstructionTrace>,
}

impl M68k {
    pub fn reset(&mut self) {
        self.state = M68kState::default();
    }

    pub fn set_pc(&mut self, pc: u32) {
        self.state.pc = pc;
    }

    pub fn raise_exception(&mut self, exception: M68kException) {
        self.state.last_exception = Some(exception);
        self.state.stopped = true;
    }

    pub fn clear_exception(&mut self) {
        self.state.last_exception = None;
        self.state.stopped = false;
    }

    pub fn step_instruction<B: M68kBus>(&mut self, bus: &mut B) -> InstructionTrace {
        if self.state.stopped {
            // Check if a pending interrupt can wake us up
            if self.state.pending_ipl > 0 {
                let mask = (self.state.sr >> 8) & 7;
                if self.state.pending_ipl as u16 > mask || self.state.pending_ipl >= 7 {
                    self.state.stopped = false;
                    // Fall through to execute_next which will process the interrupt
                } else {
                    return InstructionTrace {
                        pc: self.state.pc,
                        opcode: 0,
                        cycles: 4,
                        mnemonic: "STOPPED".to_string(),
                    };
                }
            } else {
                return InstructionTrace {
                    pc: self.state.pc,
                    opcode: 0,
                    cycles: 4,
                    mnemonic: "STOPPED".to_string(),
                };
            }
        }
        let trace = executor::execute_next(self, bus);
        if trace.cycles > 0 {
            if self.trace_ring.len() >= 64 {
                self.trace_ring.pop_front();
            }
            self.trace_ring.push_back(trace.clone());
        }
        trace
    }

    pub fn step_cycles<B: M68kBus>(&mut self, bus: &mut B, mut budget: u32) -> u32 {
        let start = budget;
        while budget >= 4 {
            let trace = self.step_instruction(bus);
            if trace.cycles == 0 {
                break;
            }
            budget = budget.saturating_sub(trace.cycles);
        }
        start - budget
    }
}

#[cfg(test)]
mod tests {
    use super::{M68k, M68kBus, M68kException};

    struct TestBus {
        mem: Vec<u8>,
    }

    impl TestBus {
        fn new(size: usize) -> Self {
            Self { mem: vec![0; size] }
        }

        fn write_program_word(&mut self, address: usize, word: u16) {
            self.mem[address] = (word >> 8) as u8;
            self.mem[address + 1] = (word & 0xFF) as u8;
        }

        fn write_program_long(&mut self, address: usize, long: u32) {
            self.write_program_word(address, (long >> 16) as u16);
            self.write_program_word(address + 2, (long & 0xFFFF) as u16);
        }
    }

    impl M68kBus for TestBus {
        fn read16(&mut self, addr: u32) -> u16 {
            let idx = addr as usize;
            ((self.mem[idx] as u16) << 8) | self.mem[idx + 1] as u16
        }

        fn write16(&mut self, addr: u32, value: u16) {
            let idx = addr as usize;
            self.mem[idx] = (value >> 8) as u8;
            self.mem[idx + 1] = (value & 0xFF) as u8;
        }
    }

    #[test]
    fn bra_short_updates_pc() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x6002);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "BRA");
        assert_eq!(cpu.state.pc, 4);
    }

    #[test]
    fn jsr_then_rts_returns_to_next_instruction() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x4EB9);
        bus.write_program_word(0x02, 0x0000);
        bus.write_program_word(0x04, 0x0008);
        bus.write_program_word(0x08, 0x4E75);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.a[7] = 0x100;

        cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.pc, 0x08);
        assert_eq!(cpu.state.a[7], 0xFC);

        cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.pc, 0x06);
        assert_eq!(cpu.state.a[7], 0x100);
    }

    #[test]
    fn moveq_sets_register_and_flags() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x70FF);

        let mut cpu = M68k::default();
        cpu.set_pc(0);

        cpu.step_instruction(&mut bus);

        assert_eq!(cpu.state.d[0], 0xFFFF_FFFF);
        assert_ne!(cpu.state.sr & (1 << 3), 0);
        assert_eq!(cpu.state.sr & (1 << 2), 0);
    }

    #[test]
    fn move_w_immediate_to_dn_preserves_upper_word() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x303C);
        bus.write_program_word(0x02, 0x8001);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.d[0] = 0xAAAA_0000;

        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0], 0xAAAA_8001);
        assert_ne!(cpu.state.sr & (1 << 3), 0);
        assert_eq!(cpu.state.sr & (1 << 2), 0);
    }

    #[test]
    fn move_b_immediate_to_dn_preserves_upper_24_bits() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x103C);
        bus.write_program_word(0x02, 0x0080);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.d[0] = 0xAABB_CC11;

        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "MOVE.B");
        assert_eq!(cpu.state.d[0], 0xAABB_CC80);
        assert_ne!(cpu.state.sr & (1 << 3), 0);
        assert_eq!(cpu.state.sr & (1 << 2), 0);
    }

    #[test]
    fn move_w_data_register_to_address_indirect() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x3080);

        let mut cpu = M68k::default();
        cpu.state.d[0] = 0x0000_BEEF;
        cpu.state.a[0] = 0x40;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(bus.read16(0x40), 0xBEEF);
    }

    #[test]
    fn move_l_address_indirect_to_data_register() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x2010);
        bus.write_program_long(0x40, 0x1234_5678);

        let mut cpu = M68k::default();
        cpu.state.a[0] = 0x40;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.L");
        assert_eq!(cpu.state.d[0], 0x1234_5678);
    }

    #[test]
    fn move_w_postinc_source_updates_an() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x3018);
        bus.write_program_word(0x40, 0xCAFE);

        let mut cpu = M68k::default();
        cpu.state.a[0] = 0x40;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0xCAFE);
        assert_eq!(cpu.state.a[0], 0x42);
    }

    #[test]
    fn move_w_predec_destination_updates_an() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x3100);

        let mut cpu = M68k::default();
        cpu.state.d[0] = 0x0000_55AA;
        cpu.state.a[0] = 0x44;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.a[0], 0x42);
        assert_eq!(bus.read16(0x42), 0x55AA);
    }

    #[test]
    fn move_w_displacement_source_reads_effective_address() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x3028);
        bus.write_program_word(0x02, 0x0006);
        bus.write_program_word(0x46, 0x0BAD);

        let mut cpu = M68k::default();
        cpu.state.a[0] = 0x40;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0x0BAD);
    }

    #[test]
    fn move_w_address_index_source_reads_effective_address() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x3030);
        bus.write_program_word(0x02, 0x0804);
        bus.write_program_word(0x4A, 0xFACE);

        let mut cpu = M68k::default();
        cpu.state.a[0] = 0x40;
        cpu.state.d[0] = 0x0000_0006;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0xFACE);
    }

    #[test]
    fn move_w_pc_displacement_source_reads_effective_address() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x303A);
        bus.write_program_word(0x02, 0x0006);
        bus.write_program_word(0x08, 0xBEEF);

        let mut cpu = M68k::default();
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0xBEEF);
    }

    #[test]
    fn move_w_pc_index_source_reads_effective_address() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x303B);
        bus.write_program_word(0x02, 0x0804);
        bus.write_program_word(0x0C, 0xDEAD);

        let mut cpu = M68k::default();
        cpu.state.d[0] = 0x0000_0006;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVE.W");
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0xDEAD);
    }

    #[test]
    fn move_pc_relative_destination_raises_illegal() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_long(0x10, 0x0000_0080);
        bus.write_program_word(0x00, 0x35C0);
        bus.write_program_word(0x02, 0x0004);

        let mut cpu = M68k::default();
        cpu.state.d[0] = 0x0000_1234;
        cpu.state.a[7] = 0x180;
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "ILLEGAL");
        assert_eq!(cpu.state.pc, 0x80);
    }

    #[test]
    fn movea_l_immediate_to_address_register() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x247C);
        bus.write_program_long(0x02, 0x1234_5678);

        let mut cpu = M68k::default();
        cpu.set_pc(0);

        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "MOVEA.L");
        assert_eq!(cpu.state.a[2], 0x1234_5678);
    }

    #[test]
    fn move_l_immediate_to_dn_writes_full_register() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x203C);
        bus.write_program_word(0x02, 0x1234);
        bus.write_program_word(0x04, 0x5678);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.d[0] = 0xFFFF_FFFF;

        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "MOVE.L");
        assert_eq!(cpu.state.d[0], 0x1234_5678);
        assert_eq!(cpu.state.sr & (1 << 3), 0);
        assert_eq!(cpu.state.sr & (1 << 2), 0);
    }

    #[test]
    fn illegal_opcode_sets_exception() {
        let mut bus = TestBus::new(0x400);
        // Line-F vector (11) at address 0x2C
        bus.write_program_long(0x2C, 0x0000_0080);
        bus.write_program_word(0x40, 0xFFFF);

        let mut cpu = M68k::default();
        cpu.set_pc(0x40);
        cpu.state.a[7] = 0x200;

        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "LINE_F");
        assert_eq!(cpu.state.pc, 0x80);
        // Standard 68000 exception frame: push PC (4), push SR (2) = 6 bytes
        assert_eq!(cpu.state.a[7], 0x1FA);
        assert_eq!(bus.read16(0x1FA), 0x2700); // SR
        assert_eq!(bus.read16(0x1FC), 0x0000); // PC high
        assert_eq!(bus.read16(0x1FE), 0x0040); // PC low
        assert_eq!(
            cpu.state.last_exception,
            Some(M68kException::LineF { opcode: 0xFFFF })
        );
    }

    #[test]
    fn odd_pc_triggers_address_error() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_long(0x0C, 0x0000_0060);
        let mut cpu = M68k::default();
        cpu.state.a[7] = 0x180;
        cpu.set_pc(1);

        let trace = cpu.step_instruction(&mut bus);

        assert_eq!(trace.mnemonic, "ADDRESS_ERROR");
        assert_eq!(cpu.state.pc, 0x60);
        assert_eq!(
            cpu.state.last_exception,
            Some(M68kException::AddressError { address: 1 })
        );
    }

    #[test]
    fn stopped_cpu_step_cycles_returns_without_looping() {
        let mut bus = TestBus::new(0x100);
        let mut cpu = M68k::default();
        cpu.raise_exception(M68kException::AddressError { address: 1 });

        let used = cpu.step_cycles(&mut bus, 64);

        // Stopped CPU consumes cycles (4 per "idle" step) to avoid infinite loops
        assert!(used > 0);
        assert!(used <= 64);
    }

    #[test]
    fn clear_exception_resumes_execution() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x4E71);
        let mut cpu = M68k::default();
        cpu.raise_exception(M68kException::IllegalInstruction { opcode: 0xFFFF });

        let stopped_trace = cpu.step_instruction(&mut bus);
        assert_eq!(stopped_trace.mnemonic, "STOPPED");

        cpu.clear_exception();
        cpu.set_pc(0);
        let trace = cpu.step_instruction(&mut bus);
        assert_eq!(trace.mnemonic, "NOP");
    }

    #[test]
    fn bsr_and_rts_flow() {
        let mut bus = TestBus::new(0x200);
        bus.write_program_word(0x00, 0x6102);
        bus.write_program_word(0x02, 0x4E71);
        bus.write_program_word(0x04, 0x4E75);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.a[7] = 0x100;

        let t1 = cpu.step_instruction(&mut bus);
        assert_eq!(t1.mnemonic, "BSR");
        assert_eq!(cpu.state.pc, 0x04);

        let t2 = cpu.step_instruction(&mut bus);
        assert_eq!(t2.mnemonic, "RTS");
        assert_eq!(cpu.state.pc, 0x02);
    }

    #[test]
    fn bcc_not_taken_advances() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x6602);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.sr |= 1 << 2;

        let t = cpu.step_instruction(&mut bus);
        assert!(t.mnemonic.starts_with("Bcc"));
        assert_eq!(cpu.state.pc, 0x02);
    }

    #[test]
    fn dbcc_loops_until_minus_one() {
        let mut bus = TestBus::new(0x100);
        bus.write_program_word(0x00, 0x51C8);
        // Displacement is relative to the address of the displacement word (0x02).
        // To branch back to 0x00: 0x00 - 0x02 = -2 = 0xFFFE
        bus.write_program_word(0x02, 0xFFFE);

        let mut cpu = M68k::default();
        cpu.set_pc(0);
        cpu.state.d[0] = 1;

        let t1 = cpu.step_instruction(&mut bus);
        assert!(t1.mnemonic.starts_with("DBcc"));
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0);
        assert_eq!(cpu.state.pc, 0x00);

        let _t2 = cpu.step_instruction(&mut bus);
        assert_eq!(cpu.state.d[0] & 0xFFFF, 0xFFFF);
        assert_eq!(cpu.state.pc, 0x04);
    }
}
