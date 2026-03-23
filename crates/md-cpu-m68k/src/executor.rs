use crate::decoder::{decode, DecodedInstruction, Direction, EaMode, MoveSize, ShiftCount};
use crate::timing::cycles_for;
use crate::{InstructionTrace, M68k, M68kBus, M68kException};

const SR_SUPERVISOR: u16 = 1 << 13;
const CCR_X: u16 = 1 << 4;
const CCR_N: u16 = 1 << 3;
const CCR_Z: u16 = 1 << 2;
const CCR_V: u16 = 1 << 1;
const CCR_C: u16 = 1 << 0;

pub fn execute_next<B: M68kBus>(cpu: &mut M68k, bus: &mut B) -> InstructionTrace {
    // Check pending interrupt
    if cpu.state.pending_ipl > 0 {
        let mask = (cpu.state.sr >> 8) & 7;
        if cpu.state.pending_ipl as u16 > mask || cpu.state.pending_ipl >= 7 {
            let level = cpu.state.pending_ipl;
            cpu.state.pending_ipl = 0;
            return take_interrupt(cpu, bus, level);
        }
    }

    if (cpu.state.pc & 1) != 0 {
        return take_exception(cpu, bus, M68kException::AddressError { address: cpu.state.pc }, cpu.state.pc, None, 50);
    }
    let pc_before = cpu.state.pc;
    let opcode = read_word(cpu, bus);
    let decoded = decode(opcode);
    let mut cycles = cycles_for(&decoded);

    match decoded {
        DecodedInstruction::Nop => {}
        DecodedInstruction::Rts => {
            cpu.state.pc = pop_long(cpu, bus);
        }
        DecodedInstruction::Rte => {
            let new_sr = pop_word(cpu, bus);
            cpu.state.pc = pop_long(cpu, bus);
            cpu.state.sr = new_sr;
        }
        DecodedInstruction::Rtr => {
            let ccr = pop_word(cpu, bus) & 0x1F;
            cpu.state.pc = pop_long(cpu, bus);
            cpu.state.sr = (cpu.state.sr & 0xFF00) | ccr;
        }
        DecodedInstruction::Reset => {}
        DecodedInstruction::Stop => {
            let new_sr = read_word(cpu, bus);
            cpu.state.sr = new_sr;
            cpu.state.stopped = true;
        }
        DecodedInstruction::TrapV => {
            if (cpu.state.sr & CCR_V) != 0 {
                return take_exception(cpu, bus, M68kException::TrapV, pc_before, Some(opcode), 34);
            }
        }
        // === Branches ===
        DecodedInstruction::Bra8(d) => {
            cpu.state.pc = add_disp(pc_before.wrapping_add(2), d as i32);
        }
        DecodedInstruction::Bra16 => {
            let base = cpu.state.pc;
            let d = read_word(cpu, bus) as i16;
            cpu.state.pc = add_disp(base, d as i32);
        }
        DecodedInstruction::Bsr8(d) => {
            let ret = cpu.state.pc;
            push_long(cpu, bus, ret);
            cpu.state.pc = add_disp(pc_before.wrapping_add(2), d as i32);
        }
        DecodedInstruction::Bsr16 => {
            let base = cpu.state.pc;
            let d = read_word(cpu, bus) as i16;
            let ret = cpu.state.pc;
            push_long(cpu, bus, ret);
            cpu.state.pc = add_disp(base, d as i32);
        }
        DecodedInstruction::Bcc8 { condition, displacement } => {
            if eval_cc(cpu.state.sr, condition) {
                cpu.state.pc = add_disp(pc_before.wrapping_add(2), displacement as i32);
                cycles = 10;
            } else {
                cycles = 8;
            }
        }
        DecodedInstruction::Bcc16 { condition } => {
            let base = cpu.state.pc;
            let d = read_word(cpu, bus) as i16;
            if eval_cc(cpu.state.sr, condition) {
                cpu.state.pc = add_disp(base, d as i32);
                cycles = 10;
            } else {
                cycles = 12;
            }
        }
        DecodedInstruction::Dbcc { condition, register } => {
            let base_pc = cpu.state.pc;
            let d = read_word(cpu, bus) as i16;
            if eval_cc(cpu.state.sr, condition) {
                cycles = 12;
            } else {
                let low = (cpu.state.d[register] & 0xFFFF) as u16;
                let next = low.wrapping_sub(1);
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_0000) | next as u32;
                if next != 0xFFFF {
                    cpu.state.pc = add_disp(base_pc, d as i32);
                    cycles = 10;
                } else {
                    cycles = 14;
                }
            }
        }
        DecodedInstruction::Scc { condition, ref ea } => {
            let val: u8 = if eval_cc(cpu.state.sr, condition) { 0xFF } else { 0x00 };
            write_ea_byte(cpu, bus, ea, val);
            cycles = if val == 0xFF { 6 } else { 4 };
        }
        // === Jumps ===
        DecodedInstruction::Jmp(ref ea) => {
            cpu.state.pc = calc_ea_addr(cpu, bus, ea);
        }
        DecodedInstruction::Jsr(ref ea) => {
            let target = calc_ea_addr(cpu, bus, ea);
            push_long(cpu, bus, cpu.state.pc);
            cpu.state.pc = target;
        }
        // === MOVE family ===
        DecodedInstruction::Move { ref size, ref src, ref dst } => {
            if matches!(dst, EaMode::PcDisplacement | EaMode::PcIndex | EaMode::Immediate) {
                return take_exception(cpu, bus, M68kException::IllegalInstruction { opcode }, pc_before, Some(opcode), 34);
            }
            match *size {
                MoveSize::Byte => {
                    let v = read_ea_byte(cpu, bus, src);
                    write_ea_byte(cpu, bus, dst, v);
                    set_nz_byte(cpu, v);
                }
                MoveSize::Word => {
                    let v = read_ea_word(cpu, bus, src);
                    write_ea_word(cpu, bus, dst, v);
                    set_nz_word(cpu, v);
                }
                MoveSize::Long => {
                    let v = read_ea_long(cpu, bus, src);
                    write_ea_long(cpu, bus, dst, v);
                    set_nz_long(cpu, v);
                }
            }
        }
        DecodedInstruction::MoveA { ref size, ref src, dst_register } => {
            let value = match *size {
                MoveSize::Byte => read_ea_byte(cpu, bus, src) as i8 as i32 as u32,
                MoveSize::Word => read_ea_word(cpu, bus, src) as i16 as i32 as u32,
                MoveSize::Long => read_ea_long(cpu, bus, src),
            };
            cpu.state.a[dst_register] = value;
        }
        DecodedInstruction::MoveQ { register, immediate } => {
            let value = immediate as i32 as u32;
            cpu.state.d[register] = value;
            set_nz_long(cpu, value);
        }
        DecodedInstruction::Movem { ref size, to_register, ref ea } => {
            let mask = read_word(cpu, bus);
            if to_register {
                exec_movem_to_reg(cpu, bus, size, ea, mask);
            } else {
                exec_movem_to_mem(cpu, bus, size, ea, mask);
            }
        }
        DecodedInstruction::MoveToSr(ref ea) => {
            let v = read_ea_word(cpu, bus, ea);
            cpu.state.sr = v;
        }
        DecodedInstruction::MoveFromSr(ref ea) => {
            let v = cpu.state.sr;
            write_ea_word(cpu, bus, ea, v);
        }
        DecodedInstruction::MoveToCcr(ref ea) => {
            let v = read_ea_word(cpu, bus, ea);
            cpu.state.sr = (cpu.state.sr & 0xFF00) | (v & 0x1F);
        }
        DecodedInstruction::MoveUsp { to_usp, register } => {
            if to_usp {
                cpu.state.usp = cpu.state.a[register];
            } else {
                cpu.state.a[register] = cpu.state.usp;
            }
        }
        // === Address ===
        DecodedInstruction::Lea { ref ea, register } => {
            cpu.state.a[register] = calc_ea_addr(cpu, bus, ea);
        }
        DecodedInstruction::Pea(ref ea) => {
            let addr = calc_ea_addr(cpu, bus, ea);
            push_long(cpu, bus, addr);
        }
        DecodedInstruction::Link { register } => {
            push_long(cpu, bus, cpu.state.a[register]);
            cpu.state.a[register] = cpu.state.a[7];
            let disp = read_word(cpu, bus) as i16 as i32;
            cpu.state.a[7] = add_disp(cpu.state.a[7], disp);
        }
        DecodedInstruction::Unlk { register } => {
            cpu.state.a[7] = cpu.state.a[register];
            cpu.state.a[register] = pop_long(cpu, bus);
        }
        DecodedInstruction::Swap(reg) => {
            let v = cpu.state.d[reg];
            let r = (v >> 16) | (v << 16);
            cpu.state.d[reg] = r;
            set_nz_long(cpu, r);
        }
        DecodedInstruction::ExtW(reg) => {
            let v = (cpu.state.d[reg] & 0xFF) as i8 as i16 as u16;
            cpu.state.d[reg] = (cpu.state.d[reg] & 0xFFFF_0000) | v as u32;
            set_nz_word(cpu, v);
        }
        DecodedInstruction::ExtL(reg) => {
            let v = (cpu.state.d[reg] & 0xFFFF) as i16 as i32 as u32;
            cpu.state.d[reg] = v;
            set_nz_long(cpu, v);
        }
        DecodedInstruction::Exg { rx, ry, mode } => {
            match mode {
                0 => { let t = cpu.state.d[rx]; cpu.state.d[rx] = cpu.state.d[ry]; cpu.state.d[ry] = t; }
                1 => { let t = cpu.state.a[rx]; cpu.state.a[rx] = cpu.state.a[ry]; cpu.state.a[ry] = t; }
                2 => { let t = cpu.state.d[rx]; cpu.state.d[rx] = cpu.state.a[ry]; cpu.state.a[ry] = t; }
                _ => {}
            }
        }
        // === Arithmetic ===
        DecodedInstruction::Add { ref size, register, ref dir, ref ea } => {
            exec_add(cpu, bus, size, register, dir, ea);
        }
        DecodedInstruction::AddA { ref size, register, ref ea } => {
            let src = match *size {
                MoveSize::Word => read_ea_word(cpu, bus, ea) as i16 as i32 as u32,
                MoveSize::Long => read_ea_long(cpu, bus, ea),
                MoveSize::Byte => read_ea_byte(cpu, bus, ea) as i8 as i32 as u32,
            };
            cpu.state.a[register] = cpu.state.a[register].wrapping_add(src);
        }
        DecodedInstruction::AddI { ref size, ref ea } => {
            exec_addi(cpu, bus, size, ea);
        }
        DecodedInstruction::AddQ { ref size, data, ref ea } => {
            exec_addq(cpu, bus, size, data, ea);
        }
        DecodedInstruction::AddX { ref size, rx, ry, mem } => {
            exec_addx(cpu, bus, size, rx, ry, mem);
        }
        DecodedInstruction::Sub { ref size, register, ref dir, ref ea } => {
            exec_sub(cpu, bus, size, register, dir, ea);
        }
        DecodedInstruction::SubA { ref size, register, ref ea } => {
            let src = match *size {
                MoveSize::Word => read_ea_word(cpu, bus, ea) as i16 as i32 as u32,
                MoveSize::Long => read_ea_long(cpu, bus, ea),
                MoveSize::Byte => read_ea_byte(cpu, bus, ea) as i8 as i32 as u32,
            };
            cpu.state.a[register] = cpu.state.a[register].wrapping_sub(src);
        }
        DecodedInstruction::SubI { ref size, ref ea } => {
            exec_subi(cpu, bus, size, ea);
        }
        DecodedInstruction::SubQ { ref size, data, ref ea } => {
            exec_subq(cpu, bus, size, data, ea);
        }
        DecodedInstruction::SubX { ref size, rx, ry, mem } => {
            exec_subx(cpu, bus, size, rx, ry, mem);
        }
        DecodedInstruction::Neg { ref size, ref ea } => {
            exec_neg(cpu, bus, size, ea);
        }
        DecodedInstruction::NegX { ref size, ref ea } => {
            exec_negx(cpu, bus, size, ea);
        }
        DecodedInstruction::Clr { ref size, ref ea } => {
            match *size {
                MoveSize::Byte => write_ea_byte(cpu, bus, ea, 0),
                MoveSize::Word => write_ea_word(cpu, bus, ea, 0),
                MoveSize::Long => write_ea_long(cpu, bus, ea, 0),
            }
            cpu.state.sr = (cpu.state.sr & !(CCR_N|CCR_V|CCR_C)) | CCR_Z;
        }
        DecodedInstruction::Tst { ref size, ref ea } => {
            match *size {
                MoveSize::Byte => { let v = read_ea_byte(cpu, bus, ea); set_nz_byte(cpu, v); }
                MoveSize::Word => { let v = read_ea_word(cpu, bus, ea); set_nz_word(cpu, v); }
                MoveSize::Long => { let v = read_ea_long(cpu, bus, ea); set_nz_long(cpu, v); }
            }
        }
        DecodedInstruction::Cmp { ref size, register, ref ea } => {
            exec_cmp(cpu, bus, size, register, ea);
        }
        DecodedInstruction::CmpA { ref size, register, ref ea } => {
            let src = match *size {
                MoveSize::Word => read_ea_word(cpu, bus, ea) as i16 as i32 as u32,
                MoveSize::Long => read_ea_long(cpu, bus, ea),
                MoveSize::Byte => read_ea_byte(cpu, bus, ea) as i8 as i32 as u32,
            };
            let dst = cpu.state.a[register];
            sub_flags_long_no_x(cpu, dst, src);
        }
        DecodedInstruction::CmpI { ref size, ref ea } => {
            exec_cmpi(cpu, bus, size, ea);
        }
        DecodedInstruction::CmpM { ref size, ax, ay } => {
            match *size {
                MoveSize::Byte => {
                    let s = read_u8(bus, cpu.state.a[ay]); cpu.state.a[ay] = cpu.state.a[ay].wrapping_add(1);
                    let d = read_u8(bus, cpu.state.a[ax]); cpu.state.a[ax] = cpu.state.a[ax].wrapping_add(1);
                    sub_flags_byte_no_x(cpu, d, s);
                }
                MoveSize::Word => {
                    let s = bus.read16(cpu.state.a[ay]); cpu.state.a[ay] = cpu.state.a[ay].wrapping_add(2);
                    let d = bus.read16(cpu.state.a[ax]); cpu.state.a[ax] = cpu.state.a[ax].wrapping_add(2);
                    sub_flags_word_no_x(cpu, d, s);
                }
                MoveSize::Long => {
                    let s = read32(bus, cpu.state.a[ay]); cpu.state.a[ay] = cpu.state.a[ay].wrapping_add(4);
                    let d = read32(bus, cpu.state.a[ax]); cpu.state.a[ax] = cpu.state.a[ax].wrapping_add(4);
                    sub_flags_long_no_x(cpu, d, s);
                }
            }
        }
        // === Logic ===
        DecodedInstruction::And { ref size, register, ref dir, ref ea } => {
            exec_logic_op(cpu, bus, size, register, dir, ea, |a, b| a & b);
        }
        DecodedInstruction::AndI { ref size, ref ea } => {
            exec_logic_imm(cpu, bus, size, ea, |a, b| a & b);
        }
        DecodedInstruction::Or { ref size, register, ref dir, ref ea } => {
            exec_logic_op(cpu, bus, size, register, dir, ea, |a, b| a | b);
        }
        DecodedInstruction::OrI { ref size, ref ea } => {
            exec_logic_imm(cpu, bus, size, ea, |a, b| a | b);
        }
        DecodedInstruction::Eor { ref size, register, ref ea } => {
            exec_eor(cpu, bus, size, register, ea);
        }
        DecodedInstruction::EorI { ref size, ref ea } => {
            exec_logic_imm(cpu, bus, size, ea, |a, b| a ^ b);
        }
        DecodedInstruction::Not { ref size, ref ea } => {
            match *size {
                MoveSize::Byte => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let v = !rmw_read_byte(cpu, bus, &t); rmw_write_byte(cpu, bus, &t, v); set_nz_byte(cpu, v); }
                MoveSize::Word => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let v = !rmw_read_word(cpu, bus, &t); rmw_write_word(cpu, bus, &t, v); set_nz_word(cpu, v); }
                MoveSize::Long => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let v = !rmw_read_long(cpu, bus, &t); rmw_write_long(cpu, bus, &t, v); set_nz_long(cpu, v); }
            }
        }
        DecodedInstruction::AndiToCcr => {
            let imm = read_word(cpu, bus) & 0x1F;
            cpu.state.sr = (cpu.state.sr & 0xFF00) | (cpu.state.sr & imm);
        }
        DecodedInstruction::AndiToSr => {
            let imm = read_word(cpu, bus);
            cpu.state.sr &= imm;
        }
        DecodedInstruction::OriToCcr => {
            let imm = read_word(cpu, bus) & 0x1F;
            cpu.state.sr |= imm;
        }
        DecodedInstruction::OriToSr => {
            let imm = read_word(cpu, bus);
            cpu.state.sr |= imm;
        }
        DecodedInstruction::EoriToCcr => {
            let imm = read_word(cpu, bus) & 0x1F;
            let ccr = cpu.state.sr & 0x1F;
            cpu.state.sr = (cpu.state.sr & 0xFF00) | (ccr ^ imm);
        }
        DecodedInstruction::EoriToSr => {
            let imm = read_word(cpu, bus);
            cpu.state.sr ^= imm;
        }
        // === Bit Operations ===
        DecodedInstruction::Btst { reg, ref ea } => {
            let bit = if let Some(r) = reg { cpu.state.d[r] } else { read_word(cpu, bus) as u32 };
            let val = read_ea_long_or_byte(cpu, bus, ea);
            let mask = match ea { EaMode::DataRegister(_) => 31, _ => 7 };
            let bit_n = bit & mask;
            if (val >> bit_n) & 1 == 0 { cpu.state.sr |= CCR_Z; } else { cpu.state.sr &= !CCR_Z; }
        }
        DecodedInstruction::Bchg { reg, ref ea } => {
            let bit = if let Some(r) = reg { cpu.state.d[r] } else { read_word(cpu, bus) as u32 };
            exec_bit_op(cpu, bus, ea, bit, |v, m| v ^ m);
        }
        DecodedInstruction::Bclr { reg, ref ea } => {
            let bit = if let Some(r) = reg { cpu.state.d[r] } else { read_word(cpu, bus) as u32 };
            exec_bit_op(cpu, bus, ea, bit, |v, m| v & !m);
        }
        DecodedInstruction::Bset { reg, ref ea } => {
            let bit = if let Some(r) = reg { cpu.state.d[r] } else { read_word(cpu, bus) as u32 };
            exec_bit_op(cpu, bus, ea, bit, |v, m| v | m);
        }
        // === Shift/Rotate ===
        DecodedInstruction::Asl { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_asl); }
        DecodedInstruction::Asr { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_asr); }
        DecodedInstruction::Lsl { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_lsl); }
        DecodedInstruction::Lsr { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_lsr); }
        DecodedInstruction::Rol { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_rol); }
        DecodedInstruction::Ror { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_ror); }
        DecodedInstruction::Roxl { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_roxl); }
        DecodedInstruction::Roxr { ref size, ref count, reg } => { exec_shift(cpu, size, count, reg, shift_roxr); }
        DecodedInstruction::AslMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_asl); }
        DecodedInstruction::AsrMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_asr); }
        DecodedInstruction::LslMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_lsl); }
        DecodedInstruction::LsrMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_lsr); }
        DecodedInstruction::RolMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_rol); }
        DecodedInstruction::RorMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_ror); }
        DecodedInstruction::RoxlMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_roxl); }
        DecodedInstruction::RoxrMem(ref ea) => { exec_shift_mem(cpu, bus, ea, shift_roxr); }
        // === Multiply/Divide ===
        DecodedInstruction::MulU { register, ref ea } => {
            let src = read_ea_word(cpu, bus, ea) as u32;
            let dst = cpu.state.d[register] & 0xFFFF;
            let result = dst.wrapping_mul(src);
            cpu.state.d[register] = result;
            set_nz_long(cpu, result);
        }
        DecodedInstruction::MulS { register, ref ea } => {
            let src = read_ea_word(cpu, bus, ea) as i16 as i32;
            let dst = (cpu.state.d[register] & 0xFFFF) as i16 as i32;
            let result = dst.wrapping_mul(src) as u32;
            cpu.state.d[register] = result;
            set_nz_long(cpu, result);
        }
        DecodedInstruction::DivU { register, ref ea } => {
            let divisor = read_ea_word(cpu, bus, ea) as u32;
            if divisor == 0 {
                return take_exception(cpu, bus, M68kException::ZeroDivide, pc_before, Some(opcode), 38);
            }
            let dividend = cpu.state.d[register];
            let quotient = dividend / divisor;
            if quotient > 0xFFFF {
                cpu.state.sr |= CCR_V; cpu.state.sr &= !CCR_C;
            } else {
                let remainder = dividend % divisor;
                cpu.state.d[register] = ((remainder & 0xFFFF) << 16) | (quotient & 0xFFFF);
                cpu.state.sr &= !(CCR_V|CCR_C);
                set_nz_word_no_clear(cpu, quotient as u16);
            }
        }
        DecodedInstruction::DivS { register, ref ea } => {
            let divisor = read_ea_word(cpu, bus, ea) as i16 as i32;
            if divisor == 0 {
                return take_exception(cpu, bus, M68kException::ZeroDivide, pc_before, Some(opcode), 38);
            }
            let dividend = cpu.state.d[register] as i32;
            let quotient = dividend / divisor;
            if quotient < -32768 || quotient > 32767 {
                cpu.state.sr |= CCR_V; cpu.state.sr &= !CCR_C;
            } else {
                let remainder = (dividend % divisor) as u32;
                cpu.state.d[register] = ((remainder & 0xFFFF) << 16) | (quotient as u16 as u32);
                cpu.state.sr &= !(CCR_V|CCR_C);
                set_nz_word_no_clear(cpu, quotient as u16);
            }
        }
        // === Trap ===
        DecodedInstruction::Trap(vector) => {
            return take_exception(cpu, bus, M68kException::Trap { vector }, pc_before, Some(opcode), 34);
        }
        // === BCD ===
        DecodedInstruction::Abcd { rx, ry, mem } => { exec_abcd(cpu, bus, rx, ry, mem); }
        DecodedInstruction::Sbcd { rx, ry, mem } => { exec_sbcd(cpu, bus, rx, ry, mem); }
        DecodedInstruction::Nbcd(ref ea) => { exec_nbcd(cpu, bus, ea); }
        // === TAS ===
        DecodedInstruction::Tas(ref ea) => {
            let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
            let v = rmw_read_byte(cpu, bus, &t);
            set_nz_byte(cpu, v);
            rmw_write_byte(cpu, bus, &t, v | 0x80);
        }
        DecodedInstruction::Illegal => {
            return take_exception(cpu, bus, M68kException::IllegalInstruction { opcode }, pc_before, Some(opcode), 34);
        }
        DecodedInstruction::LineA => {
            return take_exception(cpu, bus, M68kException::LineA { opcode }, pc_before, Some(opcode), 34);
        }
        DecodedInstruction::LineF => {
            return take_exception(cpu, bus, M68kException::LineF { opcode }, pc_before, Some(opcode), 34);
        }
    }

    cpu.state.total_cycles += cycles as u64;
    InstructionTrace { pc: pc_before, opcode, cycles, mnemonic: mnemonic_for(&decoded) }
}

