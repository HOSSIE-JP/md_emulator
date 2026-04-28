/* ===================================================================
 * GERO Block - メインエントリポイント
 * ゲームループとステートマシン
 *
 * BGプレーン構成:
 *   BG_B (低優先度) : 背景ご褒美画像（ブロック破壊で露出）
 *   BG_A (高優先度) : ブロックタイル
 *   WINDOW          : 右64pxのUIパネル（スコア、残機等）
 *   スプライト      : ボール、パドル、パワーアップアイテム
 * =================================================================== */

#include "game.h"
#include "game_resources.h"
#include "stages.h"

/* ===================================================================
 * デバッグ出力マクロ
 * KDebug_Alert はエミュレータのデバッグコンソールに出力される
 * =================================================================== */

#ifdef DEBUG
#define DBG_MSG(msg) KDebug_Alert(msg)
#else
#define DBG_MSG(msg) KDebug_Alert(msg)
#endif

/** 起動時の画面表示用デバッグメッセージ */
static void bootMessage(const char *msg)
{
    KDebug_Alert(msg);
}

/* ===================================================================
 * グローバル変数定義
 * =================================================================== */

GameState game_state;
u8 current_stage;
u32 score;
u8 lives;
u8 num_players;
bool barrier_visible;

static u16 prev_joy1;
static u16 prev_joy2;

/** ボタンが今フレーム押されたか（エッジ検出） */
static bool buttonPressed(u16 current, u16 previous, u16 button)
{
    return (current & button) && !(previous & button);
}

/* ===================================================================
 * ゲームステート遷移
 * =================================================================== */

/** ゲーム初期化（新規ゲーム開始） */
static void startNewGame(void)
{
    DBG_MSG("GERO Block: Starting new game");
    current_stage = 0;
    score = 0;
    lives = INITIAL_LIVES;

    playerInit();
    ballInit();
    blockInit();
    powerupInit();

    /* ステージロード */
    blockLoadStage(current_stage);
    DBG_MSG("GERO Block: Stage 1 loaded");

    /* 画面セットアップ */
    uiClearScreen();
    gfxDrawBackground();
    uiEnableGamePanel();
    blockDrawAll();

    game_state = STATE_SERVE;
    sndPlayBGM();
    sndPlaySE(SND_SE_GAME_START);
    DBG_MSG("GERO Block: STATE_SERVE");
}

/** 次のステージへ進む */
static void advanceStage(void)
{
    current_stage++;

    if (current_stage >= STAGE_COUNT)
    {
        /* 全ステージクリア → タイトルに戻る */
        DBG_MSG("GERO Block: All stages cleared!");
        game_state = STATE_TITLE;
        uiDrawTitle();
        return;
    }

    DBG_MSG("GERO Block: Advancing to next stage");
    ballInit();
    powerupInit();
    blockLoadStage(current_stage);

    uiClearScreen();
    gfxDrawBackground();
    uiEnableGamePanel();
    blockDrawAll();

    game_state = STATE_SERVE;
}

/** ミス処理 */
static void loseLife(void)
{
    lives--;
    if (lives == 0)
    {
        game_state = STATE_GAME_OVER;
        sndStopBGM();
        sndPlaySE(SND_SE_GAME_OVER);
        uiDrawGameOver();
    }
    else
    {
        /* リセットして再サーブ */
        ballInit();
        powerupReset();
        game_state = STATE_SERVE;
    }
}

/* ===================================================================
 * メインループ内のステート処理
 * =================================================================== */

static void handleTitle(u16 joy1, u16 joy2)
{
    /* Cボタンが押されたら2P */
    if (buttonPressed(joy1, prev_joy1, BUTTON_C) ||
        buttonPressed(joy2, prev_joy2, BUTTON_C))
    {
        num_players = 2;
    }

    /* STARTで開始 */
    if (buttonPressed(joy1, prev_joy1, BUTTON_START))
    {
        if (num_players == 0)
            num_players = 1;
        startNewGame();
    }
}

static void handleServe(u16 joy1, u16 joy2)
{
    playerUpdate(joy1, joy2);
    ballFollowPaddle(0);

    /* A / B / C でサーブ */
    if (buttonPressed(joy1, prev_joy1, BUTTON_A) ||
        buttonPressed(joy1, prev_joy1, BUTTON_B) ||
        buttonPressed(joy1, prev_joy1, BUTTON_C))
    {
        ballServe(0);
        game_state = STATE_PLAYING;
    }
}

