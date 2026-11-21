"""Lista de canais (Geral + apps) e item selecionado. Sem dependência de Windows."""
from typing import Protocol


class Channel(Protocol):
    key: str
    name: str

    def get_volume(self) -> float: ...
    def set_volume(self, v: float) -> None: ...
    def get_mute(self) -> bool: ...
    def set_mute(self, m: bool) -> None: ...


def ordered(master: Channel, apps: list[Channel]) -> list[Channel]:
    return [master] + sorted(apps, key=lambda c: c.name.lower())


class Mixer:
    def __init__(self) -> None:
        self.channels: list[Channel] = []
        self.index = 0

    @property
    def total(self) -> int:
        return len(self.channels)

    @property
    def current(self) -> Channel | None:
        return self.channels[self.index] if self.channels else None

    def refresh(self, channels: list[Channel]) -> None:
        key = self.current.key if self.current else None
        self.channels = channels
        keys = [c.key for c in channels]
        self.index = keys.index(key) if key in keys else 0

    def next(self) -> None:
        if self.channels:
            self.index = (self.index + 1) % self.total

    def prev(self) -> None:
        if self.channels:
            self.index = (self.index - 1) % self.total

    def step(self, delta_pct: int) -> None:
        c = self.current
        if c:
            pct = round(c.get_volume() * 100) + delta_pct
            c.set_volume(max(0, min(100, pct)) / 100)

    def toggle_mute(self) -> None:
        c = self.current
        if c:
            c.set_mute(not c.get_mute())