// ========== Helper functions ==========

fn read_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B) -> u16 {
    let v = bus.read16(cpu.state.pc);
    cpu.state.pc = cpu.state.pc.wrapping_add(2);
    v
}

fn read_long_imm<B: M68kBus>(cpu: &mut M68k, bus: &mut B) -> u32 {
    let hi = read_word(cpu, bus) as u32;
    let lo = read_word(cpu, bus) as u32;
    (hi << 16) | lo
}

fn read_u8<B: M68kBus>(bus: &mut B, addr: u32) -> u8 {
    bus.read8(addr)
}

fn write_u8<B: M68kBus>(bus: &mut B, addr: u32, val: u8) {
    bus.write8(addr, val);
}

fn read32<B: M68kBus>(bus: &mut B, addr: u32) -> u32 {
    let hi = bus.read16(addr) as u32;
    let lo = bus.read16(addr.wrapping_add(2)) as u32;
    (hi << 16) | lo
}

fn write32<B: M68kBus>(bus: &mut B, addr: u32, val: u32) {
    bus.write16(addr, (val >> 16) as u16);
    bus.write16(addr.wrapping_add(2), (val & 0xFFFF) as u16);
}

fn push_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B, val: u16) {
    cpu.state.a[7] = cpu.state.a[7].wrapping_sub(2);
    bus.write16(cpu.state.a[7], val);
}

