"""Conexão USB (Raw HID) com o Delphos. Só a thread daqui mexe no dispositivo: o hidapi não é thread-safe."""
import logging
import queue
import threading
from typing import Callable

import hid

from . import protocol as p

VID, PID = 0x544D, 0x0010
USAGE_PAGE, USAGE = 0xFF60, 0x61  # interface Raw HID do VIA

log = logging.getLogger(__name__)


def find_path() -> bytes | None:
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE and d["usage"] == USAGE:
            return d["path"]
    return None


class HidLink:
    """Mantém o Delphos conectado (reconecta sozinho) e entrega o que ele manda."""

    def __init__(self, on_event: Callable[[int, int], None], on_key: Callable[[int, int, bool], None]) -> None:
        self._on_event = on_event
        self._on_key = on_key
        self._out: queue.Queue[bytes] = queue.Queue(maxsize=128)
        self._stop = threading.Event()
        self._request_lock = threading.Lock()
        self._waiting_for: bytes | None = None
        self._reply: bytes | None = None
        self._got_reply = threading.Event()
        self.connected = False
        self._thread = threading.Thread(target=self._run, name="hidlink", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def send(self, report: bytes) -> bool:
        if not self.connected:
            return False
        try:
            self._out.put_nowait(report)
            return True
        except queue.Full:
            return False

    def request(self, report: bytes, match: int = 1, timeout: float = 1.0) -> bytes | None:
        """Manda e espera a resposta. O teclado repete o começo do pedido na resposta: `match` diz quantos
        bytes conferir (4 nos pedaços de buffer, que repetem comando, posição e tamanho)."""
        report = report.ljust(p.REPORT_SIZE, b"\x00")
        with self._request_lock:
            self._got_reply.clear()
            self._reply = None
            self._waiting_for = report[:match]
            if self.send(report):
                self._got_reply.wait(timeout)
            self._waiting_for = None
            return self._reply

    def hello(self) -> tuple[int, int] | None:
        reply = self.request(p.command(p.HELLO))
        return p.decode_hello(reply) if reply else None

    def _run(self) -> None:
        while not self._stop.is_set():
            path = find_path()
            if path:
                dev = hid.device()
                try:
                    dev.open_path(path)
                    self.connected = True
                    log.info("Delphos conectado")
                    self._loop(dev)
                except (OSError, ValueError) as e:
                    log.info("Delphos desconectado: %s", e)
                finally:
                    self.connected = False
                    dev.close()
                    while not self._out.empty():
                        self._out.get_nowait()
            self._stop.wait(1.0)

    def _loop(self, dev) -> None:
        while not self._stop.is_set():
            while not self._out.empty():
                if dev.write(b"\x00" + self._out.get_nowait()) < 0:
                    raise OSError("falha na escrita")
            data = dev.read(p.REPORT_SIZE, 20)
            if not data:
                continue
            report = bytes(data)
            event, key = p.decode_event(report), p.decode_key(report)
            if event is not None:
                self._on_event(*event)
            elif key is not None:
                self._on_key(*key)
            elif self._waiting_for and report.startswith(self._waiting_for):
                self._reply = report
                self._got_reply.set()
