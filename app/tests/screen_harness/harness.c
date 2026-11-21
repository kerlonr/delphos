// Desenha estados da tela com o screen.c REAL do firmware e imprime os pixels (128x64, '1'/'0').
// Entrada (stdin), uma linha por cena, campos separados por '|':
//   mic|item_mudo|volume|indice|total|nome|status_midia|texto_midia(\x1f literal)|popup|scroll
#include "qmk_stub.h"
#include "delphos.h"

uint8_t    fb[64][128];
uint32_t   now_ms     = 100000;
bool       oled_is_on = true;
pc_state_t pc;
static bool online = true;
bool pc_online(void) { return online; }

#include "screen.c"

static void unescape(char *s) {
    // "\x1f" escrito na entrada vira o byte 0x1F.
    char *w = s;
    for (char *r = s; *r; r++) {
        if (r[0] == '\\' && r[1] == 'x' && r[2] == '1' && (r[3] == 'f' || r[3] == 'F')) { *w++ = 0x1F; r += 3; }
        else *w++ = *r;
    }
    *w = '\0';
}

int main(void) {
    char line[512];
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (strncmp(line, "splash|", 7) == 0 || strcmp(line, "offline") == 0) {
            // Abertura num instante t (ms) ou a tela sem o app.
            oled_clear();
            if (line[0] == 's') draw_splash(atoi(line + 7));
            else draw_offline();
            for (int y = 0; y < 64; y++)
                for (int x = 0; x < 128; x++) putchar('0' + fb[y][x]);
            putchar('\n');
            continue;
        }
        char *f[10];
        int   n = 0;
        for (char *t = strtok(line, "|"); t && n < 10; t = strtok(NULL, "|")) f[n++] = t;
        if (n < 10) { printf("ERRO\n"); continue; }
        memset(&pc, 0, sizeof pc);
        pc.mic_muted    = atoi(f[0]);
        pc.item_muted   = atoi(f[1]);
        pc.volume       = atoi(f[2]);
        pc.index        = atoi(f[3]);
        pc.total        = atoi(f[4]);
        strncpy(pc.name, strcmp(f[5], "-") ? f[5] : "", DP_NAME_MAX);
        pc.media_status = atoi(f[6]);
        unescape(f[7]);
        strncpy(pc.media, strcmp(f[7], "-") ? f[7] : "", DP_MEDIA_MAX);
        pc.ever_seen = true;

        oled_clear();
        popup_on = atoi(f[8]);
        scroll_x = atoi(f[9]);
        draw_header();
        draw_main();
        draw_media();
        for (int y = 0; y < 64; y++) {
            for (int x = 0; x < 128; x++) putchar('0' + fb[y][x]);
        }
        putchar('\n');
    }
    return 0;
}