fn pop_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B) -> u16 {
    let v = bus.read16(cpu.state.a[7]);
    cpu.state.a[7] = cpu.state.a[7].wrapping_add(2);
    v
}

fn push_long<B: M68kBus>(cpu: &mut M68k, bus: &mut B, val: u32) {
    cpu.state.a[7] = cpu.state.a[7].wrapping_sub(4);
    write32(bus, cpu.state.a[7], val);
}

fn pop_long<B: M68kBus>(cpu: &mut M68k, bus: &mut B) -> u32 {
    let v = read32(bus, cpu.state.a[7]);
    cpu.state.a[7] = cpu.state.a[7].wrapping_add(4);
    v
}

fn add_disp(base: u32, d: i32) -> u32 {
    (base as i32).wrapping_add(d) as u32
}

fn indexed_addr(cpu: &M68k, base: u32, ext: u16) -> u32 {
    let is_addr = (ext & 0x8000) != 0;
    let ri = ((ext >> 12) & 7) as usize;
    let long = (ext & 0x0800) != 0;
    let disp = (ext & 0xFF) as u8 as i8 as i32;
    let idx_raw = if is_addr { cpu.state.a[ri] } else { cpu.state.d[ri] };
    let idx = if long { idx_raw as i32 } else { (idx_raw as i16) as i32 };
    add_disp(add_disp(base, disp), idx)
}

fn ea_inc(reg: usize, size: &MoveSize) -> u32 {
    match size {
        MoveSize::Byte => if reg == 7 { 2 } else { 1 },
        MoveSize::Word => 2,
        MoveSize::Long => 4,
    }
}

// ========== EA read/write ==========

fn calc_ea_addr<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) -> u32 {
    match ea {
        EaMode::AddressIndirect(r) | EaMode::AddressIndirectPostInc(r) => cpu.state.a[*r],
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            add_disp(cpu.state.a[*r], d)
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            indexed_addr(cpu, cpu.state.a[*r], ext)
        }
        EaMode::AbsoluteWord => read_word(cpu, bus) as i16 as i32 as u32,
        EaMode::AbsoluteLong => read_long_imm(cpu, bus),
        EaMode::PcDisplacement => {
            let base = cpu.state.pc;
            let d = read_word(cpu, bus) as i16 as i32;
            add_disp(base, d)
        }
        EaMode::PcIndex => {
            let base = cpu.state.pc;
            let ext = read_word(cpu, bus);
            indexed_addr(cpu, base, ext)
        }
        _ => 0,
    }
}

// ========== Read-modify-write helpers ==========
// These resolve the EA once, avoiding double extension word reads.

enum RmwTarget {
    DataReg(usize),
    Memory(u32),
}

fn resolve_rmw<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, sz: &MoveSize) -> RmwTarget {
    match ea {
        EaMode::DataRegister(r) => RmwTarget::DataReg(*r),
        EaMode::AddressIndirect(r) => RmwTarget::Memory(cpu.state.a[*r]),
        EaMode::AddressIndirectPostInc(r) => {
            let a = cpu.state.a[*r];
            cpu.state.a[*r] = a.wrapping_add(ea_inc(*r, sz));
            RmwTarget::Memory(a)
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(ea_inc(*r, sz));
            RmwTarget::Memory(cpu.state.a[*r])
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            RmwTarget::Memory(add_disp(cpu.state.a[*r], d))
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            RmwTarget::Memory(indexed_addr(cpu, cpu.state.a[*r], ext))
        }
        EaMode::AbsoluteWord => {
            let a = read_word(cpu, bus) as i16 as i32 as u32;
            RmwTarget::Memory(a)
        }
        EaMode::AbsoluteLong => {
            let a = read_long_imm(cpu, bus);
            RmwTarget::Memory(a)
        }
        _ => RmwTarget::Memory(0),
    }
}

fn rmw_read_byte<B: M68kBus>(cpu: &M68k, bus: &mut B, t: &RmwTarget) -> u8 {
    match t {
        RmwTarget::DataReg(r) => (cpu.state.d[*r] & 0xFF) as u8,
        RmwTarget::Memory(a) => read_u8(bus, *a),
    }
}

fn rmw_write_byte<B: M68kBus>(cpu: &mut M68k, bus: &mut B, t: &RmwTarget, v: u8) {
    match t {
        RmwTarget::DataReg(r) => cpu.state.d[*r] = (cpu.state.d[*r] & 0xFFFF_FF00) | v as u32,
        RmwTarget::Memory(a) => write_u8(bus, *a, v),
    }
}

fn rmw_read_word<B: M68kBus>(cpu: &M68k, bus: &mut B, t: &RmwTarget) -> u16 {
    match t {
        RmwTarget::DataReg(r) => (cpu.state.d[*r] & 0xFFFF) as u16,
        RmwTarget::Memory(a) => bus.read16(*a),
    }
}

fn rmw_write_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B, t: &RmwTarget, v: u16) {
    match t {
        RmwTarget::DataReg(r) => cpu.state.d[*r] = (cpu.state.d[*r] & 0xFFFF_0000) | v as u32,
        RmwTarget::Memory(a) => bus.write16(*a, v),
    }
}

fn rmw_read_long<B: M68kBus>(cpu: &M68k, bus: &mut B, t: &RmwTarget) -> u32 {
    match t {
        RmwTarget::DataReg(r) => cpu.state.d[*r],
        RmwTarget::Memory(a) => read32(bus, *a),
    }
}

fn rmw_write_long<B: M68kBus>(cpu: &mut M68k, bus: &mut B, t: &RmwTarget, v: u32) {
    match t {
        RmwTarget::DataReg(r) => cpu.state.d[*r] = v,
        RmwTarget::Memory(a) => write32(bus, *a, v),
    }
}

