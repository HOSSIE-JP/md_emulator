use crate::decoder::{cycles_for, decode, Z80Instruction, Reg8, Reg16, Cond};
use crate::{Z80Bus, Z80Trace, Z80};

const FLAG_S: u8 = 1 << 7;
const FLAG_Z: u8 = 1 << 6;
const FLAG_H: u8 = 1 << 4;
const FLAG_PV: u8 = 1 << 2;
const FLAG_N: u8 = 1 << 1;
const FLAG_C: u8 = 1 << 0;

pub fn execute_next<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> Z80Trace {
    if cpu.state.halted {
        cpu.state.total_cycles += 4;
        return Z80Trace { pc: cpu.state.pc, opcode: 0, cycles: 4, mnemonic: "HALT".to_string() };
    }
    let pc_before = cpu.state.pc;
    let opcode = read8(cpu, bus);
    let instr = decode(opcode);
    let mut cycles = cycles_for(&instr);

    match instr {
        Z80Instruction::Nop => {}
        Z80Instruction::Halt => { cpu.state.halted = true; }
        Z80Instruction::Di => { cpu.state.iff1 = false; cpu.state.iff2 = false; }
        Z80Instruction::Ei => { cpu.state.iff1 = true; cpu.state.iff2 = true; }
        // LD r8, imm
        Z80Instruction::LdR8Imm(r) => {
            let v = read8(cpu, bus);
            write_r8(cpu, bus, r, v);
        }
        // LD r8, r8
        Z80Instruction::LdR8R8(dst, src) => {
            let v = read_r8(cpu, bus, src);
            write_r8(cpu, bus, dst, v);
        }
        // LD r16, imm16
        Z80Instruction::LdR16Imm(rr) => {
            let lo = read8(cpu, bus) as u16;
            let hi = read8(cpu, bus) as u16;
            write_r16(cpu, rr, (hi << 8) | lo);
        }
        Z80Instruction::LdAAddr => {
            let lo = read8(cpu, bus) as u16;
            let hi = read8(cpu, bus) as u16;
            cpu.state.a = bus.read8((hi << 8) | lo);
        }
        Z80Instruction::LdAddrA => {
            let lo = read8(cpu, bus) as u16;
            let hi = read8(cpu, bus) as u16;
            bus.write8((hi << 8) | lo, cpu.state.a);
        }
        Z80Instruction::LdADE => { let a = get_de(cpu); cpu.state.a = bus.read8(a); }
        Z80Instruction::LdDEA => { let a = get_de(cpu); bus.write8(a, cpu.state.a); }
        Z80Instruction::LdABC => { let a = get_bc(cpu); cpu.state.a = bus.read8(a); }
        Z80Instruction::LdBCA => { let a = get_bc(cpu); bus.write8(a, cpu.state.a); }
        Z80Instruction::LdHLImm16Addr => {
            let addr = read16(cpu, bus);
            let lo = bus.read8(addr);
            let hi = bus.read8(addr.wrapping_add(1));
            cpu.state.l = lo; cpu.state.h = hi;
        }
        Z80Instruction::LdImm16AddrHL => {
            let addr = read16(cpu, bus);
            bus.write8(addr, cpu.state.l);
            bus.write8(addr.wrapping_add(1), cpu.state.h);
        }
        Z80Instruction::LdSPHL => { cpu.state.sp = get_hl(cpu); }
        Z80Instruction::LdHLAddr | Z80Instruction::LdAddrHL => {}
        // PUSH/POP
        Z80Instruction::PushR16(rr) => { let v = read_r16(cpu, rr); push16(cpu, bus, v); }
        Z80Instruction::PopR16(rr) => { let v = pop16(cpu, bus); write_r16(cpu, rr, v); }
        // ALU A,r8
        Z80Instruction::AddAR8(r) => { let v = read_r8(cpu, bus, r); alu_add(cpu, v, false); }
        Z80Instruction::AdcAR8(r) => { let v = read_r8(cpu, bus, r); let c = (cpu.state.f & FLAG_C) != 0; alu_add(cpu, v, c); }
        Z80Instruction::SubR8(r)  => { let v = read_r8(cpu, bus, r); alu_sub(cpu, v, false); }
        Z80Instruction::SbcAR8(r) => { let v = read_r8(cpu, bus, r); let c = (cpu.state.f & FLAG_C) != 0; alu_sub(cpu, v, c); }
        Z80Instruction::AndR8(r)  => { let v = read_r8(cpu, bus, r); cpu.state.a &= v; alu_logic_flags(cpu, cpu.state.a); cpu.state.f |= FLAG_H; }
        Z80Instruction::OrR8(r)   => { let v = read_r8(cpu, bus, r); cpu.state.a |= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::XorR8(r)  => { let v = read_r8(cpu, bus, r); cpu.state.a ^= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::CpR8(r)   => { let v = read_r8(cpu, bus, r); alu_cp(cpu, v); }
        // ALU imm
        Z80Instruction::AddAImm => { let v = read8(cpu, bus); alu_add(cpu, v, false); }
        Z80Instruction::SubImm  => { let v = read8(cpu, bus); alu_sub(cpu, v, false); }
        Z80Instruction::AndImm  => { let v = read8(cpu, bus); cpu.state.a &= v; alu_logic_flags(cpu, cpu.state.a); cpu.state.f |= FLAG_H; }
        Z80Instruction::OrImm   => { let v = read8(cpu, bus); cpu.state.a |= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::XorImm  => { let v = read8(cpu, bus); cpu.state.a ^= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::CpImm   => { let v = read8(cpu, bus); alu_cp(cpu, v); }
        // INC/DEC r8
        Z80Instruction::IncR8(r) => {
            let v = read_r8(cpu, bus, r);
            let res = v.wrapping_add(1);
            write_r8(cpu, bus, r, res);
            let c = cpu.state.f & FLAG_C;
            cpu.state.f = c | sz_flags(res);
            if (v & 0x0F) == 0x0F { cpu.state.f |= FLAG_H; }
            if v == 0x7F { cpu.state.f |= FLAG_PV; }
        }
        Z80Instruction::DecR8(r) => {
            let v = read_r8(cpu, bus, r);
            let res = v.wrapping_sub(1);
            write_r8(cpu, bus, r, res);
            let c = cpu.state.f & FLAG_C;
            cpu.state.f = c | sz_flags(res) | FLAG_N;
            if (v & 0x0F) == 0x00 { cpu.state.f |= FLAG_H; }
            if v == 0x80 { cpu.state.f |= FLAG_PV; }
        }
        // INC/DEC r16
        Z80Instruction::IncR16(rr) => { let v = read_r16(cpu, rr).wrapping_add(1); write_r16(cpu, rr, v); }
        Z80Instruction::DecR16(rr) => { let v = read_r16(cpu, rr).wrapping_sub(1); write_r16(cpu, rr, v); }
        // ADD HL, r16
        Z80Instruction::AddHLR16(rr) => {
            let hl = get_hl(cpu) as u32;
            let v = read_r16(cpu, rr) as u32;
            let res = hl + v;
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_PV;
            if res > 0xFFFF { cpu.state.f |= FLAG_C; }
            if ((hl ^ v ^ res) & 0x1000) != 0 { cpu.state.f |= FLAG_H; }
            set_hl(cpu, res as u16);
        }
        // Jumps
        Z80Instruction::Jr => {
            let d = read8(cpu, bus) as i8 as i16;
            cpu.state.pc = cpu.state.pc.wrapping_add(d as u16);
        }
        Z80Instruction::JrCond(cc) => {
            let d = read8(cpu, bus) as i8 as i16;
            if eval_cond(cpu, cc) {
                cpu.state.pc = cpu.state.pc.wrapping_add(d as u16);
                cycles = 12;
            } else {
                cycles = 7;
            }
        }
        Z80Instruction::Jp => { cpu.state.pc = read16(cpu, bus); }
        Z80Instruction::JpCond(cc) => {
            let addr = read16(cpu, bus);
            if eval_cond(cpu, cc) { cpu.state.pc = addr; }
        }
        Z80Instruction::JpHL => { cpu.state.pc = get_hl(cpu); }
        Z80Instruction::Call => {
            let addr = read16(cpu, bus);
            push16(cpu, bus, cpu.state.pc);
            cpu.state.pc = addr;
        }
        Z80Instruction::CallCond(cc) => {
            let addr = read16(cpu, bus);
            if eval_cond(cpu, cc) {
                push16(cpu, bus, cpu.state.pc);
                cpu.state.pc = addr;
                cycles = 17;
            } else {
                cycles = 10;
            }
        }
        Z80Instruction::Ret => { cpu.state.pc = pop16(cpu, bus); }
        Z80Instruction::RetCond(cc) => {
            if eval_cond(cpu, cc) {
                cpu.state.pc = pop16(cpu, bus);
                cycles = 11;
            } else {
                cycles = 5;
            }
        }
        Z80Instruction::Reti => {
            cpu.state.pc = pop16(cpu, bus);
            cpu.state.iff1 = cpu.state.iff2;
        }
        Z80Instruction::Rst(addr) => {
            push16(cpu, bus, cpu.state.pc);
            cpu.state.pc = addr as u16;
        }
        Z80Instruction::Djnz => {
            let d = read8(cpu, bus) as i8 as i16;
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            if cpu.state.b != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_add(d as u16);
                cycles = 13;
            } else {
                cycles = 8;
            }
        }
        // Rotate
        Z80Instruction::Rlca => {
            let bit7 = cpu.state.a >> 7;
            cpu.state.a = (cpu.state.a << 1) | bit7;
            cpu.state.f = (cpu.state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | (bit7 & FLAG_C);
        }
        Z80Instruction::Rrca => {
            let bit0 = cpu.state.a & 1;
            cpu.state.a = (cpu.state.a >> 1) | (bit0 << 7);
            cpu.state.f = (cpu.state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | (bit0 & FLAG_C);
        }
        Z80Instruction::Rla => {
            let old_c = cpu.state.f & FLAG_C;
            let bit7 = cpu.state.a >> 7;
            cpu.state.a = (cpu.state.a << 1) | old_c;
            cpu.state.f = (cpu.state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | (bit7 & FLAG_C);
        }
        Z80Instruction::Rra => {
            let old_c = cpu.state.f & FLAG_C;
            let bit0 = cpu.state.a & 1;
            cpu.state.a = (cpu.state.a >> 1) | (old_c << 7);
            cpu.state.f = (cpu.state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | (bit0 & FLAG_C);
        }
        Z80Instruction::Cpl => {
            cpu.state.a = !cpu.state.a;
            cpu.state.f |= FLAG_H | FLAG_N;
        }
        Z80Instruction::Scf => {
            cpu.state.f = (cpu.state.f & (FLAG_S | FLAG_Z | FLAG_PV)) | FLAG_C;
        }
        Z80Instruction::Ccf => {
            let old_c = cpu.state.f & FLAG_C;
            cpu.state.f &= !(FLAG_N | FLAG_C | FLAG_H);
            if old_c != 0 { cpu.state.f |= FLAG_H; } else { cpu.state.f |= FLAG_C; }
        }
        Z80Instruction::ExDEHL => {
            std::mem::swap(&mut cpu.state.d, &mut cpu.state.h);
            std::mem::swap(&mut cpu.state.e, &mut cpu.state.l);
        }
        Z80Instruction::ExAFAF => {
            std::mem::swap(&mut cpu.state.a, &mut cpu.state.a_);
            std::mem::swap(&mut cpu.state.f, &mut cpu.state.f_);
        }
        Z80Instruction::Exx => {
            std::mem::swap(&mut cpu.state.b, &mut cpu.state.b_);
            std::mem::swap(&mut cpu.state.c, &mut cpu.state.c_);
            std::mem::swap(&mut cpu.state.d, &mut cpu.state.d_);
            std::mem::swap(&mut cpu.state.e, &mut cpu.state.e_);
            std::mem::swap(&mut cpu.state.h, &mut cpu.state.h_);
            std::mem::swap(&mut cpu.state.l, &mut cpu.state.l_);
        }
        Z80Instruction::ExSPHL => {
            let spl = bus.read8(cpu.state.sp);
            let sph = bus.read8(cpu.state.sp.wrapping_add(1));
            bus.write8(cpu.state.sp, cpu.state.l);
            bus.write8(cpu.state.sp.wrapping_add(1), cpu.state.h);
            cpu.state.l = spl;
            cpu.state.h = sph;
        }
        Z80Instruction::OutNA => { let _port = read8(cpu, bus); /* I/O ignored on MD Z80 */ }
        Z80Instruction::InAN  => { let _port = read8(cpu, bus); cpu.state.a = 0xFF; /* open bus */ }
        Z80Instruction::Daa => {
            let mut a = cpu.state.a as u16;
            let n = (cpu.state.f & FLAG_N) != 0;
            let c = (cpu.state.f & FLAG_C) != 0;
            let h = (cpu.state.f & FLAG_H) != 0;
            if !n {
                if h || (a & 0x0F) > 9 { a = a.wrapping_add(6); }
                if c || a > 0x9F { a = a.wrapping_add(0x60); }
            } else {
                if h { a = a.wrapping_sub(6); }
                if c { a = a.wrapping_sub(0x60); }
            }
            cpu.state.a = a as u8;
            cpu.state.f &= FLAG_N | FLAG_C;
            if a > 0xFF { cpu.state.f |= FLAG_C; }
            cpu.state.f |= sz_flags(cpu.state.a);
            cpu.state.f |= parity(cpu.state.a);
        }
        Z80Instruction::LdiA => {
            let hl = get_hl(cpu);
            cpu.state.a = bus.read8(hl);
            set_hl(cpu, hl.wrapping_add(1));
        }
        Z80Instruction::LddA => {
            let hl = get_hl(cpu);
            cpu.state.a = bus.read8(hl);
            set_hl(cpu, hl.wrapping_sub(1));
        }
        Z80Instruction::Illegal => {}
    }

    cpu.state.total_cycles += cycles as u64;
    Z80Trace {
        pc: pc_before,
        opcode,
        cycles,
        mnemonic: mnemonic(&instr),
    }
}

fn read8<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> u8 {
    let v = bus.read8(cpu.state.pc);
    cpu.state.pc = cpu.state.pc.wrapping_add(1);
    v
}

fn read16<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> u16 {
    let lo = read8(cpu, bus) as u16;
    let hi = read8(cpu, bus) as u16;
    (hi << 8) | lo
}

fn push16<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, val: u16) {
    cpu.state.sp = cpu.state.sp.wrapping_sub(1);
    bus.write8(cpu.state.sp, (val >> 8) as u8);
    cpu.state.sp = cpu.state.sp.wrapping_sub(1);
    bus.write8(cpu.state.sp, val as u8);
}

fn pop16<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> u16 {
    let lo = bus.read8(cpu.state.sp) as u16;
    cpu.state.sp = cpu.state.sp.wrapping_add(1);
    let hi = bus.read8(cpu.state.sp) as u16;
    cpu.state.sp = cpu.state.sp.wrapping_add(1);
    (hi << 8) | lo
}

fn get_bc(cpu: &Z80) -> u16 { ((cpu.state.b as u16) << 8) | cpu.state.c as u16 }
fn get_de(cpu: &Z80) -> u16 { ((cpu.state.d as u16) << 8) | cpu.state.e as u16 }
fn get_hl(cpu: &Z80) -> u16 { ((cpu.state.h as u16) << 8) | cpu.state.l as u16 }

fn set_hl(cpu: &mut Z80, v: u16) { cpu.state.h = (v >> 8) as u8; cpu.state.l = v as u8; }

fn read_r8<B: Z80Bus>(cpu: &Z80, bus: &B, r: Reg8) -> u8 {
    match r {
        Reg8::A => cpu.state.a, Reg8::B => cpu.state.b, Reg8::C => cpu.state.c,
        Reg8::D => cpu.state.d, Reg8::E => cpu.state.e, Reg8::H => cpu.state.h,
        Reg8::L => cpu.state.l, Reg8::Mem => bus.read8(get_hl(cpu)),
    }
}

fn write_r8<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, r: Reg8, v: u8) {
    match r {
        Reg8::A => cpu.state.a = v, Reg8::B => cpu.state.b = v, Reg8::C => cpu.state.c = v,
        Reg8::D => cpu.state.d = v, Reg8::E => cpu.state.e = v, Reg8::H => cpu.state.h = v,
        Reg8::L => cpu.state.l = v, Reg8::Mem => { let a = get_hl(cpu); bus.write8(a, v); },
    }
}

fn read_r16(cpu: &Z80, rr: Reg16) -> u16 {
    match rr {
        Reg16::BC => get_bc(cpu), Reg16::DE => get_de(cpu),
        Reg16::HL => get_hl(cpu), Reg16::SP => cpu.state.sp,
        Reg16::AF => ((cpu.state.a as u16) << 8) | cpu.state.f as u16,
    }
}

fn write_r16(cpu: &mut Z80, rr: Reg16, v: u16) {
    match rr {
        Reg16::BC => { cpu.state.b = (v >> 8) as u8; cpu.state.c = v as u8; }
        Reg16::DE => { cpu.state.d = (v >> 8) as u8; cpu.state.e = v as u8; }
        Reg16::HL => { cpu.state.h = (v >> 8) as u8; cpu.state.l = v as u8; }
        Reg16::SP => { cpu.state.sp = v; }
        Reg16::AF => { cpu.state.a = (v >> 8) as u8; cpu.state.f = v as u8; }
    }
}

fn eval_cond(cpu: &Z80, cc: Cond) -> bool {
    match cc {
        Cond::NZ => (cpu.state.f & FLAG_Z) == 0,
        Cond::Z  => (cpu.state.f & FLAG_Z) != 0,
        Cond::NC => (cpu.state.f & FLAG_C) == 0,
        Cond::C  => (cpu.state.f & FLAG_C) != 0,
    }
}

fn sz_flags(v: u8) -> u8 {
    let mut f = 0u8;
    if v == 0 { f |= FLAG_Z; }
    if (v & 0x80) != 0 { f |= FLAG_S; }
    f
}

fn parity(v: u8) -> u8 {
    if v.count_ones() % 2 == 0 { FLAG_PV } else { 0 }
}

fn alu_add(cpu: &mut Z80, v: u8, carry: bool) {
    let c = if carry { 1u16 } else { 0 };
    let a = cpu.state.a as u16;
    let res = a + v as u16 + c;
    cpu.state.f = sz_flags(res as u8);
    if res > 0xFF { cpu.state.f |= FLAG_C; }
    if ((a ^ v as u16 ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
    if ((!(a ^ v as u16)) & (a ^ res) & 0x80) != 0 { cpu.state.f |= FLAG_PV; }
    cpu.state.a = res as u8;
}

fn alu_sub(cpu: &mut Z80, v: u8, carry: bool) {
    let c = if carry { 1u16 } else { 0 };
    let a = cpu.state.a as u16;
    let res = a.wrapping_sub(v as u16).wrapping_sub(c);
    cpu.state.f = sz_flags(res as u8) | FLAG_N;
    if a < v as u16 + c { cpu.state.f |= FLAG_C; }
    if ((a ^ v as u16 ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
    if ((a ^ v as u16) & (a ^ res) & 0x80) != 0 { cpu.state.f |= FLAG_PV; }
    cpu.state.a = res as u8;
}

fn alu_cp(cpu: &mut Z80, v: u8) {
    let saved_a = cpu.state.a;
    alu_sub(cpu, v, false);
    cpu.state.a = saved_a;
}

fn alu_logic_flags(cpu: &mut Z80, v: u8) {
    cpu.state.f = sz_flags(v) | parity(v);
}

fn mnemonic(instr: &Z80Instruction) -> String {
    format!("{:?}", instr)
}
