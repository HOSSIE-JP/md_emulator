const out = document.getElementById("out");
const romPathInput = document.getElementById("romPath");
const statusEl = document.getElementById("status");
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const frameImage = ctx.createImageData(canvas.width, canvas.height);
const buildVersionEl = document.getElementById("buildVersion");
const saveStateButton = document.getElementById("saveState");
const loadStateButton = document.getElementById("loadState");
const downloadStateButton = document.getElementById("downloadState");
const uploadStateButton = document.getElementById("uploadState");
const stateFileInput = document.getElementById("stateFile");

const API_BASE = "http://127.0.0.1:8080";

const TARGET_FPS = 60;
const FRAME_MS = 1000 / TARGET_FPS;
const AUDIO_SAMPLE_RATE = 48000;
const AUDIO_SAMPLES_PER_FRAME = Math.ceil(AUDIO_SAMPLE_RATE / TARGET_FPS); // ~800

const BTN_MAP = {
  up:    1 << 0,
  down:  1 << 1,
  left:  1 << 2,
  right: 1 << 3,
  b:     1 << 4,
  c:     1 << 5,
  a:     1 << 6,
  start: 1 << 7,
};

const pressed = new Set();
const touchPressed = new Set();  // buttons held via on-screen pad

let previewRunning = false;
let rafId = null;
let lastTs = 0;
let accumulator = 0;
let frameInFlight = false;
let lastButtons = 0;
let renderedFrames = 0;

// Audio state
let audioCtx = null;
let audioEnabled = false;
let audioNextTime = 0;
let savedStateData = null;

function triggerDownload(bytes, filename, mimeType = "application/octet-stream") {
  const blob = new Blob([bytes], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function saveStateFromApi() {
  const data = await request(`${API_BASE}/api/v1/emulator/save-state`, "GET");
  if (!data?.ok || !data?.state) {
    throw new Error("state save failed");
  }
  savedStateData = new Uint8Array(data.state);
  loadStateButton.disabled = false;
  return savedStateData;
}

async function loadStateToApi(bytes) {
  await request(`${API_BASE}/api/v1/emulator/load-state`, "POST", { data: Array.from(bytes) });
  savedStateData = new Uint8Array(bytes);
  loadStateButton.disabled = false;
  await refreshFrame();
}

function isEditableTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
}

function setStatus(text) {
  statusEl.textContent = `status: ${text}`;
}

function showJson(data) {
  out.textContent = JSON.stringify(data, null, 2);
}

function parseAddress(text) {
  const s = String(text ?? "").trim();
  if (!s) return null;
  if (/^0x[0-9a-f]+$/i.test(s)) {
    return Number.parseInt(s, 16) >>> 0;
  }
  if (/^[0-9]+$/.test(s)) {
    return Number.parseInt(s, 10) >>> 0;
  }
  return null;
}

async function request(url, method = "GET", body = null) {
  return requestEx(url, method, body, { quiet: false });
}

async function requestEx(url, method = "GET", body = null, options = { quiet: false }) {
  try {
    if (!options.quiet) {
      setStatus(`${method} ${url} ...`);
    }
    const response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const json = await response.json();
    if (!options.quiet) {
      setStatus(`${method} ${url} -> ${response.status}`);
    }
    return json;
  } catch (error) {
    if (!options.quiet) {
      setStatus(`${method} ${url} failed: ${error}`);
    }
    throw error;
  }
}

function drawFrame(pixelsArgb) {
  const dst = frameImage.data;
  const len = Math.min(pixelsArgb.length, canvas.width * canvas.height);
  for (let i = 0; i < len; i++) {
    const c = pixelsArgb[i] >>> 0;
    const o = i * 4;
    dst[o + 0] = (c >> 16) & 0xff;
    dst[o + 1] = (c >> 8) & 0xff;
    dst[o + 2] = c & 0xff;
    dst[o + 3] = (c >> 24) & 0xff;
  }
  ctx.putImageData(frameImage, 0, 0);
}

function initAudio() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    sampleRate: AUDIO_SAMPLE_RATE,
  });
  audioNextTime = 0;
}

