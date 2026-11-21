#pragma once

#define ENCODER_A_PINS { F6 }
#define ENCODER_B_PINS { B2 }
#define ENCODER_RESOLUTION 4

// Com esta configuração o painel mostra só as 32 linhas de cima, sem distorção (conferido com o
// padrão de teste do app). Por isso o screen.c desenha em 128x32.
#define OLED_DISPLAY_128x64
#define OLED_TIMEOUT 0 // tela sempre ligada

// Não deixa o chip dormir com o USB suspenso, para a tela continuar viva enquanto o PC liga.
#define NO_SUSPEND_POWER_DOWN
