#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MoveSize {
    Byte,
    Word,
    Long,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EaMode {
    DataRegister(usize),
    AddressRegister(usize),
    AddressIndirect(usize),
    AddressIndirectPostInc(usize),
    AddressIndirectPreDec(usize),
    AddressDisplacement(usize),
    AddressIndex(usize),
    AbsoluteWord,
    AbsoluteLong,
    PcDisplacement,
    PcIndex,
    Immediate,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    EaToReg,
    RegToEa,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShiftCount {
    Imm(u8),
    Reg(u8),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DecodedInstruction {
    Nop,
    Rts,
    Rte,
    Rtr,
    Reset,
    Stop,
    TrapV,
    Illegal,
    LineA,
    LineF,
    // Branches
    Bra8(i8),
    Bra16,
    Bsr8(i8),
    Bsr16,
    Bcc8 { condition: u8, displacement: i8 },
    Bcc16 { condition: u8 },
    Dbcc { condition: u8, register: usize },
    Scc { condition: u8, ea: EaMode },
    // Jumps
    Jmp(EaMode),
    Jsr(EaMode),
    // Move
    Move { size: MoveSize, src: EaMode, dst: EaMode },
    MoveA { size: MoveSize, src: EaMode, dst_register: usize },
    MoveQ { register: usize, immediate: i8 },
    Movem { size: MoveSize, to_register: bool, ea: EaMode },
    MoveToSr(EaMode),
    MoveFromSr(EaMode),
    MoveToCcr(EaMode),
    MoveUsp { to_usp: bool, register: usize },
    // Address
    Lea { ea: EaMode, register: usize },
    Pea(EaMode),
    Link { register: usize },
    Unlk { register: usize },
    Swap(usize),
    ExtW(usize),
    ExtL(usize),
    Exg { rx: usize, ry: usize, mode: u8 },
    // Arithmetic
    Add { size: MoveSize, register: usize, dir: Direction, ea: EaMode },
    AddA { size: MoveSize, register: usize, ea: EaMode },
    AddI { size: MoveSize, ea: EaMode },
    AddQ { size: MoveSize, data: u8, ea: EaMode },
    AddX { size: MoveSize, rx: usize, ry: usize, mem: bool },
    Sub { size: MoveSize, register: usize, dir: Direction, ea: EaMode },
    SubA { size: MoveSize, register: usize, ea: EaMode },
    SubI { size: MoveSize, ea: EaMode },
    SubQ { size: MoveSize, data: u8, ea: EaMode },
    SubX { size: MoveSize, rx: usize, ry: usize, mem: bool },
    Neg { size: MoveSize, ea: EaMode },
    NegX { size: MoveSize, ea: EaMode },
    Clr { size: MoveSize, ea: EaMode },
    Tst { size: MoveSize, ea: EaMode },
    Cmp { size: MoveSize, register: usize, ea: EaMode },
    CmpA { size: MoveSize, register: usize, ea: EaMode },
    CmpI { size: MoveSize, ea: EaMode },
    CmpM { size: MoveSize, ax: usize, ay: usize },
    // Logic
    And { size: MoveSize, register: usize, dir: Direction, ea: EaMode },
    AndI { size: MoveSize, ea: EaMode },
    Or { size: MoveSize, register: usize, dir: Direction, ea: EaMode },
    OrI { size: MoveSize, ea: EaMode },
    Eor { size: MoveSize, register: usize, ea: EaMode },
    EorI { size: MoveSize, ea: EaMode },
    Not { size: MoveSize, ea: EaMode },
    AndiToCcr, AndiToSr,
    OriToCcr, OriToSr,
    EoriToCcr, EoriToSr,
    // Bit
    Btst { reg: Option<usize>, ea: EaMode },
    Bchg { reg: Option<usize>, ea: EaMode },
    Bclr { reg: Option<usize>, ea: EaMode },
    Bset { reg: Option<usize>, ea: EaMode },
    // Shift/Rotate
    Asl { size: MoveSize, count: ShiftCount, reg: usize },
    Asr { size: MoveSize, count: ShiftCount, reg: usize },
    Lsl { size: MoveSize, count: ShiftCount, reg: usize },
    Lsr { size: MoveSize, count: ShiftCount, reg: usize },
    Rol { size: MoveSize, count: ShiftCount, reg: usize },
    Ror { size: MoveSize, count: ShiftCount, reg: usize },
    Roxl { size: MoveSize, count: ShiftCount, reg: usize },
    Roxr { size: MoveSize, count: ShiftCount, reg: usize },
    AslMem(EaMode), AsrMem(EaMode),
    LslMem(EaMode), LsrMem(EaMode),
    RolMem(EaMode), RorMem(EaMode),
    RoxlMem(EaMode), RoxrMem(EaMode),
    // Multiply/Divide
    MulU { register: usize, ea: EaMode },
    MulS { register: usize, ea: EaMode },
    DivU { register: usize, ea: EaMode },
    DivS { register: usize, ea: EaMode },
    // Trap
    Trap(u8),
    // BCD
    Abcd { rx: usize, ry: usize, mem: bool },
    Sbcd { rx: usize, ry: usize, mem: bool },
    Nbcd(EaMode),
    // TAS
    Tas(EaMode),
}

pub fn decode(opcode: u16) -> DecodedInstruction {
    let group = (opcode >> 12) & 0xF;
    match group {
        0x0 => decode_group0(opcode),
        0x1 => decode_move(opcode, MoveSize::Byte),
        0x2 => decode_move(opcode, MoveSize::Long),
        0x3 => decode_move(opcode, MoveSize::Word),
        0x4 => decode_group4(opcode),
        0x5 => decode_group5(opcode),
        0x6 => decode_group6(opcode),
        0x7 => decode_group7(opcode),
        0x8 => decode_group8(opcode),
        0x9 => decode_group9(opcode),
        0xA => DecodedInstruction::LineA,
        0xB => decode_group_b(opcode),
        0xC => decode_group_c(opcode),
        0xD => decode_group_d(opcode),
        0xE => decode_group_e(opcode),
        0xF => DecodedInstruction::LineF,
        _ => DecodedInstruction::Illegal,
    }
}

fn decode_size_2bit(bits: u8) -> Option<MoveSize> {
    match bits {
        0b00 => Some(MoveSize::Byte),
        0b01 => Some(MoveSize::Word),
        0b10 => Some(MoveSize::Long),
        _ => None,
    }
}

fn decode_ea(mode: u8, reg: u8) -> Option<EaMode> {
    match mode {
        0b000 => Some(EaMode::DataRegister(reg as usize)),
        0b001 => Some(EaMode::AddressRegister(reg as usize)),
        0b010 => Some(EaMode::AddressIndirect(reg as usize)),
        0b011 => Some(EaMode::AddressIndirectPostInc(reg as usize)),
        0b100 => Some(EaMode::AddressIndirectPreDec(reg as usize)),
        0b101 => Some(EaMode::AddressDisplacement(reg as usize)),
        0b110 => Some(EaMode::AddressIndex(reg as usize)),
        0b111 => match reg {
            0b000 => Some(EaMode::AbsoluteWord),
            0b001 => Some(EaMode::AbsoluteLong),
            0b010 => Some(EaMode::PcDisplacement),
            0b011 => Some(EaMode::PcIndex),
            0b100 => Some(EaMode::Immediate),
            _ => None,
        },
        _ => None,
    }
}

fn std_ea(opcode: u16) -> Option<EaMode> {
    let mode = ((opcode >> 3) & 7) as u8;
    let reg = (opcode & 7) as u8;
    decode_ea(mode, reg)
}

// Group 0: ORI, ANDI, SUBI, ADDI, EORI, CMPI, BTST, BCHG, BCLR, BSET
fn decode_group0(opcode: u16) -> DecodedInstruction {
    let upper6 = (opcode >> 8) & 0xFF;
    // Immediate to CCR/SR
    if opcode == 0x003C { return DecodedInstruction::OriToCcr; }
    if opcode == 0x007C { return DecodedInstruction::OriToSr; }
    if opcode == 0x023C { return DecodedInstruction::AndiToCcr; }
    if opcode == 0x027C { return DecodedInstruction::AndiToSr; }
    if opcode == 0x0A3C { return DecodedInstruction::EoriToCcr; }
    if opcode == 0x0A7C { return DecodedInstruction::EoriToSr; }

    let bit9 = (opcode >> 8) & 1;
    // Bit operations with register
    if (opcode & 0xF100) == 0x0100 && bit9 == 1 {
        let reg = ((opcode >> 9) & 7) as usize;
        let typ = ((opcode >> 6) & 3) as u8;
        if let Some(ea) = std_ea(opcode) {
            return match typ {
                0 => DecodedInstruction::Btst { reg: Some(reg), ea },
                1 => DecodedInstruction::Bchg { reg: Some(reg), ea },
                2 => DecodedInstruction::Bclr { reg: Some(reg), ea },
                3 => DecodedInstruction::Bset { reg: Some(reg), ea },
                _ => DecodedInstruction::Illegal,
            };
        }
    }

    // Bit operations with immediate
    if (upper6 & 0xFE) == 0x08 {
        let typ = ((opcode >> 6) & 3) as u8;
        if let Some(ea) = std_ea(opcode) {
            return match typ {
                0 => DecodedInstruction::Btst { reg: None, ea },
                1 => DecodedInstruction::Bchg { reg: None, ea },
                2 => DecodedInstruction::Bclr { reg: None, ea },
                3 => DecodedInstruction::Bset { reg: None, ea },
                _ => DecodedInstruction::Illegal,
            };
        }
    }

    // Immediate ALU: ORI, ANDI, SUBI, ADDI, EORI, CMPI
    let reg_field = ((opcode >> 9) & 7) as u8;
    let size_bits = ((opcode >> 6) & 3) as u8;
    if let Some(size) = decode_size_2bit(size_bits) {
        if let Some(ea) = std_ea(opcode) {
            return match reg_field {
                0b000 => DecodedInstruction::OrI { size, ea },
                0b001 => DecodedInstruction::AndI { size, ea },
                0b010 => DecodedInstruction::SubI { size, ea },
                0b011 => DecodedInstruction::AddI { size, ea },
                0b101 => DecodedInstruction::EorI { size, ea },
                0b110 => DecodedInstruction::CmpI { size, ea },
                _ => DecodedInstruction::Illegal,
            };
        }
    }

    DecodedInstruction::Illegal
}

fn decode_move(opcode: u16, size: MoveSize) -> DecodedInstruction {
    let src_mode = ((opcode >> 3) & 7) as u8;
    let src_reg = (opcode & 7) as u8;
    let dst_reg = ((opcode >> 9) & 7) as u8;
    let dst_mode = ((opcode >> 6) & 7) as u8;

    let src = match decode_ea(src_mode, src_reg) {
        Some(ea) => ea,
        None => return DecodedInstruction::Illegal,
    };

    if dst_mode == 0b001 && size != MoveSize::Byte {
        return DecodedInstruction::MoveA {
            size,
            src,
            dst_register: dst_reg as usize,
        };
    }

    let dst = match decode_ea(dst_mode, dst_reg) {
        Some(ea) => ea,
        None => return DecodedInstruction::Illegal,
    };
    DecodedInstruction::Move { size, src, dst }
}

// Group 4: Miscellaneous
fn decode_group4(opcode: u16) -> DecodedInstruction {
    // Fixed opcodes first
    match opcode {
        0x4E70 => return DecodedInstruction::Reset,
        0x4E71 => return DecodedInstruction::Nop,
        0x4E72 => return DecodedInstruction::Stop,
        0x4E73 => return DecodedInstruction::Rte,
        0x4E75 => return DecodedInstruction::Rts,
        0x4E76 => return DecodedInstruction::TrapV,
        0x4E77 => return DecodedInstruction::Rtr,
        0x4AFC => return DecodedInstruction::Illegal,
        _ => {}
    }

    // TRAP #vector
    if (opcode & 0xFFF0) == 0x4E40 {
        return DecodedInstruction::Trap((opcode & 0xF) as u8);
    }
    // LINK
    if (opcode & 0xFFF8) == 0x4E50 {
        return DecodedInstruction::Link { register: (opcode & 7) as usize };
    }
    // UNLK
    if (opcode & 0xFFF8) == 0x4E58 {
        return DecodedInstruction::Unlk { register: (opcode & 7) as usize };
    }
    // MOVE USP
    if (opcode & 0xFFF0) == 0x4E60 {
        let to_usp = (opcode & 8) == 0;
        return DecodedInstruction::MoveUsp { to_usp, register: (opcode & 7) as usize };
    }
    // SWAP
    if (opcode & 0xFFF8) == 0x4840 {
        return DecodedInstruction::Swap((opcode & 7) as usize);
    }
    // EXT.W
    if (opcode & 0xFFF8) == 0x4880 {
        return DecodedInstruction::ExtW((opcode & 7) as usize);
    }
    // EXT.L
    if (opcode & 0xFFF8) == 0x48C0 {
        return DecodedInstruction::ExtL((opcode & 7) as usize);
    }

    let sub = (opcode >> 8) & 0xF;
    let size_bits = ((opcode >> 6) & 3) as u8;

    // LEA: 0100_rrr1_11ss_sSSS
    if (opcode & 0xF1C0) == 0x41C0 {
        let reg = ((opcode >> 9) & 7) as usize;
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Lea { ea, register: reg };
        }
    }

    // CHK skipped for now

    // MOVE from SR: 0100_0000_11(ea)
    if (opcode & 0xFFC0) == 0x40C0 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::MoveFromSr(ea);
        }
    }
    // MOVE to CCR: 0100_0100_11(ea)
    if (opcode & 0xFFC0) == 0x44C0 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::MoveToCcr(ea);
        }
    }
    // MOVE to SR: 0100_0110_11(ea)
    if (opcode & 0xFFC0) == 0x46C0 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::MoveToSr(ea);
        }
    }
    // NBCD: 0100_1000_00(ea)
    if (opcode & 0xFFC0) == 0x4800 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Nbcd(ea);
        }
    }
    // PEA: 0100_1000_01(ea)
    if (opcode & 0xFFC0) == 0x4840 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Pea(ea);
        }
    }
    // TAS: 0100_1010_11(ea)
    if (opcode & 0xFFC0) == 0x4AC0 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Tas(ea);
        }
    }
    // MOVEM: 0100_1d00_1s(ea)
    if (opcode & 0xFB80) == 0x4880 {
        let to_reg = (opcode & 0x0400) != 0;
        let size = if (opcode & 0x0040) != 0 { MoveSize::Long } else { MoveSize::Word };
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Movem { size, to_register: to_reg, ea };
        }
    }

    // JSR: 0100_1110_10(ea)
    if (opcode & 0xFFC0) == 0x4E80 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Jsr(ea);
        }
    }
    // JMP: 0100_1110_11(ea)
    if (opcode & 0xFFC0) == 0x4EC0 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Jmp(ea);
        }
    }

    // CLR: 0100_0010_ss(ea)
    if sub == 0x2 && size_bits <= 2 {
        if let (Some(size), Some(ea)) = (decode_size_2bit(size_bits), std_ea(opcode)) {
            return DecodedInstruction::Clr { size, ea };
        }
    }
    // NEG: 0100_0100_ss(ea)
    if sub == 0x4 && size_bits <= 2 {
        if let (Some(size), Some(ea)) = (decode_size_2bit(size_bits), std_ea(opcode)) {
            return DecodedInstruction::Neg { size, ea };
        }
    }
    // NEGX: 0100_0000_ss(ea)
    if sub == 0x0 && size_bits <= 2 {
        if let (Some(size), Some(ea)) = (decode_size_2bit(size_bits), std_ea(opcode)) {
            return DecodedInstruction::NegX { size, ea };
        }
    }
    // NOT: 0100_0110_ss(ea)
    if sub == 0x6 && size_bits <= 2 {
        if let (Some(size), Some(ea)) = (decode_size_2bit(size_bits), std_ea(opcode)) {
            return DecodedInstruction::Not { size, ea };
        }
    }
    // TST: 0100_1010_ss(ea)
    if sub == 0xA && size_bits <= 2 {
        if let (Some(size), Some(ea)) = (decode_size_2bit(size_bits), std_ea(opcode)) {
            return DecodedInstruction::Tst { size, ea };
        }
    }

    DecodedInstruction::Illegal
}

