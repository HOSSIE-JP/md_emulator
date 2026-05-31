#include <stdint.h>

#if defined(__PCE_CD__)
#define PCE_CONFIG_IMPLEMENTATION
#endif
#if defined(__PCE__)
#include <pce.h>
#endif
#if defined(__PCE_CD__)
#include <pce-cd.h>
PCE_CDB_USE_GRAPHICS_DRIVER(1);
#endif

#include "generated/assets.h"
#include "generated/vn.h"

#define PAD_I 0x01u
#define PAD_II 0x02u
#define PAD_SEL 0x04u
#define PAD_RUN 0x08u
#define PAD_UP 0x10u
#define PAD_RIGHT 0x20u
#define PAD_DOWN 0x40u
#define PAD_LEFT 0x80u

#define PCE_VCE_ADDR_LO (*(volatile uint8_t *)0x0402)
#define PCE_VCE_ADDR_HI (*(volatile uint8_t *)0x0403)
#define PCE_VCE_DATA_LO (*(volatile uint8_t *)0x0404)
#define PCE_VCE_DATA_HI (*(volatile uint8_t *)0x0405)

#define VN_MAP_WIDTH 32u
#define VN_SATB_ADDR 0x7f00u
#define VN_WINDOW_X 1u
#define VN_WINDOW_Y 18u
#define VN_WINDOW_W 30u
#define VN_WINDOW_H 10u
#define VN_TEXT_X 2u
#define VN_TEXT_Y 19u
#define VN_TEXT_COLS 14u
#define VN_TEXT_ROWS 3u
#define VN_UI_PALETTE 15u
#define VN_UI_TILE_BASE 160u

static uint8_t current_scene = 0;
static uint8_t current_message = 0;
static uint8_t pending_sprite_refresh = 0;
static uint8_t pending_cdda_track = 0;

static void delay_frame(void)
{
#if defined(__PCE_CD__)
    pce_cdb_wait_vblank();
#else
    volatile uint16_t delay;
    for (delay = 0; delay < 6200u; delay++) {}
#endif
}

static uint8_t read_pad_raw(void)
{
#if defined(__PCE__)
    return pce_joypad_read();
#else
    return 0;
#endif
}

static void pce_editor_vram_copy(uint16_t dest, const uint8_t *source, uint16_t length)
{
#if defined(__PCE__)
    pce_vdc_set_copy_word();
    pce_vdc_copy_to_vram(dest, source, length);
#else
    (void)dest;
    (void)source;
    (void)length;
#endif
}

static void vce_write_color(uint16_t index, uint16_t color)
{
    PCE_VCE_ADDR_LO = (uint8_t)(index & 0xffu);
    PCE_VCE_ADDR_HI = (uint8_t)((index >> 8) & 0xffu);
    PCE_VCE_DATA_LO = (uint8_t)(color & 0xffu);
    PCE_VCE_DATA_HI = (uint8_t)((color >> 8) & 0xffu);
}

static const uint8_t *data_ref_ptr(const pce_editor_data_ref_t *ref)
{
    if (!ref) return 0;
    if (ref->chunk_count && ref->chunks)
    {
        pce_editor_map_asset_bank(ref->chunks[0].bank);
        return ref->chunks[0].data;
    }
    return ref->data;
}

static void copy_data_ref_to_vram(uint16_t dest, const pce_editor_data_ref_t *ref, uint16_t word_stride)
{
    uint8_t i;
    uint16_t word_offset = 0;
    if (!ref || !ref->size) return;
    if (ref->chunk_count && ref->chunks)
    {
        for (i = 0; i < ref->chunk_count; i++)
        {
            const pce_editor_data_chunk_t *chunk = &ref->chunks[i];
            if (!chunk->data || !chunk->size) continue;
            pce_editor_map_asset_bank(chunk->bank);
            pce_editor_vram_copy((uint16_t)(dest + word_offset), chunk->data, (uint16_t)chunk->size);
            word_offset = (uint16_t)(word_offset + ((chunk->size + 1u) / 2u));
        }
        return;
    }
    if (ref->data)
    {
        pce_editor_vram_copy(dest, ref->data, (uint16_t)ref->size);
        (void)word_stride;
    }
}

