"""Áudio do Windows via pycaw. Usar sempre da mesma thread (COM)."""
import os
from functools import cache

import comtypes
import win32api
from comtypes import CLSCTX_ALL
from pycaw.constants import DEVICE_STATE, AudioSessionState, CLSID_MMDeviceEnumerator, EDataFlow, ERole
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IMMDeviceEnumerator


def _enumerator():
    return comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER)


def _endpoint_volume(dev):
    # QueryInterface e não o `cast` do exemplo do pycaw: o cast libera o ponteiro duas vezes e o app fecha sozinho.
    return dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)


class MasterChannel:
    """Volume geral do Windows (saída padrão)."""

    key = "__master__"
    name = "Geral"

    def __init__(self) -> None:
        default = _enumerator().GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
        self._ep = _endpoint_volume(default)

    def get_volume(self) -> float:
        return self._ep.GetMasterVolumeLevelScalar()

    def set_volume(self, v: float) -> None:
        self._ep.SetMasterVolumeLevelScalar(v, None)

    def get_mute(self) -> bool:
        return bool(self._ep.GetMute())

    def set_mute(self, m: bool) -> None:
        self._ep.SetMute(m, None)


class AppChannel:
    """Um app = todas as sessões de áudio do mesmo .exe (o Chrome abre várias)."""

    def __init__(self, key: str, name: str, volumes: list) -> None:
        self.key, self.name, self._vols = key, name, volumes

    def get_volume(self) -> float:
        return self._vols[0].GetMasterVolume()

    def set_volume(self, v: float) -> None:
        for sv in self._vols:
            sv.SetMasterVolume(v, None)

    def get_mute(self) -> bool:
        return all(sv.GetMute() for sv in self._vols)

    def set_mute(self, m: bool) -> None:
        for sv in self._vols:
            sv.SetMute(m, None)


@cache
def friendly_name(exe_path: str) -> str:
    """Descrição do .exe ("Google Chrome"); se não tiver, o nome do arquivo ("Steam")."""
    try:
        lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
        desc = win32api.GetFileVersionInfo(exe_path, f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription")
        if desc and desc.strip():
            return desc.strip()
    except Exception:
        pass
    return os.path.splitext(os.path.basename(exe_path))[0].capitalize()


def app_channels() -> list[AppChannel]:
    groups: dict[str, AppChannel] = {}
    for s in AudioUtilities.GetAllSessions():
        try:
            if s.Process is None or s.State == AudioSessionState.Expired.value:
                continue
            exe = s.Process.exe()
        except Exception:  # o processo fechou enquanto a lista era lida
            continue
        key = os.path.basename(exe).lower()
        if key not in groups:
            groups[key] = AppChannel(key, friendly_name(exe), [])
        groups[key]._vols.append(s.SimpleAudioVolume)
    return list(groups.values())


class Mics:
    """Mute de todos os microfones ativos. O estado é sempre lido do Windows.

    Mutar = ligar o mute do Windows E zerar o volume do microfone. Alguns headsets (o H510-PRO, por
    exemplo) dizem que fazem o mute no hardware e ignoram: o Windows mostra mudo e o som passa.
    Volume 0 silencia de verdade (medido: todas as amostras viram zero). Ao desmutar, o volume volta
    ao que era; os volumes ficam em `saved_volumes` (salvo nos ajustes) para sobreviver ao app fechar.
    """

    def __init__(self, saved_volumes: dict, save) -> None:
        self._saved = saved_volumes  # id do microfone -> volume antes de mutar
        self._save = save
        self._known: set[str] = set()

    def _devices(self) -> list[tuple[str, str, object]]:
        """(id, nome, volume do microfone)"""
        devices = _enumerator().EnumAudioEndpoints(EDataFlow.eCapture.value, DEVICE_STATE.ACTIVE.value)
        out = []
        for i in range(devices.GetCount()):
            dev = devices.Item(i)
            name = AudioUtilities.CreateDevice(dev).FriendlyName or "Microfone"
            out.append((dev.GetId(), name, _endpoint_volume(dev)))
        return out

    def _mute(self, dev_id: str, ep) -> None:
        volume = ep.GetMasterVolumeLevelScalar()
        if volume > 0:
            self._saved[dev_id] = volume
        ep.SetMute(True, None)
        ep.SetMasterVolumeLevelScalar(0.0, None)

    def _unmute(self, dev_id: str, ep) -> None:
        ep.SetMute(False, None)
        if ep.GetMasterVolumeLevelScalar() == 0:
            ep.SetMasterVolumeLevelScalar(self._saved.get(dev_id, 1.0), None)

    def is_muted(self) -> bool:
        devs = self._devices()
        return bool(devs) and all(ep.GetMute() for _, _, ep in devs)

    def set_muted(self, muted: bool) -> None:
        for dev_id, _, ep in self._devices():
            self._mute(dev_id, ep) if muted else self._unmute(dev_id, ep)
        self._save()

    def toggle(self) -> bool:
        self.set_muted(not self.is_muted())
        return self.is_muted()

    def enforce(self) -> None:
        """Roda a cada segundo: mic plugado enquanto os outros estão mudos já entra mudo."""
        devs = self._devices()
        old = [ep for dev_id, _, ep in devs if dev_id in self._known]
        if old and all(ep.GetMute() for ep in old):
            for dev_id, _, ep in devs:
                if dev_id not in self._known:
                    self._mute(dev_id, ep)
                    self._save()
        self._known = {dev_id for dev_id, _, _ in devs}

    def list(self) -> list[tuple[str, bool]]:
        return [(name, bool(ep.GetMute())) for _, name, ep in self._devices()]
