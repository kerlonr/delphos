import time

import pytest

from delphos.hidlink import HidLink, find_path
from delphos.keymap import SLOTS, Keymap

pytestmark = [pytest.mark.live, pytest.mark.skipif(find_path() is None, reason="Delphos não conectado")]


@pytest.fixture(scope="module")
def km():
    link = HidLink(lambda *e: None, lambda *k: None)
    link.start()
    for _ in range(30):
        if link.connected:
            break
        time.sleep(0.1)
    yield Keymap(link)
    link.stop()


def test_reads_all_layers(km):
    layers = km.read_all()
    assert len(layers) == 4
    assert all(set(layer) == set(SLOTS) for layer in layers)


def test_set_key_on_layer_2_and_restore(km):
    before = km.read_all()[2]["1,0"]
    try:
        km.set_slot(2, "1,0", 0x0073)  # F24
        assert km.read_all()[2]["1,0"] == 0x0073
    finally:
        km.set_slot(2, "1,0", before)
    assert km.read_all()[2]["1,0"] == before


def test_encoder_roundtrip_and_restore(km):
    before = km.read_all()[1]["cw"]
    try:
        km.set_slot(1, "cw", 0x00A9)
        assert km.read_all()[1]["cw"] == 0x00A9
    finally:
        km.set_slot(1, "cw", before)


def test_macro_buffer_roundtrip_and_restore(km):
    before = km.read_macros()
    try:
        test = b"delphos\x00".ljust(len(before), b"\x00")
        km.write_macros(test)
        assert km.read_macros() == test
    finally:
        km.write_macros(before)
    assert km.read_macros() == before


def test_bad_slot_rejected(km):
    with pytest.raises(ValueError):
        km.set_slot(0, "5,5", 0x0004)
