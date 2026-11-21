// Tela do Delphos, desenhada em 128x32 (o painel só mostra as 32 linhas de cima).
// O app tem uma cópia em app/delphos/ui/oled.js; o teste test_screen_parity.py compara as duas.
//
//   [mic] ATIVO              2/4    y 0-8   (faixa acesa quando o mic está mudo)
//   Spotify                  62%    y 10-17
//   [=============---------]        y 19-22
//   > Stand By Me - Ben E. King     y 24-31 (rola se não couber)
#include QMK_KEYBOARD_H
#include "delphos.h"
#include "delphos_font.h"
#include "delphos_logo.h"

#ifdef OLED_ENABLE

#define W 128
#define H 32

#define HEADER_H 9
#define NAME_Y   10
#define BAR_Y    19
#define MEDIA_Y  24
#define MEDIA_X  8

#define SPLASH_MS     2400
#define POPUP_MS      1200
#define SCROLL_MS     40
#define SCROLL_PAUSE  1500
#define ANIM_MS       360
#define TEST_MS       10000

static bool     dirty_all   = true;
static bool     dirty_media = true;
static bool     popup_on    = false;
static uint32_t popup_until = 0;
static int16_t  scroll_x    = 0;
static uint32_t scroll_t    = 0;
static uint8_t  anim_pos    = 0;
static uint32_t anim_t      = 0;
static bool     test_on     = false;
static uint32_t test_until  = 0;
static bool     splash_on   = true; // abertura ao ligar
static uint32_t splash_t0   = 0;

void screen_mark_dirty(void) { dirty_all = true; dirty_media = true; }
void screen_mark_media_dirty(void) { dirty_media = true; scroll_x = 0; scroll_t = timer_read32() + SCROLL_PAUSE; }
void screen_volume_popup(void) { popup_until = timer_read32() + POPUP_MS; popup_on = true; dirty_all = true; }
void screen_test_pattern(void) { test_on = true; test_until = timer_read32() + TEST_MS; dirty_all = true; }

// Ícones 8 px de altura, uma coluna por byte (bit 0 = topo).
static const uint8_t PROGMEM ic_mic[]     = {0x18, 0x20, 0x5F, 0xDF, 0x5F, 0x20, 0x18};
static const uint8_t PROGMEM ic_mic_off[] = {0x19, 0x22, 0x5B, 0xD7, 0x4F, 0x20, 0x58, 0x80};
static const uint8_t PROGMEM ic_play[]    = {0x7F, 0x3E, 0x1C, 0x08};
static const uint8_t PROGMEM ic_pause[]   = {0x3E, 0x3E, 0x00, 0x3E, 0x3E};

static void px(int16_t x, int16_t y, bool on) {
    if (x >= 0 && x < W && y >= 0 && y < H) oled_write_pixel(x, y, on);
}

static void fill(int16_t x, int16_t y, int16_t w, int16_t h, bool on) {
    for (int16_t j = y; j < y + h; j++)
        for (int16_t i = x; i < x + w; i++) px(i, j, on);
}

static void icon(const uint8_t *bmp, uint8_t cols, int16_t x, int16_t y, bool on) {
    for (uint8_t c = 0; c < cols; c++) {
        uint8_t b = pgm_read_byte(bmp + c);
        for (uint8_t r = 0; r < 8; r++)
            if (b & (1 << r)) px(x + c, y + r, on);
    }
}

// Texto 6x8 (x `s`). `bold` repete cada coluna. Ignora pixels fora de [clip_l, clip_r).
static int16_t text(const char *str, int16_t x, int16_t y, uint8_t s, bool bold, bool on, int16_t clip_l, int16_t clip_r) {
    for (; *str; str++) {
        char ch = *str;
        if (ch == 0x1F) ch = '-'; // separador título/artista (só aparece se o texto for cortado no meio)
        if (ch < DF_FIRST || ch > DF_LAST) ch = '?';
        const uint8_t *g = df_font + (ch - DF_FIRST) * 6;
        for (uint8_t c = 0; c < 6; c++) {
            uint8_t b = pgm_read_byte(g + c);
            if (bold && c > 0) b |= pgm_read_byte(g + c - 1);
            int16_t cx = x + c * s;
            if (cx + s <= clip_l || cx >= clip_r) continue;
            for (uint8_t r = 0; r < 8; r++)
                if (b & (1 << r))
                    for (uint8_t dy = 0; dy < s; dy++)
                        for (uint8_t dx = 0; dx < s; dx++)
                            if (cx + dx >= clip_l && cx + dx < clip_r) px(cx + dx, y + r * s + dy, on);
        }
        x += 6 * s + (bold ? 1 : 0);
        if (x >= clip_r) break;
    }
    return x;
}

