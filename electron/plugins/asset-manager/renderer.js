export function activatePlugin({ plugin, root, logger, registerCapability }) {
  if (root) {
    root.dataset.pluginOwner = plugin.id;
  }

  registerCapability('asset-manager', {
    pluginId: plugin.id,
    root,
  });

  logger.debug('asset-manager renderer activated');
  return {
    deactivate() {
      if (root?.dataset.pluginOwner === plugin.id) {
        delete root.dataset.pluginOwner;
      }
    },
  };
}
