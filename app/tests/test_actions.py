import pytest

from delphos import actions


def test_site_gets_https():
    assert actions.normalize({"type": "site", "target": " youtube.com "})["target"] == "https://youtube.com"
    assert actions.normalize({"type": "site", "target": "http://a.b"})["target"] == "http://a.b"


def test_invalid_rejected():
    with pytest.raises(ValueError):
        actions.normalize({"type": "comando", "target": "rm -rf"})
    with pytest.raises(ValueError):
        actions.normalize({"type": "site", "target": "  "})


def test_describe():
    assert actions.describe({"type": "program", "target": r"C:\Apps\Discord\Discord.exe"}) == "Discord"
    assert actions.describe({"type": "folder", "target": "D:\Projetos\\"}) == "Projetos"
    assert actions.describe({"type": "site", "target": "https://www.youtube.com/watch?v=1"}) == "www.youtube.com"
    assert actions.describe({"type": "mute_app", "target": "spotify.exe", "label": "Spotify"}) == "Spotify"


class FakeChannel:
    def __init__(self, key):
        self.key, self.muted = key, False

    def get_mute(self):
        return self.muted

    def set_mute(self, m):
        self.muted = m


def test_mute_app_toggles_only_that_app():
    spotify, chrome = FakeChannel("spotify.exe"), FakeChannel("chrome.exe")
    actions.run({"type": "mute_app", "target": "spotify.exe"}, [spotify, chrome])
    assert spotify.muted and not chrome.muted
