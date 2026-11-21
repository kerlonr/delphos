import sys
import time

import pytest

pytestmark = [pytest.mark.live, pytest.mark.skipif(sys.platform != "win32", reason="Windows only")]


# COM já é inicializado pelo comtypes na thread principal. Não chamar CoUninitialize:
# ponteiros do pycaw liberados depois disso derrubam o processo (0xC0000005).


def _mics():
    from delphos.audio import Mics
    m = Mics({}, lambda: None)
    if not m.list():
        pytest.skip("sem microfone")
    return m


def test_mic_toggle_roundtrip_restores_volume():
    m = _mics()
    volumes = {dev_id: ep.GetMasterVolumeLevelScalar() for dev_id, _, ep in m._devices()}
    before = m.is_muted()
    try:
        m.set_muted(False)
        volumes = {dev_id: ep.GetMasterVolumeLevelScalar() for dev_id, _, ep in m._devices()}
        assert m.toggle() is True
        assert all(muted for _, muted in m.list())
        assert all(ep.GetMasterVolumeLevelScalar() == 0 for _, _, ep in m._devices())
        assert m.toggle() is False
        for dev_id, _, ep in m._devices():
            assert abs(ep.GetMasterVolumeLevelScalar() - volumes[dev_id]) < 0.01
    finally:
        m.set_muted(before)


def test_muted_mic_records_only_silence():
    """O H510-PRO ignora o mute do Windows. Gravando de verdade, mudo tem que dar silêncio absoluto."""
    sd = pytest.importorskip("sounddevice")
    np = pytest.importorskip("numpy")
    m = _mics()
    wasapi = next(h for h in sd.query_hostapis() if "WASAPI" in h["name"])  # o mesmo caminho do Discord
    before = m.is_muted()
    try:
        with sd.InputStream(device=wasapi["default_input_device"], channels=1, samplerate=48000,
                            dtype="float32") as stream:
            m.set_muted(True)
            time.sleep(0.5)
            stream.read(stream.read_available)  # descarta o que foi gravado antes do mute
            peak = float(np.abs(stream.read(24000)[0]).max())
            assert peak < 1e-4, f"microfone mudo ainda grava som (pico {peak:.5f})"  # -80 dB: inaudível
    finally:
        m.set_muted(before)


def test_master_volume_range_and_restore():
    from delphos.audio import MasterChannel
    c = MasterChannel()
    v = c.get_volume()
    assert 0.0 <= v <= 1.0
    c.set_volume(v)
    assert abs(c.get_volume() - v) < 0.01


def test_app_channels_and_names():
    from delphos.audio import app_channels, friendly_name
    for ch in app_channels():
        assert ch.name and 0.0 <= ch.get_volume() <= 1.0
    assert friendly_name(sys.executable).lower().startswith("python")
    for ch in app_channels():
        assert ch.name.isprintable(), repr(ch.name)  # sem lixo depois do \0 do FileDescription
