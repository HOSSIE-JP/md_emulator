#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reg8 { A, B, C, D, E, H, L, Mem }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reg16 { BC, DE, HL, SP, AF }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cond { NZ, Z, NC, C }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Z80Instruction {
    Nop,
    Halt,
    Di,
    Ei,
    LdR8Imm(Reg8),
    LdR8R8(Reg8, Reg8),
    LdR16Imm(Reg16),
    LdAAddr,
    LdAddrA,
    LdADE,
    LdDEA,
    LdABC,
    LdBCA,
    LdHLImm16Addr,
    LdImm16AddrHL,
    LdSPHL,
    LdHLAddr,
    LdAddrHL,
    PushR16(Reg16),
    PopR16(Reg16),
    AddAR8(Reg8),
    AdcAR8(Reg8),
    SubR8(Reg8),
    SbcAR8(Reg8),
    AndR8(Reg8),
    OrR8(Reg8),
    XorR8(Reg8),
    CpR8(Reg8),
    AddAImm,
    SubImm,
    AndImm,
    OrImm,
    XorImm,
    CpImm,
    IncR8(Reg8),
    DecR8(Reg8),
    IncR16(Reg16),
    DecR16(Reg16),
    AddHLR16(Reg16),
    Jr,
    JrCond(Cond),
    Jp,
    JpCond(Cond),
    JpHL,
    Call,
    CallCond(Cond),
    Ret,
    RetCond(Cond),
    Reti,
    Rst(u8),
    Djnz,
    Rlca,
    Rrca,
    Rla,
    Rra,
    Cpl,
    Scf,
    Ccf,
    ExDEHL,
    ExAFAF,
    Exx,
    ExSPHL,
    OutNA,
    InAN,
    Daa,
    LdiA,     // LD A,(HL); INC HL
    LddA,     // LD A,(HL); DEC HL
    Illegal,
}

pub fn decode(opcode: u8) -> Z80Instruction {
    use Z80Instruction::*;
    match opcode {
        0x00 => Nop,
        0x76 => Halt,
        0xF3 => Di,
        0xFB => Ei,
        // LD r8, imm
        0x06 => LdR8Imm(Reg8::B), 0x0E => LdR8Imm(Reg8::C),
        0x16 => LdR8Imm(Reg8::D), 0x1E => LdR8Imm(Reg8::E),
        0x26 => LdR8Imm(Reg8::H), 0x2E => LdR8Imm(Reg8::L),
        0x36 => LdR8Imm(Reg8::Mem), 0x3E => LdR8Imm(Reg8::A),
        // LD r16, imm16
        0x01 => LdR16Imm(Reg16::BC), 0x11 => LdR16Imm(Reg16::DE),
        0x21 => LdR16Imm(Reg16::HL), 0x31 => LdR16Imm(Reg16::SP),
        // LD A,(nn) / (nn),A
        0x3A => LdAAddr, 0x32 => LdAddrA,
        // LD A,(DE)/(BC) and reverse
        0x1A => LdADE, 0x12 => LdDEA,
        0x0A => LdABC, 0x02 => LdBCA,
        // LD HL,(nn) / (nn),HL
        0x2A => LdHLImm16Addr, 0x22 => LdImm16AddrHL,
        // LD SP,HL
        0xF9 => LdSPHL,
        // PUSH/POP
        0xC5 => PushR16(Reg16::BC), 0xD5 => PushR16(Reg16::DE),
        0xE5 => PushR16(Reg16::HL), 0xF5 => PushR16(Reg16::AF),
        0xC1 => PopR16(Reg16::BC), 0xD1 => PopR16(Reg16::DE),
        0xE1 => PopR16(Reg16::HL), 0xF1 => PopR16(Reg16::AF),
        // ALU A,r8
        0x80..=0x87 => AddAR8(r8_from(opcode & 7)),
        0x88..=0x8F => AdcAR8(r8_from(opcode & 7)),
        0x90..=0x97 => SubR8(r8_from(opcode & 7)),
        0x98..=0x9F => SbcAR8(r8_from(opcode & 7)),
        0xA0..=0xA7 => AndR8(r8_from(opcode & 7)),
        0xA8..=0xAF => XorR8(r8_from(opcode & 7)),
        0xB0..=0xB7 => OrR8(r8_from(opcode & 7)),
        0xB8..=0xBF => CpR8(r8_from(opcode & 7)),
        // ALU imm
        0xC6 => AddAImm, 0xD6 => SubImm,
        0xE6 => AndImm, 0xF6 => OrImm,
        0xEE => XorImm, 0xFE => CpImm,
        // LD r8,r8 block (0x40-0x7F except 0x76=HALT)
        0x40..=0x75 | 0x77..=0x7F => {
            let dst = r8_from((opcode >> 3) & 7);
            let src = r8_from(opcode & 7);
            LdR8R8(dst, src)
        }
        // INC/DEC r8
        0x04 => IncR8(Reg8::B), 0x0C => IncR8(Reg8::C),
        0x14 => IncR8(Reg8::D), 0x1C => IncR8(Reg8::E),
        0x24 => IncR8(Reg8::H), 0x2C => IncR8(Reg8::L),
        0x34 => IncR8(Reg8::Mem), 0x3C => IncR8(Reg8::A),
        0x05 => DecR8(Reg8::B), 0x0D => DecR8(Reg8::C),
        0x15 => DecR8(Reg8::D), 0x1D => DecR8(Reg8::E),
        0x25 => DecR8(Reg8::H), 0x2D => DecR8(Reg8::L),
        0x35 => DecR8(Reg8::Mem), 0x3D => DecR8(Reg8::A),
        // INC/DEC r16
        0x03 => IncR16(Reg16::BC), 0x13 => IncR16(Reg16::DE),
        0x23 => IncR16(Reg16::HL), 0x33 => IncR16(Reg16::SP),
        0x0B => DecR16(Reg16::BC), 0x1B => DecR16(Reg16::DE),
        0x2B => DecR16(Reg16::HL), 0x3B => DecR16(Reg16::SP),
        // ADD HL,r16
        0x09 => AddHLR16(Reg16::BC), 0x19 => AddHLR16(Reg16::DE),
        0x29 => AddHLR16(Reg16::HL), 0x39 => AddHLR16(Reg16::SP),
        // Jumps
        0x18 => Jr,
        0x20 => JrCond(Cond::NZ), 0x28 => JrCond(Cond::Z),
        0x30 => JrCond(Cond::NC), 0x38 => JrCond(Cond::C),
        0xC3 => Jp,
        0xC2 => JpCond(Cond::NZ), 0xCA => JpCond(Cond::Z),
        0xD2 => JpCond(Cond::NC), 0xDA => JpCond(Cond::C),
        0xE9 => JpHL,
        // Calls/Returns
        0xCD => Call,
        0xC4 => CallCond(Cond::NZ), 0xCC => CallCond(Cond::Z),
        0xD4 => CallCond(Cond::NC), 0xDC => CallCond(Cond::C),
        0xC9 => Ret,
        0xC0 => RetCond(Cond::NZ), 0xC8 => RetCond(Cond::Z),
        0xD0 => RetCond(Cond::NC), 0xD8 => RetCond(Cond::C),
        0xD9 => Exx,
        // RST
        0xC7 => Rst(0x00), 0xCF => Rst(0x08),
        0xD7 => Rst(0x10), 0xDF => Rst(0x18),
        0xE7 => Rst(0x20), 0xEF => Rst(0x28),
        0xF7 => Rst(0x30), 0xFF => Rst(0x38),
        0x10 => Djnz,
        0x07 => Rlca, 0x0F => Rrca,
        0x17 => Rla,  0x1F => Rra,
        0x2F => Cpl,  0x37 => Scf, 0x3F => Ccf,
        0xEB => ExDEHL, 0x08 => ExAFAF, 0xE3 => ExSPHL,
        0xD3 => OutNA, 0xDB => InAN,
        0x27 => Daa,
        _ => Illegal,
    }
}

