import os
import sys

VERSION = "2.1.0"


def resource(*parts: str) -> str:
    """Caminho de um arquivo do app, rodando pelo código-fonte ou pelo exe do PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)
