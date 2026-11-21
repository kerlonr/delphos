// Simula o pedaço do QMK que o screen.c usa, para compilar a tela no PC e comparar com o app.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OLED_ENABLE
#define PROGMEM
#define pgm_read_byte(p) (*(const uint8_t *)(p))

extern uint8_t  fb[64][128]; // RAM da tela (128x64), como no driver
extern uint32_t now_ms;
extern bool     oled_is_on;

static inline uint32_t timer_read32(void) { return now_ms; }
static inline uint32_t timer_elapsed32(uint32_t t) { return now_ms - t; }
static inline bool     timer_expired32(uint32_t now, uint32_t future) { return (int32_t)(now - future) >= 0; }
static inline void     oled_write_pixel(uint8_t x, uint8_t y, bool on) { if (x < 128 && y < 64) fb[y][x] = on; }
static inline void     oled_clear(void) { memset(fb, 0, sizeof(fb)); }
static inline bool     is_oled_on(void) { return oled_is_on; }
static inline bool     oled_on(void) { oled_is_on = true; return true; }
static inline bool     oled_off(void) { oled_is_on = false; return true; }