function toggleAudio() {
  if (!audioCtx) {
    initAudio();
  }
  audioEnabled = !audioEnabled;
  if (audioEnabled) {
    audioCtx.resume();
    audioNextTime = 0;
  }
  const btn = document.getElementById("toggleAudio");
  if (btn) {
    btn.textContent = audioEnabled ? "Mute" : "Unmute";
  }
}

async function fetchAndPlayAudio() {
  if (!audioEnabled || !audioCtx) return;
  try {
    const data = await requestEx(
      `${API_BASE}/api/v1/audio/samples?frames=${AUDIO_SAMPLES_PER_FRAME * 2}`,
      "GET",
      null,
      { quiet: true }
    );
    if (!data?.samples || data.samples.length === 0) return;

    const stereoSamples = data.samples;
    const numFrames = stereoSamples.length / 2;
    const buffer = audioCtx.createBuffer(2, numFrames, AUDIO_SAMPLE_RATE);
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);
    for (let i = 0; i < numFrames; i++) {
      left[i] = stereoSamples[i * 2];
      right[i] = stereoSamples[i * 2 + 1];
    }

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    if (audioNextTime < now) {
      audioNextTime = now;
    }
    source.start(audioNextTime);
    audioNextTime += buffer.duration;
  } catch {
    // Silently ignore audio fetch errors
  }
}

async function refreshFrame() {
  const frame = await requestEx(`${API_BASE}/api/v1/video/frame`, "GET", null, {
    quiet: true,
  });
  if (frame?.pixels_argb) {
    drawFrame(frame.pixels_argb);
  }
}

function computeButtons() {
  let buttons = 0;
  if (pressed.has("ArrowUp") || pressed.has("KeyW") || touchPressed.has("up"))
    buttons |= BTN_MAP.up;
  if (pressed.has("ArrowDown") || pressed.has("KeyS") || touchPressed.has("down"))
    buttons |= BTN_MAP.down;
  if (pressed.has("ArrowLeft") || pressed.has("KeyA") || touchPressed.has("left"))
    buttons |= BTN_MAP.left;
  if (pressed.has("ArrowRight") || pressed.has("KeyD") || touchPressed.has("right"))
    buttons |= BTN_MAP.right;
  if (pressed.has("KeyJ") || touchPressed.has("b")) buttons |= BTN_MAP.b;
  if (pressed.has("KeyK") || touchPressed.has("c")) buttons |= BTN_MAP.c;
  if (pressed.has("KeyU") || touchPressed.has("a")) buttons |= BTN_MAP.a;
  if (pressed.has("Enter") || touchPressed.has("start")) buttons |= BTN_MAP.start;
  return buttons;
}

async function pushControllerState(force = false) {
  const buttons = computeButtons();
  if (!force && buttons === lastButtons) {
    return;
  }
  lastButtons = buttons;
  await requestEx(
    `${API_BASE}/api/v1/input/controller`,
    "POST",
    { player: 1, buttons },
    { quiet: true }
  );
}

async function advanceOneVideoFrame() {
  if (frameInFlight) {
    return;
  }
  frameInFlight = true;
  try {
    await pushControllerState();
    await requestEx(`${API_BASE}/api/v1/emulator/step`, "POST", { frames: 1 }, { quiet: true });
    await refreshFrame();
    await fetchAndPlayAudio();
    renderedFrames += 1;
  } finally {
    frameInFlight = false;
  }
}

async function previewTick(ts) {
  if (!previewRunning) {
    return;
  }

  if (!lastTs) {
    lastTs = ts;
  }
  const delta = ts - lastTs;
  lastTs = ts;
  accumulator += delta;

  while (accumulator >= FRAME_MS) {
    accumulator -= FRAME_MS;
    await advanceOneVideoFrame();
  }

  setStatus(`preview running @${TARGET_FPS}fps target, rendered=${renderedFrames}`);
  rafId = requestAnimationFrame(previewTick);
}

