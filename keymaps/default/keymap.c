#include QMK_KEYBOARD_H
#include "raw_hid.h"
#include "via.h"
#include "delphos.h"

// Teclas próprias. A ordem tem que ser a mesma do "customKeycodes" no via.json e do app/delphos/keycodes.py.
enum delphos_keycodes {
    MIC_MUTE = QK_KB_0, // muta/desmuta todos os microfones
    MIX_NEXT,           // próximo item do mixer (Geral -> apps)
    MIX_PREV,
    MIX_UP,             // volume do item selecionado
    MIX_DOWN,
    MIX_MUTE,           // muta/desmuta o item selecionado
    ACTION_0,           // ACTION_0..ACTION_15: ação no PC configurada no app (abrir programa, site...)
    ACTION_15 = ACTION_0 + 15,
};

/*
 * ,---------------------------.
 * |     OLED    |      | Play |  <- clique do encoder (segurar + girar = troca o app)
 * |-------------+------+------|
 * |  MIC | Prev | Play | Next |
 * |------+------+------+------|
 * |  F14 |  F15 | F16  | F17  |
 * |------+------+------+------|
 * | Lock |  F18 | F19  | App> |
 * `---------------------------'
 * Só a camada 0 é definida; as outras 3 do VIA começam vazias.
 */
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_delphos(
        MIC_MUTE,   KC_MEDIA_PREV_TRACK, KC_MEDIA_PLAY_PAUSE, KC_MEDIA_NEXT_TRACK, KC_MEDIA_PLAY_PAUSE,
        KC_F14,     KC_F15,              KC_F16,              KC_F17,
        LGUI(KC_L), KC_F18,              KC_F19,              MIX_NEXT
    ),
};

const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    [0] = { ENCODER_CCW_CW(MIX_DOWN, MIX_UP) },
};

// Estado que o app do PC manda

pc_state_t pc;

static bool was_online    = false;
static bool go_bootloader = false;

bool pc_online(void) {
    return pc.ever_seen && timer_elapsed32(pc.last_seen) < DP_ONLINE_TIMEOUT_MS;
}

static void send_to_pc(uint8_t type, uint8_t a, uint8_t b, uint8_t c) {
    uint8_t buf[DP_REPORT_SIZE] = {type, a, b, c};
    raw_hid_send(buf, DP_REPORT_SIZE);
}

static void send_event(uint8_t event) {
    send_to_pc(DP_EVENT, event, 0, 0);
}

static bool is_action(uint16_t keycode) {
    return keycode >= ACTION_0 && keycode <= ACTION_15;
}

static void copy_text(char *dst, const uint8_t *src, uint8_t max) {
    memcpy(dst, src, max);
    dst[max] = '\0';
}

static void receive_state(uint8_t *data) {
    bool    mic        = data[2] & 0x01;
    bool    item_muted = data[2] & 0x02;
    uint8_t volume     = MIN(data[3], 100);
    // O app reenvia o mesmo estado a cada segundo: só redesenha se algo mudou.
    bool changed = !pc_online() || mic != pc.mic_muted || item_muted != pc.item_muted || volume != pc.volume ||
                   data[4] != pc.index || data[5] != pc.total ||
                   strncmp(pc.name, (const char *)&data[6], DP_NAME_MAX) != 0;
    pc.mic_muted  = mic;
    pc.item_muted = item_muted;
    pc.volume     = volume;
    pc.index      = data[4];
    pc.total      = data[5];
    copy_text(pc.name, &data[6], DP_NAME_MAX);
    pc.last_seen = timer_read32();
    pc.ever_seen = true;
    if (changed) screen_mark_dirty();
}

static void receive_media(uint8_t *data) {
    if (data[1] == pc.media_status && strncmp(pc.media, (const char *)&data[2], DP_MEDIA_MAX) == 0) return;
    pc.media_status = data[1];
    copy_text(pc.media, &data[2], DP_MEDIA_MAX);
    screen_mark_media_dirty();
}

// O VIA chama isto antes de tratar qualquer mensagem: true = é nossa, false = segue para o VIA.
bool via_command_kb(uint8_t *data, uint8_t length) {
    switch (data[0]) {
        case DP_STATE:
            if (data[1] == DP_PROTOCOL_VERSION) receive_state(data);
            return true;
        case DP_MEDIA:
            receive_media(data);
            return true;
        case DP_TEST:
            screen_test_pattern();
            return true;
        case DP_HELLO:
            data[1] = DP_PROTOCOL_VERSION;
            data[2] = DP_FIRMWARE_VERSION;
            raw_hid_send(data, length);
            return true;
        case DP_BOOTLOADER:
            go_bootloader = true; // reinicia fora do tratamento do USB
            return true;
        default:
            return false;
    }
}