// Group 5: ADDQ, SUBQ, Scc, DBcc
fn decode_group5(opcode: u16) -> DecodedInstruction {
    let size_bits = ((opcode >> 6) & 3) as u8;
    let data_raw = ((opcode >> 9) & 7) as u8;

    // Scc / DBcc: size field = 0b11
    if size_bits == 0b11 {
        let condition = ((opcode >> 8) & 0xF) as u8;
        let mode = ((opcode >> 3) & 7) as u8;
        let reg = (opcode & 7) as usize;
        if mode == 0b001 {
            return DecodedInstruction::Dbcc { condition, register: reg };
        }
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::Scc { condition, ea };
        }
        return DecodedInstruction::Illegal;
    }

    if let Some(size) = decode_size_2bit(size_bits) {
        let data = if data_raw == 0 { 8 } else { data_raw };
        if let Some(ea) = std_ea(opcode) {
            if (opcode & 0x0100) == 0 {
                return DecodedInstruction::AddQ { size, data, ea };
            } else {
                return DecodedInstruction::SubQ { size, data, ea };
            }
        }
    }
    DecodedInstruction::Illegal
}

// Group 6: BRA, BSR, Bcc
fn decode_group6(opcode: u16) -> DecodedInstruction {
    let condition = ((opcode >> 8) & 0xF) as u8;
    let disp8 = (opcode & 0xFF) as u8 as i8;

    match condition {
        0x0 => {
            if disp8 == 0 { DecodedInstruction::Bra16 }
            else { DecodedInstruction::Bra8(disp8) }
        }
        0x1 => {
            if disp8 == 0 { DecodedInstruction::Bsr16 }
            else { DecodedInstruction::Bsr8(disp8) }
        }
        _ => {
            if disp8 == 0 { DecodedInstruction::Bcc16 { condition } }
            else { DecodedInstruction::Bcc8 { condition, displacement: disp8 } }
        }
    }
}

