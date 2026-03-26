const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const imageData = ctx.createImageData(canvas.width, canvas.height);
const romFileInput = document.getElementById("romFile");
const loadRomButton = document.getElementById("loadRom");
const toggleRunButton = document.getElementById("toggleRun");
const stepFrameButton = document.getElementById("stepFrame");
const resetButton = document.getElementById("reset");
const toggleAudioButton = document.getElementById("toggleAudio");
const saveStateButton = document.getElementById("saveState");
const loadStateButton = document.getElementById("loadState");
const downloadStateButton = document.getElementById("downloadState");
const uploadStateButton = document.getElementById("uploadState");
const stateFileInput = document.getElementById("stateFile");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");

const TARGET_FPS = 60;
const FRAME_MS = 1000 / TARGET_FPS;
const AUDIO_SAMPLE_RATE = 48000;
const AUDIO_PULL_FRAMES = Math.ceil(AUDIO_SAMPLE_RATE / TARGET_FPS); // ~800 stereo frames per game frame

const BTN_UP = 1 << 0;
const BTN_DOWN = 1 << 1;
const BTN_LEFT = 1 << 2;
const BTN_RIGHT = 1 << 3;
const BTN_B = 1 << 4;
const BTN_C = 1 << 5;
const BTN_A = 1 << 6;
const BTN_START = 1 << 7;

const pressed = new Set();
const touchPressed = new Set();

let wasmReady = false;
let emulator = null;
let wasmModule = null;
let loadedRomBytes = null;
let running = false;
let rafId = null;
let lastTs = 0;
let accumulator = 0;
let renderedFrames = 0;
let audioContext = null;
let audioEnabled = false;
let audioNextTime = 0;
let savedStateData = null;

function toByteArray(data) {
  if (!data) {
    return null;
  }
  if (data instanceof Uint8Array) {
    return data;
  }
  if (Array.isArray(data)) {
    return new Uint8Array(data);
  }
  return new Uint8Array(data.buffer ?? data);
}

function triggerDownload(bytes, filename, mimeType = "application/octet-stream") {
  const blob = new Blob([bytes], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function setStatus(text) {
  statusEl.textContent = text;
}

function setMeta(text) {
  metaEl.textContent = text;
}

function isEditableTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }
  return target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
}

function computeButtons() {
  let buttons = 0;
  if (pressed.has("ArrowUp") || pressed.has("KeyW") || touchPressed.has("up")) buttons |= BTN_UP;
  if (pressed.has("ArrowDown") || pressed.has("KeyS") || touchPressed.has("down")) buttons |= BTN_DOWN;
  if (pressed.has("ArrowLeft") || pressed.has("KeyA") || touchPressed.has("left")) buttons |= BTN_LEFT;
  if (pressed.has("ArrowRight") || pressed.has("KeyD") || touchPressed.has("right")) buttons |= BTN_RIGHT;
  if (pressed.has("KeyJ") || touchPressed.has("b")) buttons |= BTN_B;
  if (pressed.has("KeyK") || touchPressed.has("c")) buttons |= BTN_C;
  if (pressed.has("KeyU") || touchPressed.has("a")) buttons |= BTN_A;
  if (pressed.has("Enter") || touchPressed.has("start")) buttons |= BTN_START;
  return buttons;
}

function drawFrame(pixelsArgb) {
  const dst = imageData.data;
  const limit = Math.min(pixelsArgb.length, canvas.width * canvas.height);
  for (let i = 0; i < limit; i += 1) {
    const color = pixelsArgb[i] >>> 0;
    const offset = i * 4;
    dst[offset] = (color >> 16) & 0xff;
    dst[offset + 1] = (color >> 8) & 0xff;
    dst[offset + 2] = color & 0xff;
    dst[offset + 3] = (color >> 24) & 0xff;
  }
  ctx.putImageData(imageData, 0, 0);
}

function updateMeta() {
  setMeta([
    `wasm_ready=${wasmReady}`,
    `rom_loaded=${loadedRomBytes ? "yes" : "no"}`,
    `running=${running}`,
    `audio=${audioEnabled ? "on" : "off"}`,
    `frames=${renderedFrames}`,
  ].join("\n"));
}

