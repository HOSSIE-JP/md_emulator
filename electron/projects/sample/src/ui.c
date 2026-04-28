/* ===================================================================
 * GERO Block - UI描画
 * Windowプレーンを使ったスコア・ライフ表示、
 * タイトル画面・ゲームオーバー画面
 * =================================================================== */

#include "game.h"

/* 文字列バッファ */
static char str_buf[16];

/* ===================================================================
 * 内部ヘルパー
 * =================================================================== */

/** Windowプレーン上のテキスト描画 (X座標はタイル単位)
 *  CPU転送を使用（XGMドライバ併用時のDMA_QUEUEタイミング問題を回避） */
static void drawWindowText(const char *text, u16 tile_x, u16 tile_y)
{
    VDP_drawTextEx(WINDOW, text, TILE_ATTR(PAL_SYSTEM, TRUE, FALSE, FALSE), tile_x, tile_y, CPU);
}

/** BG_A上のテキスト描画 */
static void drawBgText(const char *text, u16 tile_x, u16 tile_y)
{
    VDP_drawTextEx(BG_A, text, TILE_ATTR(PAL_SYSTEM, TRUE, FALSE, FALSE), tile_x, tile_y, CPU);
}

/* ===================================================================
 * パブリック関数
 * =================================================================== */

/** UI初期化 */
void uiInit(void)
{
    VDP_setTextPalette(PAL_SYSTEM);
}

/** ゲーム中UIパネルを有効化（Window表示） */
void uiEnableGamePanel(void)
{
    /* 右64ピクセル(4×16px列)をWindowプレーンとして使用
     * VDP_setWindowOnRight は 2タイル単位(16px)で列数指定
     * UI_PANEL_W(64) / 16 = 4列 → 右8タイル(64px)がWindow表示 */
    VDP_setWindowOnRight(UI_PANEL_W / 16);
}

/** UIパネルを無効化（タイトル画面等で全画面使用） */
void uiDisableGamePanel(void)
{
    /* FALSE = 左側、0列 = Windowなし（全画面BGプレーンを使用） */
    VDP_setWindowHPos(FALSE, 0);
}

/** 画面クリア */
void uiClearScreen(void)
{
    VDP_clearPlane(BG_A, TRUE);
    VDP_clearPlane(BG_B, TRUE);
    VDP_clearPlane(WINDOW, TRUE);
}

/** ゲーム中UI更新 */
void uiUpdate(void)
{
    /* ラベル描画 */
    drawWindowText("SCORE", UI_PANEL_TILE_X + 1, 1);
    intToStr(score, str_buf, 7);
    drawWindowText(str_buf, UI_PANEL_TILE_X + 1, 2);

    /* 残機 */
    drawWindowText("LIFE", UI_PANEL_TILE_X + 1, 5);
    intToStr(lives, str_buf, 1);
    drawWindowText(str_buf, UI_PANEL_TILE_X + 1, 6);

    /* ステージ */
    drawWindowText("STAGE", UI_PANEL_TILE_X + 1, 9);
    intToStr(current_stage + 1, str_buf, 2);
    drawWindowText(str_buf, UI_PANEL_TILE_X + 1, 10);

    /* パワーアップ状態 */
    u16 status_y = 13;
    drawWindowText("POWER", UI_PANEL_TILE_X + 1, status_y);
    status_y++;

    if (powerup_state.strong)
    {
        drawWindowText("STR", UI_PANEL_TILE_X + 1, status_y);
        status_y++;
    }
    if (powerup_state.speed_up)
    {
        drawWindowText("SPD", UI_PANEL_TILE_X + 1, status_y);
        status_y++;
    }
    if (powerup_state.barrier)
    {
        drawWindowText("BAR", UI_PANEL_TILE_X + 1, status_y);
        status_y++;
    }
    /* 余白クリア */
    for (u16 y = status_y; y < status_y + 3; y++)
    {
        drawWindowText("      ", UI_PANEL_TILE_X + 1, y);
    }

    /* 操作ガイド */
    drawWindowText("START", UI_PANEL_TILE_X + 1, 24);
    drawWindowText("PAUSE", UI_PANEL_TILE_X + 1, 25);
}

/** タイトル画面描画 */
void uiDrawTitle(void)
{
    uiClearScreen();
    uiDisableGamePanel();

    drawBgText("GERO BLOCK", 15, 6);
    drawBgText("BLOCK BREAKER", 13, 8);

    drawBgText("PRESS START", 14, 16);

    drawBgText("1P: START BUTTON", 12, 20);
    drawBgText("2P: PRESS C FIRST", 11, 22);

    /* スプライト非表示 */
    for (u8 i = 0; i < SPR_TOTAL; i++)
    {
        VDP_setSpriteFull(i, -128, -128, SPRITE_SIZE(1, 1), 0, (i < SPR_TOTAL - 1) ? i + 1 : 0);
    }
    VDP_updateSprites(SPR_TOTAL, DMA);
}

/** ゲームオーバー画面描画 */
void uiDrawGameOver(void)
{
    /* ブロック部分を暗くする代わりにテキストオーバーレイ */
    drawBgText("GAME OVER", 11, 12);
    intToStr(score, str_buf, 7);
    drawBgText("SCORE:", 12, 14);
    drawBgText(str_buf, 18, 14);
    drawBgText("PRESS START", 10, 18);
}

/** ステージクリア画面描画
 *  clear_image が指定されている場合は BG_B に画像を表示 */
void uiDrawStageClear(const Image *clear_image)
{
    if (clear_image)
    {
        /* クリア画像をBG_Bに描画（背景を上書き） */
        uiDisableGamePanel();
        VDP_clearPlane(BG_A, TRUE);
        VDP_drawImageEx(
            BG_B, clear_image,
            TILE_ATTR_FULL(PAL_BG, FALSE, FALSE, FALSE, TILE_BG_START),
            0, 0, TRUE, DMA
        );
        /* 画像描画後にゲーム用パレットを再設定 */
        gfxLoadPalettes();
    }

    drawBgText("STAGE CLEAR!", 10, 12);
    intToStr(score, str_buf, 7);
    drawBgText("SCORE:", 12, 14);
    drawBgText(str_buf, 18, 14);
    drawBgText("PRESS START", 10, 18);
}
