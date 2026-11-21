"""Gravação do firmware: o Pro Micro reinicia no bootloader (aparece uma porta COM) e o avrdude grava."""
import logging
import subprocess
import time
import winreg

from . import resource

log = logging.getLogger(__name__)

BUNDLED_FW_VERSION = 7  # DP_FIRMWARE_VERSION do .hex que vai junto com o app


def serial_ports() -> set[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as k:
            return {winreg.EnumValue(k, i)[1] for i in range(winreg.QueryInfoKey(k)[1])}
    except OSError:
        return set()


def wait_new_port(before: set[str], timeout: float) -> str | None:
    """O bootloader fica uns 8 s no ar como uma porta COM nova."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        new = serial_ports() - before
        if new:
            return sorted(new)[0]
        time.sleep(0.1)
    return None


def flash(port: str) -> bool:
    cmd = [resource("tools", "avrdude.exe"), "-C", resource("tools", "avrdude.conf"),
           "-p", "atmega32u4", "-c", "avr109", "-P", port, "-b", "57600",
           "-U", f"flash:w:{resource('tools', 'delphos.hex')}:i"]
    result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout + result.stderr
    log.info("avrdude saiu com %s:\n%s", result.returncode, output[-1500:])
    return result.returncode == 0 and "verified" in output
