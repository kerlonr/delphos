from delphos.mixer import Mixer, ordered


class FakeChannel:
    def __init__(self, key, name, vol=0.5, mute=False):
        self.key, self.name, self.vol, self.mute = key, name, vol, mute

    def get_volume(self):
        return self.vol

    def set_volume(self, v):
        self.vol = v

    def get_mute(self):
        return self.mute

    def set_mute(self, m):
        self.mute = m


MASTER = FakeChannel("__master__", "Geral")


def make(*names):
    return ordered(MASTER, [FakeChannel(n.lower(), n) for n in names])


def test_ordered_master_first_then_alpha():
    assert [c.name for c in make("spotify", "Discord", "chrome")] == ["Geral", "chrome", "Discord", "spotify"]


def test_next_prev_wrap():
    m = Mixer()
    m.refresh(make("A", "B"))
    m.prev()
    assert m.current.name == "B"
    m.next()
    assert m.index == 0 and m.total == 3


def test_step_clamps():
    m = Mixer()
    m.refresh([FakeChannel("k", "x", vol=0.99)])
    m.step(2)
    assert m.current.get_volume() == 1.0
    m.current.set_volume(0.01)
    m.step(-2)
    assert m.current.get_volume() == 0.0


def test_step_rounds_to_percent():
    m = Mixer()
    m.refresh([FakeChannel("k", "x", vol=0.333)])
    m.step(2)
    assert m.current.get_volume() == 0.35


def test_selected_app_disappears_goes_to_master():
    m = Mixer()
    m.refresh(make("A", "B"))
    m.next(); m.next()
    assert m.current.name == "B"
    m.refresh(make("A"))
    assert m.index == 0 and m.current.name == "Geral"


def test_selection_kept_when_other_app_appears():
    m = Mixer()
    m.refresh(make("B"))
    m.next()
    m.refresh(make("A", "B"))
    assert m.current.name == "B" and m.index == 2


def test_toggle_mute():
    m = Mixer()
    m.refresh(make("A"))
    m.toggle_mute()
    assert m.current.get_mute() is True


def test_empty_refresh_safe():
    m = Mixer()
    m.refresh([])
    m.next(); m.step(2); m.toggle_mute()
    assert m.current is None and m.total == 0
