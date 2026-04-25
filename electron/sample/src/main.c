/**
 * Hello World - Mega Drive Game Editor サンプル
 * SGDK を使った最小限のメガドライブゲーム
 */
#include <genesis.h>

int main(void)
{
    /* 背景色を設定（パレット 0, カラー 0: 濃い青） */
    PAL_setColor(0, RGB24_TO_VDPCOLOR(0x000060));

    /* テキスト表示 */
    VDP_drawText("*** HELLO, MEGA WORLD! ***", 3, 10);
    VDP_drawText("MD GAME EDITOR SAMPLE", 6, 13);
    VDP_drawText("PRESS START", 10, 18);

    /* メインループ */
    while (1)
    {
        SYS_doVBlankProcess();
    }

    return 0;
}
