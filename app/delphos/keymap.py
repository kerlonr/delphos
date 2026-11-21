"""Lê e grava as teclas e macros do Delphos pelo protocolo do VIA (ficam salvas na EEPROM do teclado)."""
from .hidlink import HidLink

# Comandos do VIA (quantum/via.h do QMK)
SET_KEY, RESET = 0x05, 0x06
MACRO_SIZE, MACRO_GET, MACRO_SET = 0x0D, 0x0E, 0x0F
LAYER_COUNT, KEYMAP_GET = 0x11, 0x12
GET_ENC, SET_ENC = 0x14, 0x15

ROWS, COLS = 3, 5
CHUNK = 28  # bytes por pedido (32 menos o cabeçalho)
KEYS = [(r, c) for r in range(3) for c in range(4)]
ENCODER_BUTTON = (0, 4)  # o clique do encoder é a posição (0,4) da matriz
SLOTS = [f"{r},{c}" for r, c in KEYS + [ENCODER_BUTTON]] + ["ccw", "cw"]


class Keymap:
    def __init__(self, link: HidLink) -> None:
        self.link = link

    def _request(self, *data: int, match: int = 1) -> bytes:
        reply = self.link.request(bytes(data), match)
        if reply is None or reply[0] != data[0]:
            raise OSError("o Delphos não respondeu")
        return reply

    def _read_buffer(self, command: int, size: int) -> bytes:
        out = bytearray()
        for offset in range(0, size, CHUNK):
            n = min(CHUNK, size - offset)
            out += self._request(command, offset >> 8, offset & 0xFF, n, match=4)[4:4 + n]
        return bytes(out)

    def layer_count(self) -> int:
        return self._request(LAYER_COUNT)[1]

    def read_all(self) -> list[dict]:
        """Todas as camadas: [{"0,0": código, ..., "ccw": código, "cw": código}, ...]"""
        layers = self.layer_count()
        raw = self._read_buffer(KEYMAP_GET, layers * ROWS * COLS * 2)
        result = []
        for layer in range(layers):
            keys = {}
            for r, c in KEYS + [ENCODER_BUTTON]:
                i = ((layer * ROWS + r) * COLS + c) * 2
                keys[f"{r},{c}"] = raw[i] << 8 | raw[i + 1]
            for slot, clockwise in (("ccw", 0), ("cw", 1)):
                reply = self._request(GET_ENC, layer, 0, clockwise, match=4)
                keys[slot] = reply[4] << 8 | reply[5]
            result.append(keys)
        return result

    def set_slot(self, layer: int, slot: str, code: int) -> None:
        """slot = "linha,coluna" (tecla ou clique do encoder), "ccw" ou "cw" (giro do encoder)."""
        if slot not in SLOTS:
            raise ValueError(slot)
        if slot in ("ccw", "cw"):
            self._request(SET_ENC, layer, 0, int(slot == "cw"), code >> 8, code & 0xFF)
        else:
            r, c = (int(x) for x in slot.split(","))
            self._request(SET_KEY, layer, r, c, code >> 8, code & 0xFF)

    def reset(self) -> None:
        self._request(RESET)

    def macro_size(self) -> int:
        reply = self._request(MACRO_SIZE)
        return reply[1] << 8 | reply[2]

    def read_macros(self) -> bytes:
        return self._read_buffer(MACRO_GET, self.macro_size())

    def write_macros(self, buffer: bytes) -> None:
        for offset in range(0, len(buffer), CHUNK):
            part = buffer[offset:offset + CHUNK]
            self._request(MACRO_SET, offset >> 8, offset & 0xFF, len(part), *part, match=4)
