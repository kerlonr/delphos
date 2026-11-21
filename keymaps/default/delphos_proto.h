#pragma once

// Mensagens Raw HID entre o PC e o Delphos (32 bytes). Igual a app/delphos/protocol.py.
// Os ids 0x40-0x47 não colidem com os comandos do VIA.

#define DP_REPORT_SIZE      32
#define DP_PROTOCOL_VERSION 2
#define DP_FIRMWARE_VERSION 7

#define DP_STATE      0x40 // PC -> teclado: [1]versão [2]flags (1=mic mudo, 2=item mudo) [3]volume [4]índice [5]total [6..26]nome
#define DP_EVENT      0x41 // teclado -> PC: [1]evento (DP_EV_*) [2]número da ação (DP_EV_ACTION)
#define DP_HELLO      0x42 // PC -> teclado, responde: [1]versão do protocolo [2]versão do firmware
#define DP_BOOTLOADER 0x43 // PC -> teclado: entra no modo de gravação
#define DP_MEDIA      0x44 // PC -> teclado: [1]status (DP_MEDIA_*) [2..31]título, 0x1F, artista
#define DP_KEY        0x46 // teclado -> PC: [1]linha [2]coluna [3]apertou (linha 254/255 = giro do encoder)
#define DP_TEST       0x47 // PC -> teclado: padrão de teste na tela

#define DP_EV_MIC_MUTE   1
#define DP_EV_NEXT       2
#define DP_EV_PREV       3
#define DP_EV_UP         4
#define DP_EV_DOWN       5
#define DP_EV_MUTE       6
#define DP_EV_PLAY       7
#define DP_EV_NEXT_TRACK 8
#define DP_EV_PREV_TRACK 9
#define DP_EV_ACTION     10

#define DP_MEDIA_NONE    0
#define DP_MEDIA_PLAYING 1
#define DP_MEDIA_PAUSED  2

#define DP_NAME_MAX          20
#define DP_MEDIA_MAX         29
#define DP_ONLINE_TIMEOUT_MS 3000 // sem STATE por esse tempo = app fechado