function ensureAudio() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: AUDIO_SAMPLE_RATE,
    });
  }
}

function drainAudio() {
  if (!audioEnabled || !audioContext || !emulator) {
    return;
  }
  const rawSamples = emulator.take_audio_samples(AUDIO_PULL_FRAMES);
  const samples = Array.from(rawSamples || []);
  if (samples.length < 2) {
    return;
  }
  const frameCount = Math.floor(samples.length / 2);
  const buffer = audioContext.createBuffer(2, frameCount, AUDIO_SAMPLE_RATE);
  const left = buffer.getChannelData(0);
  const right = buffer.getChannelData(1);
  for (let i = 0; i < frameCount; i += 1) {
    left[i] = samples[i * 2] ?? 0;
    right[i] = samples[i * 2 + 1] ?? 0;
  }
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  const now = audioContext.currentTime;
  if (audioNextTime < now) {
    audioNextTime = now;
  }
  source.start(audioNextTime);
  audioNextTime += buffer.duration;
}

function setButtons() {
  if (!emulator) {
    return;
  }
  emulator.set_controller_state(1, computeButtons());
}

function runOneFrame() {
  if (!emulator) {
    return;
  }
  setButtons();
  emulator.run_frame();
  drawFrame(emulator.get_framebuffer_argb());
  drainAudio();
  renderedFrames += 1;
  updateMeta();
}

function stopLoop() {
  running = false;
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  toggleRunButton.textContent = "Run";
  updateMeta();
}

function frameTick(ts) {
  if (!running) {
    return;
  }
  if (!lastTs) {
    lastTs = ts;
  }
  accumulator += ts - lastTs;
  lastTs = ts;
  while (accumulator >= FRAME_MS) {
    accumulator -= FRAME_MS;
    runOneFrame();
  }
  rafId = requestAnimationFrame(frameTick);
}

async function initializeWasm() {
  try {
    wasmModule = await import(`./pkg/md_wasm.js?v=${Date.now()}`);
    await wasmModule.default();
    emulator = new wasmModule.EmulatorHandle();
    wasmReady = true;
    loadRomButton.disabled = false;
    uploadStateButton.disabled = false;
    setStatus("wasm ready");
    // Display build version
    const buildEl = document.getElementById("buildVersion");
    if (buildEl && wasmModule.EmulatorHandle.build_version) {
      try {
        buildEl.textContent = `build: ${wasmModule.EmulatorHandle.build_version()} (WASM)`;
      } catch { /* older pkg may not have build_version */ }
    }
    updateMeta();
  } catch (error) {
    setStatus(`wasm init failed: ${error}`);
    setMeta("build frontend/pkg first: wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg");
  }
}

async function loadSelectedRom() {
  const file = romFileInput.files?.[0];
  if (!file) {
    setStatus("select a ROM file first");
    return;
  }
  if (!emulator) {
    setStatus("wasm not ready");
    return;
  }
  const arrayBuffer = await file.arrayBuffer();
  loadedRomBytes = new Uint8Array(arrayBuffer);
  emulator.load_rom(loadedRomBytes);
  emulator.reset();
  renderedFrames = 0;
  savedStateData = null;
  drawFrame(emulator.get_framebuffer_argb());
  toggleRunButton.disabled = false;
  stepFrameButton.disabled = false;
  resetButton.disabled = false;
  toggleAudioButton.disabled = false;
  saveStateButton.disabled = false;
  downloadStateButton.disabled = false;
  loadStateButton.disabled = true;
  setStatus(`ROM loaded: ${file.name} (${loadedRomBytes.length} bytes)`);
  updateMeta();
}

function resetEmulator() {
  if (!emulator || !loadedRomBytes) {
    return;
  }
  stopLoop();
  emulator.load_rom(loadedRomBytes);
  emulator.reset();
  renderedFrames = 0;
  drawFrame(emulator.get_framebuffer_argb());
  audioNextTime = 0;
  setStatus("emulator reset");
  updateMeta();
}

