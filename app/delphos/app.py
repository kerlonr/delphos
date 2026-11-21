"""Janela (pywebview) + ícone na bandeja. Fechar a janela só esconde; "Sair" fecha de verdade."""
import ctypes
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

import pystray
import webview
import win32api
import win32event
import winerror
from PIL import Image, ImageDraw

from . import installer, resource, settings
from .api import Api
from .engine import Engine

log = logging.getLogger("Delphos")


def setup_logging() -> None:
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(settings.DATA_DIR, "log.txt"), maxBytes=1_000_000, backupCount=1,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def already_running() -> bool:
    global _mutex  # precisa viver enquanto o app estiver aberto
    _mutex = win32event.CreateMutex(None, False, "Local\\Delphos")
    return win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS


def tray_icon(status_color: str | None) -> Image.Image:
    """Logo com uma bolinha de status. Sem cor = Delphos desconectado (logo apagada)."""
    img = Image.open(resource("assets", "delphos.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    if status_color:
        draw = ImageDraw.Draw(img)
        draw.ellipse((40, 40, 63, 63), fill="#191C21")
        draw.ellipse((44, 44, 59, 59), fill=status_color)
    else:
        img.putalpha(img.getchannel("A").point(lambda a: a * 55 // 100))
    return img


BG = "#191C21"


def dark_title_bar(hwnd: int) -> None:
    """Barra de título do Windows 11 na cor do app (escura, sem a faixa branca)."""
    color = int(BG[5:7] + BG[3:5] + BG[1:3], 16)  # COLORREF é 0x00BBGGRR
    for attr, value in ((20, 1), (35, color)):    # DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(value)), 4)


def webview_low_power(window, on: bool) -> None:
    """Janela escondida: suspende a página e pede ao WebView2 para soltar memória. Ao mostrar, volta sozinho."""
    try:
        from System import Action
        from Microsoft.Web.WebView2.Core import CoreWebView2MemoryUsageTargetLevel as Level
        form = window.native

        def run():
            core = form.webview.CoreWebView2
            core.MemoryUsageTargetLevel = Level.Low if on else Level.Normal
            if on:
                core.TrySuspendAsync()

        form.Invoke(Action(run))
    except Exception:
        log.exception("webview_low_power(%s)", on)


def main() -> int:
    setup_logging()
    if "--uninstall" in sys.argv:
        installer.uninstall(settings.RUN_KEY)
        return 0
    if already_running():
        return 0
    log.info("iniciando")
    if settings.autostart_enabled():
        settings.set_autostart(True)  # aponta para este exe (útil depois de instalar ou mover)

    prefs = settings.load()
    engine = Engine(prefs)
    engine.step_pct = int(prefs.get("step", 2))
    api = Api(engine, prefs)

    window = webview.create_window("Delphos", resource("delphos", "ui", "index.html"), js_api=api,
                                   width=900, height=560, min_size=(900, 560),
                                   background_color=BG, hidden="--hidden" in sys.argv)
    api.visible = "--hidden" not in sys.argv
    quitting = threading.Event()

    def on_closing():
        if quitting.is_set():
            return True
        threading.Thread(target=hide, daemon=True).start()  # fora do evento: evaluate_js espera a página
        return False

    def hide():
        api.visible = False
        window.evaluate_js("delphosHidden()")
        window.hide()
        webview_low_power(window, True)

    def show(*_):
        first = not api.visible
        api.visible = True
        webview_low_power(window, False)
        window.show()
        window.restore()
        if first:
            window.evaluate_js("delphosShown()")

    def on_loaded():
        try:
            dark_title_bar(int(window.native.Handle.ToInt64()))
        except Exception:
            log.exception("barra de título")
        if not api.visible:
            webview_low_power(window, True)

    def quit_app(*_):
        quitting.set()
        icon.stop()
        engine.stop()
        window.destroy()

    icons = {"off": tray_icon(None), "on": tray_icon("#4CC38A"), "muted": tray_icon("#FF5D61")}

    def refresh_icon():
        if not engine.link.connected:
            icon.icon, icon.title = icons["off"], "Delphos: desconectado"
        elif engine.mic_muted:
            icon.icon, icon.title = icons["muted"], "Delphos: microfone mudo"
        else:
            icon.icon, icon.title = icons["on"], "Delphos: microfone ativo"

    api._window, api._quit = window, quit_app
    window.events.closing += on_closing
    window.events.loaded += on_loaded
    icon = pystray.Icon("Delphos", icons["off"], "Delphos", menu=pystray.Menu(
        pystray.MenuItem("Abrir Delphos", show, default=True),
        pystray.MenuItem("Sair", quit_app),
    ))
    engine.on_change = refresh_icon
    engine.start()
    icon.run_detached()
    webview.start(gui="edgechromium")
    if not quitting.is_set():
        icon.stop()
        engine.stop()
    return 0
