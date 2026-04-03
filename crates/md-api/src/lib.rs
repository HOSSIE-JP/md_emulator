use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};

use axum::{
    extract::{ws::{Message, WebSocket, WebSocketUpgrade}, Query, State},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use md_core::Emulator;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tower_http::cors::CorsLayer;

#[derive(Clone)]
pub struct ApiState {
    pub emulator: Arc<Mutex<Emulator>>,
    pub request_log_enabled: Arc<AtomicBool>,
}

#[derive(Debug, Deserialize)]
pub struct StepRequest {
    pub cycles: Option<u32>,
    pub frames: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct MemoryQuery {
    pub addr: u32,
    pub len: usize,
}

#[derive(Debug, Serialize)]
pub struct OkResponse {
    pub ok: bool,
}

#[derive(Debug, Serialize)]
pub struct LoggingResponse {
    pub enabled: bool,
}

#[derive(Debug, Deserialize)]
pub struct LoggingRequest {
    pub enabled: bool,
}

#[derive(Debug, Serialize)]
pub struct FrameResponse {
    pub width: usize,
    pub height: usize,
    pub pixels_argb: Vec<u32>,
}

#[derive(Debug, Deserialize)]
pub struct ControllerRequest {
    pub player: u8,
    pub buttons: u16,
}

#[derive(Debug, Deserialize)]
pub struct LoadRomRequest {
    pub rom: Vec<u8>,
}

#[derive(Debug, Deserialize)]
pub struct LoadRomPathRequest {
    pub path: String,
}

#[derive(Debug, Deserialize)]
pub struct PlaneQuery {
    pub name: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TilesQuery {
    pub palette: Option<u8>,
}

#[derive(Debug, Deserialize)]
pub struct SaveStateRequest {
    pub data: Vec<u8>,
}

#[derive(Debug, Deserialize)]
pub struct RpcRequest {
    pub id: Option<Value>,
    pub method: String,
    pub params: Option<Value>,
}

#[derive(Debug, Serialize)]
pub struct RpcResponse {
    pub jsonrpc: String,
    pub id: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<Value>,
}

pub fn router(emulator: Arc<Mutex<Emulator>>) -> Router {
    let from_env = std::env::var("MD_API_LOG")
        .ok()
        .map(|v| {
            let lower = v.to_ascii_lowercase();
            lower == "1" || lower == "true" || lower == "on"
        })
        .unwrap_or(false);

    let state = ApiState {
        emulator,
        request_log_enabled: Arc::new(AtomicBool::new(from_env)),
    };

    Router::new()
        .route("/api/v1/health", get(health))
        .route("/api/v1/version", get(version))
        .route("/api/v1/logging", get(get_logging).post(set_logging))
        .route("/api/v1/input/controller", post(set_controller_input))
        .route("/api/v1/emulator/reset", post(reset))
        .route("/api/v1/emulator/step", post(step))
        .route("/api/v1/emulator/load-rom", post(load_rom))
        .route("/api/v1/emulator/load-rom-path", post(load_rom_path))
        .route("/api/v1/emulator/save-state", get(save_state))
        .route("/api/v1/emulator/load-state", post(load_state))
        .route("/api/v1/rom/info", get(rom_info))
        .route("/api/v1/cpu/state", get(cpu_state))
        .route("/api/v1/cpu/memory", get(memory).post(write_memory))
        .route("/api/v1/cpu/trace", get(cpu_trace))
        .route("/api/v1/video/frame", get(video_frame))
        .route("/api/v1/vdp/cram", get(vdp_cram))
        .route("/api/v1/vdp/registers", get(vdp_registers).post(set_vdp_register))
        .route("/api/v1/vdp/vram", get(vdp_vram))
        .route("/api/v1/vdp/plane", get(vdp_plane))
        .route("/api/v1/vdp/tiles", get(vdp_tiles))
        .route("/api/v1/vdp/colors", get(vdp_colors))
        .route("/api/v1/vdp/sprites", get(vdp_sprites))
        .route("/api/v1/vdp/vsram", get(vdp_vsram))
        .route("/api/v1/vdp/scanline-vsram", get(vdp_scanline_vsram))
        .route("/api/v1/audio/samples", get(audio_samples))
        .route("/api/v1/apu/state", get(apu_state))
        .route("/api/v1/ws", get(ws_upgrade))
        .route("/api/v1/mcp/rpc", post(mcp_rpc))
        .layer(CorsLayer::permissive())
        .with_state(state)
}

fn log_if_enabled(state: &ApiState, message: impl AsRef<str>) {
    if state.request_log_enabled.load(Ordering::Relaxed) {
        println!("[md-api] {}", message.as_ref());
    }
}

async fn health() -> impl IntoResponse {
    Json(OkResponse { ok: true })
}

async fn version() -> impl IntoResponse {
    Json(json!({"version": Emulator::build_version()}))
}

async fn get_logging(State(state): State<ApiState>) -> impl IntoResponse {
    Json(LoggingResponse {
        enabled: state.request_log_enabled.load(Ordering::Relaxed),
    })
}

async fn set_logging(State(state): State<ApiState>, Json(body): Json<LoggingRequest>) -> impl IntoResponse {
    state
        .request_log_enabled
        .store(body.enabled, Ordering::Relaxed);
    Json(LoggingResponse {
        enabled: state.request_log_enabled.load(Ordering::Relaxed),
    })
}

async fn reset(State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "POST /api/v1/emulator/reset");
    if let Ok(mut emu) = state.emulator.lock() {
        emu.reset();
    }
    Json(OkResponse { ok: true })
}

async fn set_controller_input(
    State(state): State<ApiState>,
    Json(body): Json<ControllerRequest>,
) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!(
            "POST /api/v1/input/controller player={} buttons=0x{:04X}",
            body.player, body.buttons
        ),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        emu.set_controller_state(body.player, body.buttons);
        return Json(json!({"ok": true}));
    }
    Json(json!({"ok": false, "error": "lock failed"}))
}