function toggleRun() {
  if (!emulator || !loadedRomBytes) {
    return;
  }
  running = !running;
  if (running) {
    lastTs = 0;
    accumulator = 0;
    toggleRunButton.textContent = "Pause";
    rafId = requestAnimationFrame(frameTick);
    setStatus("running");
  } else {
    stopLoop();
    setStatus("paused");
  }
  updateMeta();
}

async function toggleAudio() {
  if (!emulator) {
    return;
  }
  ensureAudio();
  audioEnabled = !audioEnabled;
  if (audioEnabled) {
    await audioContext.resume();
    audioNextTime = 0;
    toggleAudioButton.textContent = "Mute";
    setStatus("audio enabled");
  } else {
    toggleAudioButton.textContent = "Unmute";
    setStatus("audio muted");
  }
  updateMeta();
}

loadRomButton.addEventListener("click", () => {
  loadSelectedRom().catch((error) => setStatus(`load failed: ${error}`));
});

toggleRunButton.addEventListener("click", toggleRun);
stepFrameButton.addEventListener("click", () => {
  runOneFrame();
  setStatus("stepped one frame");
});
resetButton.addEventListener("click", resetEmulator);
toggleAudioButton.addEventListener("click", () => {
  toggleAudio().catch((error) => setStatus(`audio failed: ${error}`));
});

saveStateButton.addEventListener("click", () => {
  if (!emulator) return;
  try {
    savedStateData = toByteArray(emulator.save_state());
    loadStateButton.disabled = false;
    downloadStateButton.disabled = false;
    setStatus(`state saved (${savedStateData.length} bytes)`);
  } catch (e) {
    setStatus(`save failed: ${e}`);
  }
});

loadStateButton.addEventListener("click", () => {
  if (!emulator || !savedStateData) return;
  try {
    emulator.load_state(Array.from(savedStateData));
    drawFrame(emulator.get_framebuffer_argb());
    setStatus("state loaded");
  } catch (e) {
    setStatus(`load failed: ${e}`);
  }
});

downloadStateButton.addEventListener("click", () => {
  if (!emulator) return;
  try {
    const stateBytes = savedStateData ?? toByteArray(emulator.save_state());
    if (!stateBytes) {
      setStatus("no state available");
      return;
    }
    savedStateData = stateBytes;
    loadStateButton.disabled = false;
    triggerDownload(stateBytes, "wasm-save.mdstate", "application/octet-stream");
    setStatus(`state downloaded (${stateBytes.length} bytes)`);
  } catch (e) {
    setStatus(`download failed: ${e}`);
  }
});

uploadStateButton.addEventListener("click", async () => {
  if (!emulator) return;
  const file = stateFileInput.files?.[0];
  if (!file) {
    setStatus("select a state file first");
    return;
  }
  try {
    const stateBytes = new Uint8Array(await file.arrayBuffer());
    emulator.load_state(Array.from(stateBytes));
    savedStateData = stateBytes;
    loadStateButton.disabled = false;
    drawFrame(emulator.get_framebuffer_argb());
    setStatus(`state uploaded: ${file.name}`);
  } catch (e) {
    setStatus(`upload failed: ${e}`);
  }
});

window.addEventListener("keydown", (event) => {
  if (isEditableTarget(event.target) || event.repeat) {
    return;
  }
  pressed.add(event.code);
  event.preventDefault();
  setButtons();
});

window.addEventListener("keyup", (event) => {
  if (isEditableTarget(event.target)) {
    return;
  }
  pressed.delete(event.code);
  event.preventDefault();
  setButtons();
});

window.addEventListener("blur", () => {
  pressed.clear();
  setButtons();
});

// On-screen controller buttons (mouse/touch)
document.querySelectorAll("[data-btn]").forEach((btn) => {
  const name = btn.dataset.btn;
  const down = () => { touchPressed.add(name); setButtons(); };
  const up = () => { touchPressed.delete(name); setButtons(); };
  btn.addEventListener("mousedown", down);
  btn.addEventListener("mouseup", up);
  btn.addEventListener("mouseleave", up);
  btn.addEventListener("touchstart", (e) => { e.preventDefault(); down(); });
  btn.addEventListener("touchend", (e) => { e.preventDefault(); up(); });
  btn.addEventListener("touchcancel", (e) => { e.preventDefault(); up(); });
});

initializeWasm();