fn r8_from(code: u8) -> Reg8 {
    match code {
        0 => Reg8::B, 1 => Reg8::C, 2 => Reg8::D, 3 => Reg8::E,
        4 => Reg8::H, 5 => Reg8::L, 6 => Reg8::Mem, _ => Reg8::A,
    }
}

pub fn cycles_for(instr: &Z80Instruction) -> u32 {
    use Z80Instruction::*;
    match instr {
        Nop | Di | Ei => 4,
        Halt => 4,
        LdR8Imm(Reg8::Mem) => 10,
        LdR8Imm(_) => 7,
        LdR8R8(Reg8::Mem, _) | LdR8R8(_, Reg8::Mem) => 7,
        LdR8R8(_, _) => 4,
        LdR16Imm(_) => 10,
        LdAAddr | LdAddrA => 13,
        LdADE | LdDEA | LdABC | LdBCA => 7,
        LdHLImm16Addr | LdImm16AddrHL => 16,
        LdSPHL => 6,
        LdHLAddr | LdAddrHL => 13,
        PushR16(_) => 11,
        PopR16(_) => 10,
        AddAR8(Reg8::Mem) | SubR8(Reg8::Mem) | AndR8(Reg8::Mem) | OrR8(Reg8::Mem) | XorR8(Reg8::Mem)
        | CpR8(Reg8::Mem) | AdcAR8(Reg8::Mem) | SbcAR8(Reg8::Mem) => 7,
        AddAR8(_) | SubR8(_) | AndR8(_) | OrR8(_) | XorR8(_) | CpR8(_) | AdcAR8(_) | SbcAR8(_) => 4,
        AddAImm | SubImm | AndImm | OrImm | XorImm | CpImm => 7,
        IncR8(Reg8::Mem) | DecR8(Reg8::Mem) => 11,
        IncR8(_) | DecR8(_) => 4,
        IncR16(_) | DecR16(_) => 6,
        AddHLR16(_) => 11,
        Jr | JrCond(_) => 12,
        Jp | JpCond(_) => 10,
        JpHL => 4,
        Call | CallCond(_) => 17,
        Ret | RetCond(_) => 10,
        Reti => 14,
        Rst(_) => 11,
        Djnz => 13,
        Rlca | Rrca | Rla | Rra => 4,
        Cpl | Scf | Ccf => 4,
        ExDEHL | ExAFAF | Exx => 4,
        ExSPHL => 19,
        OutNA | InAN => 11,
        Daa => 4,
        LdiA | LddA => 7,
        Illegal => 4,
    }
}
