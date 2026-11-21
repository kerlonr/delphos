"use strict";
// Cópia em JavaScript de keymaps/default/screen.c, para o desenho do app mostrar a mesma tela do Delphos.
// Se mudar um, mude o outro: app/tests/test_screen_parity.py compara os dois pixel a pixel.

const W = 128, H = 32, HEADER_H = 9, NAME_Y = 10, BAR_Y = 19, MEDIA_Y = 24, MEDIA_X = 8;
const fb = new Uint8Array(W * H);
const ICONS = {
  mic: [0x18, 0x20, 0x5F, 0xDF, 0x5F, 0x20, 0x18],
  micOff: [0x19, 0x22, 0x5B, 0xD7, 0x4F, 0x20, 0x58, 0x80],
  play: [0x7F, 0x3E, 0x1C, 0x08],
  pause: [0x3E, 0x3E, 0x00, 0x3E, 0x3E],
};

function px(x, y, on) {
  if (x >= 0 && x < W && y >= 0 && y < H) fb[y * W + x] = on ? 1 : 0;
}

function fill(x, y, w, h, on) {
  for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) px(i, j, on);
}

function icon(columns, x, y, on) {
  columns.forEach((bits, c) => {
    for (let r = 0; r < 8; r++) if (bits & (1 << r)) px(x + c, y + r, on);
  });
}

// A fonte só tem ASCII: tira os acentos como o app faz antes de mandar para o teclado.
const plain = (s) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "");
const textW = (s, scale, bold) => plain(s).length * (6 * scale + (bold ? 1 : 0));

function text(s, x, y, scale, bold, on, clipLeft = 0, clipRight = W) {
  for (const ch of plain(s)) {
    let code = ch.charCodeAt(0);
    if (code === 0x1f) code = 45; // separador título/artista vira "-"
    if (code < DF_FIRST || code > DF_LAST) code = 63; // "?"
    const glyph = (code - DF_FIRST) * 6;
    for (let c = 0; c < 6; c++) {
      let bits = DF_FONT[glyph + c];
      if (bold && c > 0) bits |= DF_FONT[glyph + c - 1];
      const cx = x + c * scale;
      if (cx + scale <= clipLeft || cx >= clipRight) continue;
      for (let r = 0; r < 8; r++) {
        if (!(bits & (1 << r))) continue;
        for (let dy = 0; dy < scale; dy++)
          for (let dx = 0; dx < scale; dx++)
            if (cx + dx >= clipLeft && cx + dx < clipRight) px(cx + dx, y + r * scale + dy, on);
      }
    }
    x += 6 * scale + (bold ? 1 : 0);
    if (x >= clipRight) break;
  }
  return x;
}

function drawHeader(s) {
  const muted = s.mic_muted;
  fill(0, 0, W, HEADER_H, muted);
  if (muted) {
    icon(ICONS.micOff, 2, 0, false);
    text("MICROFONE MUDO", 14, 1, 1, false, false);
    return;
  }
  icon(ICONS.mic, 1, 0, true);
  text("ATIVO", 12, 1, 1, false, true);
  const position = `${s.index + 1}/${s.total}`;
  text(position, W - textW(position, 1, false), 1, 1, false, true);
}

function drawBar(s) {
  for (let x = 2; x < W - 2; x++) { px(x, BAR_Y, true); px(x, BAR_Y + 3, true); }
  px(1, BAR_Y + 1, true); px(1, BAR_Y + 2, true); px(W - 2, BAR_Y + 1, true); px(W - 2, BAR_Y + 2, true);
  if (!s.item_muted) fill(3, BAR_Y + 1, Math.floor((W - 6) * s.volume / 100), 2, true);
  else for (let x = 3; x < W - 3; x += 4) px(x, BAR_Y + 1, true);
}

const volumeText = (s) => s.item_muted ? "mudo" : `${s.volume}%`;
const mediaLine = (t) => plain(t).slice(0, 29).replace("\x1f", " - ");

function drawMain(s, popup) {
  fill(0, HEADER_H, W, MEDIA_Y - HEADER_H, false);
  const volume = volumeText(s);
  if (popup) {
    fill(0, HEADER_H, W, H - HEADER_H, false);
    text(s.name, 0, NAME_Y + 4, 1, true, true, 0, 64);
    text(volume, W - textW(volume, 2, false), HEADER_H + 1, 2, false, true);
    return;
  }
  text(s.name, 0, NAME_Y, 1, true, true, 0, W - 28);
  text(volume, W - textW(volume, 1, false), NAME_Y, 1, false, true);
  drawBar(s);
}

function drawMedia(media, scrollX) {
  fill(0, MEDIA_Y, W, H - MEDIA_Y, false);
  if (!media.status || !media.text) return;
  icon(media.status === 1 ? ICONS.pause : ICONS.play, 0, MEDIA_Y, true); // tocando = pause, como no Spotify
  const line = mediaLine(media.text);
  if (textW(line, 1, false) <= W - MEDIA_X) {
    text(line, MEDIA_X, MEDIA_Y, 1, false, true, MEDIA_X);
    return;
  }
  const end = text(line, MEDIA_X - scrollX, MEDIA_Y, 1, false, true, MEDIA_X);
  text(line, end + 18, MEDIA_Y, 1, false, true, MEDIA_X);
}

const TEXT_X = 44, DOTS_X = 78;

function drawOffline() {
  fb.fill(0);
  DF_LOGO.forEach((bits, i) => {
    const page = Math.floor(i / 32), x = i % 32;
    for (let bit = 0; bit < 8; bit++) if (bits & (1 << bit)) px(4 + x, page * 8 + bit, true);
  });
  text("Delphos", TEXT_X, 2, 1, true, true);
  text("abra o app", TEXT_X, 13, 1, false, true);
  text("no PC", TEXT_X, 22, 1, false, true);
  return fb;
}

// Três pontos que "respiram" depois do "no PC".
let offlineDot = 0, offlineFrame = 0;
function drawOfflineDots() {
  if (++offlineFrame % 8 === 0) offlineDot = (offlineDot + 1) % 3;
  fill(DOTS_X, 26, 20, 3, false);
  for (let i = 0; i < 3; i++) {
    const size = i === offlineDot ? 3 : 2;
    fill(DOTS_X + i * 8, 26, size, size, true);
  }
}

function renderScreen(screen, media, popup, scrollX) {
  fb.fill(0);
  drawHeader(screen);
  drawMain(screen, popup);
  if (!popup) drawMedia(media, scrollX);
  return fb;
}