// Group 7: MOVEQ
fn decode_group7(opcode: u16) -> DecodedInstruction {
    if (opcode & 0x0100) != 0 {
        return DecodedInstruction::Illegal;
    }
    DecodedInstruction::MoveQ {
        register: ((opcode >> 9) & 7) as usize,
        immediate: (opcode & 0xFF) as u8 as i8,
    }
}

// Group 8: OR, DIV, SBCD
fn decode_group8(opcode: u16) -> DecodedInstruction {
    let reg = ((opcode >> 9) & 7) as usize;
    let size_bits = ((opcode >> 6) & 3) as u8;
    let dir = (opcode >> 8) & 1;

    // SBCD: 1000_yyy1_0000_0xxx or 1000_yyy1_0000_1xxx
    if (opcode & 0xF1F0) == 0x8100 {
        let rx = reg;
        let ry = (opcode & 7) as usize;
        let mem = (opcode & 8) != 0;
        return DecodedInstruction::Sbcd { rx, ry, mem };
    }

    // DIVU: 1000_rrr0_11(ea)
    if dir == 0 && size_bits == 0b11 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::DivU { register: reg, ea };
        }
    }
    // DIVS: 1000_rrr1_11(ea)
    if dir == 1 && size_bits == 0b11 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::DivS { register: reg, ea };
        }
    }

    // OR
    if let Some(size) = decode_size_2bit(size_bits) {
        if let Some(ea) = std_ea(opcode) {
            let direction = if dir == 0 { Direction::EaToReg } else { Direction::RegToEa };
            return DecodedInstruction::Or { size, register: reg, dir: direction, ea };
        }
    }
    DecodedInstruction::Illegal
}