fn read_ea_byte<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) -> u8 {
    match ea {
        EaMode::DataRegister(r) => (cpu.state.d[*r] & 0xFF) as u8,
        EaMode::AddressRegister(r) => (cpu.state.a[*r] & 0xFF) as u8,
        EaMode::AddressIndirect(r) => read_u8(bus, cpu.state.a[*r]),
        EaMode::AddressIndirectPostInc(r) => {
            let a = cpu.state.a[*r]; let v = read_u8(bus, a);
            cpu.state.a[*r] = a.wrapping_add(ea_inc(*r, &MoveSize::Byte)); v
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(ea_inc(*r, &MoveSize::Byte));
            read_u8(bus, cpu.state.a[*r])
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            read_u8(bus, add_disp(cpu.state.a[*r], d))
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            read_u8(bus, indexed_addr(cpu, cpu.state.a[*r], ext))
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; read_u8(bus, a) }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); read_u8(bus, a) }
        EaMode::PcDisplacement => { let b = cpu.state.pc; let d = read_word(cpu, bus) as i16 as i32; read_u8(bus, add_disp(b, d)) }
        EaMode::PcIndex => { let b = cpu.state.pc; let ext = read_word(cpu, bus); read_u8(bus, indexed_addr(cpu, b, ext)) }
        EaMode::Immediate => (read_word(cpu, bus) & 0xFF) as u8,
    }
}

fn read_ea_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) -> u16 {
    match ea {
        EaMode::DataRegister(r) => (cpu.state.d[*r] & 0xFFFF) as u16,
        EaMode::AddressRegister(r) => (cpu.state.a[*r] & 0xFFFF) as u16,
        EaMode::AddressIndirect(r) => bus.read16(cpu.state.a[*r]),
        EaMode::AddressIndirectPostInc(r) => {
            let a = cpu.state.a[*r]; let v = bus.read16(a);
            cpu.state.a[*r] = a.wrapping_add(2); v
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(2);
            bus.read16(cpu.state.a[*r])
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            bus.read16(add_disp(cpu.state.a[*r], d))
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            bus.read16(indexed_addr(cpu, cpu.state.a[*r], ext))
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; bus.read16(a) }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); bus.read16(a) }
        EaMode::PcDisplacement => { let b = cpu.state.pc; let d = read_word(cpu, bus) as i16 as i32; bus.read16(add_disp(b, d)) }
        EaMode::PcIndex => { let b = cpu.state.pc; let ext = read_word(cpu, bus); bus.read16(indexed_addr(cpu, b, ext)) }
        EaMode::Immediate => read_word(cpu, bus),
    }
}

fn read_ea_long<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) -> u32 {
    match ea {
        EaMode::DataRegister(r) => cpu.state.d[*r],
        EaMode::AddressRegister(r) => cpu.state.a[*r],
        EaMode::AddressIndirect(r) => read32(bus, cpu.state.a[*r]),
        EaMode::AddressIndirectPostInc(r) => {
            let a = cpu.state.a[*r]; let v = read32(bus, a);
            cpu.state.a[*r] = a.wrapping_add(4); v
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(4);
            read32(bus, cpu.state.a[*r])
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            read32(bus, add_disp(cpu.state.a[*r], d))
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            read32(bus, indexed_addr(cpu, cpu.state.a[*r], ext))
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; read32(bus, a) }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); read32(bus, a) }
        EaMode::PcDisplacement => { let b = cpu.state.pc; let d = read_word(cpu, bus) as i16 as i32; read32(bus, add_disp(b, d)) }
        EaMode::PcIndex => { let b = cpu.state.pc; let ext = read_word(cpu, bus); read32(bus, indexed_addr(cpu, b, ext)) }
        EaMode::Immediate => read_long_imm(cpu, bus),
    }
}

fn write_ea_byte<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, val: u8) {
    match ea {
        EaMode::DataRegister(r) => cpu.state.d[*r] = (cpu.state.d[*r] & 0xFFFF_FF00) | val as u32,
        EaMode::AddressRegister(r) => cpu.state.a[*r] = (cpu.state.a[*r] & 0xFFFF_FF00) | val as u32,
        EaMode::AddressIndirect(r) => write_u8(bus, cpu.state.a[*r], val),
        EaMode::AddressIndirectPostInc(r) => {
            write_u8(bus, cpu.state.a[*r], val);
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_add(ea_inc(*r, &MoveSize::Byte));
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(ea_inc(*r, &MoveSize::Byte));
            write_u8(bus, cpu.state.a[*r], val);
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            write_u8(bus, add_disp(cpu.state.a[*r], d), val);
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            write_u8(bus, indexed_addr(cpu, cpu.state.a[*r], ext), val);
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; write_u8(bus, a, val); }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); write_u8(bus, a, val); }
        _ => {}
    }
}

fn write_ea_word<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, val: u16) {
    match ea {
        EaMode::DataRegister(r) => cpu.state.d[*r] = (cpu.state.d[*r] & 0xFFFF_0000) | val as u32,
        EaMode::AddressRegister(r) => cpu.state.a[*r] = val as i16 as i32 as u32,
        EaMode::AddressIndirect(r) => bus.write16(cpu.state.a[*r], val),
        EaMode::AddressIndirectPostInc(r) => {
            bus.write16(cpu.state.a[*r], val);
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_add(2);
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(2);
            bus.write16(cpu.state.a[*r], val);
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            bus.write16(add_disp(cpu.state.a[*r], d), val);
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            bus.write16(indexed_addr(cpu, cpu.state.a[*r], ext), val);
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; bus.write16(a, val); }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); bus.write16(a, val); }
        _ => {}
    }
}

fn write_ea_long<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, val: u32) {
    match ea {
        EaMode::DataRegister(r) => cpu.state.d[*r] = val,
        EaMode::AddressRegister(r) => cpu.state.a[*r] = val,
        EaMode::AddressIndirect(r) => write32(bus, cpu.state.a[*r], val),
        EaMode::AddressIndirectPostInc(r) => {
            write32(bus, cpu.state.a[*r], val);
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_add(4);
        }
        EaMode::AddressIndirectPreDec(r) => {
            cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(4);
            write32(bus, cpu.state.a[*r], val);
        }
        EaMode::AddressDisplacement(r) => {
            let d = read_word(cpu, bus) as i16 as i32;
            write32(bus, add_disp(cpu.state.a[*r], d), val);
        }
        EaMode::AddressIndex(r) => {
            let ext = read_word(cpu, bus);
            write32(bus, indexed_addr(cpu, cpu.state.a[*r], ext), val);
        }
        EaMode::AbsoluteWord => { let a = read_word(cpu, bus) as i16 as i32 as u32; write32(bus, a, val); }
        EaMode::AbsoluteLong => { let a = read_long_imm(cpu, bus); write32(bus, a, val); }
        _ => {}
    }
}

fn read_ea_long_or_byte<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) -> u32 {
    match ea {
        EaMode::DataRegister(_) => read_ea_long(cpu, bus, ea),
        _ => read_ea_byte(cpu, bus, ea) as u32,
    }
}

// ========== Flags ==========

fn set_nz_byte(cpu: &mut M68k, v: u8) {
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v & 0x80) != 0 { cpu.state.sr |= CCR_N; }
}

fn set_nz_word(cpu: &mut M68k, v: u16) {
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
}

fn set_nz_long(cpu: &mut M68k, v: u32) {
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
}

fn set_nz_word_no_clear(cpu: &mut M68k, v: u16) {
    cpu.state.sr &= !(CCR_N|CCR_Z);
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
}

fn add_flags_byte(cpu: &mut M68k, dst: u8, src: u8) -> u8 {
    let r = (dst as u16).wrapping_add(src as u16);
    let res = r as u8;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x80) != 0 { cpu.state.sr |= CCR_N; }
    if r > 0xFF { cpu.state.sr |= CCR_C | CCR_X; }
    let sv = ((!(dst ^ src)) & (src ^ res)) & 0x80;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

fn add_flags_word(cpu: &mut M68k, dst: u16, src: u16) -> u16 {
    let r = (dst as u32).wrapping_add(src as u32);
    let res = r as u16;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
    if r > 0xFFFF { cpu.state.sr |= CCR_C | CCR_X; }
    let sv = ((!(dst ^ src)) & (src ^ res)) & 0x8000;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

fn add_flags_long(cpu: &mut M68k, dst: u32, src: u32) -> u32 {
    let r = (dst as u64).wrapping_add(src as u64);
    let res = r as u32;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
    if r > 0xFFFF_FFFF { cpu.state.sr |= CCR_C | CCR_X; }
    let sv = ((!(dst ^ src)) & (src ^ res)) & 0x8000_0000;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

fn sub_flags_byte(cpu: &mut M68k, dst: u8, src: u8) -> u8 {
    sub_flags_byte_inner(cpu, dst, src, true)
}

fn sub_flags_byte_no_x(cpu: &mut M68k, dst: u8, src: u8) -> u8 {
    sub_flags_byte_inner(cpu, dst, src, false)
}

fn sub_flags_byte_inner(cpu: &mut M68k, dst: u8, src: u8, update_x: bool) -> u8 {
    let r = (dst as i16).wrapping_sub(src as i16);
    let res = r as u8;
    if update_x {
        cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    } else {
        cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    }
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x80) != 0 { cpu.state.sr |= CCR_N; }
    if (dst as u16) < (src as u16) { cpu.state.sr |= CCR_C; if update_x { cpu.state.sr |= CCR_X; } }
    let sv = ((dst ^ src) & (dst ^ res)) & 0x80;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

fn sub_flags_word(cpu: &mut M68k, dst: u16, src: u16) -> u16 {
    sub_flags_word_inner(cpu, dst, src, true)
}

fn sub_flags_word_no_x(cpu: &mut M68k, dst: u16, src: u16) -> u16 {
    sub_flags_word_inner(cpu, dst, src, false)
}

fn sub_flags_word_inner(cpu: &mut M68k, dst: u16, src: u16, update_x: bool) -> u16 {
    let r = (dst as i32).wrapping_sub(src as i32);
    let res = r as u16;
    if update_x {
        cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    } else {
        cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    }
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
    if (dst as u32) < (src as u32) { cpu.state.sr |= CCR_C; if update_x { cpu.state.sr |= CCR_X; } }
    let sv = ((dst ^ src) & (dst ^ res)) & 0x8000;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

fn sub_flags_long(cpu: &mut M68k, dst: u32, src: u32) -> u32 {
    sub_flags_long_inner(cpu, dst, src, true)
}

fn sub_flags_long_no_x(cpu: &mut M68k, dst: u32, src: u32) -> u32 {
    sub_flags_long_inner(cpu, dst, src, false)
}

fn sub_flags_long_inner(cpu: &mut M68k, dst: u32, src: u32, update_x: bool) -> u32 {
    let r = (dst as i64).wrapping_sub(src as i64);
    let res = r as u32;
    if update_x {
        cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    } else {
        cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    }
    if res == 0 { cpu.state.sr |= CCR_Z; }
    if (res & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
    if (dst as u64) < (src as u64) { cpu.state.sr |= CCR_C; if update_x { cpu.state.sr |= CCR_X; } }
    let sv = ((dst ^ src) & (dst ^ res)) & 0x8000_0000;
    if sv != 0 { cpu.state.sr |= CCR_V; }
    res
}

// ========== Arithmetic implementations ==========

fn exec_add<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, register: usize, dir: &Direction, ea: &EaMode) {
    match dir {
        Direction::EaToReg => match *size {
            MoveSize::Byte => {
                let src_val = read_ea_byte(cpu, bus, ea);
                let dst_val = (cpu.state.d[register] & 0xFF) as u8;
                let res = add_flags_byte(cpu, dst_val, src_val);
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_FF00) | res as u32;
            }
            MoveSize::Word => {
                let src_val = read_ea_word(cpu, bus, ea);
                let dst_val = (cpu.state.d[register] & 0xFFFF) as u16;
                let res = add_flags_word(cpu, dst_val, src_val);
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_0000) | res as u32;
            }
            MoveSize::Long => {
                let src_val = read_ea_long(cpu, bus, ea);
                let dst_val = cpu.state.d[register];
                let res = add_flags_long(cpu, dst_val, src_val);
                cpu.state.d[register] = res;
            }
        },
        Direction::RegToEa => match *size {
            MoveSize::Byte => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
                let dst_val = rmw_read_byte(cpu, bus, &t);
                let src_val = (cpu.state.d[register] & 0xFF) as u8;
                let res = add_flags_byte(cpu, dst_val, src_val);
                rmw_write_byte(cpu, bus, &t, res);
            }
            MoveSize::Word => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word);
                let dst_val = rmw_read_word(cpu, bus, &t);
                let src_val = (cpu.state.d[register] & 0xFFFF) as u16;
                let res = add_flags_word(cpu, dst_val, src_val);
                rmw_write_word(cpu, bus, &t, res);
            }
            MoveSize::Long => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long);
                let dst_val = rmw_read_long(cpu, bus, &t);
                let src_val = cpu.state.d[register];
                let res = add_flags_long(cpu, dst_val, src_val);
                rmw_write_long(cpu, bus, &t, res);
            }
        },
    }
}

