const base = 'http://127.0.0.1:8080';
const rom = '/Users/hossie/development/md_emulator/roms/darius.bin';
const btnC = 1 << 5;

async function req(method, path, payload) {
  const response = await fetch(base + path, {
    method,
    headers: payload ? { 'Content-Type': 'application/json' } : {},
    body: payload ? JSON.stringify(payload) : undefined,
  });
  return response.json();
}

async function step(frames) {
  await req('POST', '/api/v1/emulator/step', { frames });
}

async function setButtons(buttons) {
  await req('POST', '/api/v1/input/controller', { player: 1, buttons });
}

async function pulse(buttons, onFrames, offFrames, repeats) {
  for (let index = 0; index < repeats; index += 1) {
    await setButtons(buttons);
    await step(onFrames);
    await setButtons(0);
    await step(offFrames);
  }
}

async function main() {
  await req('POST', '/api/v1/emulator/reset', {});
  await req('POST', '/api/v1/emulator/load-rom-path', { path: rom });
  await step(240);
  await setButtons(btnC);
  await step(120);
  await setButtons(0);
  await step(30);
  await pulse(btnC, 10, 10, 20);
  await step(60);
  await step(600);

  const cpu = (await req('GET', '/api/v1/cpu/state')).cpu;
  const apu = await req('GET', '/api/v1/apu/state');
  console.log(JSON.stringify({
    z80: cpu.z80,
    z80_pc: cpu.z80_pc,
    z80_cycles: cpu.z80_cycles,
    apu: {
      regs_port0_2b: apu.regs_port0_2b,
      dac_enabled: apu.dac_enabled,
      dac_data: apu.dac_data,
      recent_non_dac: (apu.ym_write_log_recent_non_dac || []).slice(0, 12),
      recent_writes: (apu.ym_write_log_first100 || []).slice(0, 20),
      trace: (apu.z80_trace_ring || []).slice(-16),
    },
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});