// Group 9: SUB, SUBA, SUBX
fn decode_group9(opcode: u16) -> DecodedInstruction {
    let reg = ((opcode >> 9) & 7) as usize;
    let size_bits = ((opcode >> 6) & 3) as u8;
    let dir = (opcode >> 8) & 1;

    // SUBA: 1001_rrrs_11(ea)
    if size_bits == 0b11 {
        let size = if dir == 0 { MoveSize::Word } else { MoveSize::Long };
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::SubA { size, register: reg, ea };
        }
    }

    // SUBX: 1001_yyy1_ss00_mxxx
    if dir == 1 && ((opcode >> 4) & 1) == 0 && ((opcode >> 3) & 1) <= 1 {
        let ry = (opcode & 7) as usize;
        let mem = (opcode & 8) != 0;
        if size_bits <= 2 {
            if let Some(size) = decode_size_2bit(size_bits) {
                // Check low 2 bits of opcode bits 5-4 = 00
                if ((opcode >> 4) & 3) == 0 {
                    return DecodedInstruction::SubX { size, rx: reg, ry, mem };
                }
            }
        }
    }

    // SUB: 1001_rrrd_ss(ea)
    if let Some(size) = decode_size_2bit(size_bits) {
        if let Some(ea) = std_ea(opcode) {
            let direction = if dir == 0 { Direction::EaToReg } else { Direction::RegToEa };
            return DecodedInstruction::Sub { size, register: reg, dir: direction, ea };
        }
    }
    DecodedInstruction::Illegal
}

