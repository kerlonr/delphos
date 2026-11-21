"""Instala o Delphos no PC do usuário: pasta de programas, menu Iniciar e "Aplicativos instalados" do Windows."""
import os
import shutil
import subprocess
import sys
import winreg

import psutil
from win32com.client import Dispatch

from . import VERSION

INSTALL_DIR = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Delphos")
INSTALLED_EXE = os.path.join(INSTALL_DIR, "Delphos.exe")
SHORTCUT = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Delphos.lnk")
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Delphos"


def is_exe() -> bool:
    return getattr(sys, "frozen", False)


def is_installed() -> bool:
    return os.path.exists(INSTALLED_EXE)


def running_installed() -> bool:
    return is_exe() and os.path.normcase(sys.executable) == os.path.normcase(INSTALLED_EXE)


def installed_version() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            return winreg.QueryValueEx(k, "DisplayVersion")[0]
    except FileNotFoundError:
        return None


def install() -> None:
    """Copia este exe para a pasta de programas e registra no Windows."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    shutil.copy2(sys.executable, INSTALLED_EXE)

    shortcut = Dispatch("WScript.Shell").CreateShortcut(SHORTCUT)
    shortcut.TargetPath = INSTALLED_EXE
    shortcut.WorkingDirectory = INSTALL_DIR
    shortcut.IconLocation = INSTALLED_EXE
    shortcut.Save()

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, value in (("DisplayName", "Delphos"), ("DisplayVersion", VERSION), ("Publisher", "Delphos"),
                            ("DisplayIcon", INSTALLED_EXE), ("InstallLocation", INSTALL_DIR),
                            ("UninstallString", f'"{INSTALLED_EXE}" --uninstall')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def start_installed_after_exit() -> None:
    """Abre o Delphos instalado depois que este fechar (só um Delphos roda por vez)."""
    subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & start "" "{INSTALLED_EXE}"',
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)


def uninstall(run_key: str) -> None:
    """Remove atalho, registros e a pasta. Chamado pelo "Desinstalar" do Windows (Delphos.exe --uninstall)."""
    for p in psutil.process_iter(["name"]):
        if p.info["name"] == "Delphos.exe" and p.pid != os.getpid():
            p.kill()
    if os.path.exists(SHORTCUT):
        os.remove(SHORTCUT)
    for key, value in ((run_key, "Delphos"), (UNINSTALL_KEY, None)):
        try:
            if value:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, value)
            else:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass
    # O exe em uso não pode se apagar: a pasta é removida logo depois que ele fechar.
    subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & rmdir /s /q "{INSTALL_DIR}"',
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
