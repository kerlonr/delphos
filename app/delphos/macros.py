"""Macros do VIA: as 16 ficam juntas num buffer da EEPROM, separadas por \\0, no formato do send_string do QMK.

Cada passo vira bytes assim:
  texto            o próprio texto (o teclado digita como se fosse layout US)
  tecla            01 01 <tecla>      apertar e soltar
  segurar/soltar   01 02 <tecla> / 01 03 <tecla>
  esperar          01 04 <ms> |
"""
PREFIX, TAP, DOWN, UP, DELAY = 1, 1, 2, 3, 4
COUNT = 16

MOD_KEYS = {0x0100: 0xE0, 0x0200: 0xE1, 0x0400: 0xE2, 0x0800: 0xE3}  # Ctrl, Shift, Alt, Win (esquerdos)


def encode(steps: list[dict]) -> bytes:
    out = bytearray()
    for step in steps:
        kind = step["type"]
        if kind == "text":
            out += step["value"].encode("ascii", "ignore").replace(b"\x00", b"").replace(bytes([PREFIX]), b"")
        elif kind in ("tap", "down", "up"):
            out += bytes([PREFIX, {"tap": TAP, "down": DOWN, "up": UP}[kind], step["key"] & 0xFF])
        elif kind == "delay":
            out += bytes([PREFIX, DELAY]) + str(int(step["ms"])).encode() + b"|"
    return bytes(out)


def decode(data: bytes) -> list[dict]:
    steps: list[dict] = []
    i = 0
    while i < len(data):
        if data[i] == PREFIX and i + 1 < len(data):
            code = data[i + 1]
            if code == DELAY:
                end = data.find(b"|", i + 2)
                end = len(data) if end < 0 else end
                steps.append({"type": "delay", "ms": int(data[i + 2:end] or 0)})
                i = end + 1
            else:
                kind = {TAP: "tap", DOWN: "down", UP: "up"}.get(code, "tap")
                steps.append({"type": kind, "key": data[i + 2] if i + 2 < len(data) else 0})
                i += 3
            continue
        start = i
        while i < len(data) and data[i] != PREFIX:
            i += 1
        text = data[start:i].decode("ascii", "replace")
        if steps and steps[-1]["type"] == "text":
            steps[-1]["value"] += text
        else:
            steps.append({"type": "text", "value": text})
    return steps


def shortcut_steps(keycode: int) -> list[dict]:
    """Atalho do app (ex. Ctrl+C = 0x0106) vira: segurar Ctrl, apertar C, soltar Ctrl."""
    mods = [key for bit, key in MOD_KEYS.items() if keycode & bit]
    return ([{"type": "down", "key": m} for m in mods] + [{"type": "tap", "key": keycode & 0xFF}] +
            [{"type": "up", "key": m} for m in reversed(mods)])


def split(buffer: bytes) -> list[bytes]:
    parts = buffer.split(b"\x00")
    return (parts + [b""] * COUNT)[:COUNT]


def join(macros: list[bytes], size: int) -> bytes:
    data = b"\x00".join(macros[:COUNT]) + b"\x00"
    if len(data) > size:
        raise ValueError(f"as macros ocupam {len(data)} bytes, o Delphos guarda {size}")
    return data.ljust(size, b"\x00")
