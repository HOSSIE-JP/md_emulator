use serde::{Deserialize, Serialize};

/// Hardware color lookup tables (Exodus VDP reference)
const NORMAL_COLOR: [u8; 8] = [0, 34, 68, 102, 136, 170, 204, 238];
const SHADOW_COLOR: [u8; 8] = [0, 17, 34, 51, 68, 85, 102, 119];
/// Highlight = Normal/2 + 128 (clamped to 255)
const HIGHLIGHT_COLOR: [u8; 8] = [128, 145, 162, 179, 196, 213, 230, 247];

pub const FRAME_WIDTH: usize = 320;
pub const FRAME_HEIGHT: usize = 224;

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum DmaTarget {
    Vram,
    Cram,
    Vsram,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct DmaRequest {
    pub source: u32,
    pub target_addr: u16,
    pub length_words: u16,
    pub target: DmaTarget,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpriteDebugInfo {
    pub index: u8,
    pub x: i16,
    pub y: i16,
    pub width: u8,
    pub height: u8,
    pub tile: u16,
    pub palette: u8,
    pub priority: bool,
    pub hflip: bool,
    pub vflip: bool,
    pub link: u8,
}

#[derive(Debug, Clone, Copy, Default)]
struct SpritePixel {
    front_color_idx: u8,
    front_priority: bool,
    back_color_idx: u8,
    back_priority: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vdp {
    pub vram: Vec<u8>,
    pub cram: Vec<u8>,
    pub vsram: Vec<u8>,
    pub framebuffer: Vec<u32>,
    pub registers: [u8; 0x20],
    pub status: u16,
    pub h_counter: u16,
    pub v_counter: u16,
    pub address: u16,
    pub code: u8,
    pub pending_command: Option<u16>,
    pub pending_dma: Option<DmaRequest>,
    pub scanline: u16,
    pub frame: u64,
    auto_increment: u16,
    pub hint_counter: u16,
    pub vblank_flag: bool,
    /// Z80 /INT signal: fires at VBlank regardless of VINT_EN (R1 bit 5).
    /// On real hardware, Z80 /INT is directly connected to the VBlank output.
    pub z80_vblank_flag: bool,
    pub hblank_flag: bool,
    pub data_write_count: u64,
    pub ctrl_write_count: u64,
    dma_fill_pending: bool,
    pub dma_68k_count: u64,
    pub dma_68k_total_words: u64,
    pub dma_fill_count: u64,
    pub dma_copy_count: u64,
    pub last_dma_target_addr: u16,
    pub last_dma_source: u32,
    pub last_dma_length: u16,
    /// Debug: VSRAM[0] value read at each scanline during rendering
    pub debug_scanline_vsram_a: Vec<u16>,
    /// Debug: count of read_status calls that returned VBlank=1
    #[serde(default)]
    pub debug_read_status_vblank_count: u64,
    /// Debug: total read_status calls
    #[serde(default)]
    pub debug_read_status_total: u64,
}

impl Default for Vdp {
    fn default() -> Self {
        Self {
            vram: vec![0; 64 * 1024],
            cram: vec![0; 128],
            vsram: vec![0; 80],
            framebuffer: vec![0; FRAME_WIDTH * FRAME_HEIGHT],
            registers: [0; 0x20],
            status: 0x3400,
            h_counter: 0,
            v_counter: 0,
            address: 0,
            code: 0,
            pending_command: None,
            pending_dma: None,
            scanline: 0,
            frame: 0,
            auto_increment: 2,
            hint_counter: 0,
            vblank_flag: false,
            z80_vblank_flag: false,
            hblank_flag: false,
            data_write_count: 0,
            ctrl_write_count: 0,
            dma_fill_pending: false,
            dma_68k_count: 0,
            dma_68k_total_words: 0,
            dma_fill_count: 0,
            dma_copy_count: 0,
            last_dma_target_addr: 0,
            last_dma_source: 0,
            last_dma_length: 0,
            debug_scanline_vsram_a: vec![0; FRAME_HEIGHT],
            debug_read_status_vblank_count: 0,
            debug_read_status_total: 0,
        }
    }
}

impl Vdp {
    pub fn reset(&mut self) {
        *self = Self::default();
    }

    // Register helpers
    fn scroll_a_addr(&self) -> usize { ((self.registers[2] as usize) & 0x38) << 10 }
    fn scroll_b_addr(&self) -> usize { ((self.registers[4] as usize) & 0x07) << 13 }
    fn window_addr(&self) -> usize {
        // In H40 mode bit 1 is forced to 0 (mask 0x3C); in H32 use 0x3E
        let mask = if self.h40_mode() { 0x3C } else { 0x3E };
        ((self.registers[3] as usize) & mask) << 10
    }
    fn sprite_table_addr(&self) -> usize {
        // In H40 mode bit 0 is forced to 0 (mask 0x7E); in H32 use 0x7F
        let mask = if self.h40_mode() { 0x7E } else { 0x7F };
        ((self.registers[5] as usize) & mask) << 9
    }
    fn hscroll_addr(&self) -> usize  { ((self.registers[0x0D] as usize) & 0x3F) << 10 }
    fn bg_color_index(&self) -> u8   { self.registers[7] & 0x3F }
    fn hscroll_mode(&self) -> u8     { self.registers[0x0B] & 0x03 }
    fn vscroll_mode(&self) -> u8     { (self.registers[0x0B] >> 2) & 0x01 }
    fn display_enabled(&self) -> bool { (self.registers[1] & 0x40) != 0 }
    fn vint_enabled(&self) -> bool   { (self.registers[1] & 0x20) != 0 }
    fn hint_enabled(&self) -> bool   { (self.registers[0] & 0x10) != 0 }
    fn h40_mode(&self) -> bool       { (self.registers[0x0C] & 0x81) != 0 }
    fn interlace(&self) -> bool      { (self.registers[0x0C] & 0x02) != 0 }
    fn interlace_double(&self) -> bool  { self.interlace() && (self.registers[0x0C] & 0x04) != 0 }
    fn shadow_highlight_enabled(&self) -> bool { (self.registers[0x0C] & 0x08) != 0 }
    /// Palette select bit (reg 1 bit 2). When cleared, only the lowest bit
    /// of each color intensity has effect, selecting between half and minimum.
    fn palette_select(&self) -> bool { (self.registers[1] & 0x04) != 0 }

    fn scroll_size(&self) -> (usize, usize) {
        let reg = self.registers[0x10];
        let w = match reg & 0x03 {
            0 => 32, 1 => 64, 3 => 128, _ => 32,
        };
        let h = match (reg >> 4) & 0x03 {
            0 => 32, 1 => 64, 3 => 128, _ => 32,
        };
        (w, h)
    }

    fn cram_color(&self, index: u8, shadow: bool, highlight: bool) -> u32 {
        let idx = (index as usize) * 2;
        if idx + 1 >= self.cram.len() { return 0xFF000000; }
        let word = ((self.cram[idx] as u16) << 8) | self.cram[idx + 1] as u16;
        let mut b3 = ((word >> 9) & 0x07) as usize;
        let mut g3 = ((word >> 5) & 0x07) as usize;
        let mut r3 = ((word >> 1) & 0x07) as usize;
        // Palette select bit (reg 1 bit 2): when cleared, only the lowest
        // bit of each intensity value is effective, mapped to half intensity.
        if !self.palette_select() {
            r3 = (r3 & 0x01) << 2;
            g3 = (g3 & 0x01) << 2;
            b3 = (b3 & 0x01) << 2;
        }
        let table = if shadow == highlight { &NORMAL_COLOR } else if shadow { &SHADOW_COLOR } else { &HIGHLIGHT_COLOR };
        0xFF000000 | ((table[r3] as u32) << 16) | ((table[g3] as u32) << 8) | table[b3] as u32
    }

    fn cram_to_argb(&self, index: u8) -> u32 {
        self.cram_color(index, false, false)
    }

    fn left_column_blank(&self) -> bool { (self.registers[0] & 0x20) != 0 }

    fn get_tile_pixel(&self, tile_addr: usize, px: usize, py: usize) -> u8 {
        let row_offset = tile_addr + py * 4;
        let byte_idx = row_offset + (px >> 1);
        if byte_idx >= self.vram.len() { return 0; }
        let byte = self.vram[byte_idx];
        if (px & 1) == 0 { byte >> 4 } else { byte & 0x0F }
    }

    /// Read VSRAM with Exodus-accurate boundary handling: addresses >= 0x50
    /// return the ANDed result of the last two VSRAM entries.
    fn read_vsram_word(&self, addr: usize) -> u16 {
        if addr + 1 < 0x50 {
            Self::read_vram_word(&self.vsram, addr)
        } else {
            let a = Self::read_vram_word(&self.vsram, 0x4C);
            let b = Self::read_vram_word(&self.vsram, 0x4E);
            a & b
        }
    }

    fn render_scroll_line(&self, plane_addr: usize, hscroll: i32, vscroll_full: i32, vsram_offset: usize, per_col_vscroll: bool, y: usize, line_buf: &mut [(u8, bool)]) {
        let (sw, sh) = self.scroll_size();
        let screen_w = if self.h40_mode() { 320 } else { 256 };
        let interlace2 = self.interlace_double();
        let rows_per_tile: usize = if interlace2 { 16 } else { 8 };
        let effective_sh = if interlace2 { sh * 2 } else { sh };

        for x in 0..screen_w {
            // Per-2-column vscroll: each 16-pixel (2-cell) column uses its own VSRAM entry
            let vscroll_raw = if per_col_vscroll {
                let col = x / 16;
                self.read_vsram_word(col * 4 + vsram_offset) as i32
            } else {
                vscroll_full
            };
            // Mask vscroll to 10 bits (11 bits in interlace mode 2)
            let vscroll_mask = if interlace2 { 0x7FF } else { 0x3FF };
            let vscroll = vscroll_raw & vscroll_mask;

            // In interlace mode 2, effective row = row*2 + odd_frame
            let effective_y = if interlace2 {
                (y as i32) * 2 + (if (self.status & 0x0004) != 0 { 1 } else { 0 })
            } else {
                y as i32
            };

            let scrolled_y = ((effective_y + vscroll) as usize) % (effective_sh * 8);
            let tile_row = scrolled_y / rows_per_tile;
            let py = scrolled_y % rows_per_tile;

            let scrolled_x = ((x as i32 - hscroll) as usize) % (sw * 8);
            let tile_col = scrolled_x / 8;
            let px = scrolled_x % 8;

            let entry_addr = plane_addr + (tile_row * sw + tile_col) * 2;
            if entry_addr + 1 >= self.vram.len() { continue; }
            let entry = ((self.vram[entry_addr] as u16) << 8) | self.vram[entry_addr + 1] as u16;

            let tile_index = (entry & 0x07FF) as usize;
            let palette = ((entry >> 13) & 0x03) as u8;
            let priority = (entry & 0x8000) != 0;
            let hflip = (entry & 0x0800) != 0;
            let vflip = (entry & 0x1000) != 0;

            let fx = if hflip { 7 - px } else { px };
            let fy = if vflip { (rows_per_tile - 1) - py } else { py };
            // In interlace mode 2, patterns are 8x16; tile size = 64 bytes
            let bytes_per_tile = rows_per_tile * 4;
            let tile_addr = tile_index * bytes_per_tile;
            let pixel = self.get_tile_pixel(tile_addr, fx, fy);

            if x < screen_w {
                let color_idx = if pixel != 0 { palette * 16 + pixel } else { 0 };
                line_buf[x] = (color_idx, priority);
            }
        }
    }

    fn compose_color_idx(bg_idx: u8, plane_b: (u8, bool), plane_a: (u8, bool), sprite: (u8, bool)) -> u8 {
        let (b_idx, b_pri) = plane_b;
        let (a_idx, a_pri) = plane_a;
        let (s_idx, s_pri) = sprite;

        if s_pri && s_idx != 0 {
            s_idx
        } else if a_pri && a_idx != 0 {
            a_idx
        } else if b_pri && b_idx != 0 {
            b_idx
        } else if s_idx != 0 {
            s_idx
        } else if a_idx != 0 {
            a_idx
        } else if b_idx != 0 {
            b_idx
        } else {
            bg_idx
        }
    }

    fn render_sprites_line(&mut self, y: usize, line_buf: &mut [SpritePixel]) {
        let sat_base = self.sprite_table_addr();
        let screen_w = if self.h40_mode() { 320usize } else { 256 };
        let max_sprites = if self.h40_mode() { 80 } else { 64 };
        let max_per_line = if self.h40_mode() { 20 } else { 16 };
        let max_dots: usize = if self.h40_mode() { 320 } else { 256 };
        let interlace2 = self.interlace_double();
        let sprite_v_offset: i32 = if interlace2 { 256 } else { 128 };

        let mut sprites_on_line = 0;
        let mut dots_rendered: usize = 0;
        let mut link = 0u8;

        for _ in 0..max_sprites {
            let entry_base = sat_base + link as usize * 8;
            if entry_base + 7 >= self.vram.len() { break; }

            let y_pos = (((self.vram[entry_base] as u16) << 8) | self.vram[entry_base + 1] as u16) & 0x03FF;
            let sprite_y = y_pos as i32 - sprite_v_offset;
            let size_byte = self.vram[entry_base + 2];
            let h_cells = ((size_byte >> 2) & 0x03) as i32 + 1;
            let v_cells = (size_byte & 0x03) as i32 + 1;
            let rows_per_tile_s: i32 = if interlace2 { 16 } else { 8 };
            let sprite_h = v_cells * rows_per_tile_s;

            let next_link = self.vram[entry_base + 3] & 0x7F;

            let attr = ((self.vram[entry_base + 4] as u16) << 8) | self.vram[entry_base + 5] as u16;
            let x_pos = (((self.vram[entry_base + 6] as u16) << 8) | self.vram[entry_base + 7] as u16) & 0x01FF;
            let sprite_x = x_pos as i32 - 128;

            let tile_index = (attr & 0x07FF) as usize;
            let palette = ((attr >> 13) & 0x03) as u8;
            let priority = (attr & 0x8000) != 0;
            let hflip = (attr & 0x0800) != 0;
            let vflip = (attr & 0x1000) != 0;

            let iy = y as i32;
            if iy >= sprite_y && iy < sprite_y + sprite_h {
                sprites_on_line += 1;
                if sprites_on_line > max_per_line {
                    // Set sprite overflow flag (status bit 6)
                    self.status |= 0x0040;
                    break;
                }

                // Sprite masking: x_pos == 0 (raw value, not adjusted) stops
                // rendering remaining sprites on this line, but only if at
                // least one other sprite has already been found on this line
                if x_pos == 0 && sprites_on_line >= 2 {
                    break;
                }

                // In interlace mode 2, effective sprite row = row*2 + odd_frame
                let sprite_row = if interlace2 {
                    let base_row = (iy - sprite_y) * 2 + (if (self.status & 0x0004) != 0 { 1 } else { 0 });
                    if vflip { sprite_h * 2 - 1 - base_row } else { base_row }
                } else {
                    if vflip { sprite_h - 1 - (iy - sprite_y) } else { iy - sprite_y }
                };
                let py = sprite_row as usize;
                let rows_per_tile_u = rows_per_tile_s as usize;
                let cell_row = py / rows_per_tile_u;
                let row_in_cell = py % rows_per_tile_u;

                // Check dot overflow before rendering this sprite's pixels
                if dots_rendered >= max_dots {
                    self.status |= 0x0040; // sprite overflow flag
                    break;
                }

                for cx in 0..h_cells {
                    let cell_col = if hflip { (h_cells - 1 - cx) as usize } else { cx as usize };
                    let tile = tile_index + cell_col * v_cells as usize + cell_row;
                    let bytes_per_tile_s = rows_per_tile_u * 4;
                    let tile_addr = tile * bytes_per_tile_s;

                    for px_in_cell in 0..8 {
                        let fx = if hflip { 7 - px_in_cell } else { px_in_cell };
                        let pixel = self.get_tile_pixel(tile_addr, fx, row_in_cell);
                        let screen_x = sprite_x + cx * 8 + px_in_cell as i32;

                        dots_rendered += 1;
                        if pixel != 0 && screen_x >= 0 && (screen_x as usize) < screen_w {
                            let sx = screen_x as usize;
                            let color_idx = palette * 16 + pixel;
                            let cell = &mut line_buf[sx];
                            if cell.front_color_idx == 0 {
                                cell.front_color_idx = color_idx;
                                cell.front_priority = priority;
                            } else {
                                if cell.back_color_idx == 0 {
                                    cell.back_color_idx = color_idx;
                                    cell.back_priority = priority;
                                }
                                // Sprite collision: two sprites have non-transparent
                                // pixels at the same screen position
                                self.status |= 0x0020;
                            }
                        }
                    }
                }
            }

            link = next_link;
            if link == 0 { break; }
        }
    }

    pub fn step_scanline(&mut self) {
        self.v_counter = self.scanline;
        self.h_counter = 0;
        self.hblank_flag = false;

        let y = self.scanline as usize;

        if y < FRAME_HEIGHT {
            if self.display_enabled() {
                self.render_line(y);
            } else {
                let bg = self.cram_to_argb(self.bg_color_index());
                for x in 0..FRAME_WIDTH {
                    self.framebuffer[y * FRAME_WIDTH + x] = bg;
                }
            }

            // H-interrupt counter
            if self.hint_counter == 0 {
                self.hint_counter = self.registers[0x0A] as u16;
                if self.hint_enabled() {
                    self.hblank_flag = true;
                }
            } else {
                self.hint_counter -= 1;
            }
        } else {
            // During VBlank, reload counter each line
            self.hint_counter = self.registers[0x0A] as u16;
        }

        self.scanline = self.scanline.wrapping_add(1);
        if self.scanline == 224 {
            self.status |= 0x0008; // VBlank flag in status
            self.status |= 0x0080; // F flag (VInt pending)
            // Z80 /INT is directly connected to VBlank, independent of VINT_EN
            self.z80_vblank_flag = true;
            if self.vint_enabled() {
                self.vblank_flag = true;
            }
        }
        if self.scanline >= 262 {
            self.scanline = 0;
            self.frame += 1;
            self.status ^= 0x0004; // Toggle odd/even frame
            self.status &= !0x0008; // Clear VBlank
        }
    }

    fn render_line(&mut self, y: usize) {
        let screen_w = if self.h40_mode() { 320 } else { 256 };
        let bg_idx = self.bg_color_index();
        let bg_color = self.cram_to_argb(bg_idx);

        // Window plane parameters
        let win_h_pos = self.registers[0x11];
        let win_v_pos = self.registers[0x12];
        let win_right = (win_h_pos & 0x80) != 0; // 1=window is on the right side
        let win_h_cell = (win_h_pos & 0x1F) as usize * 2; // 2-cell units
        let win_down  = (win_v_pos & 0x80) != 0; // 1=window is below the split
        let win_v_cell = (win_v_pos & 0x1F) as usize; // cell rows
        // Determine if window covers this scanline vertically
        let y_cell = y / 8;
        let win_covers_full_line = if win_v_cell == 0 {
            // VP=0: DOWN=0 means "top 0 rows" = none; DOWN=1 means "from row 0 down" = all
            win_down
        } else if win_down {
            y_cell >= win_v_cell
        } else {
            y_cell < win_v_cell
        };

        // For each pixel, determine if window applies
        // Window replaces Plane A where it covers
        let win_active = |x: usize| -> bool {
            if win_covers_full_line {
                return true;
            }
            if win_h_cell == 0 {
                // HP=0: RIGHT=0 means "left 0 cells" = none; RIGHT=1 means "from cell 0 right" = all
                return win_right;
            }
            if win_right {
                x / 8 >= win_h_cell
            } else {
                x / 8 < win_h_cell
            }
        };

        // Hscroll
        let hs_addr = self.hscroll_addr();
        // Hscroll modes: 0=full screen, 1=prohibited (invalid, treat as full screen),
        // 2=per-tile (8-pixel row), 3=per-line
        let (hscroll_a, hscroll_b) = match self.hscroll_mode() {
            0 | 1 => {
                let a = (Self::read_vram_word(&self.vram, hs_addr) & 0x03FF) as i16 as i32;
                let b = (Self::read_vram_word(&self.vram, hs_addr + 2) & 0x03FF) as i16 as i32;
                (a, b)
            }
            2 => {
                let row = (y & !7) * 4;
                let a = (Self::read_vram_word(&self.vram, hs_addr + row) & 0x03FF) as i16 as i32;
                let b = (Self::read_vram_word(&self.vram, hs_addr + row + 2) & 0x03FF) as i16 as i32;
                (a, b)
            }
            _ => {
                let row = y * 4;
                let a = (Self::read_vram_word(&self.vram, hs_addr + row) & 0x03FF) as i16 as i32;
                let b = (Self::read_vram_word(&self.vram, hs_addr + row + 2) & 0x03FF) as i16 as i32;
                (a, b)
            },
        };

        // Vscroll
        let per_col_vscroll = self.vscroll_mode() == 1;
        let vscroll_a = self.read_vsram_word(0) as i32;
        let vscroll_b = self.read_vsram_word(2) as i32;

        // Debug: record VSRAM[0] for this scanline
        if y < self.debug_scanline_vsram_a.len() {
            self.debug_scanline_vsram_a[y] = vscroll_a as u16;
        }

        let mut plane_b_buf = vec![(0u8, false); screen_w];
        let mut plane_a_buf = vec![(0u8, false); screen_w];
        let mut sprite_buf = vec![SpritePixel::default(); screen_w];

        self.render_scroll_line(self.scroll_b_addr(), hscroll_b, vscroll_b, 2, per_col_vscroll, y, &mut plane_b_buf);

        // Render Plane A and Window plane
        // Window plane has no scroll; it uses a fixed nametable layout
        let win_base = self.window_addr();
        let has_any_window = (0..screen_w).any(win_active);

        if has_any_window {
            // Render scroll A only for non-window pixels
            self.render_scroll_line(self.scroll_a_addr(), hscroll_a, vscroll_a, 0, per_col_vscroll, y, &mut plane_a_buf);
            // Overwrite window area with window plane tiles
            let win_row = y / 8;
            let win_py = y % 8;
            // Window nametable stride is always based on screen width (64 cells for H40, 32 for H32)
            let win_stride = if self.h40_mode() { 64 } else { 32 };
            for x in 0..screen_w {
                if win_active(x) {
                    let win_col = x / 8;
                    let win_px = x % 8;
                    let entry_addr = win_base + (win_row * win_stride + win_col) * 2;
                    if entry_addr + 1 < self.vram.len() {
                        let entry = ((self.vram[entry_addr] as u16) << 8) | self.vram[entry_addr + 1] as u16;
                        let tile_index = (entry & 0x07FF) as usize;
                        let palette = ((entry >> 13) & 0x03) as u8;
                        let priority = (entry & 0x8000) != 0;
                        let hflip = (entry & 0x0800) != 0;
                        let vflip = (entry & 0x1000) != 0;
                        let fx = if hflip { 7 - win_px } else { win_px };
                        let fy = if vflip { 7 - win_py } else { win_py };
                        let pixel = self.get_tile_pixel(tile_index * 32, fx, fy);
                        let color_idx = if pixel != 0 { palette * 16 + pixel } else { 0 };
                        plane_a_buf[x] = (color_idx, priority);
                    }
                }
            }
        } else {
            self.render_scroll_line(self.scroll_a_addr(), hscroll_a, vscroll_a, 0, per_col_vscroll, y, &mut plane_a_buf);
        }

        self.render_sprites_line(y, &mut sprite_buf);

        let sh_mode = self.shadow_highlight_enabled();

        // Priority compositing
        for x in 0..screen_w.min(FRAME_WIDTH) {
            let (b_idx, b_pri) = plane_b_buf[x];
            let (a_idx, a_pri) = plane_a_buf[x];
            let sprite = sprite_buf[x];
            let front_sprite = (sprite.front_color_idx, sprite.front_priority);

            if sh_mode {
                let front_ci = sprite.front_color_idx;
                let is_shadow_op = (front_ci & 0x3F) == 0x3F; // palette 3, index 15
                let is_highlight_op = (front_ci & 0x3F) == 0x3E; // palette 3, index 14
                let sprite_is_normal_intensity = (front_ci & 0x0F) == 0x0E && !is_highlight_op;

                let found_sprite = front_sprite.0 != 0;
                let found_a = a_idx != 0;
                let found_b = b_idx != 0;

                // Exodus lookup-table logic, expanded directly.
                let (layer_idx, color_idx, mut shadow, mut highlight);

                if found_sprite && front_sprite.1 && !is_shadow_op && !is_highlight_op {
                    layer_idx = 0;
                    color_idx = front_sprite.0;
                    shadow = false;
                    highlight = false;
                } else if found_a && a_pri {
                    layer_idx = 1;
                    color_idx = a_idx;
                    shadow = false;
                    highlight = false;
                    if found_sprite && front_sprite.1 && is_shadow_op { shadow = true; }
                    else if found_sprite && front_sprite.1 && is_highlight_op { highlight = true; }
                } else if found_b && b_pri {
                    layer_idx = 2;
                    color_idx = b_idx;
                    shadow = false;
                    highlight = false;
                    if found_sprite && front_sprite.1 && is_shadow_op { shadow = true; }
                    else if found_sprite && front_sprite.1 && is_highlight_op { highlight = true; }
                } else if found_sprite && !is_shadow_op && !is_highlight_op {
                    layer_idx = 0;
                    color_idx = front_sprite.0;
                    shadow = !a_pri && !b_pri;
                    highlight = false;
                } else if found_a {
                    layer_idx = 1;
                    color_idx = a_idx;
                    shadow = !a_pri && !b_pri;
                    highlight = false;
                    if is_shadow_op { shadow = true; }
                    if is_highlight_op { highlight = true; }
                } else if found_b {
                    layer_idx = 2;
                    color_idx = b_idx;
                    shadow = !a_pri && !b_pri;
                    highlight = false;
                    if is_shadow_op { shadow = true; }
                    if is_highlight_op { highlight = true; }
                } else {
                    layer_idx = 3;
                    color_idx = bg_idx;
                    shadow = !a_pri && !b_pri;
                    highlight = false;
                    if is_shadow_op { shadow = true; }
                    if is_highlight_op { highlight = true; }
                }

                // Sprite palette index 14 on palette rows other than row 3 stays normal.
                if layer_idx == 0 && sprite_is_normal_intensity {
                    shadow = false;
                    highlight = false;
                }

                // Shadow and highlight cancel each other out (Exodus-verified)
                if shadow && highlight {
                    shadow = false;
                    highlight = false;
                }

                let final_idx = if color_idx != 0 { color_idx } else { bg_idx };
                self.framebuffer[y * FRAME_WIDTH + x] = self.cram_color(final_idx, shadow, highlight);
            } else {
                // Normal compositing (no shadow/highlight)
                let color_idx = Self::compose_color_idx(bg_idx, (b_idx, b_pri), (a_idx, a_pri), front_sprite);

                let c = if color_idx != 0 { self.cram_to_argb(color_idx) } else { bg_color };
                self.framebuffer[y * FRAME_WIDTH + x] = c;
            }
        }

        // Fill remaining pixels if H32 mode
        for x in screen_w..FRAME_WIDTH {
            self.framebuffer[y * FRAME_WIDTH + x] = bg_color;
        }

        // Left column blanking: Register 0 bit 5 blanks leftmost 8 pixels
        if self.left_column_blank() {
            let blank = self.cram_to_argb(bg_idx);
            for x in 0..8.min(FRAME_WIDTH) {
                self.framebuffer[y * FRAME_WIDTH + x] = blank;
            }
        }
    }

    pub fn run_frame(&mut self) {
        for _ in 0..262 {
            self.step_scanline();
        }
    }

    pub fn read_status(&mut self) -> u16 {
        let s = self.status;
        self.debug_read_status_total += 1;
        if s & 0x0008 != 0 {
            self.debug_read_status_vblank_count += 1;
        }
        self.pending_command = None;
        // Reading status auto-acknowledges pending interrupt flags
        self.vblank_flag = false;
        self.hblank_flag = false;
        // Clear F flag (VInt pending), sprite collision (bit 5), and sprite overflow (bit 6)
        self.status &= !(0x0080 | 0x0040 | 0x0020);
        s
    }

    pub fn read_hv_counter(&self) -> u16 {
        ((self.v_counter & 0xFF) << 8) | (self.h_counter & 0xFF)
    }

    pub fn write_data_port(&mut self, value: u16) {
        self.pending_command = None;
        self.data_write_count += 1;
        let bytes = value.to_be_bytes();
        match self.code & 0x0F {
            0x01 => Self::write_pair(&mut self.vram, self.address as usize, bytes),
            0x03 => Self::write_pair(&mut self.cram, self.address as usize, bytes),
            0x05 => Self::write_pair(&mut self.vsram, self.address as usize, bytes),
            _ => Self::write_pair(&mut self.vram, self.address as usize, bytes),
        }

        // Handle DMA fill: after the initial data write, fill remaining bytes
        if self.dma_fill_pending {
            self.dma_fill_pending = false;
            let fill_byte = bytes[0]; // high byte of written value
            let dma_len = ((self.registers[20] as u16) << 8) | self.registers[19] as u16;
            let inc = self.registers[0x0F] as u16;
            // First byte was written above; fill remaining (len-1) bytes
            let mut addr = self.address.wrapping_add(inc);
            for _ in 1..dma_len {
                let target = match self.code & 0x0F {
                    0x03 => &mut self.cram,
                    0x05 => &mut self.vsram,
                    _ => &mut self.vram,
                };
                let a = (addr as usize) & (target.len() - 1);
                // DMA fill writes to the odd byte (address XOR 1 for VRAM)
                if (self.code & 0x0F) != 0x03 && (self.code & 0x0F) != 0x05 {
                    let a_odd = a ^ 1;
                    if a_odd < target.len() { target[a_odd] = fill_byte; }
                } else {
                    if a < target.len() { target[a] = fill_byte; }
                }
                addr = addr.wrapping_add(inc);
            }
            self.address = addr;
            // Clear DMA length registers
            self.registers[19] = 0;
            self.registers[20] = 0;
            return;
        }

        let inc = self.registers[0x0F] as u16;
        self.address = self.address.wrapping_add(inc);
    }

    pub fn read_data_port(&mut self) -> u16 {
        self.pending_command = None;
        let value = match self.code & 0x0F {
            0x00 => Self::read_pair(&self.vram, self.address as usize),
            0x04 => Self::read_pair(&self.vsram, self.address as usize),
            0x08 => Self::read_pair(&self.cram, self.address as usize),
            _ => Self::read_pair(&self.vram, self.address as usize),
        };
        let inc = self.registers[0x0F] as u16;
        self.address = self.address.wrapping_add(inc);
        value
    }

    pub fn write_control_port(&mut self, value: u16) {
        self.ctrl_write_count += 1;
        // Register writes (0x8xxx) always take priority and reset pending state
        if (value & 0xC000) == 0x8000 {
            let _had_pending = self.pending_command.is_some();
            self.pending_command = None;
            let reg = ((value >> 8) & 0x1F) as usize;
            let val = (value & 0xFF) as u8;
            if reg < self.registers.len() {
                self.registers[reg] = val;
            }
            if reg == 0x0F {
                self.auto_increment = val as u16;
            }
            // Register write also sets the code/address from the first 2 bits
            self.code = (self.code & 0xFC) | ((value >> 14) as u8 & 0x03);
            return;
        }

        if let Some(first) = self.pending_command.take() {
            let full = ((first as u32) << 16) | value as u32;
            let cd_low = ((full >> 30) & 0x03) as u8;  // CD1:CD0
            let cd_high = ((full >> 4) & 0x0F) as u8;  // CD5:CD4:CD3:CD2 from bits 7:4 of second word
            self.code = cd_low | (cd_high << 2);
            self.address = (((full >> 16) & 0x3FFF) as u16) | ((full & 0x0003) as u16) << 14;
            // DMA is triggered when CD5 bit is set AND DMA enable bit (reg 1 bit 4) is set
            if (self.code & 0x20) != 0 && (self.registers[1] & 0x10) != 0 {
                let mode = (self.registers[23] >> 6) & 0x03;
                if mode == 3 {
                    // DMA copy (VRAM internal)
                    self.dma_copy_count += 1;
                    // DMA copy (VRAM internal) - byte by byte, dst uses auto-increment, writes to addr^1
                    let len = ((self.registers[20] as u16) << 8) | self.registers[19] as u16;
                    let inc = self.registers[0x0F] as u16;
                    let mut s_addr = ((self.registers[22] as u16) << 8) | self.registers[21] as u16;
                    let mut d_addr = self.address;
                    for _ in 0..len {
                        let s = (s_addr as usize) & 0xFFFF;
                        let d = ((d_addr as usize) ^ 1) & 0xFFFF;
                        if s < self.vram.len() && d < self.vram.len() {
                            self.vram[d] = self.vram[s];
                        }
                        s_addr = s_addr.wrapping_add(1);
                        d_addr = d_addr.wrapping_add(inc);
                    }
                    self.address = d_addr;
                } else if mode == 2 {
                    // DMA fill - triggered on next data port write
                    self.dma_fill_pending = true;
                    self.dma_fill_count += 1;
                } else {
                    // DMA from 68K memory
                    let dma_len = ((self.registers[20] as u16) << 8) | self.registers[19] as u16;
                    let dma_src = ((self.registers[23] as u32 & 0x7F) << 17)
                        | ((self.registers[22] as u32) << 9)
                        | ((self.registers[21] as u32) << 1);
                    let target = match self.code & 0x07 {
                        0x03 => DmaTarget::Cram,
                        0x05 => DmaTarget::Vsram,
                        _ => DmaTarget::Vram,
                    };
                    self.last_dma_target_addr = self.address;
                    self.last_dma_source = dma_src;
                    self.last_dma_length = dma_len;
                    self.pending_dma = Some(DmaRequest {
                        source: dma_src,
                        target_addr: self.address,
                        length_words: dma_len,
                        target,
                    });
                }
            }
        } else {
            self.pending_command = Some(value);
        }
    }

    pub fn consume_dma_request(&mut self) -> Option<DmaRequest> {
        self.pending_dma.take()
    }

    pub fn execute_dma_from_memory<F>(&mut self, request: DmaRequest, mut read_byte: F)
    where
        F: FnMut(u32) -> u8,
    {
        self.dma_68k_count += 1;
        self.dma_68k_total_words += request.length_words as u64;
        let word_count = request.length_words as usize;
        let inc = self.registers[0x0F] as u16;
        let mut dst_addr = request.target_addr;
        for w in 0..word_count {
            let src_base = request.source.wrapping_add((w * 2) as u32);
            let hi = read_byte(src_base);
            let lo = read_byte(src_base.wrapping_add(1));
            let mask = match request.target {
                DmaTarget::Vram => 0xFFFF,
                DmaTarget::Cram => 0x7F,
                DmaTarget::Vsram => 0x4F,
            };
            let a = (dst_addr as usize) & mask;
            match request.target {
                DmaTarget::Vram => {
                    if a < self.vram.len() { self.vram[a] = hi; }
                    if a + 1 < self.vram.len() { self.vram[a + 1] = lo; }
                }
                DmaTarget::Cram => {
                    if a < self.cram.len() { self.cram[a] = hi; }
                    if a + 1 < self.cram.len() { self.cram[a + 1] = lo; }
                }
                DmaTarget::Vsram => {
                    if a < self.vsram.len() { self.vsram[a] = hi; }
                    if a + 1 < self.vsram.len() { self.vsram[a + 1] = lo; }
                }
            }
            dst_addr = dst_addr.wrapping_add(inc);
        }
        self.address = dst_addr;
    }

    fn write_pair(target: &mut [u8], addr: usize, bytes: [u8; 2]) {
        let addr = addr & (target.len() - 1);
        if addr < target.len() { target[addr] = bytes[0]; }
        if addr + 1 < target.len() { target[addr + 1] = bytes[1]; }
    }

    fn read_pair(target: &[u8], addr: usize) -> u16 {
        let addr = addr & (target.len().saturating_sub(1));
        let hi = target.get(addr).copied().unwrap_or(0) as u16;
        let lo = target.get(addr + 1).copied().unwrap_or(0) as u16;
        (hi << 8) | lo
    }

    fn read_vram_word(data: &[u8], addr: usize) -> u16 {
        if addr + 1 >= data.len() { return 0; }
        ((data[addr] as u16) << 8) | data[addr + 1] as u16
    }

    // ===== Debug rendering =====

    /// Render entire scroll plane (A or B) as ARGB framebuffer.
    /// Returns (width_px, height_px, argb_pixels).
    pub fn debug_render_plane(&self, plane: char) -> (usize, usize, Vec<u32>) {
        let (sw, sh) = self.scroll_size();
        let w = sw * 8;
        let h = sh * 8;
        let base = match plane {
            'A' | 'a' => self.scroll_a_addr(),
            'W' | 'w' => self.window_addr(),
            _ => self.scroll_b_addr(),
        };
        let mut buf = vec![0xFF000000u32; w * h];
        for ty in 0..sh {
            for tx in 0..sw {
                let entry_addr = base + (ty * sw + tx) * 2;
                if entry_addr + 1 >= self.vram.len() { continue; }
                let entry = ((self.vram[entry_addr] as u16) << 8) | self.vram[entry_addr + 1] as u16;
                let tile_index = (entry & 0x07FF) as usize;
                let palette = ((entry >> 13) & 0x03) as u8;
                let hflip = (entry & 0x0800) != 0;
                let vflip = (entry & 0x1000) != 0;
                let tile_addr = tile_index * 32;
                for py in 0..8 {
                    for px in 0..8 {
                        let fx = if hflip { 7 - px } else { px };
                        let fy = if vflip { 7 - py } else { py };
                        let pixel = self.get_tile_pixel(tile_addr, fx, fy);
                        let color = if pixel != 0 {
                            self.cram_to_argb(palette * 16 + pixel)
                        } else {
                            self.cram_to_argb(self.bg_color_index())
                        };
                        buf[(ty * 8 + py) * w + tx * 8 + px] = color;
                    }
                }
            }
        }
        (w, h, buf)
    }

    /// Render all tiles in VRAM as an ARGB tile sheet.
    /// Uses the specified palette (0-3). Returns (width, height, argb_pixels).
    pub fn debug_render_tiles(&self, palette: u8) -> (usize, usize, Vec<u32>) {
        let total_tiles = self.vram.len() / 32; // 2048 tiles max in 64KB VRAM
        let cols = 32;
        let rows = (total_tiles + cols - 1) / cols;
        let w = cols * 8;
        let h = rows * 8;
        let mut buf = vec![0xFF000000u32; w * h];
        let pal = palette & 3;
        for t in 0..total_tiles {
            let tile_addr = t * 32;
            let tcol = t % cols;
            let trow = t / cols;
            for py in 0..8 {
                for px in 0..8 {
                    let pixel = self.get_tile_pixel(tile_addr, px, py);
                    let color = if pixel != 0 {
                        self.cram_to_argb(pal * 16 + pixel)
                    } else {
                        0xFF000000
                    };
                    buf[(trow * 8 + py) * w + tcol * 8 + px] = color;
                }
            }
        }
        (w, h, buf)
    }

    /// Return CRAM as 64 ARGB colors (4 palettes × 16 entries).
    pub fn debug_cram_colors(&self) -> Vec<u32> {
        (0..64).map(|i| self.cram_to_argb(i as u8)).collect()
    }

    /// Return sprite attribute entries from SAT.
    pub fn debug_sprites(&self) -> Vec<SpriteDebugInfo> {
        let sat_base = self.sprite_table_addr();
        let max_sprites = if self.h40_mode() { 80 } else { 64 };
        let mut sprites = Vec::new();
        let mut link = 0u8;

        for _ in 0..max_sprites {
            let base = sat_base + link as usize * 8;
            if base + 7 >= self.vram.len() { break; }

            let y_pos = (((self.vram[base] as u16) << 8) | self.vram[base + 1] as u16) & 0x03FF;
            let size_byte = self.vram[base + 2];
            let h_cells = ((size_byte >> 2) & 0x03) + 1;
            let v_cells = (size_byte & 0x03) + 1;
            let next_link = self.vram[base + 3] & 0x7F;
            let attr = ((self.vram[base + 4] as u16) << 8) | self.vram[base + 5] as u16;
            let x_pos = (((self.vram[base + 6] as u16) << 8) | self.vram[base + 7] as u16) & 0x01FF;

            sprites.push(SpriteDebugInfo {
                index: link,
                x: x_pos as i16 - 128,
                y: y_pos as i16 - 128,
                width: h_cells,
                height: v_cells,
                tile: attr & 0x07FF,
                palette: ((attr >> 13) & 0x03) as u8,
                priority: (attr & 0x8000) != 0,
                hflip: (attr & 0x0800) != 0,
                vflip: (attr & 0x1000) != 0,
                link: next_link,
            });

            link = next_link;
            if link == 0 { break; }
        }
        sprites
    }
}

#[cfg(test)]
mod tests {
    use super::{DmaRequest, DmaTarget, Vdp};

    #[test]
    fn data_port_writes_vram() {
        let mut vdp = Vdp::default();
        vdp.code = 0x01;
        vdp.address = 0x100;
        vdp.write_data_port(0xABCD);
        assert_eq!(vdp.vram[0x100], 0xAB);
        assert_eq!(vdp.vram[0x101], 0xCD);
    }

    #[test]
    fn control_port_writes_register() {
        let mut vdp = Vdp::default();
        vdp.write_control_port(0x8104);
        assert_eq!(vdp.registers[1], 0x04);
    }

    #[test]
    fn dma_copies_into_vram() {
        let mut vdp = Vdp::default();
        vdp.registers[0x0F] = 0x02; // auto-increment = 2
        vdp.registers[19] = 0x02;
        vdp.registers[20] = 0x00;
        vdp.registers[21] = 0x00;
        vdp.registers[22] = 0x40;
        vdp.registers[23] = 0x00;
        let req = DmaRequest {
            source: 0x8000,
            target_addr: 0,
            length_words: 2,
            target: DmaTarget::Vram,
        };
        vdp.execute_dma_from_memory(req, |addr| (addr & 0xFF) as u8);
        // source bytes: 0x8000→0x00, 0x8001→0x01, 0x8002→0x02, 0x8003→0x03
        assert_eq!(vdp.vram[0], 0x00);
        assert_eq!(vdp.vram[1], 0x01);
        assert_eq!(vdp.vram[2], 0x02);
        assert_eq!(vdp.vram[3], 0x03);
    }

    #[test]
    fn tile_rendering_produces_color() {
        let mut vdp = Vdp::default();
        // Setup: enable display
        vdp.registers[1] = 0x64;
        vdp.registers[0x0C] = 0x81; // H40
        vdp.registers[0x10] = 0x01; // 64x32 scroll
        // Write a tile pattern at tile 1
        let tile_addr = 32; // tile 1 = 32 bytes
        for i in 0..32 {
            vdp.vram[tile_addr + i] = 0x11; // pixel value 1 in both nibbles
        }
        // Write scroll A nametable entry pointing to tile 1, palette 0
        let sa_addr = vdp.scroll_a_addr();
        vdp.vram[sa_addr] = 0x00;
        vdp.vram[sa_addr + 1] = 0x01;
        // Write a color (red) in CRAM index 1
        vdp.cram[2] = 0x00;
        vdp.cram[3] = 0x0E; // R=7
        vdp.step_scanline();
        // First pixel should not be background
        let pixel = vdp.framebuffer[0];
        assert_ne!(pixel, 0xFF000000);
    }

    #[test]
    fn vblank_status_bit_set_during_vblank() {
        let mut vdp = Vdp::default();
        // Advance to scanline 223 (last active line)
        for _ in 0..223 {
            vdp.step_scanline();
        }
        assert_eq!(vdp.scanline, 223);
        // VBlank not yet active
        assert_eq!(vdp.status & 0x0008, 0, "VBlank should not be set before scanline 224");

        // Advance to scanline 224 (VBlank starts)
        vdp.step_scanline();
        assert_eq!(vdp.scanline, 224);
        assert_ne!(vdp.status & 0x0008, 0, "VBlank should be set at scanline 224");

        // read_status should return with VBlank bit set
        let s = vdp.read_status();
        assert_ne!(s & 0x0008, 0, "read_status should return VBlank=1 during VBlank");

        // VBlank bit should PERSIST after read_status (only F/coll/overflow cleared)
        assert_ne!(vdp.status & 0x0008, 0, "VBlank bit should persist after read_status");

        // Advance through VBlank (scanlines 225-261)
        for _ in 225..262 {
            vdp.step_scanline();
        }
        // Still in VBlank at scanline 261
        let s2 = vdp.read_status();
        assert_ne!(s2 & 0x0008, 0, "VBlank should still be set at scanline 261");

        // Advance to scanline 262 → wraps to 0 (new frame)
        vdp.step_scanline();
        assert_eq!(vdp.scanline, 0);
        assert_eq!(vdp.status & 0x0008, 0, "VBlank should be cleared at new frame");
    }
}
