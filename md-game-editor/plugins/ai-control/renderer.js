export function activatePlugin({ root, api, registerCapability }) {
  root.innerHTML = `
    <div class="ai-control-page">
      <div class="ai-control-header">
        <div>
          <h2>AI Control</h2>
          <p>localhost REST / MCP bridge を起動して、外部AIツールからプロジェクト作成、アセット登録、ビルドを操作できます。</p>
        </div>
        <div class="ai-control-status" data-status>確認中...</div>
      </div>
      <div class="ai-control-controls">
        <label>
          Port
          <input data-port type="number" min="1024" max="65535" value="17777" />
        </label>
        <button data-start>Start</button>
        <button data-stop>Stop</button>
        <button data-refresh>Refresh</button>
      </div>
      <div class="ai-control-info">
        <div data-base-url></div>
        <label>
          Token
          <input data-token readonly type="text" value="" />
        </label>
        <div data-mcp></div>
      </div>
      <div class="ai-control-grid">
        <section>
          <h3>Tools</h3>
          <ul data-tools></ul>
        </section>
        <section>
          <h3>Log</h3>
          <pre data-log></pre>
        </section>
      </div>
    </div>
  `;

  const ui = {
    port: root.querySelector('[data-port]'),
    start: root.querySelector('[data-start]'),
    stop: root.querySelector('[data-stop]'),
    refresh: root.querySelector('[data-refresh]'),
    status: root.querySelector('[data-status]'),
    baseUrl: root.querySelector('[data-base-url]'),
    token: root.querySelector('[data-token]'),
    mcp: root.querySelector('[data-mcp]'),
    tools: root.querySelector('[data-tools]'),
    log: root.querySelector('[data-log]'),
  };

  function appendLog(entry) {
    const line = typeof entry === 'string'
      ? entry
      : `[${entry?.at || new Date().toISOString()}] ${entry?.level || 'info'} ${entry?.message || ''}`;
    ui.log.textContent = `${ui.log.textContent}\n${line}`.trim().slice(-12000);
    ui.log.scrollTop = ui.log.scrollHeight;
  }

  function renderStatus(state) {
    const running = Boolean(state?.running);
    ui.status.textContent = running ? `Running : ${state.port}` : 'Stopped';
    ui.status.dataset.running = running ? 'true' : 'false';
    ui.stop.disabled = !running;
    ui.baseUrl.textContent = running ? `REST: ${state.baseUrl}` : 'REST: stopped';
    ui.token.value = state?.token || '';
    ui.mcp.textContent = running
      ? `MCP endpoint: ${state.mcpEndpoint} / stdio sidecar: scripts/md-game-editor-mcp.js`
      : 'MCP: stopped';
    if (state?.port) ui.port.value = String(state.port);
    if (Array.isArray(state?.logs)) {
      ui.log.textContent = '';
      state.logs.forEach(appendLog);
    }
  }

  async function refresh() {
    const [state, tools] = await Promise.all([
      api.electronAPI.getAiControlStatus(),
      api.electronAPI.listAiControlTools(),
    ]);
    renderStatus(state || {});
    ui.tools.innerHTML = '';
    (tools?.tools || []).forEach((tool) => {
      const li = document.createElement('li');
      li.textContent = `${tool.name}${tool.mutates ? ' *' : ''}`;
      ui.tools.appendChild(li);
    });
  }

  ui.start.addEventListener('click', async () => {
    const port = Number(ui.port.value) || 17777;
    const result = await api.electronAPI.startAiControlServer({ port });
    appendLog(`start: ${JSON.stringify({ ok: result?.ok, port: result?.port, fallbackUsed: result?.fallbackUsed })}`);
    await refresh();
  });

  ui.stop.addEventListener('click', async () => {
    const result = await api.electronAPI.stopAiControlServer();
    appendLog(`stop: ${JSON.stringify(result)}`);
    await refresh();
  });

  ui.refresh.addEventListener('click', refresh);
  api.electronAPI.onAiControlLog((entry) => appendLog(entry));

  registerCapability('ai-control', {
    refresh,
    start: (options = {}) => api.electronAPI.startAiControlServer(options),
    stop: () => api.electronAPI.stopAiControlServer(),
    status: () => api.electronAPI.getAiControlStatus(),
  });

  refresh().catch((err) => {
    ui.status.textContent = `確認失敗: ${err?.message || err}`;
  });

  return {
    deactivate() {
      root.innerHTML = '';
    },
  };
}