async function runOneFrameStep(frames = 1) {
  await pushControllerState(true);
  await request(`${API_BASE}/api/v1/emulator/step`, "POST", { frames });
  const [cpu, rom, frame] = await Promise.all([
    request(`${API_BASE}/api/v1/cpu/state`, "GET"),
    request(`${API_BASE}/api/v1/rom/info`, "GET"),
    requestEx(`${API_BASE}/api/v1/video/frame`, "GET", null, { quiet: true }),
  ]);
  if (frame?.pixels_argb) {
    drawFrame(frame.pixels_argb);
  }
  showJson({ cpu, rom });
}

document.getElementById("reset").addEventListener("click", async () => {
  try {
    const data = await request(`${API_BASE}/api/v1/emulator/reset`, "POST");
    await refreshFrame();
    showJson(data);
  } catch {
  }
});

document.getElementById("step").addEventListener("click", async () => {
  try {
    await runOneFrameStep(1);
  } catch {
  }
});

document.getElementById("step10").addEventListener("click", async () => {
  try {
    await runOneFrameStep(10);
  } catch {
  }
});

const setBreakpointButton = document.getElementById("setBreakpoint");
if (setBreakpointButton) {
  setBreakpointButton.addEventListener("click", async () => {
    const bpInput = document.getElementById("breakpointAddr");
    const address = parseAddress(bpInput?.value);
    if (address === null) {
      setStatus("invalid breakpoint address");
      return;
    }
    try {
      const data = await request(`${API_BASE}/api/v1/emulator/breakpoint`, "POST", { address });
      showJson(data);
    } catch {
    }
  });
}

const stepInstructionButton = document.getElementById("stepInstruction");
if (stepInstructionButton) {
  stepInstructionButton.addEventListener("click", async () => {
    try {
      const data = await request(`${API_BASE}/api/v1/emulator/step-instruction`, "POST");
      const [cpu, trace] = await Promise.all([
        request(`${API_BASE}/api/v1/cpu/state`, "GET"),
        request(`${API_BASE}/api/v1/cpu/trace`, "GET"),
      ]);
      await refreshFrame();
      showJson({ step_instruction: data, cpu, trace });
    } catch {
    }
  });
}

const resumeButton = document.getElementById("resume");
if (resumeButton) {
  resumeButton.addEventListener("click", async () => {
    try {
      const data = await request(`${API_BASE}/api/v1/emulator/resume`, "POST");
      showJson(data);
    } catch {
    }
  });
}

const registersButton = document.getElementById("registers");
if (registersButton) {
  registersButton.addEventListener("click", async () => {
    try {
      const cpu = await request(`${API_BASE}/api/v1/cpu/state`, "GET");
      showJson({ registers: cpu?.cpu?.m68k ?? cpu?.cpu ?? cpu });
    } catch {
    }
  });
}

const traceButton = document.getElementById("trace");
if (traceButton) {
  traceButton.addEventListener("click", async () => {
    try {
      const trace = await request(`${API_BASE}/api/v1/cpu/trace`, "GET");
      showJson(trace);
    } catch {
    }
  });
}

document.getElementById("loadRomPath").addEventListener("click", async () => {
  try {
    const payload = { path: romPathInput.value };
    const data = await request(`${API_BASE}/api/v1/emulator/load-rom-path`, "POST", payload);
    savedStateData = null;
    loadStateButton.disabled = true;
    await refreshFrame();
    showJson(data);
  } catch {
  }
});

document.getElementById("loadRomFile").addEventListener("click", async () => {
  const fileInput = document.getElementById("romFile");
  const file = fileInput.files?.[0];
  if (!file) { setStatus("select a ROM file first"); return; }
  try {
    setStatus(`uploading ${file.name}...`);
    const arrayBuffer = await file.arrayBuffer();
    const bytes = Array.from(new Uint8Array(arrayBuffer));
    const data = await request(`${API_BASE}/api/v1/emulator/load-rom`, "POST", { rom: bytes });
    savedStateData = null;
    loadStateButton.disabled = true;
    await refreshFrame();
    showJson(data);
  } catch {
  }
});

