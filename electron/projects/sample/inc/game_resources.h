/* ===================================================================
 * GERO Block - リソースバインディング（自動生成 - 編集しないでください）
 * Generated: 2026-02-27T17:29:30.886Z
 * =================================================================== */

#ifndef _GAME_RESOURCES_H_
#define _GAME_RESOURCES_H_

#include "resources.h"

/* --- スプライトバインディング --- */
#define RES_SPR_BALL spr_8x8
#define RES_SPR_PADDLE spr_32x32
#define RES_SPR_POWERUP_MULTI_BALL spr_16x8
#define RES_SPR_POWERUP_STRONG spr_16x8
#define RES_SPR_POWERUP_SPEED_UP spr_16x8
#define RES_SPR_POWERUP_BARRIER spr_16x8
#define RES_SPR_BLOCK_WHITE spr_16x8
#define RES_SPR_BLOCK_YELLOW spr_16x8
#define RES_SPR_BLOCK_GREEN spr_16x8
#define RES_SPR_BLOCK_BLUE spr_16x8
#define RES_SPR_BLOCK_RED spr_16x8
#define RES_SPR_BLOCK_GRAY spr_16x8

/* --- 画像バインディング --- */
#define RES_IMG_STAGE_BACKGROUND img_comfyui

/* --- SEバインディング --- */
#define RES_SE_BALL_HIT_PADDLE se_s1_ring1
#define RES_SE_BALL_HIT_WALL se_s1_ring1
#define RES_SE_BLOCK_BREAK se_s1_ring1
#define RES_SE_BLOCK_HIT se_s1_ring1
#define RES_SE_POWERUP_APPEAR se_s1_ring1
#define RES_SE_POWERUP_GET se_s1_ring1
#define RES_SE_BALL_LOSE se_s1_ring1
#define RES_SE_GAME_OVER se_s1_ring1
#define RES_SE_STAGE_CLEAR se_s1_ring1
#define RES_SE_GAME_START se_s1_ring1
#define RES_SE_PAUSE se_s1_ring1

/* --- BGMバインディング --- */
#define RES_BGM_0 bgm_19

/* BGM形式: PCM (WAV ソース) */
#define BGM_IS_PCM 1

/* --- ゲーム設定（エディタから生成） --- */
#undef INITIAL_LIVES
#define INITIAL_LIVES 3
#undef BALL_BASE_SPEED
#define BALL_BASE_SPEED FIX16(2)
#undef PADDLE_SPEED
#define PADDLE_SPEED FIX16(3)
#undef BGM_VOLUME
#define BGM_VOLUME 100

#endif /* _GAME_RESOURCES_H_ */