static void handlePlaying(u16 joy1, u16 joy2)
{
    playerUpdate(joy1, joy2);
    ballUpdate();
    powerupUpdate();

    /* 全ボール消滅チェック */
    if (ballActiveCount() == 0)
    {
        loseLife();
        return;
    }

    /* ステージクリアチェック */
    if (blockCheckClear())
    {
        game_state = STATE_STAGE_CLEAR;
        sndPlaySE(SND_SE_STAGE_CLEAR);
        uiDrawStageClear(stage_table[current_stage].clear_image);
    }

    /* ポーズ */
    if (buttonPressed(joy1, prev_joy1, BUTTON_START))
    {
        game_state = STATE_PAUSE;
        sndPlaySE(SND_SE_PAUSE);
    }
}

static void handlePause(u16 joy1)
{
    /* STARTで復帰 */
    if (buttonPressed(joy1, prev_joy1, BUTTON_START))
    {
        game_state = STATE_PLAYING;
    }
}

static void handleStageClear(u16 joy1)
{
    if (buttonPressed(joy1, prev_joy1, BUTTON_START) ||
        buttonPressed(joy1, prev_joy1, BUTTON_A))
    {
        advanceStage();
    }
}

static void handleGameOver(u16 joy1)
{
    if (buttonPressed(joy1, prev_joy1, BUTTON_START))
    {
        num_players = 0;
        game_state = STATE_TITLE;
        sndStopBGM();
        uiDrawTitle();
    }
}

/* ===================================================================
 * メインエントリポイント
 * =================================================================== */

int main(bool hard_reset)
{
    /* --- 起動ログ --- */
    bootMessage("GERO Block: Starting...");

    /* --- VDP初期化 --- */
    VDP_setScreenWidth320();
    bootMessage("GERO Block: VDP initialized (320 mode)");

    /* --- グラフィック初期化 --- */
    gfxInit();
    bootMessage("GERO Block: GFX initialized (palettes + tiles)");

    /* --- サウンド初期化 --- */
    sndInit();
    bootMessage("GERO Block: Sound initialized");

    /* --- UI初期化 --- */
    uiInit();
    bootMessage("GERO Block: UI initialized");

    /* --- ステージデータ検証 --- */
    if (STAGE_COUNT == 0)
    {
        bootMessage("GERO Block ERROR: STAGE_COUNT is 0!");
        VDP_drawText("ERROR: NO STAGES", 7, 10);
        VDP_drawText("Export stages from", 6, 12);
        VDP_drawText("the editor first.", 6, 13);
        while (TRUE) { SYS_doVBlankProcess(); }
    }

    {
        /* 各ステージテーブルのポインタ検証 */
        char stage_buf[32];
        for (u8 i = 0; i < STAGE_COUNT && i < 10; i++)
        {
            if (stage_table[i].blocks == NULL)
            {
                sprintf(stage_buf, "ERR: Stage %d blocks=NULL", i + 1);
                bootMessage(stage_buf);
                VDP_drawText(stage_buf, 2, 10 + i);
            }
        }
        sprintf(stage_buf, "GERO Block: %d stages loaded", STAGE_COUNT);
        bootMessage(stage_buf);
    }

    /* --- 変数初期化 --- */
    game_state = STATE_TITLE;
    current_stage = 0;
    score = 0;
    lives = INITIAL_LIVES;
    num_players = 0;
    barrier_visible = FALSE;
    prev_joy1 = 0;
    prev_joy2 = 0;
    bootMessage("GERO Block: Variables initialized");

    /* --- タイトル画面 --- */
    uiDrawTitle();
    bootMessage("GERO Block: Title screen drawn, entering main loop");

    /* ===================================================================
     * メインゲームループ
     * =================================================================== */
    while (TRUE)
    {
        /* 入力読み取り */
        u16 joy1 = JOY_readJoypad(JOY_1);
        u16 joy2 = JOY_readJoypad(JOY_2);

        /* ステート処理 */
        switch (game_state)
        {
            case STATE_TITLE:
                handleTitle(joy1, joy2);
                break;

            case STATE_SERVE:
                handleServe(joy1, joy2);
                break;

            case STATE_PLAYING:
                handlePlaying(joy1, joy2);
                break;

            case STATE_PAUSE:
                handlePause(joy1);
                break;

            case STATE_STAGE_CLEAR:
                handleStageClear(joy1);
                break;

            case STATE_GAME_OVER:
                handleGameOver(joy1);
                break;
        }

        /* スプライト描画（プレイ中のみ） */
        if (game_state == STATE_SERVE || game_state == STATE_PLAYING || game_state == STATE_PAUSE)
        {
            playerDraw();
            ballDraw();
            powerupDraw();
            uiUpdate();

            /* スプライトチェーン終端 */
            VDP_updateSprites(SPR_TOTAL, DMA);
        }

        /* 前フレーム入力保存 */
        prev_joy1 = joy1;
        prev_joy2 = joy2;

        /* VBlank同期 */
        SYS_doVBlankProcess();
    }

    return 0;
}
