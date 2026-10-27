"""Accesos directos de Windows (escritorio y menu Inicio) para abrir LumenFarm con su icono."""

import sys
from pathlib import Path

from lumen.rutas import ASSETS, RAIZ

NOMBRE = "Lumen Farm.lnk"
NOMBRE_VIEJO = "Trefot Farm.lnk"  # el de la version 2
ICONO = ASSETS / "icono" / "lumen.ico"
SCRIPT = RAIZ / "LumenFarm.pyw"


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


def migrar_viejos() -> bool:
    """Cambia los accesos de la version 2 por los nuevos. True si habia alguno."""
    try:
        viejos = [c / NOMBRE_VIEJO for c in _carpetas() if (c / NOMBRE_VIEJO).is_file()]
        if not viejos:
            return False
        crear()
        for ruta in viejos:
            ruta.unlink(missing_ok=True)
        return True
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
