"""Accesos directos de Windows (escritorio y menu Inicio) para abrir TrefotFarm con su icono."""

import sys
from pathlib import Path

from trefot.rutas import ASSETS, RAIZ

NOMBRE = "Trefot Farm.lnk"
ICONO = ASSETS / "icono" / "trefot.ico"
SCRIPT = RAIZ / "TrefotFarm.pyw"


def _python_sin_consola() -> Path:
    actual = Path(sys.executable)
    sin_consola = actual.with_name("pythonw.exe")
    return sin_consola if sin_consola.is_file() else actual


def _carpetas() -> list[Path]:
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    return [Path(shell.SpecialFolders("Desktop")), Path(shell.SpecialFolders("Programs"))]


def existen() -> bool:
    try:
        return all((c / NOMBRE).is_file() for c in _carpetas())
    except Exception:
        return False


def crear() -> list[Path]:
    """Crea (o rehace) los accesos directos. Devuelve donde quedaron."""
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    hechos = []
    for carpeta in _carpetas():
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / NOMBRE
        acceso = shell.CreateShortCut(str(ruta))
        acceso.TargetPath = str(_python_sin_consola())
        acceso.Arguments = f'"{SCRIPT}"'
        acceso.WorkingDirectory = str(RAIZ)
        acceso.IconLocation = f"{ICONO},0"
        acceso.Description = "Autofarming para The Seven Deadly Sins: Grand Cross"
        acceso.save()
        hechos.append(ruta)
    return hechos


if __name__ == "__main__":  # lo usa Instalar.bat
    for ruta in crear():
        print(f"Acceso directo creado: {ruta}")
