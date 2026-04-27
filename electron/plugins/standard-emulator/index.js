'use strict';

/**
 * 標準エミュレーター（WASM）プラグイン
 * TestPlay 実行時のフックを提供します。
 * 実際の起動処理は main.js の window:openTestPlay が担当します。
 */

/**
 * @param {{ romPath: string }} payload
 */
async function onTestPlay(payload) {
  // main.js のデフォルト TestPlay 処理（WASM ウィンドウ起動）に委譲
  // このフックは将来の拡張用（ログ出力・パラメータ変更など）のために用意されています
  return { ok: true, handled: false };
}

module.exports = { onTestPlay };
