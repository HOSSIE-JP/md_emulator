export function createPluginRuntime() {
  return {
    active: new Map(),
    activations: new Map(),
    capabilities: new Map(),
    capabilityWaiters: new Map(),
    eventTarget: new EventTarget(),
    hostRoots: [],
    styleLinks: [],
  };
}

function enabledFilter(isEnabled) {
  return (entry) => (typeof isEnabled === 'function' ? isEnabled(entry.pluginId) : true);
}

export function registerRuntimeCapability(runtime, plugin, name, implementation = {}) {
  const capability = String(name || '').trim();
  if (!capability) return;
  const provider = { pluginId: plugin.id, implementation };
  runtime.capabilities.set(capability, [...(runtime.capabilities.get(capability) || []), provider]);
  for (const resolve of runtime.capabilityWaiters.get(capability) || []) resolve(implementation);
  runtime.capabilityWaiters.delete(capability);
  runtime.eventTarget.dispatchEvent(new CustomEvent('capability:registered', {
    detail: { capability, pluginId: plugin.id, implementation },
  }));
}

export function getRuntimeCapability(runtime, name, isEnabled) {
  return (runtime.capabilities.get(name) || []).find(enabledFilter(isEnabled))?.implementation || null;
}

export function getRuntimeCapabilities(runtime, name, isEnabled) {
  return (runtime.capabilities.get(name) || [])
    .filter(enabledFilter(isEnabled))
    .map((entry) => entry.implementation)
    .sort((left, right) => Number(right?.priority || 0) - Number(left?.priority || 0));
}

export function listRuntimeCapabilities(runtime, isEnabled) {
  return Array.from(runtime.capabilities, ([name, entries]) => ({
    name,
    providers: entries.filter(enabledFilter(isEnabled)).map((entry) => entry.pluginId),
  })).filter((entry) => entry.providers.length > 0);
}

export function waitForRuntimeCapability(runtime, name, timeoutMs, getCurrent) {
  const capability = String(name || '').trim();
  if (!capability) return Promise.resolve(null);
  const current = getCurrent?.(capability);
  if (current) return Promise.resolve(current);
  return new Promise((resolve) => {
    let done;
    const timer = window.setTimeout(() => done(null), Math.max(0, Number(timeoutMs) || 0));
    done = (value) => {
      window.clearTimeout(timer);
      const pending = (runtime.capabilityWaiters.get(capability) || []).filter((item) => item !== done);
      if (pending.length) runtime.capabilityWaiters.set(capability, pending);
      else runtime.capabilityWaiters.delete(capability);
      resolve(value || null);
    };
    runtime.capabilityWaiters.set(capability, [...(runtime.capabilityWaiters.get(capability) || []), done]);
  });
}

export function clearPluginRuntime(runtime, onDeactivateError) {
  for (const activation of runtime.activations.values()) {
    try {
      activation?.deactivate?.();
    } catch (err) {
      onDeactivateError?.(err);
    }
  }
  runtime.activations.clear();
  runtime.capabilities.clear();
  for (const waiters of runtime.capabilityWaiters.values()) waiters.forEach((resolve) => resolve(null));
  runtime.capabilityWaiters.clear();
  runtime.styleLinks.splice(0).forEach((link) => link.remove());
  runtime.hostRoots.splice(0).forEach((root) => root.remove());
  runtime.eventTarget = new EventTarget();
}
