from delphos.media import match_session, media_text

AUMIDS = ["SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "Chrome", "MSEdge"]


def test_match_store_spotify():
    assert match_session(AUMIDS, "spotify.exe") == 0


def test_match_plain_exe():
    assert match_session(AUMIDS, "chrome.exe") == 1


def test_no_match_or_master():
    assert match_session(AUMIDS, "discord.exe") is None
    assert match_session(AUMIDS, "__master__") is None
    assert match_session(AUMIDS, None) is None


def test_media_text():
    assert media_text("Stand By Me", "Ben E. King") == "Stand By MeBen E. King"
    assert media_text("GTA 6 - #7", "Canal") == "GTA 6 - #7Canal"
    assert media_text("Video", "") == "Video"
    assert media_text("", "") == ""
