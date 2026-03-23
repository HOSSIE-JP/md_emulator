const out = document.getElementById("out");
const romPathInput = document.getElementById("romPath");
const statusEl = document.getElementById("status");
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const frameImage = ctx.createImageData(canvas.width, canvas.height);

const TARGET_FPS = 60;
const FRAME_MS = 1000 / TARGET_FPS;

const BTN_UP = 1 << 0;
const BTN_DOWN = 1 << 1;
const BTN_LEFT = 1 << 2;
const BTN_RIGHT = 1 << 3;
const BTN_B = 1 << 4;
const BTN_C = 1 << 5;
const BTN_A = 1 << 6;
const BTN_START = 1 << 7;

const pressed = new Set();

let previewRunning = false;
let rafId = null;
let lastTs = 0;
let accumulator = 0;
let frameInFlight = false;
let lastButtons = 0;
let renderedFrames = 0;

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

async function refreshFrame() {
  const frame = await requestEx("http://127.0.0.1:8080/api/v1/video/frame", "GET", null, {
    quiet: true,
  });
  if (frame?.pixels_argb) {
    drawFrame(frame.pixels_argb);
  }
}

function computeButtons() {
  let buttons = 0;
  if (pressed.has("ArrowUp") || pressed.has("KeyW")) {
    buttons |= BTN_UP;
  }
  if (pressed.has("ArrowDown") || pressed.has("KeyS")) {
    buttons |= BTN_DOWN;
  }
  if (pressed.has("ArrowLeft") || pressed.has("KeyA")) {
    buttons |= BTN_LEFT;
  }
  if (pressed.has("ArrowRight") || pressed.has("KeyD")) {
    buttons |= BTN_RIGHT;
  }
  if (pressed.has("KeyJ")) {
    buttons |= BTN_B;
  }
  if (pressed.has("KeyK")) {
    buttons |= BTN_C;
  }
  if (pressed.has("KeyU")) {
    buttons |= BTN_A;
  }
  if (pressed.has("Enter")) {
    buttons |= BTN_START;
  }
  return buttons;
}

async function pushControllerState(force = false) {
  const buttons = computeButtons();
  if (!force && buttons === lastButtons) {
    return;
  }
  lastButtons = buttons;
  await requestEx(
    "http://127.0.0.1:8080/api/v1/input/controller",
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
    await requestEx("http://127.0.0.1:8080/api/v1/emulator/step", "POST", { frames: 1 }, { quiet: true });
    await refreshFrame();
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
  await request("http://127.0.0.1:8080/api/v1/emulator/step", "POST", { frames });
  const [cpu, rom, frame] = await Promise.all([
    request("http://127.0.0.1:8080/api/v1/cpu/state", "GET"),
    request("http://127.0.0.1:8080/api/v1/rom/info", "GET"),
    requestEx("http://127.0.0.1:8080/api/v1/video/frame", "GET", null, { quiet: true }),
  ]);
  if (frame?.pixels_argb) {
    drawFrame(frame.pixels_argb);
  }
  showJson({ cpu, rom });
}

document.getElementById("reset").addEventListener("click", async () => {
  try {
    const data = await request("http://127.0.0.1:8080/api/v1/emulator/reset", "POST");
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

document.getElementById("loadRomPath").addEventListener("click", async () => {
  try {
    const payload = { path: romPathInput.value };
    const data = await request("http://127.0.0.1:8080/api/v1/emulator/load-rom-path", "POST", payload);
    await refreshFrame();
    showJson(data);
  } catch {
  }
});

document.getElementById("romInfo").addEventListener("click", async () => {
  try {
    const data = await request("http://127.0.0.1:8080/api/v1/rom/info", "GET");
    showJson(data);
  } catch {
  }
});

document.getElementById("toggleApiLog").addEventListener("click", async () => {
  try {
    const current = await request("http://127.0.0.1:8080/api/v1/logging", "GET");
    const next = await request("http://127.0.0.1:8080/api/v1/logging", "POST", {
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

showJson({
  keyboard: {
    up: ["ArrowUp", "W"],
    down: ["ArrowDown", "S"],
    left: ["ArrowLeft", "A"],
    right: ["ArrowRight", "D"],
    b: ["J"],
    c: ["K"],
    a: ["U"],
    start: ["Enter"],
  },
});