async fn step(State(state): State<ApiState>, Json(body): Json<StepRequest>) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!(
            "POST /api/v1/emulator/step cycles={:?} frames={:?}",
            body.cycles, body.frames
        ),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        if let Some(frames) = body.frames {
            for _ in 0..frames {
                emu.run_frame();
            }
        } else {
            emu.step(body.cycles.unwrap_or(488));
        }
    }
    Json(OkResponse { ok: true })
}

async fn load_rom(State(state): State<ApiState>, Json(body): Json<LoadRomRequest>) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!("POST /api/v1/emulator/load-rom bytes={}", body.rom.len()),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        let _ = emu.load_rom_bytes(&body.rom);
    }
    Json(OkResponse { ok: true })
}

async fn load_rom_path(
    State(state): State<ApiState>,
    Json(body): Json<LoadRomPathRequest>,
) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!("POST /api/v1/emulator/load-rom-path path={}", body.path),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        let result = emu.load_rom(&body.path);
        return match result {
            Ok(_) => Json(json!({"ok": true})),
            Err(err) => Json(json!({"ok": false, "error": err.to_string()})),
        };
    }
    Json(json!({"ok": false, "error": "lock failed"}))
}

async fn save_state(State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "GET /api/v1/emulator/save-state");
    if let Ok(emu) = state.emulator.lock() {
        if let Ok(state_data) = emu.save_state() {
            return Json(json!({"ok": true, "state": state_data}));
        }
    }
    Json(json!({"ok": false}))
}

async fn load_state(State(state): State<ApiState>, Json(body): Json<SaveStateRequest>) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!("POST /api/v1/emulator/load-state bytes={}", body.data.len()),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        let _ = emu.load_state(&body.data);
    }
    Json(OkResponse { ok: true })
}

async fn cpu_state(State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "GET /api/v1/cpu/state");
    if let Ok(emu) = state.emulator.lock() {
        return Json(serde_json::json!({"cpu": emu.get_cpu_state()}));
    }
    Json(serde_json::json!({"error": "lock failed"}))
}

async fn cpu_trace(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        return Json(serde_json::json!({"exception_trace": emu.exception_trace(), "trace_ring": emu.trace_ring()}));
    }
    Json(serde_json::json!({"error": "lock failed"}))
}

async fn memory(State(state): State<ApiState>, Query(query): Query<MemoryQuery>) -> impl IntoResponse {
    log_if_enabled(
        &state,
        format!("GET /api/v1/cpu/memory addr={} len={}", query.addr, query.len),
    );
    if let Ok(emu) = state.emulator.lock() {
        let data = emu.get_memory(query.addr, query.len);
        return Json(serde_json::json!({"address": query.addr, "data": data}));
    }
    Json(serde_json::json!({"error": "lock failed"}))
}

async fn write_memory(
    State(state): State<ApiState>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    let addr = body["addr"].as_u64().unwrap_or(0) as u32;
    let data: Vec<u8> = body["data"]
        .as_array()
        .map(|a| a.iter().filter_map(|v| v.as_u64().map(|n| n as u8)).collect())
        .unwrap_or_default();
    log_if_enabled(
        &state,
        format!("POST /api/v1/cpu/memory addr=0x{:X} len={}", addr, data.len()),
    );
    if let Ok(mut emu) = state.emulator.lock() {
        emu.set_memory(addr, &data);
        return Json(serde_json::json!({"ok": true, "addr": addr, "len": data.len()}));
    }
    Json(serde_json::json!({"error": "lock failed"}))
}

