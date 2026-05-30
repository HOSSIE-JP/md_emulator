'use strict';

const path = require('path');

module.exports = {
  appRoot: __dirname,
  appId: 'jp.co.geroneko.md.editor.desktop',
  productName: 'MegaDriveGameEditor',
  displayName: 'MD Game Editor',
  defaultCoreId: 'mega-drive',
  allowedCoreIds: ['mega-drive'],
  pluginsRoot: path.join(__dirname, 'plugins'),
  templatesRoot: path.join(__dirname, 'template'),
  projectsRootName: 'projects',
  toolsRootName: 'tools',
};
