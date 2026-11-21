"""Pede ao Delphos para entrar no modo de gravação. Firmware antigo ignora: use o reset ou o bootmagic."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import hid  # noqa: E402

from delphos import protocol as p  # noqa: E402
from delphos.hidlink import find_path  # noqa: E402

path = find_path()
if not path:
    sys.exit("Delphos não encontrado: entre no modo de gravação pelo reset ou bootmagic.")
dev = hid.device()
dev.open_path(path)
dev.write(b"\x00" + p.command(p.BOOTLOADER))
print("modo de gravação solicitado")