async fn rom_info(State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "GET /api/v1/rom/info");
    if let Ok(emu) = state.emulator.lock() {
        return Json(json!({"loaded": emu.rom_loaded(), "info": emu.get_rom_info()}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn video_frame(State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "GET /api/v1/video/frame");
    if let Ok(emu) = state.emulator.lock() {
        let (width, height) = emu.frame_dimensions();
        return Json(json!(FrameResponse {
            width,
            height,
            pixels_argb: emu.get_framebuffer_argb().to_vec(),
        }));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_cram(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let cram = emu.get_cram();
        let entries: Vec<u16> = cram.chunks_exact(2).map(|c| ((c[0] as u16) << 8) | c[1] as u16).collect();
        return Json(json!({"cram": entries}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_registers(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let regs = emu.get_vdp_registers();
        let (code, address, status, frame, data_writes, ctrl_writes) = emu.get_vdp_debug();
        let dma = emu.get_vdp_dma_debug();
        return Json(json!({
            "registers": regs,
            "code": code,
            "address": address,
            "status": status,
            "frame": frame,
            "data_writes": data_writes,
            "ctrl_writes": ctrl_writes,
            "dma_68k_count": dma.0,
            "dma_68k_total_words": dma.1,
            "dma_fill_count": dma.2,
            "dma_copy_count": dma.3,
            "last_dma_target_addr": dma.4,
            "last_dma_source": dma.5,
            "last_dma_length": dma.6,
            "hint_delivered": emu.hint_delivered_count,
            "vint_delivered": emu.vint_delivered_count,
        }));
    }
    Json(json!({"error": "lock failed"}))
}

async fn set_vdp_register(
    State(state): State<ApiState>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    let reg = body["reg"].as_u64().unwrap_or(0) as u8;
    let value = body["value"].as_u64().unwrap_or(0) as u8;
    if let Ok(mut emu) = state.emulator.lock() {
        emu.set_vdp_register(reg, value);
        return Json(json!({"ok": true, "reg": reg, "value": value}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_vram(State(state): State<ApiState>, Query(query): Query<MemoryQuery>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let vram = emu.get_vram();
        let start = query.addr as usize;
        let end = (start + query.len).min(vram.len());
        let data: Vec<u8> = if start < vram.len() { vram[start..end].to_vec() } else { vec![] };
        return Json(json!({"addr": start, "data": data}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_plane(State(state): State<ApiState>, Query(query): Query<PlaneQuery>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let name = query.name.as_deref().unwrap_or("A");
        let plane_char = match name.to_uppercase().as_str() {
            "A" => 'A',
            "B" => 'B',
            "W" | "WINDOW" => 'W',
            _ => return Json(json!({"error": "invalid plane name, use A/B/W"})),
        };
        let (width, height, pixels) = emu.debug_render_plane(plane_char);
        return Json(json!({"plane": name.to_uppercase(), "width": width, "height": height, "pixels_argb": pixels}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_tiles(State(state): State<ApiState>, Query(query): Query<TilesQuery>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let palette = query.palette.unwrap_or(0).min(3);
        let (width, height, pixels) = emu.debug_render_tiles(palette);
        return Json(json!({"palette": palette, "width": width, "height": height, "pixels_argb": pixels}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_colors(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let colors = emu.debug_cram_colors();
        return Json(json!({"colors_argb": colors}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_sprites(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let sprites = emu.debug_sprites();
        return Json(json!({"sprites": sprites}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_vsram(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let vsram = emu.get_vsram();
        let entries: Vec<u16> = vsram.chunks_exact(2).map(|c| ((c[0] as u16) << 8) | c[1] as u16).collect();
        return Json(json!({"vsram": entries}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn vdp_scanline_vsram(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        let data = emu.get_scanline_vsram_a();
        return Json(json!({"scanline_vsram_a": data}));
    }
    Json(json!({"error": "lock failed"}))
}

#[derive(Debug, Deserialize)]
pub struct AudioQuery {
    pub frames: Option<usize>,
}

async fn audio_samples(State(state): State<ApiState>, Query(query): Query<AudioQuery>) -> impl IntoResponse {
    if let Ok(mut emu) = state.emulator.lock() {
        let frames = query.frames.unwrap_or(800);
        let samples = emu.take_audio_samples(frames);
        return Json(json!({"sample_rate": 48000, "channels": 2, "samples": samples}));
    }
    Json(json!({"error": "lock failed"}))
}

async fn apu_state(State(state): State<ApiState>) -> impl IntoResponse {
    if let Ok(emu) = state.emulator.lock() {
        return Json(emu.get_apu_debug());
    }
    Json(json!({"error": "lock failed"}))
}

async fn ws_upgrade(ws: WebSocketUpgrade, State(state): State<ApiState>) -> impl IntoResponse {
    log_if_enabled(&state, "GET /api/v1/ws (upgrade)");
    ws.on_upgrade(move |socket| ws_session(socket, state))
}

async fn ws_session(mut socket: WebSocket, state: ApiState) {
    while let Some(Ok(msg)) = socket.recv().await {
        if let Message::Text(text) = msg {
            log_if_enabled(&state, format!("WS recv: {}", text));
            let parsed = serde_json::from_str::<RpcRequest>(&text);
            let response = match parsed {
                Ok(req) => handle_rpc(req, &state),
                Err(err) => RpcResponse {
                    jsonrpc: "2.0".to_string(),
                    id: None,
                    result: None,
                    error: Some(json!({"code": -32700, "message": err.to_string()})),
                },
            };
            let payload = serde_json::to_string(&response).unwrap_or_else(|_| {
                "{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32603,\"message\":\"serialization\"}}".to_string()
            });
            if socket.send(Message::Text(payload.into())).await.is_err() {
                break;
            }
        }
    }
}

async fn mcp_rpc(State(state): State<ApiState>, Json(req): Json<RpcRequest>) -> impl IntoResponse {
    log_if_enabled(&state, format!("POST /api/v1/mcp/rpc method={}", req.method));
    Json(handle_rpc(req, &state))
}

fn handle_rpc(req: RpcRequest, state: &ApiState) -> RpcResponse {
    let id = req.id.clone();
    if let Ok(mut emu) = state.emulator.lock() {
        let result = match req.method.as_str() {
            "load_rom" => {
                if let Some(params) = req.params {
                    if let Some(rom) = params.get("rom") {
                        if let Ok(bytes) = serde_json::from_value::<Vec<u8>>(rom.clone()) {
                            let _ = emu.load_rom_bytes(&bytes);
                            Some(json!({"ok": true}))
                        } else {
                            None
                        }
                    } else {
                        None
                    }
                } else {
                    None
                }
            }
            "load_rom_path" => {
                let path = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("path"))
                    .and_then(|v| v.as_str())
                    .map(ToOwned::to_owned);
                if let Some(path) = path {
                    match emu.load_rom(path) {
                        Ok(_) => Some(json!({"ok": true})),
                        Err(err) => Some(json!({"ok": false, "error": err.to_string()})),
                    }
                } else {
                    None
                }
            }
            "reset" => {
                emu.reset();
                Some(json!({"ok": true}))
            }
            "step" => {
                let cycles = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("cycles"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(488) as u32;
                emu.step(cycles);
                Some(json!({"ok": true, "cycles": cycles}))
            }
            "run_frame" => {
                emu.run_frame();
                Some(json!({"ok": true}))
            }
            "pause" => {
                emu.pause();
                Some(json!({"ok": true}))
            }
            "set_controller_state" => {
                let player = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("player"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(1) as u8;
                let buttons = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("buttons"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u16;
                emu.set_controller_state(player, buttons);
                Some(json!({"ok": true, "player": player, "buttons": buttons}))
            }
            "get_cpu_state" => Some(json!({"cpu": emu.get_cpu_state()})),
            "get_rom_info" => Some(json!({"loaded": emu.rom_loaded(), "info": emu.get_rom_info()})),
            "get_memory" => {
                let addr = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("address"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u32;
                let len = req
                    .params
                    .as_ref()
                    .and_then(|v| v.get("length"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(16) as usize;
                Some(json!({"address": addr, "data": emu.get_memory(addr, len)}))
            }
            "save_state" => {
                if let Ok(data) = emu.save_state() {
                    Some(json!({"state": data}))
                } else {
                    None
                }
            }
            "load_state" => {
                if let Some(params) = req.params {
                    if let Some(state_value) = params.get("state") {
                        if let Ok(data) = serde_json::from_value::<Vec<u8>>(state_value.clone()) {
                            let _ = emu.load_state(&data);
                            Some(json!({"ok": true}))
                        } else {
                            None
                        }
                    } else {
                        None
                    }
                } else {
                    None
                }
            }
            _ => {
                return RpcResponse {
                    jsonrpc: "2.0".to_string(),
                    id,
                    result: None,
                    error: Some(json!({"code": -32601, "message": "method not found"})),
                }
            }
        };

        if let Some(result) = result {
            return RpcResponse {
                jsonrpc: "2.0".to_string(),
                id,
                result: Some(result),
                error: None,
            };
        }
    }

    RpcResponse {
        jsonrpc: "2.0".to_string(),
        id,
        result: None,
        error: Some(json!({"code": -32603, "message": "internal error"})),
    }
}
