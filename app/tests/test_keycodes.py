from delphos import keycodes as k


def test_known_labels():
    assert k.label(0x7E00) == "Mic Mute"
    assert k.label(0x7E01) == "Próximo app"
    assert k.label(0x00AE) == "Play/Pause"
    assert k.label(0x0068) == "F13"
    assert k.label(0x080F) == "Bloquear tela"
    assert k.label(0x0000) == "Nenhuma"


def test_shortcut_labels():
    assert k.label(0x0100 | 0x06) == "Copiar"  # preset vence o nome genérico
    assert k.label(0x0100 | 0x04) == "Ctrl+A"
    assert k.label(0x0A16) == "Recorte de tela"  # Win+Shift+S é um preset
    assert k.label(0x0300 | 0x17) == "Ctrl+Shift+T"
    assert k.label(0x0C04) == "Alt+Win+A"


def test_unknown_is_hex():
    assert k.label(0x5300) == "0x5300"


def test_shortcut_from_js():
    assert k.from_js(["ctrl", "shift"], "KeyT") == 0x0317
    assert k.from_js(["meta"], "KeyL") == 0x080F
    assert k.from_js([], "F13") == 0x0068
    assert k.from_js(["alt"], "Digit1") == 0x041E
    assert k.from_js([], "ArrowLeft") == 0x0050
    assert k.from_js(["ctrl"], "Unidentified") is None


def test_catalog_has_categories_and_unique_codes():
    cats = k.catalog()
    names = [c["name"] for c in cats]
    assert names[:3] == ["Delphos", "Mídia", "Sistema"] and "Camadas" in names
    codes = [i["code"] for c in cats for i in c["items"]]
    assert len(codes) == len(set(codes))
    assert 0x7E00 in codes and 0x0073 in codes  # Mic Mute e F24


def test_layer_macro_and_action_codes():
    assert k.label(0x5221) == "Segurar: camada 1"
    assert k.label(0x5200) == "Ir para camada 0"
    assert k.label(0x7700) == "Macro 1" and k.macro_index(0x770F) == 15 and k.macro_index(0x7710) is None
    assert k.label(0x7E06) == "Ação 1" and k.action_index(0x7E15) == 15 and k.action_index(0x7E05) is None
