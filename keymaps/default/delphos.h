#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "delphos_proto.h"

// Estado que o app do PC manda. Escrito no keymap.c, lido no screen.c.
typedef struct {
    bool     mic_muted;
    bool     item_muted;
    uint8_t  volume;
    uint8_t  index;
    uint8_t  total;
    char     name[DP_NAME_MAX + 1];
    uint8_t  media_status;
    char     media[DP_MEDIA_MAX + 1];
    uint32_t last_seen;
    bool     ever_seen;
} pc_state_t;

extern pc_state_t pc;

bool pc_online(void);

// screen.c
void screen_mark_dirty(void);       // redesenha tudo
void screen_mark_media_dirty(void); // só as linhas da música
void screen_volume_popup(void);     // mostra o volume grande por um instante
void screen_test_pattern(void);     // bordas e réguas para conferir o painel