document.getElementById("romInfo").addEventListener("click", async () => {
  try {
    const data = await request(`${API_BASE}/api/v1/rom/info`, "GET");
    showJson(data);
  } catch {
  }
});

document.getElementById("toggleApiLog").addEventListener("click", async () => {
  try {
    const current = await request(`${API_BASE}/api/v1/logging`, "GET");
    const next = await request(`${API_BASE}/api/v1/logging`, "POST", {
      enabled: !current.enabled,
    });
    showJson({ logging: next });
  } catch {
  }
});

document.getElementById("runPreview").addEventListener("click", async () => {
  if (previewRunning) {
    return;
  }
  previewRunning = true;
  accumulator = 0;
  lastTs = 0;
  renderedFrames = 0;
  await pushControllerState(true);
  rafId = requestAnimationFrame(previewTick);
  setStatus("preview running");
});

document.getElementById("stopPreview").addEventListener("click", () => {
  previewRunning = false;
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  setStatus("preview stopped");
});

document.getElementById("toggleAudio").addEventListener("click", () => {
  toggleAudio();
});

saveStateButton.addEventListener("click", async () => {
  try {
    const bytes = await saveStateFromApi();
    setStatus(`state saved (${bytes.length} bytes)`);
  } catch (error) {
    setStatus(`state save failed: ${error}`);
  }
});

loadStateButton.addEventListener("click", async () => {
  if (!savedStateData) {
    setStatus("no saved state in memory");
    return;
  }
  try {
    await loadStateToApi(savedStateData);
    setStatus("state loaded");
  } catch (error) {
    setStatus(`state load failed: ${error}`);
  }
});

downloadStateButton.addEventListener("click", async () => {
  try {
    const bytes = await saveStateFromApi();
    triggerDownload(bytes, "api-save.mdstate", "application/octet-stream");
    setStatus(`state downloaded (${bytes.length} bytes)`);
  } catch (error) {
    setStatus(`state download failed: ${error}`);
  }
});

uploadStateButton.addEventListener("click", async () => {
  const file = stateFileInput.files?.[0];
  if (!file) {
    setStatus("select a state file first");
    return;
  }
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    await loadStateToApi(bytes);
    setStatus(`state uploaded: ${file.name}`);
  } catch (error) {
    setStatus(`state upload failed: ${error}`);
  }
});

window.addEventListener("keydown", async (event) => {
  if (isEditableTarget(event.target)) {
    return;
  }
  if (event.repeat) {
    return;
  }
  pressed.add(event.code);
  event.preventDefault();
  try {
    await pushControllerState();
  } catch {
  }
});

window.addEventListener("keyup", async (event) => {
  if (isEditableTarget(event.target)) {
    return;
  }
  pressed.delete(event.code);
  event.preventDefault();
  try {
    await pushControllerState();
  } catch {
  }
});

window.addEventListener("blur", async () => {
  pressed.clear();
  try {
    await pushControllerState(true);
  } catch {
  }
});

refreshFrame().catch((error) => {
  setStatus(`initial fetch failed: ${error}`);
});

// On-screen controller buttons (mouse/touch)
document.querySelectorAll("[data-btn]").forEach((btn) => {
  const name = btn.dataset.btn;
  const down = () => { touchPressed.add(name); pushControllerState().catch(() => {}); };
  const up = () => { touchPressed.delete(name); pushControllerState().catch(() => {}); };
  btn.addEventListener("mousedown", down);
  btn.addEventListener("mouseup", up);
  btn.addEventListener("mouseleave", up);
  btn.addEventListener("touchstart", (e) => { e.preventDefault(); down(); });
  btn.addEventListener("touchend", (e) => { e.preventDefault(); up(); });
  btn.addEventListener("touchcancel", (e) => { e.preventDefault(); up(); });
});

// Fetch and display build version
requestEx(`${API_BASE}/api/v1/version`, "GET", null, { quiet: true })
  .then((data) => {
    if (buildVersionEl && data?.version) {
      buildVersionEl.textContent = `build: ${data.version} (API)`;
    }
  })
  .catch(() => {
    if (buildVersionEl) buildVersionEl.textContent = "build: API unreachable";
  });