// Group B: CMP, CMPA, CMPM, EOR
fn decode_group_b(opcode: u16) -> DecodedInstruction {
    let reg = ((opcode >> 9) & 7) as usize;
    let size_bits = ((opcode >> 6) & 3) as u8;
    let dir = (opcode >> 8) & 1;

    // CMPA: 1011_rrrs_11(ea)
    if size_bits == 0b11 {
        let size = if dir == 0 { MoveSize::Word } else { MoveSize::Long };
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::CmpA { size, register: reg, ea };
        }
    }

    // CMPM: 1011_xxx1_ss00_1yyy
    if dir == 1 && (opcode & 0x38) == 0x08 {
        if let Some(size) = decode_size_2bit(size_bits) {
            let ay = (opcode & 7) as usize;
            return DecodedInstruction::CmpM { size, ax: reg, ay };
        }
    }

    if let Some(size) = decode_size_2bit(size_bits) {
        if dir == 0 {
            // CMP: 1011_rrr0_ss(ea)
            if let Some(ea) = std_ea(opcode) {
                return DecodedInstruction::Cmp { size, register: reg, ea };
            }
        } else {
            // EOR: 1011_rrr1_ss(ea)
            if let Some(ea) = std_ea(opcode) {
                return DecodedInstruction::Eor { size, register: reg, ea };
            }
        }
    }
    DecodedInstruction::Illegal
}