// Tela sempre ligada

extern bool oled_initialized; // drivers/oled/oled_driver.c

static void delphos_tick(void) {
    if (go_bootloader) reset_keyboard();
    if (oled_initialized && !is_oled_on()) oled_on(); // a tela fica sempre ligada

    // O QMK tenta ligar a tela uma vez só. Se ela ainda não estava pronta, ficaria apagada: tenta de novo.
    static uint32_t last_try = 0;
    if (!oled_initialized && timer_elapsed32(last_try) > 500) {
        last_try = timer_read32();
        if (oled_init(OLED_ROTATION_0)) screen_mark_dirty();
    }

    bool online = pc_online();
    if (online != was_online) {
        was_online = online;
        screen_mark_dirty();
    }
}

void housekeeping_task_user(void) {
    delphos_tick();
}

// Com o USB suspenso (PC ligando ou dormindo) o QMK para de desenhar a tela até apertar uma tecla.
// Aqui ela continua desenhando (precisa do NO_SUSPEND_POWER_DOWN do config.h).
void suspend_power_down_user(void) {
    static uint32_t last = 0;
    if (timer_elapsed32(last) < 30) return;
    last = timer_read32();
    delphos_tick();
    oled_task();
}

void suspend_wakeup_init_user(void) {
    screen_mark_dirty();
}

// Teclas

static bool encoder_held   = false;
static bool encoder_turned = false; // girou com o botão apertado: troca de app e não manda o clique

static bool is_delphos_key(uint16_t keycode) {
    return keycode >= MIC_MUTE && keycode <= ACTION_15;
}

// Com o app aberto, as teclas de mídia vão para o app selecionado no Delphos.
static uint8_t media_event(uint16_t keycode) {
    switch (keycode) {
        case KC_MEDIA_PLAY_PAUSE: return DP_EV_PLAY;
        case KC_MEDIA_NEXT_TRACK: return DP_EV_NEXT_TRACK;
        case KC_MEDIA_PREV_TRACK: return DP_EV_PREV_TRACK;
        default: return 0;
    }
}

static void volume_step(bool up) {
    if (encoder_held) {
        encoder_turned = true;
        if (pc_online()) send_event(up ? DP_EV_NEXT : DP_EV_PREV);
    } else if (pc_online()) {
        send_event(up ? DP_EV_UP : DP_EV_DOWN);
        screen_volume_popup();
    } else {
        tap_code(up ? KC_AUDIO_VOL_UP : KC_AUDIO_VOL_DOWN);
    }
}

static void delphos_key(uint16_t keycode) {
    bool online = pc_online();
    if (is_action(keycode)) {
        if (online) send_to_pc(DP_EVENT, DP_EV_ACTION, keycode - ACTION_0, 0);
        return;
    }
    switch (keycode) {
        case MIC_MUTE: if (online) send_event(DP_EV_MIC_MUTE); break;
        case MIX_NEXT: if (online) send_event(DP_EV_NEXT); break;
        case MIX_PREV: if (online) send_event(DP_EV_PREV); break;
        case MIX_UP:   volume_step(true); break;
        case MIX_DOWN: volume_step(false); break;
        case MIX_MUTE:
            if (online) send_event(DP_EV_MUTE);
            else tap_code(KC_AUDIO_MUTE);
            break;
    }
}

// O clique do encoder só age ao soltar. shortcut: tecla de camada não funciona nele; usar action_exec se precisar.
static void encoder_click(uint16_t keycode) {
    uint8_t event = media_event(keycode);
    if (is_delphos_key(keycode)) delphos_key(keycode);
    else if (event && pc_online()) send_event(event);
    else tap_code16(keycode);
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (pc_online()) send_to_pc(DP_KEY, record->event.key.row, record->event.key.col, record->event.pressed);

    bool encoder_button = record->event.key.row == 0 && record->event.key.col == 4;
    if (encoder_button) {
        encoder_held = record->event.pressed;
        if (record->event.pressed) encoder_turned = false;
        else if (!encoder_turned) encoder_click(keycode);
        return false;
    }
    if (is_delphos_key(keycode)) {
        if (record->event.pressed) delphos_key(keycode);
        return false;
    }
    // Só o apertar vai para o app; o soltar segue normal (não prende a tecla se o app abrir/fechar no meio).
    uint8_t event = media_event(keycode);
    if (event && record->event.pressed && pc_online()) {
        send_event(event);
        return false;
    }
    return true;
}
