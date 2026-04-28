export function activatePlugin({ api, logger, registerCapability }) {
  registerCapability('audio-convert-ui', {
    openAudioConvertModal: api.openAudioConvertModal,
  });

  logger.debug('audio-converter renderer activated');
}