fn exec_addi<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let imm = (read_word(cpu, bus) & 0xFF) as u8; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t); let r = add_flags_byte(cpu, d, imm); rmw_write_byte(cpu, bus, &t, r); }
        MoveSize::Word => { let imm = read_word(cpu, bus); let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t); let r = add_flags_word(cpu, d, imm); rmw_write_word(cpu, bus, &t, r); }
        MoveSize::Long => { let imm = read_long_imm(cpu, bus); let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = add_flags_long(cpu, d, imm); rmw_write_long(cpu, bus, &t, r); }
    }
}

fn exec_addq<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, data: u8, ea: &EaMode) {
    if let EaMode::AddressRegister(r) = ea {
        cpu.state.a[*r] = cpu.state.a[*r].wrapping_add(data as u32);
        return;
    }
    match *size {
        MoveSize::Byte => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t); let r = add_flags_byte(cpu, d, data); rmw_write_byte(cpu, bus, &t, r); }
        MoveSize::Word => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t); let r = add_flags_word(cpu, d, data as u16); rmw_write_word(cpu, bus, &t, r); }
        MoveSize::Long => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = add_flags_long(cpu, d, data as u32); rmw_write_long(cpu, bus, &t, r); }
    }
}

fn exec_addx<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, rx: usize, ry: usize, mem: bool) {
    let x = if (cpu.state.sr & CCR_X) != 0 { 1u32 } else { 0 };
    match *size {
        MoveSize::Byte => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(1);
                let sv = read_u8(bus, cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(1);
                let dv = read_u8(bus, cpu.state.a[rx]);
                (sv, dv)
            } else { ((cpu.state.d[ry] & 0xFF) as u8, (cpu.state.d[rx] & 0xFF) as u8) };
            let r = (d as u16).wrapping_add(s as u16).wrapping_add(x as u16);
            let res = r as u8;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x80) != 0 { cpu.state.sr |= CCR_N; }
            if r > 0xFF { cpu.state.sr |= CCR_C | CCR_X; }
            if ((!(d ^ s)) & (s ^ res)) & 0x80 != 0 { cpu.state.sr |= CCR_V; }
            if mem { write_u8(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_FF00) | res as u32; }
        }
        MoveSize::Word => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(2);
                let sv = bus.read16(cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(2);
                let dv = bus.read16(cpu.state.a[rx]);
                (sv, dv)
            } else { ((cpu.state.d[ry] & 0xFFFF) as u16, (cpu.state.d[rx] & 0xFFFF) as u16) };
            let r = (d as u32).wrapping_add(s as u32).wrapping_add(x);
            let res = r as u16;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
            if r > 0xFFFF { cpu.state.sr |= CCR_C | CCR_X; }
            if ((!(d ^ s)) & (s ^ res)) & 0x8000 != 0 { cpu.state.sr |= CCR_V; }
            if mem { bus.write16(cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_0000) | res as u32; }
        }
        MoveSize::Long => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(4);
                let sv = read32(bus, cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(4);
                let dv = read32(bus, cpu.state.a[rx]);
                (sv, dv)
            } else { (cpu.state.d[ry], cpu.state.d[rx]) };
            let r = (d as u64).wrapping_add(s as u64).wrapping_add(x as u64);
            let res = r as u32;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
            if r > 0xFFFF_FFFF { cpu.state.sr |= CCR_C | CCR_X; }
            if ((!(d ^ s)) & (s ^ res)) & 0x8000_0000 != 0 { cpu.state.sr |= CCR_V; }
            if mem { write32(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = res; }
        }
    }
}

fn exec_sub<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, register: usize, dir: &Direction, ea: &EaMode) {
    match dir {
        Direction::EaToReg => match *size {
            MoveSize::Byte => {
                let s = read_ea_byte(cpu, bus, ea);
                let d = (cpu.state.d[register] & 0xFF) as u8;
                let res = sub_flags_byte(cpu, d, s);
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_FF00) | res as u32;
            }
            MoveSize::Word => {
                let s = read_ea_word(cpu, bus, ea);
                let d = (cpu.state.d[register] & 0xFFFF) as u16;
                let res = sub_flags_word(cpu, d, s);
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_0000) | res as u32;
            }
            MoveSize::Long => {
                let s = read_ea_long(cpu, bus, ea);
                let d = cpu.state.d[register];
                let res = sub_flags_long(cpu, d, s);
                cpu.state.d[register] = res;
            }
        },
        Direction::RegToEa => match *size {
            MoveSize::Byte => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
                let d = rmw_read_byte(cpu, bus, &t);
                let s = (cpu.state.d[register] & 0xFF) as u8;
                let res = sub_flags_byte(cpu, d, s);
                rmw_write_byte(cpu, bus, &t, res);
            }
            MoveSize::Word => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word);
                let d = rmw_read_word(cpu, bus, &t);
                let s = (cpu.state.d[register] & 0xFFFF) as u16;
                let res = sub_flags_word(cpu, d, s);
                rmw_write_word(cpu, bus, &t, res);
            }
            MoveSize::Long => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long);
                let d = rmw_read_long(cpu, bus, &t);
                let s = cpu.state.d[register];
                let res = sub_flags_long(cpu, d, s);
                rmw_write_long(cpu, bus, &t, res);
            }
        },
    }
}

fn exec_subi<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let imm = (read_word(cpu, bus) & 0xFF) as u8; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t); let r = sub_flags_byte(cpu, d, imm); rmw_write_byte(cpu, bus, &t, r); }
        MoveSize::Word => { let imm = read_word(cpu, bus); let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t); let r = sub_flags_word(cpu, d, imm); rmw_write_word(cpu, bus, &t, r); }
        MoveSize::Long => { let imm = read_long_imm(cpu, bus); let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = sub_flags_long(cpu, d, imm); rmw_write_long(cpu, bus, &t, r); }
    }
}

fn exec_subq<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, data: u8, ea: &EaMode) {
    if let EaMode::AddressRegister(r) = ea {
        cpu.state.a[*r] = cpu.state.a[*r].wrapping_sub(data as u32);
        return;
    }
    match *size {
        MoveSize::Byte => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t); let r = sub_flags_byte(cpu, d, data); rmw_write_byte(cpu, bus, &t, r); }
        MoveSize::Word => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t); let r = sub_flags_word(cpu, d, data as u16); rmw_write_word(cpu, bus, &t, r); }
        MoveSize::Long => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = sub_flags_long(cpu, d, data as u32); rmw_write_long(cpu, bus, &t, r); }
    }
}

fn exec_subx<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, rx: usize, ry: usize, mem: bool) {
    let x = if (cpu.state.sr & CCR_X) != 0 { 1u32 } else { 0 };
    match *size {
        MoveSize::Long => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(4); let sv = read32(bus, cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(4); let dv = read32(bus, cpu.state.a[rx]);
                (sv, dv)
            } else { (cpu.state.d[ry], cpu.state.d[rx]) };
            let r = (d as u64).wrapping_sub(s as u64).wrapping_sub(x as u64);
            let res = r as u32;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
            if (d as u64) < (s as u64).wrapping_add(x as u64) { cpu.state.sr |= CCR_C | CCR_X; }
            if ((d ^ s) & (d ^ res)) & 0x8000_0000 != 0 { cpu.state.sr |= CCR_V; }
            if mem { write32(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = res; }
        }
        MoveSize::Word => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(2); let sv = bus.read16(cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(2); let dv = bus.read16(cpu.state.a[rx]);
                (sv, dv)
            } else { ((cpu.state.d[ry] & 0xFFFF) as u16, (cpu.state.d[rx] & 0xFFFF) as u16) };
            let r = (d as u32).wrapping_sub(s as u32).wrapping_sub(x);
            let res = r as u16;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
            if (d as u32) < (s as u32).wrapping_add(x) { cpu.state.sr |= CCR_C | CCR_X; }
            if ((d ^ s) & (d ^ res)) & 0x8000 != 0 { cpu.state.sr |= CCR_V; }
            if mem { bus.write16(cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_0000) | res as u32; }
        }
        MoveSize::Byte => {
            let (s, d) = if mem {
                cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(1); let sv = read_u8(bus, cpu.state.a[ry]);
                cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(1); let dv = read_u8(bus, cpu.state.a[rx]);
                (sv, dv)
            } else { ((cpu.state.d[ry] & 0xFF) as u8, (cpu.state.d[rx] & 0xFF) as u8) };
            let r = (d as u16).wrapping_sub(s as u16).wrapping_sub(x as u16);
            let res = r as u8;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x80) != 0 { cpu.state.sr |= CCR_N; }
            if (d as u16) < (s as u16).wrapping_add(x as u16) { cpu.state.sr |= CCR_C | CCR_X; }
            if ((d ^ s) & (d ^ res)) & 0x80 != 0 { cpu.state.sr |= CCR_V; }
            if mem { write_u8(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_FF00) | res as u32; }
        }
    }
}

