use md_core::{CpuState, Emulator};
use serde::Serialize;
use wasm_bindgen::prelude::*;

#[derive(Serialize)]
struct VdpRegistersResponse {
    registers: Vec<u8>,
    code: u8,
    address: u16,
    status: u16,
    frame: u64,
    data_writes: u64,
    ctrl_writes: u64,
    dma_68k_count: u64,
    dma_68k_total_words: u64,
    dma_fill_count: u64,
    dma_copy_count: u64,
    last_dma_target_addr: u16,
    last_dma_source: u32,
    last_dma_length: u16,
    hint_delivered: u64,
    vint_delivered: u64,
}

#[derive(Serialize)]
struct PlaneResponse {
    plane: String,
    width: usize,
    height: usize,
    pixels_argb: Vec<u32>,
}

#[derive(Serialize)]
struct TilesResponse {
    palette: u8,
    width: usize,
    height: usize,
    pixels_argb: Vec<u32>,
}

#[derive(Serialize)]
struct ColorsResponse {
    colors_argb: Vec<u32>,
}

#[derive(Serialize)]
struct SpritesResponse<T> {
    sprites: T,
}

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

    pub fn build_version() -> String {
        Emulator::build_version()
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

    pub fn get_vdp_registers_json(&self) -> Result<JsValue, JsValue> {
        let regs = self.emu.get_vdp_registers();
        let (code, address, status, frame, data_writes, ctrl_writes) = self.emu.get_vdp_debug();
        let dma = self.emu.get_vdp_dma_debug();

        let payload = VdpRegistersResponse {
            registers: regs,
            code,
            address,
            status,
            frame,
            data_writes,
            ctrl_writes,
            dma_68k_count: dma.0,
            dma_68k_total_words: dma.1,
            dma_fill_count: dma.2,
            dma_copy_count: dma.3,
            last_dma_target_addr: dma.4,
            last_dma_source: dma.5,
            last_dma_length: dma.6,
            hint_delivered: self.emu.hint_delivered_count,
            vint_delivered: self.emu.vint_delivered_count,
        };
        serde_wasm_bindgen::to_value(&payload).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn debug_render_plane(&self, plane: String) -> Result<JsValue, JsValue> {
        let normalized = plane.to_uppercase();
        let plane_char = match normalized.as_str() {
            "A" => 'A',
            "B" => 'B',
            "W" | "WINDOW" => 'W',
            _ => return Err(JsValue::from_str("invalid plane name, use A/B/W")),
        };
        let (width, height, pixels) = self.emu.debug_render_plane(plane_char);
        let payload = PlaneResponse {
            plane: normalized,
            width,
            height,
            pixels_argb: pixels,
        };
        serde_wasm_bindgen::to_value(&payload).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn debug_render_tiles(&self, palette: u8) -> Result<JsValue, JsValue> {
        let palette = palette.min(3);
        let (width, height, pixels) = self.emu.debug_render_tiles(palette);
        let payload = TilesResponse {
            palette,
            width,
            height,
            pixels_argb: pixels,
        };
        serde_wasm_bindgen::to_value(&payload).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn debug_cram_colors_json(&self) -> Result<JsValue, JsValue> {
        let payload = ColorsResponse {
            colors_argb: self.emu.debug_cram_colors(),
        };
        serde_wasm_bindgen::to_value(&payload).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    pub fn debug_sprites_json(&self) -> Result<JsValue, JsValue> {
        let payload = SpritesResponse {
            sprites: self.emu.debug_sprites(),
        };
        serde_wasm_bindgen::to_value(&payload).map_err(|e| JsValue::from_str(&e.to_string()))
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
