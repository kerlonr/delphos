"""A tela do app (oled.js) tem que ser idêntica, pixel a pixel, à do firmware (screen.c).

Compila o screen.c real com um driver de tela falso (gcc do QMK MSYS) e roda o oled.js no node,
com as mesmas cenas. Também confere que nada é desenhado nas linhas 32-63, que o painel não mostra.
"""
import json
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
ROOT = os.path.dirname(APP)
KEYMAP = os.path.join(ROOT, "keymaps", "default")
UI = os.path.join(APP, "delphos", "ui")
GCC = shutil.which("gcc") or r"C:\QMK_MSYS\mingw64\bin\gcc.exe"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(not (os.path.exists(GCC) and NODE), reason="precisa de gcc e node")

# mic, item_mudo, volume, índice, total, nome, status, mídia, popup, scroll
SCENES = [
    (0, 0, 100, 0, 4, "Geral", 0, "", 0, 0),
    (1, 0, 62, 1, 4, "Spotify", 1, "Stand By Me\x1fBen E. King", 0, 0),
    (0, 1, 40, 2, 5, "Google Chrome", 2, "GTA 6 - #7: Aqui o DODO\x1fFunky", 0, 0),
    (0, 0, 7, 3, 9, "Um nome bem comprido de app", 1, "Titulo que rola muito longo\x1fArtista", 0, 37),
    (1, 1, 0, 0, 1, "Geral", 1, "Curta", 1, 0),
    (0, 0, 100, 0, 2, "Steam", 1, "Musica sem artista", 1, 0),
]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    out = tmp_path_factory.mktemp("screen") / "harness.exe"
    env = dict(os.environ, PATH=os.path.dirname(GCC) + os.pathsep + os.environ.get("PATH", ""))
    subprocess.run([GCC, "-std=gnu11", "-O0", "-static", "-Wall", "-Wno-unused-function",
                    '-DQMK_KEYBOARD_H="qmk_stub.h"', "-I", os.path.join(HERE, "screen_harness"), "-I", KEYMAP,
                    os.path.join(HERE, "screen_harness", "harness.c"), "-o", str(out)],
                   check=True, env=env, capture_output=True)
    return str(out)


def firmware_frames(harness):
    lines = "\n".join("|".join(str(v if v != "" else "-").replace("\x1f", "\\x1f") for v in s) for s in SCENES) + "\n"
    r = subprocess.run([harness], input=lines, capture_output=True, text=True, check=True)
    return r.stdout.split()


def app_frames():
    js = f"""
const fs = require('fs'), vm = require('vm');
const ctx = {{}}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync({json.dumps(os.path.join(UI, 'font.js'))}, 'utf8') + '\\n' +
                fs.readFileSync({json.dumps(os.path.join(UI, 'oled.js'))}, 'utf8') +
                '\\nthis.renderScreen = renderScreen;', ctx);
const scenes = JSON.parse(fs.readFileSync(0, 'utf8'));
for (const [mic, im, vol, idx, tot, name, st, text, popup, scroll] of scenes) {{
  const fb = ctx.renderScreen({{mic_muted: !!mic, item_muted: !!im, volume: vol, index: idx, total: tot, name}},
                              {{status: st, text}}, !!popup, scroll);
  let s = Array.from(fb).join('');
  s += '0'.repeat(128 * 64 - s.length);  // o app só tem as 32 linhas visíveis
  console.log(s);
}}
"""
    r = subprocess.run([NODE, "-e", js], input=json.dumps(SCENES), capture_output=True, text=True, check=True,
                       encoding="utf-8")
    return r.stdout.split()


def ascii_art(frame: str) -> str:
    return "\n".join(frame[y * 128:(y + 1) * 128].replace("0", ".").replace("1", "#") for y in range(32))


def test_app_mirror_matches_firmware_pixel_by_pixel(harness):
    fw, app = firmware_frames(harness), app_frames()
    assert len(fw) == len(app) == len(SCENES)
    for scene, a, b in zip(SCENES, fw, app):
        assert a == b, f"cena {scene} difere\nfirmware:\n{ascii_art(a)}\napp:\n{ascii_art(b)}"


def test_nothing_drawn_below_row_32(harness):
    for scene, frame in zip(SCENES, firmware_frames(harness)):
        assert "1" not in frame[32 * 128:], f"cena {scene} desenhou nas linhas 32-63, que o painel não mostra"


def test_muted_header_is_clean(harness):
    # Mic mudo: faixa acesa com texto escuro, sem negrito; a linha embaixo da faixa fica livre.
    frame = firmware_frames(harness)[1]
    header = frame[: 9 * 128]
    assert header.count("1") > header.count("0")  # faixa acesa
    assert "1" not in frame[9 * 128: 10 * 128]


def run_harness(harness, lines: list[str]) -> list[str]:
    return subprocess.run([harness], input="\n".join(lines) + "\n", capture_output=True, text=True,
                          check=True).stdout.split()


def app_offline_frame() -> str:
    js = f"""
const fs = require('fs'), vm = require('vm');
const ctx = {{}}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync({json.dumps(os.path.join(UI, 'font.js'))}, 'utf8') + '\\n' +
                fs.readFileSync({json.dumps(os.path.join(UI, 'oled.js'))}, 'utf8') +
                '\\nthis.drawOffline = drawOffline;', ctx);
console.log(Array.from(ctx.drawOffline()).join(''));
"""
    return subprocess.run([NODE, "-e", js], capture_output=True, text=True, check=True).stdout.strip()


def test_offline_screen_matches_and_fits(harness):
    fw = run_harness(harness, ["offline"])[0]
    app = app_offline_frame()
    assert fw[:128 * 32] == app, f"firmware:\n{ascii_art(fw)}\napp:\n{ascii_art(app)}"
    assert all(fw[y * 128 + 127] == "0" for y in range(32))  # o texto cabe: nada encosta na borda direita


def test_splash_starts_dark_and_ends_with_whole_logo(harness):
    start, end, offline = run_harness(harness, ["splash|0", "splash|2300", "offline"])
    logo_area = lambda frame: "".join(frame[y * 128 + 4:y * 128 + 36] for y in range(32))
    assert "1" not in start
    assert logo_area(end) == logo_area(offline)