fn exec_neg<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let v = rmw_read_byte(cpu, bus, &t); let r = sub_flags_byte(cpu, 0, v); rmw_write_byte(cpu, bus, &t, r); }
        MoveSize::Word => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let v = rmw_read_word(cpu, bus, &t); let r = sub_flags_word(cpu, 0, v); rmw_write_word(cpu, bus, &t, r); }
        MoveSize::Long => { let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let v = rmw_read_long(cpu, bus, &t); let r = sub_flags_long(cpu, 0, v); rmw_write_long(cpu, bus, &t, r); }
    }
}

fn exec_negx<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode) {
    let x = if (cpu.state.sr & CCR_X) != 0 { 1u32 } else { 0 };
    match *size {
        MoveSize::Long => {
            let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long);
            let v = rmw_read_long(cpu, bus, &t);
            let r = 0u64.wrapping_sub(v as u64).wrapping_sub(x as u64);
            let res = r as u32;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000_0000) != 0 { cpu.state.sr |= CCR_N; }
            if v != 0 || x != 0 { cpu.state.sr |= CCR_C | CCR_X; }
            rmw_write_long(cpu, bus, &t, res);
        }
        MoveSize::Word => {
            let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word);
            let v = rmw_read_word(cpu, bus, &t);
            let r = 0u32.wrapping_sub(v as u32).wrapping_sub(x);
            let res = r as u16;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x8000) != 0 { cpu.state.sr |= CCR_N; }
            if v != 0 || x != 0 { cpu.state.sr |= CCR_C | CCR_X; }
            rmw_write_word(cpu, bus, &t, res);
        }
        MoveSize::Byte => {
            let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
            let v = rmw_read_byte(cpu, bus, &t);
            let r = 0u16.wrapping_sub(v as u16).wrapping_sub(x as u16);
            let res = r as u8;
            let old_z = cpu.state.sr & CCR_Z;
            cpu.state.sr &= !(CCR_X|CCR_N|CCR_V|CCR_C);
            if res != 0 { cpu.state.sr &= !CCR_Z; } else { cpu.state.sr |= old_z & CCR_Z; }
            if (res & 0x80) != 0 { cpu.state.sr |= CCR_N; }
            if v != 0 || x != 0 { cpu.state.sr |= CCR_C | CCR_X; }
            rmw_write_byte(cpu, bus, &t, res);
        }
    }
}

fn exec_cmp<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, register: usize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let s = read_ea_byte(cpu, bus, ea); let d = (cpu.state.d[register] & 0xFF) as u8; sub_flags_byte_no_x(cpu, d, s); }
        MoveSize::Word => { let s = read_ea_word(cpu, bus, ea); let d = (cpu.state.d[register] & 0xFFFF) as u16; sub_flags_word_no_x(cpu, d, s); }
        MoveSize::Long => { let s = read_ea_long(cpu, bus, ea); let d = cpu.state.d[register]; sub_flags_long_no_x(cpu, d, s); }
    }
}

fn exec_cmpi<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let imm = (read_word(cpu, bus) & 0xFF) as u8; let d = read_ea_byte(cpu, bus, ea); sub_flags_byte_no_x(cpu, d, imm); }
        MoveSize::Word => { let imm = read_word(cpu, bus); let d = read_ea_word(cpu, bus, ea); sub_flags_word_no_x(cpu, d, imm); }
        MoveSize::Long => { let imm = read_long_imm(cpu, bus); let d = read_ea_long(cpu, bus, ea); sub_flags_long_no_x(cpu, d, imm); }
    }
}

// ========== Logic ==========

fn exec_logic_op<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, register: usize, dir: &Direction, ea: &EaMode, op: fn(u32, u32) -> u32) {
    match dir {
        Direction::EaToReg => match *size {
            MoveSize::Byte => {
                let s = read_ea_byte(cpu, bus, ea) as u32;
                let d = (cpu.state.d[register] & 0xFF) as u32;
                let res = op(d, s) as u8;
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_FF00) | res as u32;
                set_nz_byte(cpu, res);
            }
            MoveSize::Word => {
                let s = read_ea_word(cpu, bus, ea) as u32;
                let d = (cpu.state.d[register] & 0xFFFF) as u32;
                let res = op(d, s) as u16;
                cpu.state.d[register] = (cpu.state.d[register] & 0xFFFF_0000) | res as u32;
                set_nz_word(cpu, res);
            }
            MoveSize::Long => {
                let s = read_ea_long(cpu, bus, ea);
                let d = cpu.state.d[register];
                let res = op(d, s);
                cpu.state.d[register] = res;
                set_nz_long(cpu, res);
            }
        },
        Direction::RegToEa => match *size {
            MoveSize::Byte => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
                let d = rmw_read_byte(cpu, bus, &t) as u32;
                let s = (cpu.state.d[register] & 0xFF) as u32;
                let res = op(d, s) as u8;
                rmw_write_byte(cpu, bus, &t, res);
                set_nz_byte(cpu, res);
            }
            MoveSize::Word => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word);
                let d = rmw_read_word(cpu, bus, &t) as u32;
                let s = (cpu.state.d[register] & 0xFFFF) as u32;
                let res = op(d, s) as u16;
                rmw_write_word(cpu, bus, &t, res);
                set_nz_word(cpu, res);
            }
            MoveSize::Long => {
                let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long);
                let d = rmw_read_long(cpu, bus, &t);
                let s = cpu.state.d[register];
                let res = op(d, s);
                rmw_write_long(cpu, bus, &t, res);
                set_nz_long(cpu, res);
            }
        },
    }
}

fn exec_logic_imm<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode, op: fn(u32, u32) -> u32) {
    match *size {
        MoveSize::Byte => { let imm = (read_word(cpu, bus) & 0xFF) as u32; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t) as u32; let r = op(d, imm) as u8; rmw_write_byte(cpu, bus, &t, r); set_nz_byte(cpu, r); }
        MoveSize::Word => { let imm = read_word(cpu, bus) as u32; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t) as u32; let r = op(d, imm) as u16; rmw_write_word(cpu, bus, &t, r); set_nz_word(cpu, r); }
        MoveSize::Long => { let imm = read_long_imm(cpu, bus); let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = op(d, imm); rmw_write_long(cpu, bus, &t, r); set_nz_long(cpu, r); }
    }
}

fn exec_eor<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, register: usize, ea: &EaMode) {
    match *size {
        MoveSize::Byte => { let s = (cpu.state.d[register] & 0xFF) as u8; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte); let d = rmw_read_byte(cpu, bus, &t); let r = d ^ s; rmw_write_byte(cpu, bus, &t, r); set_nz_byte(cpu, r); }
        MoveSize::Word => { let s = (cpu.state.d[register] & 0xFFFF) as u16; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word); let d = rmw_read_word(cpu, bus, &t); let r = d ^ s; rmw_write_word(cpu, bus, &t, r); set_nz_word(cpu, r); }
        MoveSize::Long => { let s = cpu.state.d[register]; let t = resolve_rmw(cpu, bus, ea, &MoveSize::Long); let d = rmw_read_long(cpu, bus, &t); let r = d ^ s; rmw_write_long(cpu, bus, &t, r); set_nz_long(cpu, r); }
    }
}

// ========== Bit operations ==========

fn exec_bit_op<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, bit: u32, op: fn(u32, u32) -> u32) {
    match ea {
        EaMode::DataRegister(r) => {
            let mask_bit = bit & 31;
            let val = cpu.state.d[*r];
            if (val >> mask_bit) & 1 == 0 { cpu.state.sr |= CCR_Z; } else { cpu.state.sr &= !CCR_Z; }
            cpu.state.d[*r] = op(val, 1 << mask_bit);
        }
        _ => {
            let mask_bit = bit & 7;
            let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
            let val = rmw_read_byte(cpu, bus, &t) as u32;
            if (val >> mask_bit) & 1 == 0 { cpu.state.sr |= CCR_Z; } else { cpu.state.sr &= !CCR_Z; }
            rmw_write_byte(cpu, bus, &t, op(val, 1 << mask_bit) as u8);
        }
    }
}

// ========== Shifts ==========

type ShiftFn = fn(&mut M68k, u32, u32, u32) -> u32;

fn shift_asl(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    let mut overflow = false;
    for _ in 0..count {
        let msb = (v >> (bits - 1)) & 1;
        v = (v << 1) & mask;
        if msb != 0 { cpu.state.sr |= CCR_C | CCR_X; } else { cpu.state.sr &= !(CCR_C | CCR_X); }
        if ((v >> (bits - 1)) & 1) != msb { overflow = true; }
    }
    if overflow { cpu.state.sr |= CCR_V; }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    if count == 0 { cpu.state.sr &= !(CCR_V|CCR_C); set_nz_for(cpu, v, bits); }
    v
}

fn shift_asr(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let sign = (val >> (bits - 1)) & 1;
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let lsb = v & 1;
        v = (v >> 1) | (sign << (bits - 1));
        v &= mask;
        if lsb != 0 { cpu.state.sr |= CCR_C | CCR_X; } else { cpu.state.sr &= !(CCR_C | CCR_X); }
    }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    if count == 0 { cpu.state.sr &= !CCR_C; set_nz_for(cpu, v, bits); }
    v
}

fn shift_lsl(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let msb = (v >> (bits - 1)) & 1;
        v = (v << 1) & mask;
        if msb != 0 { cpu.state.sr |= CCR_C | CCR_X; } else { cpu.state.sr &= !(CCR_C | CCR_X); }
    }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    if count == 0 { cpu.state.sr &= !CCR_C; set_nz_for(cpu, v, bits); }
    v
}

fn shift_lsr(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_X|CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let lsb = v & 1;
        v >>= 1;
        if lsb != 0 { cpu.state.sr |= CCR_C | CCR_X; } else { cpu.state.sr &= !(CCR_C | CCR_X); }
    }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    if count == 0 { cpu.state.sr &= !CCR_C; set_nz_for(cpu, v, bits); }
    v
}

