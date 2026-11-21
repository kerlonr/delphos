from delphos import protocol as p


def test_state_layout():
    r = p.encode_state(True, False, 62, 1, 5, "Spotify")
    assert len(r) == 32
    assert r[0] == p.STATE and r[1] == p.PROTOCOL_VERSION
    assert r[2] == 0b01 and r[3] == 62 and r[4] == 1 and r[5] == 5
    assert r[6:14] == b"Spotify\x00"


def test_state_flags_item_muted():
    assert p.encode_state(False, True, 0, 0, 1, "")[2] == 0b10


def test_state_volume_clamped():
    assert p.encode_state(False, False, 150, 0, 1, "x")[3] == 100
    assert p.encode_state(False, False, -5, 0, 1, "x")[3] == 0


def test_state_name_truncated_and_terminated():
    r = p.encode_state(False, False, 0, 0, 1, "A" * 40)
    assert r[6:26] == b"A" * 20 and r[26] == 0


def test_state_non_ascii():
    assert p.encode_state(False, False, 0, 0, 1, "Música")[6:13] == b"Musica\x00"


def test_decode_event():
    assert p.decode_event(bytes([p.EVENT, p.EV_UP]) + bytes(30)) == (p.EV_UP, 0)
    assert p.decode_event(bytes([0x02, 1]) + bytes(30)) is None
    assert p.decode_event(bytes([p.EVENT, 99]) + bytes(30)) is None
    assert p.decode_event(b"") is None


def test_hello_roundtrip():
    assert p.command(p.HELLO)[0] == p.HELLO and len(p.command(p.HELLO)) == 32
    assert p.decode_hello(bytes([p.HELLO, 1, 3]) + bytes(29)) == (1, 3)
    assert p.decode_hello(bytes([0xFF]) + bytes(31)) is None


def test_v2_version_and_media_events():
    assert p.PROTOCOL_VERSION == 2
    assert (p.EV_PLAY, p.EV_NEXT_TRACK, p.EV_PREV_TRACK) == (7, 8, 9)
    assert p.decode_event(bytes([p.EVENT, p.EV_PREV_TRACK]) + bytes(30)) == (p.EV_PREV_TRACK, 0)
    assert p.decode_event(bytes([p.EVENT, p.EV_ACTION, 5]) + bytes(29)) == (p.EV_ACTION, 5)
    assert p.decode_event(bytes([p.EVENT, 11]) + bytes(30)) is None


def test_media_packet():
    r = p.encode_media(p.MEDIA_PLAYING, "Stand By Me - Ben E. King")
    assert len(r) == 32 and r[0] == p.MEDIA and r[1] == 1
    assert r[2:27] == b"Stand By Me - Ben E. King" and r[27] == 0


def test_media_packet_truncated_terminated():
    r = p.encode_media(p.MEDIA_PAUSED, "x" * 50)
    assert r[1] == 2 and r[2:31] == b"x" * 29 and r[31] == 0


def test_media_packet_strips_accents():
    assert p.encode_media(p.MEDIA_NONE, "Começaram")[2:12] == b"Comecaram\x00"


def test_key_event_and_test_pattern():
    assert p.decode_key(bytes([p.KEY, 2, 3, 1]) + bytes(28)) == (2, 3, True)
    assert p.decode_key(bytes([p.KEY, 254, 0, 1]) + bytes(28)) == (254, 0, True)
    assert p.decode_key(bytes([p.EVENT, 2, 3, 1]) + bytes(28)) is None
