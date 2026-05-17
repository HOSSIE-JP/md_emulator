#if defined(__CC65__)
#include <conio.h>
#include <joystick.h>
#include <pce.h>
#elif defined(__PCE__)
#include <pce.h>
#include <stdint.h>

#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define COLOR_YELLOW 7
#define COLOR_LIGHTBLUE 14
#define COLOR_GRAY2 12

#define TEXT_COLS 32
#define FONT_BASE_TILE 256

static unsigned char pce_text_palette = 0;
static unsigned char pce_text_ready = 0;

static const uint8_t glyph_blank[7] = { 0, 0, 0, 0, 0, 0, 0 };
static const uint8_t glyph_hash[7] = { 10, 31, 10, 10, 31, 10, 0 };
static const uint8_t glyph_dot[7] = { 0, 0, 0, 0, 0, 12, 12 };
static const uint8_t glyph_colon[7] = { 0, 12, 12, 0, 12, 12, 0 };
static const uint8_t glyph_dash[7] = { 0, 0, 0, 31, 0, 0, 0 };
static const uint8_t glyph_slash[7] = { 1, 2, 4, 8, 16, 0, 0 };
static const uint8_t glyph_0[7] = { 14, 17, 19, 21, 25, 17, 14 };
static const uint8_t glyph_1[7] = { 4, 12, 4, 4, 4, 4, 14 };
static const uint8_t glyph_2[7] = { 14, 17, 1, 2, 4, 8, 31 };
static const uint8_t glyph_3[7] = { 30, 1, 1, 14, 1, 1, 30 };
static const uint8_t glyph_4[7] = { 2, 6, 10, 18, 31, 2, 2 };
static const uint8_t glyph_5[7] = { 31, 16, 30, 1, 1, 17, 14 };
static const uint8_t glyph_6[7] = { 6, 8, 16, 30, 17, 17, 14 };
static const uint8_t glyph_7[7] = { 31, 1, 2, 4, 8, 8, 8 };
static const uint8_t glyph_8[7] = { 14, 17, 17, 14, 17, 17, 14 };
static const uint8_t glyph_9[7] = { 14, 17, 17, 15, 1, 2, 12 };
static const uint8_t glyph_A[7] = { 14, 17, 17, 31, 17, 17, 17 };
static const uint8_t glyph_B[7] = { 30, 17, 17, 30, 17, 17, 30 };
static const uint8_t glyph_C[7] = { 14, 17, 16, 16, 16, 17, 14 };
static const uint8_t glyph_D[7] = { 30, 17, 17, 17, 17, 17, 30 };
static const uint8_t glyph_E[7] = { 31, 16, 16, 30, 16, 16, 31 };
static const uint8_t glyph_F[7] = { 31, 16, 16, 30, 16, 16, 16 };
static const uint8_t glyph_G[7] = { 14, 17, 16, 23, 17, 17, 14 };
static const uint8_t glyph_H[7] = { 17, 17, 17, 31, 17, 17, 17 };
static const uint8_t glyph_I[7] = { 14, 4, 4, 4, 4, 4, 14 };
static const uint8_t glyph_J[7] = { 7, 2, 2, 2, 18, 18, 12 };
static const uint8_t glyph_K[7] = { 17, 18, 20, 24, 20, 18, 17 };
static const uint8_t glyph_L[7] = { 16, 16, 16, 16, 16, 16, 31 };
static const uint8_t glyph_M[7] = { 17, 27, 21, 21, 17, 17, 17 };
static const uint8_t glyph_N[7] = { 17, 25, 21, 19, 17, 17, 17 };
static const uint8_t glyph_O[7] = { 14, 17, 17, 17, 17, 17, 14 };
static const uint8_t glyph_P[7] = { 30, 17, 17, 30, 16, 16, 16 };
static const uint8_t glyph_Q[7] = { 14, 17, 17, 17, 21, 18, 13 };
static const uint8_t glyph_R[7] = { 30, 17, 17, 30, 20, 18, 17 };
static const uint8_t glyph_S[7] = { 15, 16, 16, 14, 1, 1, 30 };
static const uint8_t glyph_T[7] = { 31, 4, 4, 4, 4, 4, 4 };
static const uint8_t glyph_U[7] = { 17, 17, 17, 17, 17, 17, 14 };
static const uint8_t glyph_V[7] = { 17, 17, 17, 17, 17, 10, 4 };
static const uint8_t glyph_W[7] = { 17, 17, 17, 21, 21, 21, 10 };
static const uint8_t glyph_X[7] = { 17, 17, 10, 4, 10, 17, 17 };
static const uint8_t glyph_Y[7] = { 17, 17, 10, 4, 4, 4, 4 };
static const uint8_t glyph_Z[7] = { 31, 1, 2, 4, 8, 16, 31 };

