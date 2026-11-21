"""Funções que a janela chama pelo JavaScript (window.pywebview.api.*)."""
import json
import logging
import os
import threading
import time

import webview

from . import VERSION, actions, firmware, installer, keycodes, macros, settings
from . import protocol as p
from .engine import Engine
from .keymap import Keymap

log = logging.getLogger(__name__)

MEDIA_BUTTONS = {"play": p.EV_PLAY, "next": p.EV_NEXT_TRACK, "prev": p.EV_PREV_TRACK}


class Api:
    def __init__(self, engine: Engine, prefs: dict) -> None:
        self._engine = engine
        self._device = Keymap(engine.link)
        self._prefs = prefs
        self._window = None             # preenchidos pelo app.py
        self._quit = lambda: None
        self._flash_state = {"running": False, "message": "", "needs_boot": False}
        self._fw_installed: int | None = None
        self._fw_checked = False
        self._layers: list[dict] = []
        self._macro_buffer = b""
        engine.actions = prefs.get("actions", {})

    def meta(self) -> dict:
        catalog = keycodes.catalog()
        return {"catalog": catalog, "labels": {i["code"]: i["label"] for c in catalog for i in c["items"]},
                "action_types": actions.TYPES, "version": VERSION}

    def state(self) -> dict:
        e = self._engine
        connected = e.link.connected
        if connected and not self._fw_checked:
            hello = e.link.hello()
            self._fw_installed = hello[1] if hello else None
        self._fw_checked = connected
        current = next((a for a in e.snapshot["apps"] if a["selected"]), None)
        screen = None
        if current:
            screen = {"key": current["key"], "name": current["name"], "volume": current["volume"],
                      "item_muted": current["muted"], "mic_muted": e.mic_muted,
                      "index": e.mixer.index, "total": e.mixer.total}
        status, text = e.snapshot["media"]
        return {
            "connected": connected, "mic_muted": e.mic_muted, "screen": screen,
            "apps": e.snapshot["apps"], "mics": e.snapshot["mics"],
            "hidden_apps": [{"key": k, "name": n} for k, n in self._prefs.get("hidden_apps", {}).items()],
            "media": {"status": status, "text": text},
            "firmware": {"installed": self._fw_installed, "bundled": firmware.BUNDLED_FW_VERSION} if connected else None,
            "flash": self._flash_state,
            "keys_down": sorted(e.keys_down), "knob": e.knob,
        }

    # Teclas, macros e ações

    def _label(self, code: int) -> str:
        n = keycodes.action_index(code)
        action = self._engine.actions.get(str(n)) if n is not None else None
        return actions.describe(action) if action else keycodes.label(code)

    def keymap(self) -> dict | None:
        """Tudo que o editor precisa: as 4 camadas, as macros e as ações."""
        try:
            self._layers = self._device.read_all()
            self._macro_buffer = self._device.read_macros()
        except OSError:
            log.exception("falha ao ler as teclas")
            return None
        codes = {code for layer in self._layers for code in layer.values()}
        return {
            "layers": self._layers,
            "labels": {code: self._label(code) for code in codes},
            "macros": [macros.decode(m) for m in macros.split(self._macro_buffer)],
            "macro_space": len(self._macro_buffer),
            "actions": self._engine.actions,
        }

    def set_key(self, layer: int, slot: str, code: int) -> dict | None:
        self._device.set_slot(layer, slot, code)
        log.info("camada %s, tecla %s = %s", layer, slot, keycodes.label(code))
        return self.keymap()

    def reset_keys(self) -> dict | None:
        self._device.reset()
        return self.keymap()

    def shortcut(self, mods: list, code: str) -> dict | None:
        keycode = keycodes.from_js(mods, code)
        return None if keycode is None else {"code": keycode, "label": keycodes.label(keycode)}

    def shortcut_steps(self, code: int) -> list[dict]:
        return macros.shortcut_steps(code)

    def _free_index(self, index_of, count: int) -> int:
        """Primeira macro/ação que nenhuma tecla de nenhuma camada usa."""
        used = {index_of(code) for layer in self._layers for code in layer.values()}
        for n in range(count):
            if n not in used:
                return n
        raise ValueError("todas as 16 já estão em uso")

    def save_macro(self, layer: int, slot: str, steps: list[dict]) -> dict | None:
        index = keycodes.macro_index(self._layers[layer][slot])
        if index is None:
            index = self._free_index(keycodes.macro_index, keycodes.MACRO_COUNT)
        all_macros = macros.split(self._macro_buffer)
        all_macros[index] = macros.encode(steps)
        self._device.write_macros(macros.join(all_macros, len(self._macro_buffer)))
        return self.set_key(layer, slot, keycodes.MACRO_0 + index)

    def save_action(self, layer: int, slot: str, action: dict) -> dict | None:
        index = keycodes.action_index(self._layers[layer][slot])
        if index is None:
            index = self._free_index(keycodes.action_index, keycodes.ACTION_COUNT)
        self._engine.actions[str(index)] = actions.normalize(action)
        self._prefs["actions"] = self._engine.actions
        settings.save(self._prefs)
        return self.set_key(layer, slot, keycodes.ACTION_0 + index)

    def pick_file(self, folder: bool) -> str | None:
        kind = webview.FileDialog.FOLDER if folder else webview.FileDialog.OPEN
        types = () if folder else ("Programas (*.exe;*.lnk;*.bat)", "Todos os arquivos (*.*)")
        result = self._window.create_file_dialog(kind, file_types=types)
        return result[0] if result else None

    # Backup

    def export_backup(self) -> str | None:
        path = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename="delphos-backup.json",
                                              file_types=("Backup do Delphos (*.json)",))
        if not path:
            return None
        path = path if isinstance(path, str) else path[0]
        self.keymap()
        data = {"delphos_backup": 1, "layers": self._layers, "macros": self._macro_buffer.hex(),
                "actions": self._engine.actions}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def import_backup(self) -> dict | None:
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Backup do Delphos (*.json)",))
        if not result:
            return None
        with open(result[0], encoding="utf-8") as f:
            data = json.load(f)
        if data.get("delphos_backup") != 1:
            raise ValueError("este arquivo não é um backup do Delphos")
        for layer, keys in enumerate(data["layers"]):
            for slot, code in keys.items():
                self._device.set_slot(layer, slot, code)
        self._device.write_macros(bytes.fromhex(data["macros"]))
        self._engine.actions = data.get("actions", {})
        self._prefs["actions"] = self._engine.actions
        settings.save(self._prefs)
        return self.keymap()

    # Mixer

    def select(self, key: str) -> None:
        self._engine.select(key)

    def set_volume(self, key: str, pct: int) -> None:
        self._engine.set_volume(key, int(pct))

    def toggle_mute(self, key: str) -> None:
        self._engine.toggle_mute(key)

    def hide_app(self, key: str, name: str) -> None:
        self._engine.set_hidden(key, name, True)

    def show_app(self, key: str) -> None:
        self._engine.set_hidden(key, "", False)

    def toggle_mic(self) -> None:
        self._engine.press(p.EV_MIC_MUTE)

    def media(self, button: str) -> None:
        self._engine.press(MEDIA_BUTTONS[button])

    # Ajustes

    def settings(self) -> dict:
        return {"autostart": settings.autostart_enabled(), "step": self._engine.step_pct,
                "is_exe": installer.is_exe(), "installed": installer.is_installed(),
                "running_installed": installer.running_installed(),
                "installed_version": installer.installed_version(), "version": VERSION}

    def set_autostart(self, on: bool) -> None:
        settings.set_autostart(on)

    def set_step(self, pct: int) -> None:
        self._engine.step_pct = max(1, min(10, int(pct)))
        self._prefs["step"] = self._engine.step_pct
        settings.save(self._prefs)

    def test_screen(self) -> None:
        self._engine.link.send(p.command(p.TEST))

    def open_log(self) -> None:
        os.startfile(settings.DATA_DIR)

    def install(self) -> None:
        """Instala (ou atualiza), fecha este e abre o Delphos instalado."""
        installer.install()
        installer.start_installed_after_exit()
        threading.Timer(0.3, self._quit).start()

    # Firmware

    def flash(self) -> None:
        if not self._flash_state["running"]:
            threading.Thread(target=self._flash, name="flash", daemon=True).start()

    def _say(self, message: str, needs_boot: bool = False) -> None:
        self._flash_state.update(message=message, needs_boot=needs_boot)

    def _flash(self) -> None:
        self._flash_state["running"] = True
        try:
            before = firmware.serial_ports()
            port = None
            if self._engine.link.hello():  # firmware do Delphos: dá para pedir o bootloader pelo USB
                self._say("Reiniciando o Delphos no modo de gravação…")
                self._engine.link.send(p.command(p.BOOTLOADER))
                port = firmware.wait_new_port(before, 15)
            if port is None:
                self._say("Aperte o botão de boot do Delphos agora.", needs_boot=True)
                port = firmware.wait_new_port(before, 90)
            if port is None:
                self._say("O Delphos não entrou no modo de gravação. Tente de novo.")
                return
            self._say("Gravando…")
            if not firmware.flash(port):
                self._say("A gravação falhou. Veja o log e tente de novo.")
                return
            self._say("Reconectando…")
            end = time.monotonic() + 15
            while time.monotonic() < end and not self._engine.link.connected:
                time.sleep(0.3)
            time.sleep(0.5)
            hello = self._engine.link.hello()
            self._fw_installed = hello[1] if hello else None
            self._say(f"Firmware {self._fw_installed} instalado." if hello else "Gravado, mas o Delphos não respondeu.")
        except Exception:
            log.exception("falha ao gravar o firmware")
            self._say("Erro inesperado ao gravar. Veja o log.")
        finally:
            self._flash_state["running"] = False
