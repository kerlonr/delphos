"""Gera, a partir da logo oficial (app/assets/logo_source.png), todos os formatos que o projeto usa:

  app/assets/delphos.png, delphos.ico   ícone do exe, da janela e da bandeja
  app/delphos/ui/logo.png              logo da interface
  keymaps/default/delphos_logo.h       logo 32x32 da tela do Delphos
  app/delphos/ui/font.js               fonte + logo da tela para o espelho do app
"""
import os
import re

from PIL import Image, ImageDraw

APP = os.path.dirname(os.path.abspath(__file__))
KEYMAP = os.path.join(os.path.dirname(APP), "keymaps", "default")
UI = os.path.join(APP, "delphos", "ui")
MARK = (255, 0, 255)


def cut_out(path: str) -> Image.Image:
    """Tira o fundo preto (tudo que está fora da borda branca) e devolve a logo num quadrado transparente."""
    img = Image.open(path).convert("RGB")
    ImageDraw.floodfill(img, (0, 0), MARK, thresh=40)
    alpha = Image.new("L", img.size)
    alpha.putdata([0 if pixel == MARK else 255 for pixel in img.get_flattened_data()])
    logo = Image.open(path).convert("RGBA")
    logo.putalpha(alpha)
    logo = logo.crop(alpha.getbbox())
    side = max(logo.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
    return square


def oled_bitmap(logo: Image.Image) -> list[int]:
    """32x32 de 1 bit (claro = pixel aceso), no formato da tela: 4 faixas de 8 linhas, bit 0 em cima."""
    on_black = Image.new("RGB", logo.size, "black")
    on_black.paste(logo, mask=logo.getchannel("A"))
    small = on_black.convert("L").resize((32, 32), Image.LANCZOS)
    return [sum((small.getpixel((x, page * 8 + bit)) > 110) << bit for bit in range(8))
            for page in range(4) for x in range(32)]


def c_array(values: list[int]) -> str:
    return ",\n    ".join(", ".join(f"0x{v:02X}" for v in values[i:i + 16]) for i in range(0, len(values), 16))


def main() -> None:
    logo = cut_out(os.path.join(APP, "assets", "logo_source.png"))
    logo.resize((256, 256), Image.LANCZOS).save(os.path.join(APP, "assets", "delphos.png"))
    logo.save(os.path.join(APP, "assets", "delphos.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    logo.resize((64, 64), Image.LANCZOS).save(os.path.join(UI, "logo.png"))

    oled = oled_bitmap(logo)
    with open(os.path.join(KEYMAP, "delphos_logo.h"), "w", encoding="utf-8", newline="\n") as f:
        f.write("#pragma once\n// Logo 32x32 da tela. Gerado por app/generate_assets.py.\n"
                f"static const uint8_t PROGMEM delphos_logo[] = {{\n    {c_array(oled)}\n}};\n")

    with open(os.path.join(KEYMAP, "delphos_font.h"), encoding="utf-8") as f:
        font_src = f.read()
    font = [int(v, 16) for v in re.findall(r"0x[0-9A-F]{2}", re.sub(r"//.*", "", font_src.split("{", 1)[1]))]
    with open(os.path.join(UI, "font.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("// Gerado por app/generate_assets.py a partir de keymaps/default/delphos_font.h e delphos_logo.h.\n"
                "const DF_FIRST = 0x20, DF_LAST = 0x7E;\n"
                f"const DF_FONT = [{','.join(map(str, font))}];\n"
                f"const DF_LOGO = [{','.join(map(str, oled))}];\n")


if __name__ == "__main__":
    main()