static const uint8_t *glyph_for(unsigned char c)
{
    if (c >= 'a' && c <= 'z') c = (unsigned char)(c - 32);
    switch (c)
    {
        case '#': return glyph_hash;
        case '.': return glyph_dot;
        case ':': return glyph_colon;
        case '-': return glyph_dash;
        case '/': return glyph_slash;
        case '0': return glyph_0;
        case '1': return glyph_1;
        case '2': return glyph_2;
        case '3': return glyph_3;
        case '4': return glyph_4;
        case '5': return glyph_5;
        case '6': return glyph_6;
        case '7': return glyph_7;
        case '8': return glyph_8;
        case '9': return glyph_9;
        case 'A': return glyph_A;
        case 'B': return glyph_B;
        case 'C': return glyph_C;
        case 'D': return glyph_D;
        case 'E': return glyph_E;
        case 'F': return glyph_F;
        case 'G': return glyph_G;
        case 'H': return glyph_H;
        case 'I': return glyph_I;
        case 'J': return glyph_J;
        case 'K': return glyph_K;
        case 'L': return glyph_L;
        case 'M': return glyph_M;
        case 'N': return glyph_N;
        case 'O': return glyph_O;
        case 'P': return glyph_P;
        case 'Q': return glyph_Q;
        case 'R': return glyph_R;
        case 'S': return glyph_S;
        case 'T': return glyph_T;
        case 'U': return glyph_U;
        case 'V': return glyph_V;
        case 'W': return glyph_W;
        case 'X': return glyph_X;
        case 'Y': return glyph_Y;
        case 'Z': return glyph_Z;
        default: return glyph_blank;
    }
}

static void upload_font_tile(unsigned char c)
{
    uint8_t tile[32];
    unsigned char y;
    const uint8_t *glyph = glyph_for(c);
    for (y = 0; y < 8; y++)
    {
        const uint8_t bits = y < 7 ? (uint8_t)(glyph[y] << 1) : 0;
        tile[(y * 2)] = bits;
        tile[(y * 2) + 1] = 0;
        tile[16 + (y * 2)] = 0;
        tile[16 + (y * 2) + 1] = 0;
    }
    pce_vdc_copy_to_vram((uint16_t)((FONT_BASE_TILE + c) * 16u), tile, sizeof(tile));
}

