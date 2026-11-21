"""Mensagens Raw HID entre o PC e o Delphos. Igual a keymaps/default/delphos_proto.h."""
import unicodedata

REPORT_SIZE = 32
PROTOCOL_VERSION = 2

STATE = 0x40       # PC -> teclado: mic, volume e nome do item selecionado
EVENT = 0x41       # teclado -> PC: tecla do Delphos (EV_*)
HELLO = 0x42       # PC -> teclado, responde a versão
BOOTLOADER = 0x43  # PC -> teclado: entra no modo de gravação
MEDIA = 0x44       # PC -> teclado: música tocando
KEY = 0x46         # teclado -> PC: tecla apertada/solta, para o app acender o desenho
TEST = 0x47        # PC -> teclado: padrão de teste na tela

ENC_CW_ROW, ENC_CCW_ROW = 254, 255  # linha que o QMK usa para o giro do encoder

EV_MIC_MUTE, EV_NEXT, EV_PREV, EV_UP, EV_DOWN, EV_MUTE, EV_PLAY, EV_NEXT_TRACK, EV_PREV_TRACK, EV_ACTION = range(1, 11)

MEDIA_NONE, MEDIA_PLAYING, MEDIA_PAUSED = 0, 1, 2

NAME_MAX = 20
MEDIA_TEXT_MAX = 29


def _pad(data: bytes) -> bytes:
    return data[:REPORT_SIZE].ljust(REPORT_SIZE, b"\x00")


def ascii_text(s: str, limit: int) -> bytes:
    """A fonte da tela só tem ASCII: "Música" vira "Musica", o resto vira '?'."""
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return plain.encode("ascii", "replace")[:limit] + b"\x00"


def command(cmd: int) -> bytes:
    return _pad(bytes([cmd]))


def encode_state(mic_muted: bool, item_muted: bool, volume: int, index: int, total: int, name: str) -> bytes:
    flags = (1 if mic_muted else 0) | (2 if item_muted else 0)
    volume = max(0, min(100, int(volume)))
    return _pad(bytes([STATE, PROTOCOL_VERSION, flags, volume, index & 0xFF, total & 0xFF]) + ascii_text(name, NAME_MAX))


def encode_media(status: int, text: str) -> bytes:
    return _pad(bytes([MEDIA, status]) + ascii_text(text, MEDIA_TEXT_MAX))


def decode_event(report: bytes) -> tuple[int, int] | None:
    """(evento, número da ação). O número só vale para EV_ACTION."""
    if len(report) >= 3 and report[0] == EVENT and EV_MIC_MUTE <= report[1] <= EV_ACTION:
        return report[1], report[2]
    return None


def decode_hello(report: bytes) -> tuple[int, int] | None:
    """(versão do protocolo, versão do firmware)"""
    if len(report) >= 3 and report[0] == HELLO:
        return report[1], report[2]
    return None


def decode_key(report: bytes) -> tuple[int, int, bool] | None:
    """(linha, coluna, apertou)"""
    if len(report) >= 4 and report[0] == KEY:
        return report[1], report[2], bool(report[3])
    return None
