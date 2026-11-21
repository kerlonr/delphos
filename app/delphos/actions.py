"""Ações no PC das teclas "Ação 1..16" do Delphos."""
import logging
import os
import webbrowser

log = logging.getLogger(__name__)

TYPES = {
    "program": "Abrir programa",
    "site": "Abrir site",
    "folder": "Abrir pasta",
    "mute_app": "Mutar som de um app",
}


def describe(action: dict) -> str:
    """Nome curto para mostrar na tecla, ex. "Discord" ou "youtube.com"."""
    target = action.get("target", "")
    if action.get("type") in ("program", "folder"):
        return os.path.splitext(os.path.basename(target.rstrip("\\/")))[0] or target
    if action.get("type") == "site":
        return target.split("://", 1)[-1].split("/", 1)[0]
    return action.get("label") or target


def normalize(action: dict) -> dict:
    kind, target = action["type"], action["target"].strip()
    if kind not in TYPES or not target:
        raise ValueError("ação inválida")
    if kind == "site" and "://" not in target:
        target = "https://" + target
    return {**action, "type": kind, "target": target}


def run(action: dict, channels: list) -> None:
    """Roda na thread do engine (mutar um app mexe no áudio)."""
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
    except OSError:
        log.exception("ação falhou: %s", action)