fn shift_rol(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let msb = (v >> (bits - 1)) & 1;
        v = ((v << 1) | msb) & mask;
        if msb != 0 { cpu.state.sr |= CCR_C; } else { cpu.state.sr &= !CCR_C; }
    }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    v
}

fn shift_ror(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let lsb = v & 1;
        v = (v >> 1) | (lsb << (bits - 1));
        v &= mask;
        if lsb != 0 { cpu.state.sr |= CCR_C; } else { cpu.state.sr &= !CCR_C; }
    }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    v
}

fn shift_roxl(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    let mut x = if (cpu.state.sr & CCR_X) != 0 { 1u32 } else { 0 };
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let msb = (v >> (bits - 1)) & 1;
        v = ((v << 1) | x) & mask;
        x = msb;
    }
    if x != 0 { cpu.state.sr |= CCR_C | CCR_X; }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    v
}

fn shift_roxr(cpu: &mut M68k, val: u32, count: u32, mask: u32) -> u32 {
    let bits = if mask == 0xFF { 8 } else if mask == 0xFFFF { 16 } else { 32 };
    let mut v = val & mask;
    let mut x = if (cpu.state.sr & CCR_X) != 0 { 1u32 } else { 0 };
    cpu.state.sr &= !(CCR_N|CCR_Z|CCR_V|CCR_C);
    for _ in 0..count {
        let lsb = v & 1;
        v = (v >> 1) | (x << (bits - 1));
        v &= mask;
        x = lsb;
    }
    if x != 0 { cpu.state.sr |= CCR_C | CCR_X; }
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
    v
}

fn set_nz_for(cpu: &mut M68k, v: u32, bits: u32) {
    cpu.state.sr &= !(CCR_N|CCR_Z);
    if v == 0 { cpu.state.sr |= CCR_Z; }
    if (v >> (bits - 1)) & 1 != 0 { cpu.state.sr |= CCR_N; }
}

fn exec_shift(cpu: &mut M68k, size: &MoveSize, count: &ShiftCount, reg: usize, op: ShiftFn) {
    let cnt = match count {
        ShiftCount::Imm(n) => *n as u32,
        ShiftCount::Reg(r) => cpu.state.d[*r as usize] & 63,
    };
    let mask = match size { MoveSize::Byte => 0xFFu32, MoveSize::Word => 0xFFFF, MoveSize::Long => 0xFFFF_FFFF };
    let val = cpu.state.d[reg] & mask;
    let result = op(cpu, val, cnt, mask);
    match size {
        MoveSize::Byte => cpu.state.d[reg] = (cpu.state.d[reg] & 0xFFFF_FF00) | (result & 0xFF),
        MoveSize::Word => cpu.state.d[reg] = (cpu.state.d[reg] & 0xFFFF_0000) | (result & 0xFFFF),
        MoveSize::Long => cpu.state.d[reg] = result,
    }
}

fn exec_shift_mem<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode, op: ShiftFn) {
    let t = resolve_rmw(cpu, bus, ea, &MoveSize::Word);
    let val = rmw_read_word(cpu, bus, &t) as u32;
    let result = op(cpu, val, 1, 0xFFFF);
    rmw_write_word(cpu, bus, &t, result as u16);
}

// ========== MOVEM ==========

fn exec_movem_to_reg<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode, mask: u16) {
    let mut addr = calc_ea_addr(cpu, bus, ea);
    for i in 0..16 {
        if (mask >> i) & 1 != 0 {
            match *size {
                MoveSize::Word => {
                    let v = bus.read16(addr) as i16 as i32 as u32;
                    if i < 8 { cpu.state.d[i] = v; } else { cpu.state.a[i - 8] = v; }
                    addr = addr.wrapping_add(2);
                }
                MoveSize::Long => {
                    let v = read32(bus, addr);
                    if i < 8 { cpu.state.d[i] = v; } else { cpu.state.a[i - 8] = v; }
                    addr = addr.wrapping_add(4);
                }
                _ => {}
            }
        }
    }
    if let EaMode::AddressIndirectPostInc(r) = ea {
        cpu.state.a[*r] = addr;
    }
}

fn exec_movem_to_mem<B: M68kBus>(cpu: &mut M68k, bus: &mut B, size: &MoveSize, ea: &EaMode, mask: u16) {
    if let EaMode::AddressIndirectPreDec(r) = ea {
        let inc = match size { MoveSize::Word => 2u32, MoveSize::Long => 4, _ => 2 };
        let mut addr = cpu.state.a[*r];
        for i in (0..16).rev() {
            if (mask >> (15 - i)) & 1 != 0 {
                addr = addr.wrapping_sub(inc);
                match *size {
                    MoveSize::Word => {
                        let v = if i < 8 { (cpu.state.d[i] & 0xFFFF) as u16 } else { (cpu.state.a[i - 8] & 0xFFFF) as u16 };
                        bus.write16(addr, v);
                    }
                    MoveSize::Long => {
                        let v = if i < 8 { cpu.state.d[i] } else { cpu.state.a[i - 8] };
                        write32(bus, addr, v);
                    }
                    _ => {}
                }
            }
        }
        cpu.state.a[*r] = addr;
    } else {
        let mut addr = calc_ea_addr(cpu, bus, ea);
        for i in 0..16 {
            if (mask >> i) & 1 != 0 {
                match *size {
                    MoveSize::Word => {
                        let v = if i < 8 { (cpu.state.d[i] & 0xFFFF) as u16 } else { (cpu.state.a[i - 8] & 0xFFFF) as u16 };
                        bus.write16(addr, v);
                        addr = addr.wrapping_add(2);
                    }
                    MoveSize::Long => {
                        let v = if i < 8 { cpu.state.d[i] } else { cpu.state.a[i - 8] };
                        write32(bus, addr, v);
                        addr = addr.wrapping_add(4);
                    }
                    _ => {}
                }
            }
        }
    }
}

// ========== BCD ==========

fn exec_abcd<B: M68kBus>(cpu: &mut M68k, bus: &mut B, rx: usize, ry: usize, mem: bool) {
    let (s, d) = if mem {
        cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(1);
        let sv = read_u8(bus, cpu.state.a[ry]);
        cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(1);
        let dv = read_u8(bus, cpu.state.a[rx]);
        (sv, dv)
    } else {
        ((cpu.state.d[ry] & 0xFF) as u8, (cpu.state.d[rx] & 0xFF) as u8)
    };
    let x = if (cpu.state.sr & CCR_X) != 0 { 1u16 } else { 0 };
    let low = (d & 0xF) as u16 + (s & 0xF) as u16 + x;
    let carry_low = if low > 9 { 6 } else { 0 };
    let high = (d >> 4) as u16 + (s >> 4) as u16 + (low + carry_low) / 16;
    let carry_high = if high > 9 { 6 } else { 0 };
    let result = (((high + carry_high) & 0xF) << 4) | ((low + carry_low) & 0xF);
    let carry = (high + carry_high) > 15;
    cpu.state.sr &= !(CCR_X | CCR_C);
    if carry { cpu.state.sr |= CCR_X | CCR_C; }
    let res = result as u8;
    if res != 0 { cpu.state.sr &= !CCR_Z; }
    if mem { write_u8(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_FF00) | res as u32; }
}

fn exec_sbcd<B: M68kBus>(cpu: &mut M68k, bus: &mut B, rx: usize, ry: usize, mem: bool) {
    let (s, d) = if mem {
        cpu.state.a[ry] = cpu.state.a[ry].wrapping_sub(1);
        let sv = read_u8(bus, cpu.state.a[ry]);
        cpu.state.a[rx] = cpu.state.a[rx].wrapping_sub(1);
        let dv = read_u8(bus, cpu.state.a[rx]);
        (sv, dv)
    } else {
        ((cpu.state.d[ry] & 0xFF) as u8, (cpu.state.d[rx] & 0xFF) as u8)
    };
    let x = if (cpu.state.sr & CCR_X) != 0 { 1i16 } else { 0 };
    let low = (d & 0xF) as i16 - (s & 0xF) as i16 - x;
    let borrow_low = if low < 0 { 6 } else { 0 };
    let high = (d >> 4) as i16 - (s >> 4) as i16 - if low < 0 { 1 } else { 0 };
    let borrow_high = if high < 0 { 6 } else { 0 };
    let result = (((high.wrapping_sub(borrow_high)) & 0xF) << 4) | ((low.wrapping_sub(borrow_low)) & 0xF);
    cpu.state.sr &= !(CCR_X | CCR_C);
    if high < 0 { cpu.state.sr |= CCR_X | CCR_C; }
    let res = result as u8;
    if res != 0 { cpu.state.sr &= !CCR_Z; }
    if mem { write_u8(bus, cpu.state.a[rx], res); } else { cpu.state.d[rx] = (cpu.state.d[rx] & 0xFFFF_FF00) | res as u32; }
}

fn exec_nbcd<B: M68kBus>(cpu: &mut M68k, bus: &mut B, ea: &EaMode) {
    let t = resolve_rmw(cpu, bus, ea, &MoveSize::Byte);
    let d = rmw_read_byte(cpu, bus, &t);
    let x = if (cpu.state.sr & CCR_X) != 0 { 1u16 } else { 0 };
    let low = 0u16.wrapping_sub(d as u16 & 0xF).wrapping_sub(x);
    let borrow_low = if low > 9 { 6 } else { 0 };
    let high = 0u16.wrapping_sub(d as u16 >> 4).wrapping_sub(if low > 9 { 1 } else { 0 });
    let borrow_high = if high > 9 { 6 } else { 0 };
    let result = (((high.wrapping_sub(borrow_high)) & 0xF) << 4) | ((low.wrapping_sub(borrow_low)) & 0xF);
    cpu.state.sr &= !(CCR_X | CCR_C);
    if (d as u16 + x) > 0 { cpu.state.sr |= CCR_X | CCR_C; }
    let res = result as u8;
    if res != 0 { cpu.state.sr &= !CCR_Z; }
    rmw_write_byte(cpu, bus, &t, res);
}

// ========== Exception and Interrupt ==========

fn exception_vector(exception: &M68kException) -> u32 {
    match exception {
        M68kException::AddressError { .. } => 3,
        M68kException::IllegalInstruction { .. } => 4,
        M68kException::ZeroDivide => 5,
        M68kException::TrapV => 7,
        M68kException::Trap { vector } => 32 + *vector as u32,
        M68kException::LineA { .. } => 10,
        M68kException::LineF { .. } => 11,
    }
}

