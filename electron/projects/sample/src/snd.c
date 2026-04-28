/* ===================================================================
 * GERO Block - サウンド管理（XGM2 ドライバ使用）
 * XGM2 は XGM の後継ドライバで、以下の利点がある:
 *   - PCM 事前登録不要（直接再生）
 *   - 3 PCM チャンネル（13.3 KHz / 6.65 KHz）
 *   - 改善された DMA 競合保護
 *   - フェードイン/フェードアウト対応
 * =================================================================== */

#include "game.h"
#include "game_resources.h"

/* ===================================================================
 * 内部ヘルパー: SE ID → サンプルデータ解決
 * =================================================================== */

/**
 * SE ID に対応するサンプルデータとサイズを取得
 * XGM2 では PCM を直接再生するため、IDをサンプルポインタに変換する
 */
static bool getSEData(u8 se_id, const u8 **out_sample, u32 *out_len)
{
    const u8 *sample = NULL;
    u32 len = 0;

    switch (se_id)
    {
#ifdef RES_SE_BALL_HIT_PADDLE
        case SND_SE_BALL_HIT_PADDLE:
            sample = RES_SE_BALL_HIT_PADDLE;
            len = sizeof(RES_SE_BALL_HIT_PADDLE);
            break;
#endif
#ifdef RES_SE_BALL_HIT_WALL
        case SND_SE_BALL_HIT_WALL:
            sample = RES_SE_BALL_HIT_WALL;
            len = sizeof(RES_SE_BALL_HIT_WALL);
            break;
#endif
#ifdef RES_SE_BLOCK_BREAK
        case SND_SE_BLOCK_BREAK:
            sample = RES_SE_BLOCK_BREAK;
            len = sizeof(RES_SE_BLOCK_BREAK);
            break;
#endif
#ifdef RES_SE_BLOCK_HIT
        case SND_SE_BLOCK_HIT:
            sample = RES_SE_BLOCK_HIT;
            len = sizeof(RES_SE_BLOCK_HIT);
            break;
#endif
#ifdef RES_SE_POWERUP_APPEAR
        case SND_SE_POWERUP_APPEAR:
            sample = RES_SE_POWERUP_APPEAR;
            len = sizeof(RES_SE_POWERUP_APPEAR);
            break;
#endif
#ifdef RES_SE_POWERUP_GET
        case SND_SE_POWERUP_GET:
            sample = RES_SE_POWERUP_GET;
            len = sizeof(RES_SE_POWERUP_GET);
            break;
#endif
#ifdef RES_SE_BALL_LOSE
        case SND_SE_BALL_LOSE:
            sample = RES_SE_BALL_LOSE;
            len = sizeof(RES_SE_BALL_LOSE);
            break;
#endif
#ifdef RES_SE_GAME_OVER
        case SND_SE_GAME_OVER:
            sample = RES_SE_GAME_OVER;
            len = sizeof(RES_SE_GAME_OVER);
            break;
#endif
#ifdef RES_SE_STAGE_CLEAR
        case SND_SE_STAGE_CLEAR:
            sample = RES_SE_STAGE_CLEAR;
            len = sizeof(RES_SE_STAGE_CLEAR);
            break;
#endif
#ifdef RES_SE_GAME_START
        case SND_SE_GAME_START:
            sample = RES_SE_GAME_START;
            len = sizeof(RES_SE_GAME_START);
            break;
#endif
#ifdef RES_SE_PAUSE
        case SND_SE_PAUSE:
            sample = RES_SE_PAUSE;
            len = sizeof(RES_SE_PAUSE);
            break;
#endif
        default:
            break;
    }

    if (sample && len > 0)
    {
        *out_sample = sample;
        *out_len = len;
        return TRUE;
    }
    return FALSE;
}

/* ===================================================================
 * パブリック関数
 * =================================================================== */

/** サウンド初期化: XGM2 ドライバをロード */
void sndInit(void)
{
    Z80_loadDriver(Z80_DRIVER_XGM2, TRUE);
}

/** BGM ボリューム設定 (0-100)
 *  XGM2 (VGM) モード: FM/PSG 両方のボリュームを設定
 *  PCM (WAV) モード: ハードウェア制約によりランタイム調整不可 */
void sndSetBGMVolume(u8 volume)
{
    if (volume > 100) volume = 100;
#ifndef BGM_IS_PCM
    XGM2_setFMVolume(volume);
    XGM2_setPSGVolume(volume);
#endif
    (void)volume; /* PCMモードでは未使用: 警告抑制 */
}

/** BGM 再生開始 */
void sndPlayBGM(void)
{
#ifdef RES_BGM_0
    #ifdef BGM_IS_PCM
    /* WAV (PCM) BGM: チャンネル1でループ再生 (13.3 KHz) */
    XGM2_playPCMEx(RES_BGM_0, sizeof(RES_BGM_0), SOUND_PCM_CH1, 15, FALSE, TRUE);
    #else
    /* VGM (XGM2) BGM: XGM2ミュージックとして再生 */
    XGM2_play(RES_BGM_0);
    /* エディタで設定したBGMボリュームを適用 */
    sndSetBGMVolume(BGM_VOLUME);
    #endif
#endif
}

/** BGM 停止 */
void sndStopBGM(void)
{
#ifdef BGM_IS_PCM
    XGM2_stopPCM(SOUND_PCM_CH1);
#else
    XGM2_stop();
#endif
}

/** SE 再生
 *  XGM2 は PCM を直接再生するため、事前登録不要
 *  チャンネル2を使用（チャンネル1はBGMのPCMに使用される場合がある）
 *  チャンネル3はフォールバック用 */
void sndPlaySE(u8 se_id)
{
    const u8 *sample;
    u32 len;

    if (getSEData(se_id, &sample, &len))
        XGM2_playPCM(sample, len, SOUND_PCM_CH2);
}
