"""Ações no PC das teclas "Ação 1..16" do Delphos."""
import logging
import os
import threading
import webbrowser

import psutil
import win32con
import win32gui
import win32process

log = logging.getLogger(__name__)

TYPES = {
    "program": "Abrir programa",
    "site": "Abrir site",
    "folder": "Abrir pasta",
    "mute_app": "Mutar som de um app",
    "close_selected": "Fechar app selecionado",
}
NO_TARGET = ("close_selected",)  # age no app selecionado no Delphos, sem alvo fixo


def describe(action: dict) -> str:
    """Nome curto para mostrar na tecla, ex. "Discord" ou "youtube.com"."""
    target = action.get("target", "")
    if action.get("type") == "program" and target.endswith(":"):  # link de app da Store, ex. "spotify:"
        return target[:-1].capitalize()
    if action.get("type") in ("program", "folder"):
        return os.path.splitext(os.path.basename(target.rstrip("\\/")))[0] or target
    if action.get("type") == "site":
        return target.split("://", 1)[-1].split("/", 1)[0]
    if action.get("type") == "close_selected":
        return "Fechar app"
    return action.get("label") or target


def normalize(action: dict) -> dict:
    kind, target = action["type"], action.get("target", "").strip()
    if kind not in TYPES or not (target or kind in NO_TARGET):
        raise ValueError("ação inválida")
    if kind == "site" and "://" not in target:
        target = "https://" + target
    return {**action, "type": kind, "target": target}


def _visible_windows(pids: set[int]) -> list[int]:
    found = []
    def check(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] in pids:
            found.append(hwnd)
    win32gui.EnumWindows(check, None)
    return found


def close_app(exe: str, timeout: float = 3.0) -> None:
    """Igual ao Alt+F4 em todas as janelas do .exe. Quem continuar rodando sem janela visível
    (foi para a bandeja, ou nunca teve janela) é finalizado. Quem ainda mostra janela (ex. "salvar
    alterações?") fica, para não perder nada."""
    procs = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == exe]
    if not procs:
        return
    for hwnd in _visible_windows({p.pid for p in procs}):
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    if alive and not _visible_windows({p.pid for p in alive}):
        for p in alive:
            try:
                p.kill()
            except psutil.Error:
                pass
    log.info("fechou %s", exe)


def run(action: dict, channels: list, current: str | None = None) -> None:
    """Roda na thread do engine (mutar um app mexe no áudio). `current` = app selecionado."""
    kind, target = action["type"], action["target"]
    try:
        if kind in ("program", "folder"):
            os.startfile(target)
        elif kind == "site":
            webbrowser.open(target)
        elif kind == "mute_app":
            for c in channels:
                if c.key == target:
                    c.set_mute(not c.get_mute())
        elif kind == "close_selected":
            if current and current != "__master__":
                # em outra thread: espera o app fechar sem travar o engine
                threading.Thread(target=close_app, args=(current,), daemon=True).start()
    except OSError:
        log.exception("ação falhou: %s", action)
