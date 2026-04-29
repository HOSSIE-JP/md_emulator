import {
  AUDIO_EXTS,
  IMAGE_EXTS,
  allowedTypesForExtension,
  defaultSubDirForType,
  inferTypeFromExtension,
  normalizeSymbolName,
} from './asset-utils.mjs';

const DEFAULT_TYPES = ['PALETTE', 'IMAGE', 'BITMAP', 'SPRITE', 'XGM', 'XGM2', 'WAV', 'MAP', 'TILEMAP', 'TILESET'];

export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  if (root) {
    root.dataset.pluginOwner = plugin.id;
  }

  registerCapability('asset-manager', {
    pluginId: plugin.id,
    root,
  });

  registerCapability('asset-type-provider', {
    priority: 0,
    getTypeInfo(file = {}) {
      const ext = String(file.ext || '').toLowerCase();
      const initialType = inferTypeFromExtension(ext);
      const fileName = String(file.fileName || '');
      const isAudioInput = AUDIO_EXTS.includes(ext);
      return {
        initialType,
        allowedTypes: allowedTypesForExtension(ext, DEFAULT_TYPES),
        defaultSubdir: defaultSubDirForType(initialType),
        defaultSymbol: normalizeSymbolName(fileName),
        suggestedFileName: initialType === 'WAV' && isAudioInput
          ? `${fileName.replace(/\.[^.]+$/, '')}.wav`
          : fileName,
        isImageInput: IMAGE_EXTS.includes(ext),
        isAudioInput,
      };
    },
  });

  registerCapability('image-import-pipeline', {
    priority: 0,
    async convertToIndexed16({ sourcePath, targetSize } = {}) {
      const resizeCapability = api.capabilities.get('image-resize');
      if (!resizeCapability?.openResizeModal) {
        return {
          canceled: true,
          convertedDataUrl: '',
          originalDataUrl: '',
          warning: '画像リサイズコンバータープラグインが無効または未インストールです',
        };
      }

      const read = await api.electronAPI.readFileAsDataUrl(sourcePath);
      if (!read?.ok || !read.dataUrl) {
        return { canceled: true, convertedDataUrl: '', originalDataUrl: '', warning: read?.error || '' };
      }

      const img = new Image();
      img.src = read.dataUrl;
      await img.decode();

      let warning = '';
      let workingDataUrl = read.dataUrl;
      const resizeResult = await resizeCapability.openResizeModal(read.dataUrl, img.naturalWidth, img.naturalHeight, {
        targetSize: targetSize || null,
      });
      if (!resizeResult.ok) {
        return { canceled: true, convertedDataUrl: '', originalDataUrl: read.dataUrl, warning: 'リサイズ/クリッピングをキャンセルしました' };
      }
      if (resizeResult.dataUrl && resizeResult.dataUrl !== read.dataUrl) {
        workingDataUrl = resizeResult.dataUrl;
        warning = 'リサイズ/クリッピングを適用しました';
      }

      const workImg = new Image();
      workImg.src = workingDataUrl;
      await workImg.decode();

      const canvas = document.createElement('canvas');
      canvas.width = workImg.width;
      canvas.height = workImg.height;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(workImg, 0, 0);
      const imageData = ctx.getImageData(0, 0, workImg.width, workImg.height);
      const quantizeCapability = api.capabilities.get('image-quantize');
      const countColors = quantizeCapability?.countUniqueColors || api.countUniqueColors;
      const unique = countColors(imageData);

      if (unique <= 16) {
        let savedDataUrl = '';
        if (workingDataUrl !== read.dataUrl) {
          try {
            const encodeIndexed = quantizeCapability?.imageDataToIndexedPng || api.imageDataToIndexedPng;
            savedDataUrl = await encodeIndexed(imageData);
          } catch (err) {
            logger.warn(`indexed PNG 変換失敗、RGBA PNG にフォールバック: ${String(err?.message || err)}`);
            savedDataUrl = workingDataUrl;
          }
        }
        return {
          canceled: false,
          convertedDataUrl: savedDataUrl,
          originalDataUrl: read.dataUrl,
          warning,
        };
      }

      if (!quantizeCapability?.openQuantizeModal) {
        return {
          canceled: true,
          convertedDataUrl: '',
          originalDataUrl: read.dataUrl,
          warning: '画像減色コンバータープラグインが無効または未インストールです',
        };
      }

      const quantized = await quantizeCapability.openQuantizeModal(workingDataUrl, { sourcePath });
      if (!quantized.ok) {
        return {
          canceled: true,
          convertedDataUrl: '',
          originalDataUrl: read.dataUrl,
          warning: '減色変換をキャンセルしました',
        };
      }

      return {
        canceled: false,
        convertedDataUrl: quantized.dataUrl,
        originalDataUrl: read.dataUrl,
        warning: `${warning ? `${warning} / ` : ''}減色変換を適用: ${unique} colors -> 16 colors`,
      };
    },
  });

  registerCapability('asset-import-handler', {
    priority: 0,
    canHandle() {
      return true;
    },
    getDefaultTypeInfo(file) {
      return api.capabilities.get('asset-type-provider')?.getTypeInfo(file) || null;
    },
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
