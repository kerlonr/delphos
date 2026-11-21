"""Música/vídeo tocando, por app, via controle de mídia do Windows."""
import asyncio
import logging
import os
import threading

from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus

from . import protocol as p

log = logging.getLogger(__name__)

SEP = "\x1f"  # separa título e artista (títulos do YouTube costumam ter " - ")


def match_session(aumids: list[str], exe_key: str | None) -> int | None:
    """Sessão de mídia do app selecionado. O id pode ser da loja ("SpotifyAB...!Spotify") ou simples ("Chrome")."""
    if not exe_key or exe_key == "__master__":
        return None
    stem = os.path.splitext(exe_key)[0].lower()
    for i, aumid in enumerate(aumids):
        if stem in aumid.lower():
            return i
    return None


def media_text(title: str, artist: str) -> str:
    return f"{title}{SEP}{artist}" if title and artist else title


class Media:
    """A API do Windows é assíncrona: roda num loop próprio e o engine chama info()/command()."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="media", daemon=True).start()
        self._manager = None

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=2)

    async def _session(self, exe_key):
        if self._manager is None:
            self._manager = await SessionManager.request_async()
        sessions = list(self._manager.get_sessions())
        i = match_session([s.source_app_user_model_id for s in sessions], exe_key)
        # "Geral" ou app sem mídia: usa a mídia que o Windows considera atual.
        return sessions[i] if i is not None else self._manager.get_current_session()

    async def _info(self, exe_key):
        session = await self._session(exe_key)
        if session is None:
            return p.MEDIA_NONE, ""
        props = await session.try_get_media_properties_async()
        status = {PlaybackStatus.PLAYING: p.MEDIA_PLAYING, PlaybackStatus.PAUSED: p.MEDIA_PAUSED}.get(
            session.get_playback_info().playback_status, p.MEDIA_NONE)
        return status, media_text(props.title or "", props.artist or "")

    async def _command(self, exe_key, action):
        session = await self._session(exe_key)
        if session is None:
            return False
        run = {p.EV_PLAY: session.try_toggle_play_pause_async,
               p.EV_NEXT_TRACK: session.try_skip_next_async,
               p.EV_PREV_TRACK: session.try_skip_previous_async}[action]
        return await run()

    def info(self, exe_key: str | None) -> tuple[int, str]:
        try:
            return self._run(self._info(exe_key))
        except Exception:
            return p.MEDIA_NONE, ""

    def command(self, exe_key: str | None, action: int) -> None:
        try:
            self._run(self._command(exe_key, action))
        except Exception:
            log.exception("falha no comando de mídia")
