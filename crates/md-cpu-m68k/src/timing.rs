use crate::decoder::{DecodedInstruction, EaMode, MoveSize};

pub fn cycles_for(instruction: &DecodedInstruction) -> u32 {
    match instruction {
        DecodedInstruction::Nop => 4,
        DecodedInstruction::Rts => 16,
        DecodedInstruction::Rte => 20,
        DecodedInstruction::Rtr => 20,
        DecodedInstruction::Reset => 132,
        DecodedInstruction::Stop => 4,
        DecodedInstruction::TrapV => 4,
        DecodedInstruction::Bra8(_) | DecodedInstruction::Bra16 => 10,
        DecodedInstruction::Bsr8(_) | DecodedInstruction::Bsr16 => 18,
        DecodedInstruction::Bcc8 { .. } | DecodedInstruction::Bcc16 { .. } => 10,
        DecodedInstruction::Dbcc { .. } => 12,
        DecodedInstruction::Jmp(ea) => 8 + ea_ctrl_cost(ea),
        DecodedInstruction::Jsr(ea) => 16 + ea_ctrl_cost(ea),
        DecodedInstruction::Move { size, src, dst } => {
            let base = match size {
                MoveSize::Long => 4,
                _ => 4,
            };
            base + ea_cost(src, *size) + ea_cost(dst, *size)
        }
        DecodedInstruction::MoveA { size, src, .. } => {
            let base = if matches!(size, MoveSize::Long) { 4 } else { 4 };
            base + ea_cost(src, *size)
        }
        DecodedInstruction::MoveQ { .. } => 4,
        DecodedInstruction::Movem { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 12 } else { 12 };
            base + ea_ctrl_cost(ea)
        }
        DecodedInstruction::MoveToSr(ea) => 12 + ea_cost(ea, MoveSize::Word),
        DecodedInstruction::MoveFromSr(ea) => 8 + if matches!(ea, EaMode::DataRegister(_)) { 0 } else { ea_cost(ea, MoveSize::Word) },
        DecodedInstruction::MoveToCcr(ea) => 12 + ea_cost(ea, MoveSize::Word),
        DecodedInstruction::MoveUsp { .. } => 4,
        DecodedInstruction::Lea { ea, .. } => 4 + ea_ctrl_cost(ea),
        DecodedInstruction::Pea(ea) => 12 + ea_ctrl_cost(ea),
        DecodedInstruction::Link { .. } => 16,
        DecodedInstruction::Unlk { .. } => 12,
        DecodedInstruction::Swap(_) => 4,
        DecodedInstruction::ExtW(_) | DecodedInstruction::ExtL(_) => 4,
        DecodedInstruction::Exg { .. } => 6,
        DecodedInstruction::Scc { ea, .. } => if matches!(ea, EaMode::DataRegister(_)) { 4 } else { 8 + ea_cost(ea, MoveSize::Byte) },
        DecodedInstruction::Add { size, ea, .. } | DecodedInstruction::Sub { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 8 } else { 4 };
            base + ea_cost(ea, *size)
        }
        DecodedInstruction::AddA { size, ea, .. } | DecodedInstruction::SubA { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 8 } else { 8 };
            base + ea_cost(ea, *size)
        }
        DecodedInstruction::AddI { size, ea, .. } | DecodedInstruction::SubI { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 16 } else { 8 };
            base + ea_cost(ea, *size)
        }
        DecodedInstruction::AddQ { size, ea, .. } | DecodedInstruction::SubQ { size, ea, .. } => {
            if matches!(ea, EaMode::AddressRegister(_)) { 8 }
            else if matches!(size, MoveSize::Long) { 8 }
            else { 4 + ea_cost(ea, *size) }
        }
        DecodedInstruction::AddX { size, .. } | DecodedInstruction::SubX { size, ..  } => {
            if matches!(size, MoveSize::Long) { 8 } else { 4 }
        }
        DecodedInstruction::Neg { size, ea } | DecodedInstruction::NegX { size, ea } | DecodedInstruction::Not { size, ea } | DecodedInstruction::Clr { size, ea } => {
            if matches!(ea, EaMode::DataRegister(_)) {
                if matches!(size, MoveSize::Long) { 6 } else { 4 }
            } else {
                (if matches!(size, MoveSize::Long) { 12 } else { 8 }) + ea_cost(ea, *size)
            }
        }
        DecodedInstruction::Tst { size, ea } => 4 + ea_cost(ea, *size),
        DecodedInstruction::Cmp { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 6 } else { 4 };
            base + ea_cost(ea, *size)
        }
        DecodedInstruction::CmpA { size, ea, .. } => 6 + ea_cost(ea, *size),
        DecodedInstruction::CmpI { size, ea, .. } => {
            if matches!(ea, EaMode::DataRegister(_)) {
                if matches!(size, MoveSize::Long) { 14 } else { 8 }
            } else { 8 + ea_cost(ea, *size) }
        }
        DecodedInstruction::CmpM { size, .. } => if matches!(size, MoveSize::Long) { 20 } else { 12 },
        DecodedInstruction::And { size, ea, .. } | DecodedInstruction::Or { size, ea, .. } => {
            let base = if matches!(size, MoveSize::Long) { 8 } else { 4 };
            base + ea_cost(ea, *size)
        }
        DecodedInstruction::AndI { size, ea, .. } | DecodedInstruction::OrI { size, ea, .. } | DecodedInstruction::EorI { size, ea, .. } => {
            if matches!(ea, EaMode::DataRegister(_)) {
                if matches!(size, MoveSize::Long) { 16 } else { 8 }
            } else { 12 + ea_cost(ea, *size) }
        }
        DecodedInstruction::Eor { size, ea, .. } => {
            if matches!(ea, EaMode::DataRegister(_)) {
                if matches!(size, MoveSize::Long) { 8 } else { 4 }
            } else { 8 + ea_cost(ea, *size) }
        }
        DecodedInstruction::AndiToCcr | DecodedInstruction::OriToCcr | DecodedInstruction::EoriToCcr => 20,
        DecodedInstruction::AndiToSr | DecodedInstruction::OriToSr | DecodedInstruction::EoriToSr => 20,
        DecodedInstruction::Btst { ea, .. } => if matches!(ea, EaMode::DataRegister(_)) { 6 } else { 4 + ea_cost(ea, MoveSize::Byte) },
        DecodedInstruction::Bchg { ea, .. } | DecodedInstruction::Bclr { ea, .. } | DecodedInstruction::Bset { ea, .. } => {
            if matches!(ea, EaMode::DataRegister(_)) { 8 } else { 8 + ea_cost(ea, MoveSize::Byte) }
        }
        DecodedInstruction::Asl { size, .. } | DecodedInstruction::Asr { size, .. }
        | DecodedInstruction::Lsl { size, .. } | DecodedInstruction::Lsr { size, .. }
        | DecodedInstruction::Rol { size, .. } | DecodedInstruction::Ror { size, .. }
        | DecodedInstruction::Roxl { size, .. } | DecodedInstruction::Roxr { size, .. } => {
            if matches!(size, MoveSize::Long) { 8 } else { 6 }
        }
        DecodedInstruction::AslMem(_) | DecodedInstruction::AsrMem(_)
        | DecodedInstruction::LslMem(_) | DecodedInstruction::LsrMem(_)
        | DecodedInstruction::RolMem(_) | DecodedInstruction::RorMem(_)
        | DecodedInstruction::RoxlMem(_) | DecodedInstruction::RoxrMem(_) => 8,
        DecodedInstruction::MulU { .. } | DecodedInstruction::MulS { .. } => 70,
        DecodedInstruction::DivU { .. } | DecodedInstruction::DivS { .. } => 140,
        DecodedInstruction::Trap(_) => 34,
        DecodedInstruction::Abcd { .. } | DecodedInstruction::Sbcd { .. } => 6,
        DecodedInstruction::Nbcd(ea) => if matches!(ea, EaMode::DataRegister(_)) { 6 } else { 8 + ea_cost(ea, MoveSize::Byte) },
        DecodedInstruction::Tas(ea) => if matches!(ea, EaMode::DataRegister(_)) { 4 } else { 14 + ea_cost(ea, MoveSize::Byte) },
        DecodedInstruction::Illegal => 34,
        DecodedInstruction::LineA | DecodedInstruction::LineF => 34,
    }
}

