'use strict';

const path = require('path');

function findMacBundleDir(exePath) {
  let current = path.resolve(path.dirname(exePath));
  while (current && current !== path.dirname(current)) {
    if (current.toLowerCase().endsWith('.app')) {
      return current;
    }
    current = path.dirname(current);
  }
  return null;
}

function resolvePortableDataDir({ app, dirname = __dirname, platform = process.platform }) {
  if (!app?.isPackaged) {
    return path.join(dirname, 'data');
  }

  const exePath = app.getPath('exe');
  if (platform === 'darwin') {
    const bundleDir = findMacBundleDir(exePath);
    if (bundleDir) {
      return path.join(path.dirname(bundleDir), 'data');
    }
  }
  return path.join(path.dirname(exePath), 'data');
}

function applyPortableMode(app, options = {}) {
  const dataDir = resolvePortableDataDir({
    app,
    dirname: options.dirname || __dirname,
    platform: options.platform || process.platform,
  });
  app.setPath('userData', dataDir);
  app.setPath('logs', path.join(dataDir, 'logs'));
  return dataDir;
}

module.exports = {
  applyPortableMode,
  findMacBundleDir,
  resolvePortableDataDir,
};
