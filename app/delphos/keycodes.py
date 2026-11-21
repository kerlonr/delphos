"""Códigos de tecla do QMK usados no editor do app (valores de quantum/keycodes.h)."""

MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_WIN = 0x0100, 0x0200, 0x0400, 0x0800

# Ordem igual a delphos_keycodes no keymap.c (QK_KB_0 = 0x7E00).
DELPHOS = [
    (0x7E00, "Mic Mute"), (0x7E01, "Próximo app"), (0x7E02, "App anterior"),
    (0x7E03, "Volume +"), (0x7E04, "Volume −"), (0x7E05, "Mutar app"),
]
MEDIA = [
    (0x00AE, "Play/Pause"), (0x00AB, "Próxima faixa"), (0x00AC, "Faixa anterior"), (0x00AD, "Stop"),
    (0x00A8, "Mute geral"), (0x00A9, "Volume Windows +"), (0x00AA, "Volume Windows −"),
]
SYSTEM = [
    (MOD_WIN | 0x0F, "Bloquear tela"), (0x0046, "Print Screen"), (MOD_WIN | MOD_SHIFT | 0x16, "Recorte de tela"),
    (MOD_WIN | 0x07, "Área de trabalho"), (MOD_WIN | 0x08, "Explorador"), (MOD_CTRL | MOD_SHIFT | 0x29, "Gerenciador de tarefas"),
    (0x00B2, "Calculadora"), (0x00B5, "Navegador"), (0x00B1, "E-mail"),
    (MOD_CTRL | 0x06, "Copiar"), (MOD_CTRL | 0x19, "Colar"), (MOD_CTRL | 0x1D, "Desfazer"),
]
FKEYS = [(0x0068 + i, f"F{13 + i}") for i in range(12)] + [(0x003A + i, f"F{1 + i}") for i in range(12)]
LETTERS = [(0x0004 + i, chr(ord("A") + i)) for i in range(26)] + [(0x001E + i, str((i + 1) % 10)) for i in range(10)]
OTHER = [
    (0x0028, "Enter"), (0x0029, "Esc"), (0x002A, "Backspace"), (0x002B, "Tab"), (0x002C, "Espaço"),
    (0x004C, "Delete"), (0x004A, "Home"), (0x004D, "End"), (0x004B, "Page Up"), (0x004E, "Page Down"),
    (0x0052, "↑"), (0x0051, "↓"), (0x0050, "←"), (0x004F, "→"),
    (0x0000, "Nenhuma"), (0x0001, "Transparente"),
]
# Camadas (QK_TO, QK_MOMENTARY e QK_TOGGLE_LAYER do QMK)
LAYERS = ([(0x5200 + n, f"Ir para camada {n}") for n in range(4)] +
          [(0x5220 + n, f"Segurar: camada {n}") for n in range(1, 4)] +
          [(0x5260 + n, f"Liga/desliga camada {n}") for n in range(1, 4)])

MACRO_0, MACRO_COUNT = 0x7700, 16    # QK_MACRO_0
ACTION_0, ACTION_COUNT = 0x7E06, 16  # ACTION_0 no keymap.c (logo depois das teclas do Delphos)

_CATS = [("Delphos", DELPHOS), ("Mídia", MEDIA), ("Sistema", SYSTEM), ("F-keys", FKEYS),
         ("Letras e números", LETTERS), ("Camadas", LAYERS), ("Outras", OTHER)]
_NAMES = {c: n for _, items in _CATS for c, n in items}
_NAMES.update({MACRO_0 + n: f"Macro {n + 1}" for n in range(MACRO_COUNT)})
_NAMES.update({ACTION_0 + n: f"Ação {n + 1}" for n in range(ACTION_COUNT)})
_BASIC = {c: n for c, n in FKEYS + LETTERS + OTHER}


def catalog() -> list[dict]:
    return [{"name": n, "items": [{"code": c, "label": l} for c, l in items]} for n, items in _CATS]


def macro_index(code: int) -> int | None:
    return code - MACRO_0 if MACRO_0 <= code < MACRO_0 + MACRO_COUNT else None


def action_index(code: int) -> int | None:
    return code - ACTION_0 if ACTION_0 <= code < ACTION_0 + ACTION_COUNT else None


def label(code: int) -> str:
    if code in _NAMES:
        return _NAMES[code]
    # Atalho = tecla simples (byte de baixo) + modificadores esquerdos (bits 0x0F00).
    key, mods = code & 0x00FF, code & 0xFF00
    if mods and (mods & ~0x0F00) == 0 and key in _BASIC:
        names = [name for bit, name in ((MOD_CTRL, "Ctrl"), (MOD_SHIFT, "Shift"), (MOD_ALT, "Alt"), (MOD_WIN, "Win"))
                 if mods & bit]
        return "+".join(names + [_BASIC[key]])
    return f"0x{code:04X}"


# Tecla vinda do navegador (KeyboardEvent.code) -> código HID
_JS = {f"Key{chr(ord('A') + i)}": 0x04 + i for i in range(26)}
_JS.update({f"Digit{(i + 1) % 10}": 0x1E + i for i in range(10)})
_JS.update({f"F{i + 1}": 0x3A + i for i in range(12)})
_JS.update({f"F{13 + i}": 0x68 + i for i in range(12)})
_JS.update({"Enter": 0x28, "Escape": 0x29, "Backspace": 0x2A, "Tab": 0x2B, "Space": 0x2C, "Delete": 0x4C,
            "Home": 0x4A, "End": 0x4D, "PageUp": 0x4B, "PageDown": 0x4E, "ArrowRight": 0x4F,
            "ArrowLeft": 0x50, "ArrowDown": 0x51, "ArrowUp": 0x52, "PrintScreen": 0x46})
_JS_MODS = {"ctrl": MOD_CTRL, "shift": MOD_SHIFT, "alt": MOD_ALT, "meta": MOD_WIN}


def from_js(mods: list[str], code: str) -> int | None:
    """Atalho gravado no app, ex. (["ctrl", "shift"], "KeyT") -> Ctrl+Shift+T no formato do QMK."""
    if code not in _JS:
        return None
    keycode = _JS[code]
    for name in mods:
        keycode |= _JS_MODS.get(name, 0)
    return keycode