static void init_text_screen(void)
{
    unsigned int c;
    uint16_t row[TEXT_COLS];
    unsigned char y;
    if (pce_text_ready) return;
    pce_vdc_set_resolution(256, 224, VCE_COLORBURST_ON);
    pce_vdc_bg_set_size(VDC_BG_SIZE_32_32);
    pce_vdc_set_copy_word();
    pce_vce_set_color(VCE_COLOR_INDEX(0, 0), VCE_COLOR(0, 0, 0));
    pce_vce_set_color(VCE_COLOR_INDEX(0, 1), VCE_COLOR(7, 7, 7));
    pce_vce_set_color(VCE_COLOR_INDEX(1, 0), VCE_COLOR(0, 0, 0));
    pce_vce_set_color(VCE_COLOR_INDEX(1, 1), VCE_COLOR(7, 7, 0));
    pce_vce_set_color(VCE_COLOR_INDEX(2, 0), VCE_COLOR(0, 0, 0));
    pce_vce_set_color(VCE_COLOR_INDEX(2, 1), VCE_COLOR(2, 5, 7));
    pce_vce_set_color(VCE_COLOR_INDEX(3, 0), VCE_COLOR(0, 0, 0));
    pce_vce_set_color(VCE_COLOR_INDEX(3, 1), VCE_COLOR(4, 4, 4));
    for (c = 0; c < 128; c++)
    {
        upload_font_tile((unsigned char)c);
    }
    for (c = 0; c < TEXT_COLS; c++)
    {
        row[c] = (uint16_t)(FONT_BASE_TILE + ' ');
    }
    for (y = 0; y < 28; y++)
    {
        pce_vdc_copy_to_vram((uint16_t)(y * TEXT_COLS), row, sizeof(row));
    }
    pce_vdc_bg_enable();
    pce_text_ready = 1;
}

static void bgcolor(unsigned char color) { (void)color; }
static void bordercolor(unsigned char color) { (void)color; }
static void cursor(unsigned char onoff) { (void)onoff; }
static void textcolor(unsigned char color)
{
    pce_text_palette = color == COLOR_YELLOW ? 1 : (color == COLOR_LIGHTBLUE ? 2 : (color == COLOR_GRAY2 ? 3 : 0));
}
static void clrscr(void) { pce_text_ready = 0; init_text_screen(); }
static void cputsxy(unsigned char x, unsigned char y, const char *s)
{
    uint16_t addr;
    uint16_t entry;
    unsigned char ch;
    init_text_screen();
    while (*s && x < TEXT_COLS)
    {
        ch = (unsigned char)*s++;
        if (ch >= 'a' && ch <= 'z') ch = (unsigned char)(ch - 32);
        addr = (uint16_t)(y * TEXT_COLS + x);
        entry = (uint16_t)(((uint16_t)pce_text_palette << 12) | (FONT_BASE_TILE + ch));
        pce_vdc_copy_to_vram(addr, &entry, sizeof(entry));
        x++;
    }
}
static void waitvsync(void)
{
    volatile unsigned int delay;
    for (delay = 0; delay < 6000; delay++) {}
}
#else
#include <stdint.h>
static void bgcolor(unsigned char color) { (void)color; }
static void bordercolor(unsigned char color) { (void)color; }
static void cputsxy(unsigned char x, unsigned char y, const char *s) { (void)x; (void)y; (void)s; }
static void cursor(unsigned char onoff) { (void)onoff; }
static void clrscr(void) {}
static void textcolor(unsigned char color) { (void)color; }
static void waitvsync(void) {}
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define COLOR_YELLOW 7
#define COLOR_LIGHTBLUE 14
#define COLOR_GRAY2 12
#endif

#include "generated/assets.h"

#define PCE_PSG_SELECT (*(volatile unsigned char *)0x0800)
#define PCE_PSG_GLOBAL (*(volatile unsigned char *)0x0801)
#define PCE_PSG_FREQ_LO (*(volatile unsigned char *)0x0802)
#define PCE_PSG_FREQ_HI (*(volatile unsigned char *)0x0803)
#define PCE_PSG_CONTROL (*(volatile unsigned char *)0x0804)
#define PCE_PSG_BALANCE (*(volatile unsigned char *)0x0805)

#if defined(__CC65__)
static unsigned char pce_pad_ready = 0;
#endif

static unsigned char read_pad_raw(void)
{
#if defined(__CC65__)
    if (!pce_pad_ready)
    {
        joy_install((void *)pce_stdjoy_joy);
        pce_pad_ready = 1;
    }
    return joy_read(JOY_1);
#elif defined(__PCE__)
    return pce_joypad_read();
#else
    return 0;
#endif
}