static void upload_palette(const pce_editor_data_ref_t *palette, uint16_t base_index, uint8_t fallback_dark)
{
    uint16_t i;
    uint16_t color_count;
    const uint8_t *data;
    if (!palette || !palette->size) return;
    data = data_ref_ptr(palette);
    if (!data) return;
    color_count = (uint16_t)(palette->size / 2u);
    if (color_count > 16u) color_count = 16u;
    for (i = 0; i < color_count; i++)
    {
        const uint16_t raw = (uint16_t)(data[i * 2u] | ((uint16_t)data[(i * 2u) + 1u] << 8));
        vce_write_color((uint16_t)(base_index + i), raw);
    }
    for (; i < 16u; i++)
    {
        vce_write_color((uint16_t)(base_index + i), fallback_dark ? 0x0000u : 0x01ffu);
    }
}

static void upload_ui_palette(void)
{
    uint8_t i;
    uint16_t base = (uint16_t)(VN_UI_PALETTE * 16u);
    vce_write_color((uint16_t)(base + 0u), 0x0000u);
    for (i = 1u; i < 16u; i++)
    {
        vce_write_color((uint16_t)(base + i), 0x01ffu);
    }
}

static void fill_vram_words(uint16_t addr, uint16_t value, uint16_t count);

static void upload_ui_tiles(void)
{
    fill_vram_words((uint16_t)(VN_UI_TILE_BASE * 16u), 0x0000u, 16u);
    fill_vram_words((uint16_t)((VN_UI_TILE_BASE + 1u) * 16u), 0x0000u, 16u);
}

static void upload_font_tiles(void)
{
    pce_editor_vram_copy((uint16_t)(PCE_VN_FONT_TILE_BASE * 16u), pce_vn_font_tiles, (uint16_t)(pce_vn_font_glyph_count * 128u));
}

static void write_map_words(uint16_t map_addr, const uint16_t *words, uint16_t count)
{
#if defined(__PCE__)
    uint16_t i;
    pce_vdc_set_copy_word();
    pce_vdc_poke(VDC_REG_VRAM_WRITE_ADDR, map_addr);
    for (i = 0; i < count; i++)
    {
        pce_vdc_poke(VDC_REG_VRAM_DATA, words[i]);
    }
#else
    pce_editor_vram_copy(map_addr, (const uint8_t *)words, (uint16_t)(count * 2u));
#endif
}

static void fill_vram_words(uint16_t addr, uint16_t value, uint16_t count)
{
#if defined(__PCE__)
    uint16_t i;
    pce_vdc_set_copy_word();
    pce_vdc_poke(VDC_REG_VRAM_WRITE_ADDR, addr);
    for (i = 0; i < count; i++)
    {
        pce_vdc_poke(VDC_REG_VRAM_DATA, value);
    }
#else
    (void)addr;
    (void)value;
    (void)count;
#endif
}

static uint16_t ui_tile(uint16_t tile)
{
    return (uint16_t)((VN_UI_PALETTE << 12) | tile);
}

static void fill_window_rect(void)
{
    uint8_t row;
    uint8_t col;
    static uint16_t line[VN_WINDOW_W];
    for (row = 0; row < VN_WINDOW_H; row++)
    {
        for (col = 0; col < VN_WINDOW_W; col++)
        {
            const uint8_t edge = (row == 0u || row == (VN_WINDOW_H - 1u) || col == 0u || col == (VN_WINDOW_W - 1u));
            line[col] = ui_tile((uint16_t)(VN_UI_TILE_BASE + (edge ? 1u : 0u)));
        }
        write_map_words((uint16_t)(((VN_WINDOW_Y + row) * VN_MAP_WIDTH) + VN_WINDOW_X), line, VN_WINDOW_W);
    }
}

static void draw_glyph(uint8_t glyph, uint8_t x, uint8_t y)
{
    static uint16_t top[2];
    static uint16_t bottom[2];
    uint16_t tile = (uint16_t)(PCE_VN_FONT_TILE_BASE + ((uint16_t)glyph * 4u));
    top[0] = ui_tile(tile);
    top[1] = ui_tile((uint16_t)(tile + 1u));
    bottom[0] = ui_tile((uint16_t)(tile + 2u));
    bottom[1] = ui_tile((uint16_t)(tile + 3u));
    write_map_words((uint16_t)((y * VN_MAP_WIDTH) + x), top, 2u);
    write_map_words((uint16_t)(((y + 1u) * VN_MAP_WIDTH) + x), bottom, 2u);
}