fn ea_cost(ea: &EaMode, size: MoveSize) -> u32 {
    match ea {
        EaMode::DataRegister(_) | EaMode::AddressRegister(_) => 0,
        EaMode::AddressIndirect(_) => if matches!(size, MoveSize::Long) { 8 } else { 4 },
        EaMode::AddressIndirectPostInc(_) | EaMode::AddressIndirectPreDec(_) => if matches!(size, MoveSize::Long) { 8 } else { 4 },
        EaMode::AddressDisplacement(_) => if matches!(size, MoveSize::Long) { 12 } else { 8 },
        EaMode::AddressIndex(_) => if matches!(size, MoveSize::Long) { 14 } else { 10 },
        EaMode::AbsoluteWord => if matches!(size, MoveSize::Long) { 12 } else { 8 },
        EaMode::AbsoluteLong => if matches!(size, MoveSize::Long) { 16 } else { 12 },
        EaMode::PcDisplacement => if matches!(size, MoveSize::Long) { 12 } else { 8 },
        EaMode::PcIndex => if matches!(size, MoveSize::Long) { 14 } else { 10 },
        EaMode::Immediate => match size {
            MoveSize::Byte | MoveSize::Word => 4,
            MoveSize::Long => 8,
        },
    }
}

fn ea_ctrl_cost(ea: &EaMode) -> u32 {
    match ea {
        EaMode::AddressIndirect(_) => 0,
        EaMode::AddressDisplacement(_) => 4,
        EaMode::AddressIndex(_) => 6,
        EaMode::AbsoluteWord => 4,
        EaMode::AbsoluteLong => 8,
        EaMode::PcDisplacement => 4,
        EaMode::PcIndex => 6,
        _ => 0,
    }
}
