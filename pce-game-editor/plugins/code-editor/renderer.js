export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  root.innerHTML = `
    <div class="code-plugin-layout">
      <aside class="tree-panel">
        <div class="pane-header">
          <h2>Project Files</h2>
          <button class="mini-btn" data-action="refresh" type="button">更新</button>
        </div>
        <div class="tree-list" data-role="tree"></div>
      </aside>
      <section class="editor-panel">
        <div class="editor-toolbar">
          <div class="editor-filename" data-role="filename">ファイルを選択してください</div>
          <button class="mini-btn" data-action="save" type="button" disabled>保存</button>
        </div>
        <textarea class="code-textarea" data-role="editor" spellcheck="false" disabled></textarea>
      </section>
    </div>
  `;

  const tree = root.querySelector('[data-role="tree"]');
  const editor = root.querySelector('[data-role="editor"]');
  const filename = root.querySelector('[data-role="filename"]');
  const btnSave = root.querySelector('[data-action="save"]');
  const btnRefresh = root.querySelector('[data-action="refresh"]');
  let selectedPath = '';
  let dirty = false;

  function flatten(entries, depth = 0) {
    return entries.flatMap((entry) => {
      if (entry.type === 'directory') {
        return [
          { ...entry, depth },
          ...flatten(entry.children || [], depth + 1),
        ];
      }
      return [{ ...entry, depth }];
    });
  }

  async function loadTree() {
    const result = await api.electronAPI.listCodeTree({ path: '' });
    if (!result.ok) {
      tree.innerHTML = `<p class="meta">${result.error}</p>`;
      return;
    }
    tree.innerHTML = flatten(result.entries || []).map((entry) => {
      const isFile = entry.type === 'file';
      const indent = Math.min(72, 8 + entry.depth * 14);
      return `
        <button class="tree-item ${isFile ? 'file' : 'dir'} ${entry.path === selectedPath ? 'active' : ''}"
          data-path="${entry.path}"
          data-type="${entry.type}"
          style="padding-left:${indent}px"
          type="button">${isFile ? '□' : '▸'} ${entry.name}</button>
      `;
    }).join('');
    tree.querySelectorAll('.tree-item.file').forEach((button) => {
      button.addEventListener('click', () => openFile(button.dataset.path));
    });
  }

  async function openFile(filePath) {
    if (dirty && !confirm('未保存の変更を破棄しますか？')) return;
    const result = await api.electronAPI.readCodeFile({ path: filePath });
    if (!result.ok) {
      logger.error(result.error);
      return;
    }
    selectedPath = filePath;
    dirty = false;
    filename.textContent = filePath;
    editor.value = result.content || '';
    editor.disabled = false;
    btnSave.disabled = false;
    await loadTree();
  }

  async function saveFile() {
    if (!selectedPath) return;
    const result = await api.electronAPI.writeCodeFile({ path: selectedPath, content: editor.value });
    if (!result.ok) {
      logger.error(result.error);
      return;
    }
    dirty = false;
    logger.info(`保存しました: ${selectedPath}`);
  }

  editor.addEventListener('input', () => { dirty = true; });
  btnSave.addEventListener('click', saveFile);
  btnRefresh.addEventListener('click', loadTree);

  registerCapability('code-editor', { pluginId: plugin.id, root, reload: loadTree });
  void loadTree();
  return { deactivate() {} };
}