// Group C: AND, MUL, ABCD, EXG
fn decode_group_c(opcode: u16) -> DecodedInstruction {
    let reg = ((opcode >> 9) & 7) as usize;
    let size_bits = ((opcode >> 6) & 3) as u8;
    let dir = (opcode >> 8) & 1;

    // ABCD: 1100_yyy1_0000_mxxx
    if (opcode & 0xF1F0) == 0xC100 {
        let ry = (opcode & 7) as usize;
        let mem = (opcode & 8) != 0;
        return DecodedInstruction::Abcd { rx: reg, ry, mem };
    }

    // EXG: 1100_xxx1_ooooo_yyy
    if dir == 1 {
        let mode = ((opcode >> 3) & 0x1F) as u8;
        match mode {
            0b01000 => {
                let ry = (opcode & 7) as usize;
                return DecodedInstruction::Exg { rx: reg, ry, mode: 0 };
            }
            0b01001 => {
                let ry = (opcode & 7) as usize;
                return DecodedInstruction::Exg { rx: reg, ry, mode: 1 };
            }
            0b10001 => {
                let ry = (opcode & 7) as usize;
                return DecodedInstruction::Exg { rx: reg, ry, mode: 2 };
            }
            _ => {}
        }
    }

    // MULU: 1100_rrr0_11(ea)
    if dir == 0 && size_bits == 0b11 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::MulU { register: reg, ea };
        }
    }
    // MULS: 1100_rrr1_11(ea)
    if dir == 1 && size_bits == 0b11 {
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::MulS { register: reg, ea };
        }
    }

    // AND
    if let Some(size) = decode_size_2bit(size_bits) {
        if let Some(ea) = std_ea(opcode) {
            let direction = if dir == 0 { Direction::EaToReg } else { Direction::RegToEa };
            return DecodedInstruction::And { size, register: reg, dir: direction, ea };
        }
    }
    DecodedInstruction::Illegal
}