static int16_t text_w(const char *s, uint8_t scale, bool bold) { return strlen(s) * (6 * scale + (bold ? 1 : 0)); }

static void draw_header(void) {
    bool m = pc.mic_muted;
    fill(0, 0, W, HEADER_H, m);
    if (m) {
        // Faixa acesa só com ícone + palavra, sem negrito (negrito escuro em fundo aceso borra).
        icon(ic_mic_off, 8, 2, 0, false);
        text("MICROFONE MUDO", 14, 1, 1, false, false, 0, W);
        return;
    }
    icon(ic_mic, 7, 1, 0, true);
    text("ATIVO", 12, 1, 1, false, true, 0, W);
    char pos[8];
    snprintf(pos, sizeof(pos), "%u/%u", pc.index + 1, pc.total);
    text(pos, W - text_w(pos, 1, false), 1, 1, false, true, 0, W);
}

static void draw_bar(void) {
    for (int16_t x = 2; x < W - 2; x++) { px(x, BAR_Y, true); px(x, BAR_Y + 3, true); }
    px(1, BAR_Y + 1, true); px(1, BAR_Y + 2, true); px(W - 2, BAR_Y + 1, true); px(W - 2, BAR_Y + 2, true);
    int16_t f = (int16_t)(W - 6) * pc.volume / 100;
    if (!pc.item_muted) fill(3, BAR_Y + 1, f, 2, true);
    else for (int16_t x = 3; x < W - 3; x += 4) px(x, BAR_Y + 1, true);
}

static void volume_str(char *v, uint8_t n) {
    if (pc.item_muted) snprintf(v, n, "mudo");
    else snprintf(v, n, "%u%%", pc.volume);
}

static void draw_main(void) {
    fill(0, HEADER_H, W, MEDIA_Y - HEADER_H, false);
    char v[6];
    volume_str(v, sizeof(v));
    if (popup_on) {
        // Enquanto o encoder gira: nome pequeno + volume em 2x, ocupando a área do nome e da barra.
        fill(0, HEADER_H, W, H - HEADER_H, false);
        text(pc.name, 0, NAME_Y + 4, 1, true, true, 0, 64);
        text(v, W - text_w(v, 2, false), HEADER_H + 1, 2, false, true, 0, W);
        return;
    }
    text(pc.name, 0, NAME_Y, 1, true, true, 0, W - 28);
    text(v, W - text_w(v, 1, false), NAME_Y, 1, false, true, 0, W);
    draw_bar();
}

// "título\x1fartista" vira "título - artista", numa linha que rola.
static void media_line(char *out, uint8_t n) {
    uint8_t j = 0;
    for (const char *s = pc.media; *s && j < n - 4; s++) {
        if (*s == 0x1F) { out[j++] = ' '; out[j++] = '-'; out[j++] = ' '; }
        else out[j++] = *s;
    }
    out[j] = '\0';
}

static int16_t media_w(void) {
    char l[DP_MEDIA_MAX + 4];
    media_line(l, sizeof(l));
    return text_w(l, 1, false);
}

static void draw_media(void) {
    if (popup_on) return;
    fill(0, MEDIA_Y, W, H - MEDIA_Y, false);
    if (pc.media_status == DP_MEDIA_NONE || !pc.media[0]) return;
    bool playing = pc.media_status == DP_MEDIA_PLAYING;
    icon(playing ? ic_play : ic_pause, playing ? 4 : 5, 0, MEDIA_Y, true);
    char l[DP_MEDIA_MAX + 4];
    media_line(l, sizeof(l));
    if (text_w(l, 1, false) <= W - MEDIA_X) {
        text(l, MEDIA_X, MEDIA_Y, 1, false, true, MEDIA_X, W);
        return;
    }
    int16_t x = text(l, MEDIA_X - scroll_x, MEDIA_Y, 1, false, true, MEDIA_X, W);
    text(l, x + 18, MEDIA_Y, 1, false, true, MEDIA_X, W);
}