static void draw_hex(unsigned char value)
{
    static const char hex[] = "0123456789ABCDEF";
    char out[3];
    out[0] = hex[(value >> 4) & 0x0f];
    out[1] = hex[value & 0x0f];
    out[2] = 0;
    textcolor(value ? COLOR_YELLOW : COLOR_LIGHTBLUE);
    cputsxy(12, 5, out);
    textcolor(COLOR_WHITE);
}

static void draw_frame(unsigned int frame)
{
    static const char hex[] = "0123456789ABCDEF";
    char out[5];
    out[0] = hex[(frame >> 12) & 0x0f];
    out[1] = hex[(frame >> 8) & 0x0f];
    out[2] = hex[(frame >> 4) & 0x0f];
    out[3] = hex[frame & 0x0f];
    out[4] = 0;
    textcolor(COLOR_LIGHTBLUE);
    cputsxy(12, 4, out);
    textcolor(COLOR_WHITE);
}

static void draw_button_state(unsigned char x, unsigned char y, const char *label, unsigned char active)
{
    textcolor(active ? COLOR_YELLOW : COLOR_GRAY2);
    cputsxy(x, y, label);
    textcolor(COLOR_WHITE);
}

static void draw_pad_state(unsigned char pad)
{
    draw_button_state(2, 7, "I", pad & 0x01);
    draw_button_state(6, 7, "II", pad & 0x02);
    draw_button_state(11, 7, "SEL", pad & 0x04);
    draw_button_state(17, 7, "RUN", pad & 0x08);
    draw_button_state(2, 8, "UP", pad & 0x10);
    draw_button_state(7, 8, "RIGHT", pad & 0x20);
    draw_button_state(15, 8, "DOWN", pad & 0x40);
    draw_button_state(23, 8, "LEFT", pad & 0x80);
}

static void play_beep(unsigned int period)
{
    PCE_PSG_SELECT = 0;
    PCE_PSG_GLOBAL = 0xff;
    PCE_PSG_FREQ_LO = (unsigned char)(period & 0xff);
    PCE_PSG_FREQ_HI = (unsigned char)((period >> 8) & 0x0f);
    PCE_PSG_BALANCE = 0xff;
    PCE_PSG_CONTROL = 0x9f;
}

static void draw_generated_image(void)
{
    unsigned char row;
    for (row = 0; row < pce_editor_image_row_count; row++)
    {
        cputsxy(2, (unsigned char)(12 + row), pce_editor_image_rows[row]);
    }
}

int main(void)
{
    unsigned char pad;
    unsigned char last_pad = 0xff;
    unsigned int frame = 0;

    bordercolor(COLOR_BLACK);
    bgcolor(COLOR_BLACK);
    textcolor(COLOR_WHITE);
    cursor(0);
    clrscr();
    textcolor(COLOR_LIGHTBLUE);
    cputsxy(2, 1, "PCE GAME EDITOR SAMPLE");
    textcolor(COLOR_WHITE);
    cputsxy(2, 3, "Hello World from PC Engine");
    cputsxy(2, 4, "FRAME:");
    cputsxy(2, 5, "PAD RAW:");
    cputsxy(2, 10, "Generated image asset:");
    cputsxy(2, 21, "PAD INPUT CHANGES COLORS");
    draw_generated_image();
    play_beep(pce_editor_tone_period);

    while (1)
    {
        pad = read_pad_raw();
        if (pad != last_pad)
        {
            draw_pad_state(pad);
            last_pad = pad;
        }
        draw_hex(pad);
        draw_frame(frame);
        frame++;
        if (frame == 60)
        {
            PCE_PSG_CONTROL = 0x00;
        }
        waitvsync();
    }
    return 0;
}
