use md_core::{CpuState, Emulator};
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub struct EmulatorHandle {
    emu: Emulator,
}

#[wasm_bindgen]
impl EmulatorHandle {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            emu: Emulator::new(),
        }
    }

    pub fn load_rom(&mut self, rom: Vec<u8>) -> Result<(), JsValue> {
        self.emu
            .load_rom_bytes(&rom)
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn reset(&mut self) {
        self.emu.reset();
    }

    pub fn step(&mut self, cycles: u32) {
        self.emu.step(cycles);
    }

    pub fn run_frame(&mut self) {
        self.emu.run_frame();
    }

    pub fn pause(&mut self) {
        self.emu.pause();
    }

    pub fn resume(&mut self) {
        self.emu.resume();
    }

    pub fn step_instruction(&mut self) {
        self.emu.step_instruction();
    }

    pub fn set_breakpoint(&mut self, address: u32) {
        self.emu.set_breakpoint(address);
    }

    pub fn set_controller_state(&mut self, player: u8, buttons: u16) {
        self.emu.set_controller_state(player, buttons);
    }

    pub fn get_memory(&self, address: u32, length: usize) -> Vec<u8> {
        self.emu.get_memory(address, length)
    }

    pub fn get_vram(&self) -> Vec<u8> {
        self.emu.get_vram().to_vec()
    }

    pub fn get_cram(&self) -> Vec<u8> {
        self.emu.get_cram().to_vec()
    }

    pub fn get_cpu_state(&self) -> Result<JsValue, JsValue> {
        let state: CpuState = self.emu.get_cpu_state();
        serde_wasm_bindgen::to_value(&state).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn trace_execution(&self) -> Result<JsValue, JsValue> {
        let trace = self.emu.trace_execution();
        serde_wasm_bindgen::to_value(&trace).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn get_framebuffer_argb(&self) -> Vec<u32> {
        self.emu.get_framebuffer_argb().to_vec()
    }

    pub fn take_audio_samples(&mut self, frames: usize) -> Vec<f32> {
        self.emu.take_audio_samples(frames)
    }

    pub fn save_state(&self) -> Result<Vec<u8>, JsValue> {
        self.emu
            .save_state()
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn load_state(&mut self, data: Vec<u8>) -> Result<(), JsValue> {
        self.emu
            .load_state(&data)
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }
}