static void draw_message_text(const pce_vn_message_t *message)
{
    uint8_t i;
    uint8_t col = 0;
    uint8_t row = 0;
    if (!message || !message->glyphs) return;
    for (i = 0; i < message->glyph_count; i++)
    {
        const uint8_t glyph = message->glyphs[i];
        if (glyph == PCE_VN_GLYPH_END) break;
        if (glyph == 0u)
        {
            col++;
        }
        else
        {
            draw_glyph(glyph, (uint8_t)(VN_TEXT_X + (col * 2u)), (uint8_t)(VN_TEXT_Y + (row * 2u)));
            col++;
        }
        if (col >= VN_TEXT_COLS)
        {
            col = 0;
            row++;
            if (row >= VN_TEXT_ROWS) break;
        }
    }
}

static void upload_bg_graphics(const pce_editor_bg_asset_t *bg)
{
    uint8_t row;
    uint16_t row_bytes;
    const uint8_t *map;
    if (!bg) return;
    upload_palette(&bg->palette, (uint16_t)(bg->palette_bank * 16u), 0);
    copy_data_ref_to_vram((uint16_t)(bg->tile_base * 16u), &bg->tiles, 16u);
    map = data_ref_ptr(&bg->map);
    if (!map) return;
    row_bytes = (uint16_t)(bg->width_tiles * 2u);
    for (row = 0; row < bg->height_tiles; row++)
    {
        pce_editor_vram_copy(
            (uint16_t)(bg->map_base + ((uint16_t)row * VN_MAP_WIDTH)),
            map + ((uint16_t)row * row_bytes),
            row_bytes
        );
    }
}

static uint16_t sprite_attr_for_size(const pce_editor_sprite_asset_t *sprite)
{
    uint16_t attr = (uint16_t)(VDC_SPRITE_FG | VDC_SPRITE_COLOR(sprite->palette_bank));
    if (sprite->cell_width >= 32u) attr |= VDC_SPRITE_WIDTH_32;
    if (sprite->cell_height >= 64u) attr |= VDC_SPRITE_HEIGHT_64;
    else if (sprite->cell_height >= 32u) attr |= VDC_SPRITE_HEIGHT_32;
    return attr;
}

static void clear_sprites(void)
{
#if defined(__PCE_CD__)
    pce_cdb_vdc_sprite_table_set_vram_addr(VN_SATB_ADDR);
    pce_cdb_vdc_sprite_table_clear();
#endif
}

static void show_character_sprite(const pce_editor_sprite_asset_t *sprite, uint8_t x, uint8_t y)
{
    if (!sprite || !sprite->patterns.size) return;
    upload_palette(&sprite->palette, (uint16_t)(256u + (sprite->palette_bank * 16u)), 1);
    copy_data_ref_to_vram((uint16_t)(sprite->pattern_base * 64u), &sprite->patterns, 64u);
#if defined(__PCE_CD__)
    pce_cdb_vdc_sprite_table_set_vram_addr(VN_SATB_ADDR);
    *PCE_CDB_SPR_INDEX = 0;
    *PCE_CDB_SPR_Y = (uint16_t)(y + 64u);
    *PCE_CDB_SPR_X = (uint16_t)(x + 32u);
    *PCE_CDB_SPR_PATTERN = sprite->pattern_base;
    *PCE_CDB_SPR_ATTR = sprite_attr_for_size(sprite);
    pce_cdb_vdc_sprite_table_put();
    pce_cdb_vdc_bg_sprite_enable();
#else
    (void)x;
    (void)y;
#endif
}

static void play_cdda_track(uint8_t track)
{
#if defined(__PCE_CD__)
    pce_sector_t start;
    pce_sector_t end;
    if (track < 2u) return;
    start.track = track;
    start.track_end = track;
    end.track = track;
    end.track_end = track;
    (void)pce_cdb_cdda_play(PCE_CDB_LOCATION_TYPE_TRACK, start, PCE_CDB_LOCATION_TYPE_UNTIL_END, end, PCE_CDB_CDDA_PLAY_REPEAT);
#else
    (void)track;
#endif
}

