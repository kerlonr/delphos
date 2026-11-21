"""Coração do app: aplica as teclas do Delphos e da interface no áudio e manda o estado para a tela."""
import gc
import logging
import queue
import threading
import time
from typing import Callable

import comtypes
import psutil

from . import actions, audio, settings
from . import protocol as p
from .hidlink import HidLink
from .media import match_session, media_only
from .media import Media
from .mixer import Mixer, ordered

log = logging.getLogger(__name__)

REFRESH_S = 1.0
MEDIA_EVENTS = (p.EV_PLAY, p.EV_NEXT_TRACK, p.EV_PREV_TRACK)


class Engine:
    def __init__(self, prefs: dict) -> None:
        self.prefs = prefs
        # Tudo que mexe no áudio passa por esta fila e roda na thread do engine (o COM exige uma thread só).
        # (evento, número da ação) = tecla do Delphos; função = pedido da interface.
        self.events: queue.Queue[tuple[int, int] | Callable] = queue.Queue()
        self.link = HidLink(lambda event, arg: self.events.put((event, arg)), self._on_key)
        self.actions: dict[str, dict] = {}   # "0".."15" -> ação no PC (vem dos ajustes)
        self.mixer = Mixer()
        self.media = Media()
        self.mic_muted = False
        self.step_pct = 2
        self.keys_down: set[str] = set()     # teclas físicas apertadas agora ("linha,coluna")
        self.knob = {"dir": 0, "seq": 0}     # último giro do encoder
        self.snapshot: dict = {"mics": [], "apps": [], "media": (p.MEDIA_NONE, "")}
        self.on_change = lambda: None        # chamado quando conexão ou mic mudam (ícone da bandeja)
        self._mics: audio.Mics | None = None
        self._media_due = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)

    def start(self) -> None:
        self.link.start()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self.link.stop()

    def _on_key(self, row: int, col: int, down: bool) -> None:
        if row in (p.ENC_CW_ROW, p.ENC_CCW_ROW):
            if down:
                self.knob = {"dir": 1 if row == p.ENC_CW_ROW else -1, "seq": self.knob["seq"] + 1}
        elif down:
            self.keys_down.add(f"{row},{col}")
        else:
            self.keys_down.discard(f"{row},{col}")

    # Pedidos da interface (qualquer thread)

    def press(self, event: int, arg: int = 0) -> None:
        self.events.put((event, arg))

    def select(self, key: str) -> None:
        def run():
            keys = [c.key for c in self.mixer.channels]
            if key in keys:
                self.mixer.index = keys.index(key)
                self._media_due = 0
        self.events.put(run)

    def set_volume(self, key: str, pct: int) -> None:
        def run():
            for c in self.mixer.channels:
                if c.key == key:
                    c.set_volume(max(0, min(100, pct)) / 100)
        self.events.put(run)

    def toggle_mute(self, key: str) -> None:
        def run():
            for c in self.mixer.channels:
                if c.key == key:
                    c.set_mute(not c.get_mute())
        self.events.put(run)

    def set_hidden(self, key: str, name: str, hidden: bool) -> None:
        """Esconde ou mostra um app no mixer (e no Delphos). Fica salvo nos ajustes."""
        def run():
            apps = self.prefs.setdefault("hidden_apps", {})
            if hidden:
                apps[key] = name
            else:
                apps.pop(key, None)
            settings.save(self.prefs)
            self._refresh()
        self.events.put(run)

    # Thread do engine

    def _current_key(self) -> str | None:
        return self.mixer.current.key if self.mixer.current else None

    def _refresh(self) -> None:
        apps = audio.app_channels()
        keys = {c.key for c in apps}
        ids = [i for i in self.media.app_ids() if not any(match_session([i], k) == 0 for k in keys)]
        if ids:  # só lista os processos se tem app com mídia e sem áudio
            running = {p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info["name"]}
            apps += media_only(ids, keys, running)
        hidden = self.prefs.get("hidden_apps", {})
        self.mixer.refresh(ordered(audio.MasterChannel(), [c for c in apps if c.key not in hidden]))
        self._mics.enforce()
        self.mic_muted = self._mics.is_muted()
        self.snapshot["mics"] = self._mics.list()
        current = self._current_key()
        self.snapshot["apps"] = [{"key": c.key, "name": c.name, "volume": round(c.get_volume() * 100),
                                  "muted": c.get_mute(), "selected": c.key == current,
                                  "silent": getattr(c, "silent", False)} for c in self.mixer.channels]

    def _apply(self, item, now: float) -> None:
        if callable(item):
            item()
            return
        event, arg = item
        if event == p.EV_ACTION:
            action = self.actions.get(str(arg))
            if action:
                actions.run(action, self.mixer.channels, self._current_key())
        elif event == p.EV_MIC_MUTE:
            self.mic_muted = self._mics.toggle()
            log.info("mic %s", "mudo" if self.mic_muted else "ativo")
        elif event in (p.EV_NEXT, p.EV_PREV):
            self.mixer.next() if event == p.EV_NEXT else self.mixer.prev()
            self._media_due = 0
        elif event in (p.EV_UP, p.EV_DOWN):
            self.mixer.step(self.step_pct if event == p.EV_UP else -self.step_pct)
        elif event == p.EV_MUTE:
            self.mixer.toggle_mute()
        elif event in MEDIA_EVENTS:
            self.media.command(self._current_key(), event)
            self._media_due = now + 0.3  # o Windows atualiza o status logo depois do comando

    def _state(self) -> bytes:
        c = self.mixer.current
        if c is None:
            return p.encode_state(self.mic_muted, False, 0, 0, 0, "sem audio")
        return p.encode_state(self.mic_muted, c.get_mute(), round(c.get_volume() * 100),
                              self.mixer.index, self.mixer.total, c.name)

    def _run(self) -> None:
        comtypes.CoInitialize()
        self._mics = audio.Mics(self.prefs.setdefault("mic_volumes", {}), lambda: settings.save(self.prefs))
        last_refresh = last_sent_at = 0.0
        last_state = last_media = b""
        was_connected = False
        last_icon = None
        while not self._stop.is_set():
            try:
                try:
                    # tecla do Delphos ou pedido da interface acorda na hora; sem nada, checa 4x por segundo
                    self._apply(self.events.get(timeout=0.25), time.monotonic())
                except queue.Empty:
                    pass
                now = time.monotonic()
                if now - last_refresh >= REFRESH_S:
                    self._refresh()
                    last_refresh = now
                if now >= self._media_due:
                    self.snapshot["media"] = self.media.info(self._current_key())
                    self._media_due = now + REFRESH_S

                # O teclado só considera o app aberto se receber o estado pelo menos a cada 3 s.
                state, media = self._state(), p.encode_media(*self.snapshot["media"])
                connected = self.link.connected
                changed = state != last_state or media != last_media
                if connected and (changed or not was_connected or now - last_sent_at >= REFRESH_S):
                    if self.link.send(state) and self.link.send(media):
                        last_state, last_media, last_sent_at = state, media, now

                if (connected, self.mic_muted) != last_icon:
                    last_icon = (connected, self.mic_muted)
                    self.on_change()
                was_connected = connected
            except Exception:
                # Normalmente um app que fechou no meio da leitura do áudio: relê a lista e segue.
                log.exception("erro no loop de áudio")
                last_refresh = 0.0
                time.sleep(0.2)
        # Solta os objetos de áudio antes do CoUninitialize, senão o app fecha com erro.
        self.mixer.channels = []
        self._mics = None
        gc.collect()
        comtypes.CoUninitialize()
