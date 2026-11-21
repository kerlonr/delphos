import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_configure(config):
    config.addinivalue_line("markers", "live: precisa do Windows real (áudio/teclado)")
    # Aviso de dentro do sounddevice com o numpy novo; não é do nosso código.
    config.addinivalue_line("filterwarnings", "ignore::DeprecationWarning:sounddevice")