// Logo 32x32 na altura toda da tela. `rows` = quantas linhas de cima mostrar (32 = inteira).
static void draw_logo(int16_t x0, uint8_t rows) {
    for (uint8_t page = 0; page < 4; page++)
        for (uint8_t x = 0; x < 32; x++) {
            uint8_t bits = pgm_read_byte(delphos_logo + page * 32 + x);
            for (uint8_t bit = 0; bit < 8; bit++)
                if ((bits & (1 << bit)) && page * 8 + bit < rows) px(x0 + x, page * 8 + bit, true);
        }
}

#define TEXT_X 44 // texto à direita da logo
#define DOTS_X 78 // pontos animados depois do "no PC"

static void draw_splash(uint32_t t) {
    // 0-600 ms: a logo aparece de cima para baixo; 700-1500: "Delphos" letra a letra; 1500-2000: linha embaixo.
    oled_clear();
    draw_logo(4, t >= 600 ? 32 : t * 32 / 600);
    if (t >= 700) {
        static const char name[] = "Delphos";
        uint8_t letters = t >= 1500 ? 7 : (t - 700) / 115;
        char    shown[8];
        memcpy(shown, name, letters);
        shown[letters] = '\0';
        text(shown, TEXT_X, 8, 1, true, true, 0, W);
    }
    if (t >= 1500) {
        int16_t length = t >= 2000 ? 49 : (t - 1500) * 49 / 500;
        for (int16_t x = TEXT_X; x < TEXT_X + length; x++) px(x, 19, true);
    }
}

static void draw_offline(void) {
    oled_clear();
    draw_logo(4, 32);
    text("Delphos", TEXT_X, 2, 1, true, true, 0, W);
    text("abra o app", TEXT_X, 13, 1, false, true, 0, W);
    text("no PC", TEXT_X, 22, 1, false, true, 0, W);
}

static void draw_test(void) {
    oled_clear();
    for (int16_t x = 0; x < W; x++) { px(x, 0, true); px(x, H - 1, true); }
    for (int16_t y = 0; y < H; y++) { px(0, y, true); px(W - 1, y, true); }
    for (int16_t x = 16; x < W; x += 16) { fill(x, 1, 1, 3, true); fill(x, H - 4, 1, 3, true); }
    fill(1, 16, 3, 1, true); fill(W - 4, 16, 3, 1, true);
    text("borda inteira?", (W - text_w("borda inteira?", 1, false)) / 2, 12, 1, false, true, 0, W);
}

bool oled_task_user(void) {
    uint32_t now    = timer_read32();
    bool     online = pc_online();

    if (splash_on) {
        if (!splash_t0) splash_t0 = now | 1;
        uint32_t t = timer_elapsed32(splash_t0);
        if (t < SPLASH_MS) {
            draw_splash(t);
            return false;
        }
        splash_on = false;
        screen_mark_dirty();
    }

    if (test_on) {
        if (timer_expired32(now, test_until)) { test_on = false; screen_mark_dirty(); oled_clear(); }
        else {
            if (dirty_all) { draw_test(); dirty_all = false; }
            return false;
        }
    }

    if (!online) {
        if (dirty_all) { draw_offline(); dirty_all = false; dirty_media = false; }
        if (timer_expired32(now, anim_t)) {
            // Três pontos que "respiram" depois do "no PC".
            anim_t   = now + ANIM_MS;
            anim_pos = (anim_pos + 1) % 3;
            fill(DOTS_X, 26, 20, 3, false);
            for (uint8_t i = 0; i < 3; i++) fill(DOTS_X + i * 8, 26, i == anim_pos ? 3 : 2, i == anim_pos ? 3 : 2, true);
        }
        return false;
    }

    if (popup_on && timer_expired32(now, popup_until)) { popup_on = false; dirty_all = true; }

    if (dirty_all) {
        draw_header();
        draw_main();
        dirty_all   = false;
        dirty_media = true;
    }
    if (!popup_on && pc.media_status != DP_MEDIA_NONE && media_w() > W - MEDIA_X && timer_expired32(now, scroll_t)) {
        scroll_t    = now + SCROLL_MS;
        scroll_x    = (scroll_x + 1) % (media_w() + 18);
        dirty_media = true;
    }
    if (dirty_media) { draw_media(); dirty_media = false; }
    return false;
}
#endif