// Group D: ADD, ADDA, ADDX
fn decode_group_d(opcode: u16) -> DecodedInstruction {
    let reg = ((opcode >> 9) & 7) as usize;
    let size_bits = ((opcode >> 6) & 3) as u8;
    let dir = (opcode >> 8) & 1;

    // ADDA: 1101_rrrs_11(ea)
    if size_bits == 0b11 {
        let size = if dir == 0 { MoveSize::Word } else { MoveSize::Long };
        if let Some(ea) = std_ea(opcode) {
            return DecodedInstruction::AddA { size, register: reg, ea };
        }
    }

    // ADDX: 1101_yyy1_ss00_mxxx
    if dir == 1 && ((opcode >> 4) & 3) == 0 {
        if let Some(size) = decode_size_2bit(size_bits) {
            let ry = (opcode & 7) as usize;
            let mem = (opcode & 8) != 0;
            return DecodedInstruction::AddX { size, rx: reg, ry, mem };
        }
    }

    // ADD: 1101_rrrd_ss(ea)
    if let Some(size) = decode_size_2bit(size_bits) {
        if let Some(ea) = std_ea(opcode) {
            let direction = if dir == 0 { Direction::EaToReg } else { Direction::RegToEa };
            return DecodedInstruction::Add { size, register: reg, dir: direction, ea };
        }
    }
    DecodedInstruction::Illegal
}

// Group E: Shifts and Rotates
fn decode_group_e(opcode: u16) -> DecodedInstruction {
    let size_bits = ((opcode >> 6) & 3) as u8;

    // Memory shifts: size field = 0b11
    if size_bits == 0b11 {
        let kind = ((opcode >> 9) & 3) as u8;
        let dir_bit = (opcode >> 8) & 1;
        if let Some(ea) = std_ea(opcode) {
            return match (kind, dir_bit) {
                (0, 0) => DecodedInstruction::AsrMem(ea),
                (0, 1) => DecodedInstruction::AslMem(ea),
                (1, 0) => DecodedInstruction::LsrMem(ea),
                (1, 1) => DecodedInstruction::LslMem(ea),
                (2, 0) => DecodedInstruction::RoxrMem(ea),
                (2, 1) => DecodedInstruction::RoxlMem(ea),
                (3, 0) => DecodedInstruction::RorMem(ea),
                (3, 1) => DecodedInstruction::RolMem(ea),
                _ => DecodedInstruction::Illegal,
            };
        }
        return DecodedInstruction::Illegal;
    }

    // Register shifts
    if let Some(size) = decode_size_2bit(size_bits) {
        let count_reg = ((opcode >> 9) & 7) as u8;
        let dir_bit = (opcode >> 8) & 1;
        let ir = (opcode >> 5) & 1;
        let kind = ((opcode >> 3) & 3) as u8;
        let reg = (opcode & 7) as usize;

        let count = if ir == 0 {
            ShiftCount::Imm(if count_reg == 0 { 8 } else { count_reg })
        } else {
            ShiftCount::Reg(count_reg)
        };

        return match (kind, dir_bit) {
            (0, 0) => DecodedInstruction::Asr { size, count, reg },
            (0, 1) => DecodedInstruction::Asl { size, count, reg },
            (1, 0) => DecodedInstruction::Lsr { size, count, reg },
            (1, 1) => DecodedInstruction::Lsl { size, count, reg },
            (2, 0) => DecodedInstruction::Roxr { size, count, reg },
            (2, 1) => DecodedInstruction::Roxl { size, count, reg },
            (3, 0) => DecodedInstruction::Ror { size, count, reg },
            (3, 1) => DecodedInstruction::Rol { size, count, reg },
            _ => DecodedInstruction::Illegal,
        };
    }
    DecodedInstruction::Illegal
}
