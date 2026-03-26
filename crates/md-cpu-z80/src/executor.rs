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
    bump_r(cpu);

    let (cycles, mnemonic_str) = match opcode {
        0xCB => exec_cb(cpu, bus),
        0xDD => exec_ddfd(cpu, bus, true),
        0xFD => exec_ddfd(cpu, bus, false),
        0xED => exec_ed(cpu, bus),
        _ => exec_unprefixed(cpu, bus, opcode),
    };

    cpu.state.total_cycles += cycles as u64;
    Z80Trace {
        pc: pc_before,
        opcode,
        cycles,
        mnemonic: mnemonic_str,
    }
}

// ──────── Unprefixed instruction execution ────────
fn exec_unprefixed<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, opcode: u8) -> (u32, String) {
    let instr = decode(opcode);
    let mut cycles = cycles_for(&instr);

    match instr {
        Z80Instruction::Nop => {}
        Z80Instruction::Halt => { cpu.state.halted = true; }
        Z80Instruction::Di => { cpu.state.iff1 = false; cpu.state.iff2 = false; cpu.state.ei_delay = 0; }
        Z80Instruction::Ei => {
            cpu.state.iff1 = true;
            cpu.state.iff2 = true;
            cpu.state.ei_delay = 1;
        }
        Z80Instruction::LdR8Imm(r) => {
            let v = read8(cpu, bus);
            write_r8(cpu, bus, r, v);
        }
        Z80Instruction::LdR8R8(dst, src) => {
            let v = read_r8(cpu, bus, src);
            write_r8(cpu, bus, dst, v);
        }
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
        Z80Instruction::PushR16(rr) => { let v = read_r16(cpu, rr); push16(cpu, bus, v); }
        Z80Instruction::PopR16(rr) => { let v = pop16(cpu, bus); write_r16(cpu, rr, v); }
        Z80Instruction::AddAR8(r) => { let v = read_r8(cpu, bus, r); alu_add(cpu, v, false); }
        Z80Instruction::AdcAR8(r) => { let v = read_r8(cpu, bus, r); let c = (cpu.state.f & FLAG_C) != 0; alu_add(cpu, v, c); }
        Z80Instruction::SubR8(r)  => { let v = read_r8(cpu, bus, r); alu_sub(cpu, v, false); }
        Z80Instruction::SbcAR8(r) => { let v = read_r8(cpu, bus, r); let c = (cpu.state.f & FLAG_C) != 0; alu_sub(cpu, v, c); }
        Z80Instruction::AndR8(r)  => { let v = read_r8(cpu, bus, r); cpu.state.a &= v; alu_logic_flags(cpu, cpu.state.a); cpu.state.f |= FLAG_H; }
        Z80Instruction::OrR8(r)   => { let v = read_r8(cpu, bus, r); cpu.state.a |= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::XorR8(r)  => { let v = read_r8(cpu, bus, r); cpu.state.a ^= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::CpR8(r)   => { let v = read_r8(cpu, bus, r); alu_cp(cpu, v); }
        Z80Instruction::AddAImm => { let v = read8(cpu, bus); alu_add(cpu, v, false); }
        Z80Instruction::AdcAImm => { let v = read8(cpu, bus); let c = (cpu.state.f & FLAG_C) != 0; alu_add(cpu, v, c); }
        Z80Instruction::SubImm  => { let v = read8(cpu, bus); alu_sub(cpu, v, false); }
        Z80Instruction::SbcAImm => { let v = read8(cpu, bus); let c = (cpu.state.f & FLAG_C) != 0; alu_sub(cpu, v, c); }
        Z80Instruction::AndImm  => { let v = read8(cpu, bus); cpu.state.a &= v; alu_logic_flags(cpu, cpu.state.a); cpu.state.f |= FLAG_H; }
        Z80Instruction::OrImm   => { let v = read8(cpu, bus); cpu.state.a |= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::XorImm  => { let v = read8(cpu, bus); cpu.state.a ^= v; alu_logic_flags(cpu, cpu.state.a); }
        Z80Instruction::CpImm   => { let v = read8(cpu, bus); alu_cp(cpu, v); }
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
        Z80Instruction::IncR16(rr) => { let v = read_r16(cpu, rr).wrapping_add(1); write_r16(cpu, rr, v); }
        Z80Instruction::DecR16(rr) => { let v = read_r16(cpu, rr).wrapping_sub(1); write_r16(cpu, rr, v); }
        Z80Instruction::AddHLR16(rr) => {
            let hl = get_hl(cpu) as u32;
            let v = read_r16(cpu, rr) as u32;
            let res = hl + v;
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_PV;
            if res > 0xFFFF { cpu.state.f |= FLAG_C; }
            if ((hl ^ v ^ res) & 0x1000) != 0 { cpu.state.f |= FLAG_H; }
            set_hl(cpu, res as u16);
        }
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
        Z80Instruction::OutNA => { let _port = read8(cpu, bus); }
        Z80Instruction::InAN  => { let _port = read8(cpu, bus); cpu.state.a = 0xFF; }
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

    (cycles, format!("{:?}", instr))
}

// ──────── CB prefix: bit operations ────────
fn exec_cb<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> (u32, String) {
    let op = read8(cpu, bus);
    bump_r(cpu);
    let r_idx = op & 7;
    let bit = (op >> 3) & 7;
    let group = op >> 6;

    let val = read_r8_idx(cpu, bus, r_idx);
    let is_mem = r_idx == 6;

    match group {
        0 => {
            // Rotates/shifts
            let (result, carry) = match bit {
                0 => { let c = val >> 7; ((val << 1) | c, c) }                      // RLC
                1 => { let c = val & 1; ((val >> 1) | (c << 7), c) }                // RRC
                2 => { let c = val >> 7; ((val << 1) | (cpu.state.f & FLAG_C), c) }  // RL
                3 => { let c = val & 1; ((val >> 1) | ((cpu.state.f & FLAG_C) << 7), c) } // RR
                4 => { let c = val >> 7; (val << 1, c) }                             // SLA
                5 => { let c = val & 1; (((val as i8) >> 1) as u8, c) }              // SRA
                6 => { let c = val >> 7; ((val << 1) | 1, c) }                       // SLL (undocumented)
                _ => { let c = val & 1; (val >> 1, c) }                              // SRL
            };
            write_r8_idx(cpu, bus, r_idx, result);
            cpu.state.f = sz_flags(result) | parity(result) | (carry & FLAG_C);
            (if is_mem { 15 } else { 8 }, format!("CB {:02X}", op))
        }
        1 => {
            // BIT b,r
            let tested = val & (1 << bit);
            cpu.state.f = (cpu.state.f & FLAG_C) | FLAG_H | sz_flags(tested);
            if tested == 0 { cpu.state.f |= FLAG_PV; }
            (if is_mem { 12 } else { 8 }, format!("BIT {},r{}", bit, r_idx))
        }
        2 => {
            // RES b,r
            write_r8_idx(cpu, bus, r_idx, val & !(1 << bit));
            (if is_mem { 15 } else { 8 }, format!("RES {},r{}", bit, r_idx))
        }
        _ => {
            // SET b,r
            write_r8_idx(cpu, bus, r_idx, val | (1 << bit));
            (if is_mem { 15 } else { 8 }, format!("SET {},r{}", bit, r_idx))
        }
    }
}

// ──────── DD/FD prefix: IX/IY indexed operations ────────
fn exec_ddfd<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, is_ix: bool) -> (u32, String) {
    let op = read8(cpu, bus);
    bump_r(cpu);
    let name = if is_ix { "IX" } else { "IY" };

    // DDCB / FDCB double prefix
    if op == 0xCB {
        return exec_ddfdcb(cpu, bus, is_ix);
    }

    if matches!(op, 0x24 | 0x25 | 0x26 | 0x2C | 0x2D | 0x2E) {
        return exec_ddfd_hl_ops(cpu, bus, is_ix, op, name);
    }

    if (0x40..=0x7F).contains(&op) && op != 0x76 {
        let dst = (op >> 3) & 7;
        let src = op & 7;
        if dst != 6 && src != 6 && (uses_index_high_low(dst) || uses_index_high_low(src)) {
            let value = read_r8_ddfd_idx(cpu, bus, is_ix, src);
            write_r8_ddfd_idx(cpu, bus, is_ix, dst, value);
            return (8, format!("LD r{},r{}", dst, src));
        }
    }

    if (0x80..=0xBF).contains(&op) {
        let src = op & 7;
        if uses_index_high_low(src) {
            let value = read_r8_ddfd_idx(cpu, bus, is_ix, src);
            match (op >> 3) & 7 {
                0 => alu_add(cpu, value, false),
                1 => {
                    let carry = (cpu.state.f & FLAG_C) != 0;
                    alu_add(cpu, value, carry);
                }
                2 => alu_sub(cpu, value, false),
                3 => {
                    let carry = (cpu.state.f & FLAG_C) != 0;
                    alu_sub(cpu, value, carry);
                }
                4 => {
                    cpu.state.a &= value;
                    alu_logic_flags(cpu, cpu.state.a);
                    cpu.state.f |= FLAG_H;
                }
                5 => {
                    cpu.state.a ^= value;
                    alu_logic_flags(cpu, cpu.state.a);
                }
                6 => {
                    cpu.state.a |= value;
                    alu_logic_flags(cpu, cpu.state.a);
                }
                _ => alu_cp(cpu, value),
            }
            return (8, format!("ALU A,r{}", src));
        }
    }

    match op {
        // LD IX/IY,nn
        0x21 => {
            let v = read16(cpu, bus);
            set_ixy(cpu, is_ix, v);
            (14, format!("LD {},0x{:04X}", name, v))
        }
        // LD (nn),IX/IY
        0x22 => {
            let addr = read16(cpu, bus);
            let v = get_ixy(cpu, is_ix);
            bus.write8(addr, v as u8);
            bus.write8(addr.wrapping_add(1), (v >> 8) as u8);
            (20, format!("LD (0x{:04X}),{}", addr, name))
        }
        // INC IX/IY
        0x23 => {
            let v = get_ixy(cpu, is_ix).wrapping_add(1);
            set_ixy(cpu, is_ix, v);
            (10, format!("INC {}", name))
        }
        // DEC IX/IY
        0x2B => {
            let v = get_ixy(cpu, is_ix).wrapping_sub(1);
            set_ixy(cpu, is_ix, v);
            (10, format!("DEC {}", name))
        }
        // LD IX/IY,(nn)
        0x2A => {
            let addr = read16(cpu, bus);
            let lo = bus.read8(addr) as u16;
            let hi = bus.read8(addr.wrapping_add(1)) as u16;
            set_ixy(cpu, is_ix, (hi << 8) | lo);
            (20, format!("LD {},(0x{:04X})", name, addr))
        }
        // INC (IX/IY+d)
        0x34 => {
            let d = read8(cpu, bus) as i8;
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            let v = bus.read8(addr);
            let res = v.wrapping_add(1);
            bus.write8(addr, res);
            let c = cpu.state.f & FLAG_C;
            cpu.state.f = c | sz_flags(res);
            if (v & 0x0F) == 0x0F { cpu.state.f |= FLAG_H; }
            if v == 0x7F { cpu.state.f |= FLAG_PV; }
            (23, format!("INC ({}+{})", name, d))
        }
        // DEC (IX/IY+d)
        0x35 => {
            let d = read8(cpu, bus) as i8;
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            let v = bus.read8(addr);
            let res = v.wrapping_sub(1);
            bus.write8(addr, res);
            let c = cpu.state.f & FLAG_C;
            cpu.state.f = c | sz_flags(res) | FLAG_N;
            if (v & 0x0F) == 0x00 { cpu.state.f |= FLAG_H; }
            if v == 0x80 { cpu.state.f |= FLAG_PV; }
            (23, format!("DEC ({}+{})", name, d))
        }
        // LD (IX/IY+d),n
        0x36 => {
            let d = read8(cpu, bus) as i8;
            let n = read8(cpu, bus);
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            bus.write8(addr, n);
            (19, format!("LD ({}+{}),0x{:02X}", name, d, n))
        }
        // ADD IX/IY,rr
        0x09 | 0x19 | 0x29 | 0x39 => {
            let rr_val = match op {
                0x09 => get_bc(cpu) as u32,
                0x19 => get_de(cpu) as u32,
                0x29 => get_ixy(cpu, is_ix) as u32,
                _    => cpu.state.sp as u32,
            };
            let ixy = get_ixy(cpu, is_ix) as u32;
            let res = ixy + rr_val;
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_PV;
            if res > 0xFFFF { cpu.state.f |= FLAG_C; }
            if ((ixy ^ rr_val ^ res) & 0x1000) != 0 { cpu.state.f |= FLAG_H; }
            set_ixy(cpu, is_ix, res as u16);
            (15, format!("ADD {},{}", name, match op {
                0x09 => "BC", 0x19 => "DE", 0x29 => name, _ => "SP"
            }))
        }
        // LD r,(IX/IY+d)
        0x46 | 0x4E | 0x56 | 0x5E | 0x66 | 0x6E | 0x7E => {
            let d = read8(cpu, bus) as i8;
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            let v = bus.read8(addr);
            let dst = (op >> 3) & 7;
            write_r8_idx(cpu, bus, dst, v);
            (19, format!("LD r{},({}+{})", dst, name, d))
        }
        // LD (IX/IY+d),r
        0x70 | 0x71 | 0x72 | 0x73 | 0x74 | 0x75 | 0x77 => {
            let d = read8(cpu, bus) as i8;
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            let src = op & 7;
            let v = read_r8_idx(cpu, bus, src);
            bus.write8(addr, v);
            (19, format!("LD ({}+{}),r{}", name, d, src))
        }
        // ALU A,(IX/IY+d)
        0x86 | 0x8E | 0x96 | 0x9E | 0xA6 | 0xAE | 0xB6 | 0xBE => {
            let d = read8(cpu, bus) as i8;
            let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
            let v = bus.read8(addr);
            match (op >> 3) & 7 {
                0 => alu_add(cpu, v, false),
                1 => { let c = (cpu.state.f & FLAG_C) != 0; alu_add(cpu, v, c); }
                2 => alu_sub(cpu, v, false),
                3 => { let c = (cpu.state.f & FLAG_C) != 0; alu_sub(cpu, v, c); }
                4 => { cpu.state.a &= v; alu_logic_flags(cpu, cpu.state.a); cpu.state.f |= FLAG_H; }
                5 => { cpu.state.a ^= v; alu_logic_flags(cpu, cpu.state.a); }
                6 => { cpu.state.a |= v; alu_logic_flags(cpu, cpu.state.a); }
                _ => alu_cp(cpu, v),
            };
            (19, format!("ALU A,({}+{})", name, d))
        }
        // PUSH IX/IY
        0xE5 => {
            let v = get_ixy(cpu, is_ix);
            push16(cpu, bus, v);
            (15, format!("PUSH {}", name))
        }
        // POP IX/IY
        0xE1 => {
            let v = pop16(cpu, bus);
            set_ixy(cpu, is_ix, v);
            (14, format!("POP {}", name))
        }
        // JP (IX/IY)
        0xE9 => {
            cpu.state.pc = get_ixy(cpu, is_ix);
            (8, format!("JP ({})", name))
        }
        // EX (SP),IX/IY
        0xE3 => {
            let spl = bus.read8(cpu.state.sp);
            let sph = bus.read8(cpu.state.sp.wrapping_add(1));
            let ixy = get_ixy(cpu, is_ix);
            bus.write8(cpu.state.sp, ixy as u8);
            bus.write8(cpu.state.sp.wrapping_add(1), (ixy >> 8) as u8);
            set_ixy(cpu, is_ix, ((sph as u16) << 8) | spl as u16);
            (23, format!("EX (SP),{}", name))
        }
        // LD SP,IX/IY
        0xF9 => {
            cpu.state.sp = get_ixy(cpu, is_ix);
            (10, format!("LD SP,{}", name))
        }
        // For instructions that do not use HL, DD/FD acts as a redundant prefix.
        // Execute the underlying instruction in-place so PC/cycles/interrupt timing stay aligned.
        _ => {
            let (cycles, mnemonic) = match op {
                0xED => exec_ed(cpu, bus),
                _ => exec_unprefixed(cpu, bus, op),
            };
            return (cycles + 4, format!("{} {}", name, mnemonic));
        }
    }
}

fn exec_ddfd_hl_ops<B: Z80Bus>(cpu: &mut Z80, _bus: &mut B, is_ix: bool, op: u8, name: &str) -> (u32, String) {
    match op {
        0x24 | 0x2C => {
            let value = read_index_half(cpu, is_ix, (op >> 3) & 1 != 0).wrapping_add(1);
            write_index_half(cpu, is_ix, (op >> 3) & 1 != 0, value);
            let carry = cpu.state.f & FLAG_C;
            cpu.state.f = carry | sz_flags(value);
            if (value.wrapping_sub(1) & 0x0F) == 0x0F {
                cpu.state.f |= FLAG_H;
            }
            if value.wrapping_sub(1) == 0x7F {
                cpu.state.f |= FLAG_PV;
            }
            (8, format!("INC {}{}", name, if (op >> 3) & 1 == 0 { "H" } else { "L" }))
        }
        0x25 | 0x2D => {
            let was_low = (op >> 3) & 1 != 0;
            let previous = read_index_half(cpu, is_ix, was_low);
            let value = previous.wrapping_sub(1);
            write_index_half(cpu, is_ix, was_low, value);
            let carry = cpu.state.f & FLAG_C;
            cpu.state.f = carry | sz_flags(value) | FLAG_N;
            if (previous & 0x0F) == 0x00 {
                cpu.state.f |= FLAG_H;
            }
            if previous == 0x80 {
                cpu.state.f |= FLAG_PV;
            }
            (8, format!("DEC {}{}", name, if was_low { "L" } else { "H" }))
        }
        0x26 | 0x2E => {
            let value = read8(cpu, _bus);
            let is_low = (op >> 3) & 1 != 0;
            write_index_half(cpu, is_ix, is_low, value);
            (11, format!("LD {}{},0x{:02X}", name, if is_low { "L" } else { "H" }, value))
        }
        _ => unreachable!(),
    }
}

// ──────── DDCB/FDCB prefix: indexed bit operations ────────
fn exec_ddfdcb<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, is_ix: bool) -> (u32, String) {
    let d = read8(cpu, bus) as i8;
    let op = read8(cpu, bus);
    bump_r(cpu);
    let addr = get_ixy(cpu, is_ix).wrapping_add(d as u16);
    let val = bus.read8(addr);
    let bit = (op >> 3) & 7;
    let group = op >> 6;
    let name = if is_ix { "IX" } else { "IY" };

    match group {
        0 => {
            // Rotate/shift (IX/IY+d)
            let (result, carry) = match bit {
                0 => { let c = val >> 7; ((val << 1) | c, c) }
                1 => { let c = val & 1; ((val >> 1) | (c << 7), c) }
                2 => { let c = val >> 7; ((val << 1) | (cpu.state.f & FLAG_C), c) }
                3 => { let c = val & 1; ((val >> 1) | ((cpu.state.f & FLAG_C) << 7), c) }
                4 => { let c = val >> 7; (val << 1, c) }
                5 => { let c = val & 1; (((val as i8) >> 1) as u8, c) }
                6 => { let c = val >> 7; ((val << 1) | 1, c) }
                _ => { let c = val & 1; (val >> 1, c) }
            };
            bus.write8(addr, result);
            // Also store in register if r_idx != 6 (undocumented)
            let r_idx = op & 7;
            if r_idx != 6 { write_r8_idx(cpu, bus, r_idx, result); }
            cpu.state.f = sz_flags(result) | parity(result) | (carry & FLAG_C);
            (23, format!("ROT ({}+{})", name, d))
        }
        1 => {
            // BIT b,(IX/IY+d)
            let tested = val & (1 << bit);
            cpu.state.f = (cpu.state.f & FLAG_C) | FLAG_H | sz_flags(tested);
            if tested == 0 { cpu.state.f |= FLAG_PV; }
            (20, format!("BIT {},({}+{})", bit, name, d))
        }
        2 => {
            // RES b,(IX/IY+d)
            let result = val & !(1 << bit);
            bus.write8(addr, result);
            let r_idx = op & 7;
            if r_idx != 6 { write_r8_idx(cpu, bus, r_idx, result); }
            (23, format!("RES {},({}+{})", bit, name, d))
        }
        _ => {
            // SET b,(IX/IY+d)
            let result = val | (1 << bit);
            bus.write8(addr, result);
            let r_idx = op & 7;
            if r_idx != 6 { write_r8_idx(cpu, bus, r_idx, result); }
            (23, format!("SET {},({}+{})", bit, name, d))
        }
    }
}

// ──────── ED prefix: extended instructions ────────
fn exec_ed<B: Z80Bus>(cpu: &mut Z80, bus: &mut B) -> (u32, String) {
    let op = read8(cpu, bus);
    bump_r(cpu);
    match op {
        // IN r,(C)
        0x40 | 0x48 | 0x50 | 0x58 | 0x60 | 0x68 | 0x78 => {
            // Mega Drive Z80 has no generic Z80 I/O space; keep legacy behavior.
            let v = 0xFFu8;
            let r_idx = (op >> 3) & 7;
            write_r8_idx(cpu, bus, r_idx, v);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(v) | parity(v);
            (12, format!("IN r{},(C)", r_idx))
        }
        // IN F,(C) - undocumented, only sets flags
        0x70 => {
            let v = 0xFFu8;
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(v) | parity(v);
            (12, "IN F,(C)".into())
        }
        // OUT (C),r
        0x41 | 0x49 | 0x51 | 0x59 | 0x61 | 0x69 | 0x79 => {
            // Mega Drive Z80 I/O OUT is not mapped as generic memory write here.
            (12, format!("OUT (C),r{}", (op >> 3) & 7))
        }
        // OUT (C),0
        0x71 => { (12, "OUT (C),0".into()) }
        // SBC HL,rr
        0x42 | 0x52 | 0x62 | 0x72 => {
            let rr = ed_rr_idx(cpu, (op >> 4) & 3);
            let hl = get_hl(cpu) as u32;
            let c = if (cpu.state.f & FLAG_C) != 0 { 1u32 } else { 0 };
            let res = hl.wrapping_sub(rr as u32).wrapping_sub(c);
            cpu.state.f = FLAG_N;
            if (res & 0x8000) != 0 { cpu.state.f |= FLAG_S; }
            if (res as u16) == 0 { cpu.state.f |= FLAG_Z; }
            if res > 0xFFFF { cpu.state.f |= FLAG_C; }
            if ((hl ^ rr as u32) & (hl ^ res) & 0x8000) != 0 { cpu.state.f |= FLAG_PV; }
            if ((hl ^ rr as u32 ^ res) & 0x1000) != 0 { cpu.state.f |= FLAG_H; }
            set_hl(cpu, res as u16);
            (15, format!("SBC HL,{}", ed_rr_name((op >> 4) & 3)))
        }
        // ADC HL,rr
        0x4A | 0x5A | 0x6A | 0x7A => {
            let rr = ed_rr_idx(cpu, (op >> 4) & 3);
            let hl = get_hl(cpu) as u32;
            let c = if (cpu.state.f & FLAG_C) != 0 { 1u32 } else { 0 };
            let res = hl + rr as u32 + c;
            cpu.state.f = 0;
            if (res & 0x8000) != 0 { cpu.state.f |= FLAG_S; }
            if (res as u16) == 0 { cpu.state.f |= FLAG_Z; }
            if res > 0xFFFF { cpu.state.f |= FLAG_C; }
            if ((!(hl ^ rr as u32)) & (hl ^ res) & 0x8000) != 0 { cpu.state.f |= FLAG_PV; }
            if ((hl ^ rr as u32 ^ res) & 0x1000) != 0 { cpu.state.f |= FLAG_H; }
            set_hl(cpu, res as u16);
            (15, format!("ADC HL,{}", ed_rr_name((op >> 4) & 3)))
        }
        // LD (nn),rr
        0x43 | 0x53 | 0x63 | 0x73 => {
            let addr = read16(cpu, bus);
            let rr = ed_rr_idx(cpu, (op >> 4) & 3);
            bus.write8(addr, rr as u8);
            bus.write8(addr.wrapping_add(1), (rr >> 8) as u8);
            (20, format!("LD (0x{:04X}),{}", addr, ed_rr_name((op >> 4) & 3)))
        }
        // LD rr,(nn)
        0x4B | 0x5B | 0x6B | 0x7B => {
            let addr = read16(cpu, bus);
            let lo = bus.read8(addr) as u16;
            let hi = bus.read8(addr.wrapping_add(1)) as u16;
            let v = (hi << 8) | lo;
            ed_write_rr(cpu, (op >> 4) & 3, v);
            (20, format!("LD {},(0x{:04X})", ed_rr_name((op >> 4) & 3), addr))
        }
        // NEG
        0x44 | 0x4C | 0x54 | 0x5C | 0x64 | 0x6C | 0x74 | 0x7C => {
            let v = cpu.state.a;
            cpu.state.a = 0;
            alu_sub(cpu, v, false);
            (8, "NEG".into())
        }
        // RETN
        0x45 | 0x55 | 0x65 | 0x75 => {
            cpu.state.pc = pop16(cpu, bus);
            cpu.state.iff1 = cpu.state.iff2;
            (14, "RETN".into())
        }
        // RETI
        0x4D | 0x5D | 0x6D | 0x7D => {
            cpu.state.pc = pop16(cpu, bus);
            cpu.state.iff1 = cpu.state.iff2;
            (14, "RETI".into())
        }
        // IM 0
        0x46 | 0x66 => { cpu.state.im = 0; (8, "IM 0".into()) }
        // IM 1
        0x56 | 0x76 => { cpu.state.im = 1; (8, "IM 1".into()) }
        // IM 2
        0x5E | 0x7E => { cpu.state.im = 2; (8, "IM 2".into()) }
        // LD I,A
        0x47 => { cpu.state.i = cpu.state.a; (9, "LD I,A".into()) }
        // LD R,A
        0x4F => {
            cpu.state.r = (cpu.state.r & 0x80) | (cpu.state.a & 0x7F);
            (9, "LD R,A".into())
        }
        // LD A,I
        0x57 => {
            cpu.state.a = cpu.state.i;
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(cpu.state.a);
            if cpu.state.iff2 { cpu.state.f |= FLAG_PV; }
            (9, "LD A,I".into())
        }
        // LD A,R
        0x5F => {
            cpu.state.a = cpu.state.r;
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(cpu.state.a);
            if cpu.state.iff2 { cpu.state.f |= FLAG_PV; }
            (9, "LD A,R".into())
        }
        // RRD
        0x67 => {
            let hl = get_hl(cpu);
            let mem = bus.read8(hl);
            let new_mem = (cpu.state.a << 4) | (mem >> 4);
            cpu.state.a = (cpu.state.a & 0xF0) | (mem & 0x0F);
            bus.write8(hl, new_mem);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(cpu.state.a) | parity(cpu.state.a);
            (18, "RRD".into())
        }
        // RLD
        0x6F => {
            let hl = get_hl(cpu);
            let mem = bus.read8(hl);
            let new_mem = (mem << 4) | (cpu.state.a & 0x0F);
            cpu.state.a = (cpu.state.a & 0xF0) | (mem >> 4);
            bus.write8(hl, new_mem);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(cpu.state.a) | parity(cpu.state.a);
            (18, "RLD".into())
        }
        // LDI
        0xA0 => {
            let hl = get_hl(cpu);
            let de = get_de(cpu);
            let v = bus.read8(hl);
            bus.write8(de, v);
            set_hl(cpu, hl.wrapping_add(1));
            set_de(cpu, de.wrapping_add(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_C;
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            (16, "LDI".into())
        }
        // LDIR
        0xB0 => {
            let hl = get_hl(cpu);
            let de = get_de(cpu);
            let v = bus.read8(hl);
            bus.write8(de, v);
            set_hl(cpu, hl.wrapping_add(1));
            set_de(cpu, de.wrapping_add(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_C;
            if bc != 0 {
                cpu.state.f |= FLAG_PV;
                cpu.state.pc = cpu.state.pc.wrapping_sub(2); // repeat
                return (21, "LDIR".into());
            }
            (16, "LDIR".into())
        }
        // LDD
        0xA8 => {
            let hl = get_hl(cpu);
            let de = get_de(cpu);
            let v = bus.read8(hl);
            bus.write8(de, v);
            set_hl(cpu, hl.wrapping_sub(1));
            set_de(cpu, de.wrapping_sub(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_C;
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            (16, "LDD".into())
        }
        // LDDR
        0xB8 => {
            let hl = get_hl(cpu);
            let de = get_de(cpu);
            let v = bus.read8(hl);
            bus.write8(de, v);
            set_hl(cpu, hl.wrapping_sub(1));
            set_de(cpu, de.wrapping_sub(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            cpu.state.f &= FLAG_S | FLAG_Z | FLAG_C;
            if bc != 0 {
                cpu.state.f |= FLAG_PV;
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "LDDR".into());
            }
            (16, "LDDR".into())
        }
        // CPI
        0xA1 => {
            let hl = get_hl(cpu);
            let v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_add(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            let res = cpu.state.a.wrapping_sub(v);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(res) | FLAG_N;
            if ((cpu.state.a ^ v ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            (16, "CPI".into())
        }
        // CPIR
        0xB1 => {
            let hl = get_hl(cpu);
            let v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_add(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            let res = cpu.state.a.wrapping_sub(v);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(res) | FLAG_N;
            if ((cpu.state.a ^ v ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            if bc != 0 && res != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "CPIR".into());
            }
            (16, "CPIR".into())
        }
        // CPD
        0xA9 => {
            let hl = get_hl(cpu);
            let v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_sub(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            let res = cpu.state.a.wrapping_sub(v);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(res) | FLAG_N;
            if ((cpu.state.a ^ v ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            (16, "CPD".into())
        }
        // CPDR
        0xB9 => {
            let hl = get_hl(cpu);
            let v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_sub(1));
            let bc = get_bc(cpu).wrapping_sub(1);
            set_bc(cpu, bc);
            let res = cpu.state.a.wrapping_sub(v);
            cpu.state.f = (cpu.state.f & FLAG_C) | sz_flags(res) | FLAG_N;
            if ((cpu.state.a ^ v ^ res) & 0x10) != 0 { cpu.state.f |= FLAG_H; }
            if bc != 0 { cpu.state.f |= FLAG_PV; }
            if bc != 0 && res != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "CPDR".into());
            }
            (16, "CPDR".into())
        }
        // INI
        0xA2 => {
            let v = 0xFFu8;
            let hl = get_hl(cpu);
            bus.write8(hl, v);
            set_hl(cpu, hl.wrapping_add(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            (16, "INI".into())
        }
        // INIR
        0xB2 => {
            let v = 0xFFu8;
            let hl = get_hl(cpu);
            bus.write8(hl, v);
            set_hl(cpu, hl.wrapping_add(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            if cpu.state.b != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "INIR".into());
            }
            (16, "INIR".into())
        }
        // IND
        0xAA => {
            let v = 0xFFu8;
            let hl = get_hl(cpu);
            bus.write8(hl, v);
            set_hl(cpu, hl.wrapping_sub(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            (16, "IND".into())
        }
        // INDR
        0xBA => {
            let v = 0xFFu8;
            let hl = get_hl(cpu);
            bus.write8(hl, v);
            set_hl(cpu, hl.wrapping_sub(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            if cpu.state.b != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "INDR".into());
            }
            (16, "INDR".into())
        }
        // OUTI
        0xA3 => {
            let hl = get_hl(cpu);
            let _v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_add(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            (16, "OUTI".into())
        }
        // OTIR
        0xB3 => {
            let hl = get_hl(cpu);
            let _v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_add(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            if cpu.state.b != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "OTIR".into());
            }
            (16, "OTIR".into())
        }
        // OUTD
        0xAB => {
            let hl = get_hl(cpu);
            let _v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_sub(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            (16, "OUTD".into())
        }
        // OTDR
        0xBB => {
            let hl = get_hl(cpu);
            let _v = bus.read8(hl);
            set_hl(cpu, hl.wrapping_sub(1));
            cpu.state.b = cpu.state.b.wrapping_sub(1);
            cpu.state.f = sz_flags(cpu.state.b) | FLAG_N;
            if cpu.state.b != 0 {
                cpu.state.pc = cpu.state.pc.wrapping_sub(2);
                return (21, "OTDR".into());
            }
            (16, "OTDR".into())
        }
        // Unrecognized ED: NOP (2 bytes consumed)
        _ => (8, format!("ED {:02X} NOP", op))
    }
}

// ──────── Helper functions ────────

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
fn set_de(cpu: &mut Z80, v: u16) { cpu.state.d = (v >> 8) as u8; cpu.state.e = v as u8; }
fn set_bc(cpu: &mut Z80, v: u16) { cpu.state.b = (v >> 8) as u8; cpu.state.c = v as u8; }

fn get_ixy(cpu: &Z80, is_ix: bool) -> u16 {
    if is_ix { cpu.state.ix } else { cpu.state.iy }
}

fn set_ixy(cpu: &mut Z80, is_ix: bool, v: u16) {
    if is_ix { cpu.state.ix = v; } else { cpu.state.iy = v; }
}

fn uses_index_high_low(idx: u8) -> bool {
    idx == 4 || idx == 5
}

fn read_index_half(cpu: &Z80, is_ix: bool, is_low: bool) -> u8 {
    let value = get_ixy(cpu, is_ix);
    if is_low { value as u8 } else { (value >> 8) as u8 }
}

fn write_index_half(cpu: &mut Z80, is_ix: bool, is_low: bool, value: u8) {
    let current = get_ixy(cpu, is_ix);
    let updated = if is_low {
        (current & 0xFF00) | value as u16
    } else {
        ((value as u16) << 8) | (current & 0x00FF)
    };
    set_ixy(cpu, is_ix, updated);
}

fn read_r8_ddfd_idx<B: Z80Bus>(cpu: &Z80, bus: &B, is_ix: bool, idx: u8) -> u8 {
    match idx {
        4 => read_index_half(cpu, is_ix, false),
        5 => read_index_half(cpu, is_ix, true),
        _ => read_r8_idx(cpu, bus, idx),
    }
}

fn write_r8_ddfd_idx<B: Z80Bus>(cpu: &mut Z80, bus: &mut B, is_ix: bool, idx: u8, value: u8) {
    match idx {
        4 => write_index_half(cpu, is_ix, false, value),
        5 => write_index_half(cpu, is_ix, true, value),
        _ => write_r8_idx(cpu, bus, idx, value),
    }
}

/// Read register by 3-bit index (B=0, C=1, D=2, E=3, H=4, L=5, (HL)=6, A=7)
fn read_r8_idx<B: Z80Bus>(cpu: &Z80, bus: &B, idx: u8) -> u8 {
    match idx {
        0 => cpu.state.b, 1 => cpu.state.c, 2 => cpu.state.d, 3 => cpu.state.e,
        4 => cpu.state.h, 5 => cpu.state.l, 6 => bus.read8(get_hl(cpu)), _ => cpu.state.a,
    }
}

/// Write register by 3-bit index
fn write_r8_idx<BT: Z80Bus>(cpu: &mut Z80, bus: &mut BT, idx: u8, v: u8) {
    match idx {
        0 => cpu.state.b = v, 1 => cpu.state.c = v, 2 => cpu.state.d = v, 3 => cpu.state.e = v,
        4 => cpu.state.h = v, 5 => cpu.state.l = v,
        6 => { let a = get_hl(cpu); bus.write8(a, v); }
        _ => cpu.state.a = v,
    }
}

fn read_r8<BT: Z80Bus>(cpu: &Z80, bus: &BT, r: Reg8) -> u8 {
    match r {
        Reg8::A => cpu.state.a, Reg8::B => cpu.state.b, Reg8::C => cpu.state.c,
        Reg8::D => cpu.state.d, Reg8::E => cpu.state.e, Reg8::H => cpu.state.h,
        Reg8::L => cpu.state.l, Reg8::Mem => bus.read8(get_hl(cpu)),
    }
}

fn write_r8<BT: Z80Bus>(cpu: &mut Z80, bus: &mut BT, r: Reg8, v: u8) {
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

/// Get 16-bit register pair for ED prefix (BC=0, DE=1, HL=2, SP=3)
fn ed_rr_idx(cpu: &Z80, idx: u8) -> u16 {
    match idx {
        0 => get_bc(cpu), 1 => get_de(cpu), 2 => get_hl(cpu), _ => cpu.state.sp,
    }
}

fn ed_write_rr(cpu: &mut Z80, idx: u8, v: u16) {
    match idx {
        0 => set_bc(cpu, v), 1 => set_de(cpu, v), 2 => set_hl(cpu, v), _ => cpu.state.sp = v,
    }
}

fn ed_rr_name(idx: u8) -> &'static str {
    match idx { 0 => "BC", 1 => "DE", 2 => "HL", _ => "SP" }
}

fn eval_cond(cpu: &Z80, cc: Cond) -> bool {
    match cc {
        Cond::NZ => (cpu.state.f & FLAG_Z) == 0,
        Cond::Z  => (cpu.state.f & FLAG_Z) != 0,
        Cond::NC => (cpu.state.f & FLAG_C) == 0,
        Cond::C  => (cpu.state.f & FLAG_C) != 0,
        Cond::PO => (cpu.state.f & FLAG_PV) == 0,
        Cond::PE => (cpu.state.f & FLAG_PV) != 0,
        Cond::P  => (cpu.state.f & FLAG_S) == 0,
        Cond::M  => (cpu.state.f & FLAG_S) != 0,
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

fn bump_r(cpu: &mut Z80) {
    cpu.state.r = (cpu.state.r & 0x80) | ((cpu.state.r.wrapping_add(1)) & 0x7F);
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