static void play_adpcm_voice(signed char voice_index)
{
#if defined(__PCE_CD__)
    const pce_editor_adpcm_asset_t *voice;
    if (voice_index < 0 || (uint8_t)voice_index >= pce_editor_adpcm_asset_count) return;
    voice = &pce_editor_adpcm_assets[(uint8_t)voice_index];
    if (!voice->data || !voice->data_size) return;
    pce_cdb_adpcm_reset();
    (void)pce_cdb_adpcm_read_from_ram(PCE_CDB_ADDRESS_BYTES, (uint16_t)(uintptr_t)voice->data, voice->adpcm_address, (uint16_t)voice->data_size);
    (void)pce_cdb_adpcm_play(voice->adpcm_address, (uint16_t)voice->data_size, voice->divider, voice->loop ? PCE_CDB_ADPCM_REPEAT : PCE_CDB_ADPCM_ONE_SHOT);
#else
    (void)voice_index;
#endif
}

static void show_scene(uint8_t scene_index)
{
    const pce_vn_scene_t *scene;
    if (!pce_vn_scene_count) return;
    if (scene_index >= pce_vn_scene_count) scene_index = pce_vn_start_scene;
    current_scene = scene_index;
    current_message = 0;
    scene = &pce_vn_scenes[current_scene];
    if (scene->bg_index < pce_editor_bg_asset_count)
    {
        upload_bg_graphics(&pce_editor_bg_assets[scene->bg_index]);
    }
    pending_sprite_refresh = 0;
    pending_cdda_track = scene->cdda_track;
}

static void refresh_scene_sprites(void)
{
    uint8_t i;
    const pce_vn_scene_t *scene = &pce_vn_scenes[current_scene];
    clear_sprites();
    for (i = 0; i < scene->character_count; i++)
    {
        const pce_vn_character_t *character = &scene->characters[i];
        if (character->sprite_index < pce_editor_sprite_asset_count)
        {
            show_character_sprite(&pce_editor_sprite_assets[character->sprite_index], character->x, character->y);
        }
    }
    pending_sprite_refresh = 0;
}

static void show_current_message(void)
{
    const pce_vn_scene_t *scene = &pce_vn_scenes[current_scene];
    uint8_t message_index;
    if (current_message >= scene->message_count) current_message = 0;
    message_index = (uint8_t)(scene->message_start + current_message);
    fill_window_rect();
    if (message_index < pce_vn_message_count)
    {
        const pce_vn_message_t *message = &pce_vn_messages[message_index];
        draw_message_text(message);
        delay_frame();
        play_adpcm_voice(message->voice_index);
    }
}

static void init_video(void)
{
#if defined(__PCE__)
    pce_vdc_set_resolution(256, 224, VCE_COLORBURST_ON);
    pce_vdc_bg_set_size(VDC_BG_SIZE_32_32);
    pce_vdc_set_copy_word();
    pce_vdc_bg_enable();
    pce_vdc_sprite_enable();
    pce_vdc_sprite_set_table_start(VN_SATB_ADDR);
#endif
    upload_ui_palette();
    upload_ui_tiles();
    upload_font_tiles();
}

int main(void)
{
    uint8_t i;
    uint8_t pad;
    uint8_t last_pad;
    uint8_t pressed;

    init_video();
    show_scene(pce_vn_start_scene);
    show_current_message();
    for (i = 0; i < 4u; i++) delay_frame();
    pending_sprite_refresh = 0;
    for (i = 0; i < 30u; i++) delay_frame();
    if (pending_cdda_track >= 2u)
    {
        play_cdda_track(pending_cdda_track);
        pending_cdda_track = 0;
    }
    last_pad = read_pad_raw();

    while (1)
    {
        pad = read_pad_raw();
        pressed = (uint8_t)(pad & (uint8_t)~last_pad);
        if (pressed & (PAD_I | PAD_II | PAD_RUN | PAD_RIGHT | PAD_DOWN))
        {
            const pce_vn_scene_t *scene = &pce_vn_scenes[current_scene];
            current_message++;
            if (current_message >= scene->message_count)
            {
                if (scene->next_scene >= 0)
                {
                    show_scene((uint8_t)scene->next_scene);
                }
                else
                {
                    current_message = 0;
                }
            }
            show_current_message();
            if (pending_sprite_refresh)
            {
                for (i = 0; i < 4u; i++) delay_frame();
                refresh_scene_sprites();
            }
            if (pending_cdda_track >= 2u)
            {
                for (i = 0; i < 8u; i++) delay_frame();
                play_cdda_track(pending_cdda_track);
                pending_cdda_track = 0;
            }
        }
        last_pad = pad;
        delay_frame();
    }
    return 0;
}
