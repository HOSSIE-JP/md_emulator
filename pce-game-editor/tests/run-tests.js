'use strict';

const path = require('node:path');
const { loadAppConfig } = require('../../game-editor-common');

loadAppConfig(require('../app.config'));

[
  'pce-app-separation.test.js',
  'pce-asset-manager.test.js',
  'pce-setup-manager.test.js',
].forEach((file) => require(path.join(__dirname, file)));
