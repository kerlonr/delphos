from delphos.media import match_session, media_only, media_text

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


def test_media_only_lists_silent_spotify():
    chans = media_only(AUMIDS, set(), {"spotify.exe", "chrome.exe"})
    assert [(c.key, c.name) for c in chans] == [("spotify.exe", "Spotify"), ("chrome.exe", "Chrome")]
    assert chans[0].silent and chans[0].get_volume() == 1.0


def test_media_only_skips_apps_with_audio_and_not_running():
    # chrome já tem áudio; msedge e o id do Firefox (hash) não são processos rodando
    chans = media_only(AUMIDS + ["308046B0AF4A39CB"], {"chrome.exe"}, {"spotify.exe", "chrome.exe"})
    assert [c.key for c in chans] == ["spotify.exe"]
    assert media_only(AUMIDS, {"spotify.exe"}, {"spotify.exe"}) == []
