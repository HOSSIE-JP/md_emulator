#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddressingMode {
    DataRegisterDirect(usize),
    AddressRegisterDirect(usize),
    Immediate,
    AbsoluteLong,
    Unknown,
}

pub fn decode_mode(mode_bits: u16, register_bits: u16) -> AddressingMode {
    match mode_bits {
        0b000 => AddressingMode::DataRegisterDirect(register_bits as usize),
        0b001 => AddressingMode::AddressRegisterDirect(register_bits as usize),
        0b111 if register_bits == 0b100 => AddressingMode::Immediate,
        0b111 if register_bits == 0b001 => AddressingMode::AbsoluteLong,
        _ => AddressingMode::Unknown,
    }
}
