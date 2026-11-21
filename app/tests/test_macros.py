import pytest

from delphos import macros as m


def test_text_and_keys_roundtrip():
    steps = [{"type": "text", "value": "ola"}, {"type": "tap", "key": 0x28},
             {"type": "delay", "ms": 250}, {"type": "down", "key": 0xE0}, {"type": "up", "key": 0xE0}]
    data = m.encode(steps)
    assert data == b"ola\x01\x01\x28\x01\x04250|\x01\x02\xe0\x01\x03\xe0"
    assert m.decode(data) == steps


def test_text_drops_non_ascii_and_control_prefix():
    assert m.encode([{"type": "text", "value": "aç\x01b"}]) == b"ab"


def test_shortcut_expands_to_hold_and_release():
    assert m.shortcut_steps(0x0300 | 0x17) == [  # Ctrl+Shift+T
        {"type": "down", "key": 0xE0}, {"type": "down", "key": 0xE1},
        {"type": "tap", "key": 0x17},
        {"type": "up", "key": 0xE1}, {"type": "up", "key": 0xE0},
    ]


def test_split_and_join_buffer():
    buf = m.join([b"a", b"", b"bc"], 20)
    assert len(buf) == 20 and buf[-1] == 0
    assert m.split(buf)[:3] == [b"a", b"", b"bc"]
    assert len(m.split(buf)) == 16


def test_join_rejects_overflow():
    with pytest.raises(ValueError):
        m.join([b"x" * 30], 20)