fn exception_mnemonic(exception: &M68kException) -> String {
    match exception {
        M68kException::IllegalInstruction { .. } => "ILLEGAL".into(),
        M68kException::AddressError { .. } => "ADDRESS_ERROR".into(),
        M68kException::ZeroDivide => "ZERO_DIVIDE".into(),
        M68kException::TrapV => "TRAPV".into(),
        M68kException::Trap { vector } => format!("TRAP #{}", vector),
        M68kException::LineA { .. } => "LINE_A".into(),
        M68kException::LineF { .. } => "LINE_F".into(),
    }
}

fn take_exception<B: M68kBus>(cpu: &mut M68k, bus: &mut B, exception: M68kException, fault_pc: u32, fault_opcode: Option<u16>, cycles: u32) -> InstructionTrace {
    let vector = exception_vector(&exception);
    let sr_before = cpu.state.sr;
    let mnemonic = exception_mnemonic(&exception);
    cpu.state.last_exception = Some(exception);
    cpu.state.last_exception_pc = fault_pc;
    // Freeze trace ring at exception time
    cpu.exception_trace = cpu.trace_ring.iter().cloned().collect();
    cpu.state.sr |= SR_SUPERVISOR;
    push_long(cpu, bus, fault_pc);
    push_word(cpu, bus, sr_before);
    let handler = read32(bus, vector * 4);
    cpu.state.pc = handler;
    cpu.state.total_cycles += cycles as u64;
    InstructionTrace { pc: fault_pc, opcode: fault_opcode.unwrap_or(0), cycles, mnemonic }
}

fn take_interrupt<B: M68kBus>(cpu: &mut M68k, bus: &mut B, level: u8) -> InstructionTrace {
    let sr_before = cpu.state.sr;
    cpu.state.sr = (cpu.state.sr & !0x0700) | ((level as u16) << 8) | SR_SUPERVISOR;
    cpu.state.stopped = false;
    push_long(cpu, bus, cpu.state.pc);
    push_word(cpu, bus, sr_before);
    let vector_addr = (24 + level as u32) * 4;
    let handler = read32(bus, vector_addr);
    cpu.state.pc = handler;
    let cycles = 44u32;
    cpu.state.total_cycles += cycles as u64;
    InstructionTrace { pc: cpu.state.pc, opcode: 0, cycles, mnemonic: format!("INT{}", level) }
}

// ========== Condition code evaluation ==========

fn eval_cc(sr: u16, condition: u8) -> bool {
    let c = (sr & CCR_C) != 0;
    let v = (sr & CCR_V) != 0;
    let z = (sr & CCR_Z) != 0;
    let n = (sr & CCR_N) != 0;
    match condition & 0xF {
        0x0 => true,
        0x1 => false,
        0x2 => !c && !z,
        0x3 => c || z,
        0x4 => !c,
        0x5 => c,
        0x6 => !z,
        0x7 => z,
        0x8 => !v,
        0x9 => v,
        0xA => !n,
        0xB => n,
        0xC => n == v,
        0xD => n != v,
        0xE => !z && (n == v),
        0xF => z || (n != v),
        _ => false,
    }
}

// ========== Mnemonic ==========

fn mnemonic_for(instr: &DecodedInstruction) -> String {
    match instr {
        DecodedInstruction::Nop => "NOP".into(),
        DecodedInstruction::Rts => "RTS".into(),
        DecodedInstruction::Rte => "RTE".into(),
        DecodedInstruction::Rtr => "RTR".into(),
        DecodedInstruction::Reset => "RESET".into(),
        DecodedInstruction::Stop => "STOP".into(),
        DecodedInstruction::TrapV => "TRAPV".into(),
        DecodedInstruction::Bra8(_) | DecodedInstruction::Bra16 => "BRA".into(),
        DecodedInstruction::Bsr8(_) | DecodedInstruction::Bsr16 => "BSR".into(),
        DecodedInstruction::Bcc8 { condition, .. } | DecodedInstruction::Bcc16 { condition } => format!("Bcc({:X})", condition),
        DecodedInstruction::Dbcc { condition, .. } => format!("DBcc({:X})", condition),
        DecodedInstruction::Scc { condition, .. } => format!("Scc({:X})", condition),
        DecodedInstruction::Jmp(_) => "JMP".into(),
        DecodedInstruction::Jsr(_) => "JSR".into(),
        DecodedInstruction::Move { size, .. } => format!("MOVE.{}", sz(size)),
        DecodedInstruction::MoveA { size, .. } => format!("MOVEA.{}", sz(size)),
        DecodedInstruction::MoveQ { .. } => "MOVEQ".into(),
        DecodedInstruction::Movem { size, .. } => format!("MOVEM.{}", sz(size)),
        DecodedInstruction::MoveToSr(_) => "MOVE_TO_SR".into(),
        DecodedInstruction::MoveFromSr(_) => "MOVE_FROM_SR".into(),
        DecodedInstruction::MoveToCcr(_) => "MOVE_TO_CCR".into(),
        DecodedInstruction::MoveUsp { .. } => "MOVE_USP".into(),
        DecodedInstruction::Lea { .. } => "LEA".into(),
        DecodedInstruction::Pea(_) => "PEA".into(),
        DecodedInstruction::Link { .. } => "LINK".into(),
        DecodedInstruction::Unlk { .. } => "UNLK".into(),
        DecodedInstruction::Swap(_) => "SWAP".into(),
        DecodedInstruction::ExtW(_) => "EXT.W".into(),
        DecodedInstruction::ExtL(_) => "EXT.L".into(),
        DecodedInstruction::Exg { .. } => "EXG".into(),
        DecodedInstruction::Add { size, .. } => format!("ADD.{}", sz(size)),
        DecodedInstruction::AddA { size, .. } => format!("ADDA.{}", sz(size)),
        DecodedInstruction::AddI { size, .. } => format!("ADDI.{}", sz(size)),
        DecodedInstruction::AddQ { size, .. } => format!("ADDQ.{}", sz(size)),
        DecodedInstruction::AddX { size, .. } => format!("ADDX.{}", sz(size)),
        DecodedInstruction::Sub { size, .. } => format!("SUB.{}", sz(size)),
        DecodedInstruction::SubA { size, .. } => format!("SUBA.{}", sz(size)),
        DecodedInstruction::SubI { size, .. } => format!("SUBI.{}", sz(size)),
        DecodedInstruction::SubQ { size, .. } => format!("SUBQ.{}", sz(size)),
        DecodedInstruction::SubX { size, .. } => format!("SUBX.{}", sz(size)),
        DecodedInstruction::Neg { size, .. } => format!("NEG.{}", sz(size)),
        DecodedInstruction::NegX { size, .. } => format!("NEGX.{}", sz(size)),
        DecodedInstruction::Clr { size, .. } => format!("CLR.{}", sz(size)),
        DecodedInstruction::Tst { size, .. } => format!("TST.{}", sz(size)),
        DecodedInstruction::Cmp { size, .. } => format!("CMP.{}", sz(size)),
        DecodedInstruction::CmpA { size, .. } => format!("CMPA.{}", sz(size)),
        DecodedInstruction::CmpI { size, .. } => format!("CMPI.{}", sz(size)),
        DecodedInstruction::CmpM { size, .. } => format!("CMPM.{}", sz(size)),
        DecodedInstruction::And { size, .. } => format!("AND.{}", sz(size)),
        DecodedInstruction::AndI { size, .. } => format!("ANDI.{}", sz(size)),
        DecodedInstruction::Or { size, .. } => format!("OR.{}", sz(size)),
        DecodedInstruction::OrI { size, .. } => format!("ORI.{}", sz(size)),
        DecodedInstruction::Eor { size, .. } => format!("EOR.{}", sz(size)),
        DecodedInstruction::EorI { size, .. } => format!("EORI.{}", sz(size)),
        DecodedInstruction::Not { size, .. } => format!("NOT.{}", sz(size)),
        DecodedInstruction::AndiToCcr => "ANDI_CCR".into(),
        DecodedInstruction::AndiToSr => "ANDI_SR".into(),
        DecodedInstruction::OriToCcr => "ORI_CCR".into(),
        DecodedInstruction::OriToSr => "ORI_SR".into(),
        DecodedInstruction::EoriToCcr => "EORI_CCR".into(),
        DecodedInstruction::EoriToSr => "EORI_SR".into(),
        DecodedInstruction::Btst { .. } => "BTST".into(),
        DecodedInstruction::Bchg { .. } => "BCHG".into(),
        DecodedInstruction::Bclr { .. } => "BCLR".into(),
        DecodedInstruction::Bset { .. } => "BSET".into(),
        DecodedInstruction::Asl { .. } | DecodedInstruction::AslMem(_) => "ASL".into(),
        DecodedInstruction::Asr { .. } | DecodedInstruction::AsrMem(_) => "ASR".into(),
        DecodedInstruction::Lsl { .. } | DecodedInstruction::LslMem(_) => "LSL".into(),
        DecodedInstruction::Lsr { .. } | DecodedInstruction::LsrMem(_) => "LSR".into(),
        DecodedInstruction::Rol { .. } | DecodedInstruction::RolMem(_) => "ROL".into(),
        DecodedInstruction::Ror { .. } | DecodedInstruction::RorMem(_) => "ROR".into(),
        DecodedInstruction::Roxl { .. } | DecodedInstruction::RoxlMem(_) => "ROXL".into(),
        DecodedInstruction::Roxr { .. } | DecodedInstruction::RoxrMem(_) => "ROXR".into(),
        DecodedInstruction::MulU { .. } => "MULU".into(),
        DecodedInstruction::MulS { .. } => "MULS".into(),
        DecodedInstruction::DivU { .. } => "DIVU".into(),
        DecodedInstruction::DivS { .. } => "DIVS".into(),
        DecodedInstruction::Trap(v) => format!("TRAP #{}", v),
        DecodedInstruction::Abcd { .. } => "ABCD".into(),
        DecodedInstruction::Sbcd { .. } => "SBCD".into(),
        DecodedInstruction::Nbcd(_) => "NBCD".into(),
        DecodedInstruction::Tas(_) => "TAS".into(),
        DecodedInstruction::Illegal => "ILLEGAL".into(),
        DecodedInstruction::LineA => "LINE_A".into(),
        DecodedInstruction::LineF => "LINE_F".into(),
    }
}

fn sz(s: &MoveSize) -> &'static str {
    match s { MoveSize::Byte => "B", MoveSize::Word => "W", MoveSize::Long => "L" }
}
