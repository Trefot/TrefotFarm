"""Actualizaciones obligatorias desde el repositorio privado de GitHub (con git).

Cualquier commit nuevo en la rama remota cuenta como actualizacion. Al actualizar:
  1. Si hay cambios locales en archivos del programa, se respaldan en logs/respaldo_<fecha>/.
  2. La copia local queda igual que la remota (tus capturas, config.yaml y logs no se tocan:
     estan fuera de git).
  3. Si cambio requirements.txt, se reinstalan las dependencias.
"""

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

from trefot.rutas import LOGS, RAIZ

RAMA = "master"
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ErrorActualizacion(RuntimeError):
    pass


@dataclass
class Estado:
    configurado: bool = False  # hay repositorio git con remoto
    hay_update: bool = False
    version_local: str = ""
    version_remota: str = ""
    cambios: list[str] = field(default_factory=list)  # mensajes de los commits nuevos
    error: str = ""  # sin internet, sin permiso...
    revisado: float = 0.0


def _git(*args: str, timeout: float = 60) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, creationflags=_SIN_VENTANA,
        )
    except FileNotFoundError as e:
        raise ErrorActualizacion("git no esta instalado.") from e
    except subprocess.TimeoutExpired as e:
        raise ErrorActualizacion("git tardo demasiado (¿sin internet?).") from e
    if r.returncode != 0:
        raise ErrorActualizacion((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"git {args[0]} fallo")
    return r.stdout.strip()


def _version_de(texto: str) -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', texto)
    return m.group(1) if m else "?"


def version_local() -> str:
    return _version_de((RAIZ / "trefot" / "__init__.py").read_text(encoding="utf-8"))


def url_remota() -> str:
    try:
        return _git("remote", "get-url", "origin", timeout=10)
    except ErrorActualizacion:
        return ""


def configurar_remoto(url: str) -> None:
    url = url.strip()
    if not url:
        raise ErrorActualizacion("Escribe la URL del repositorio.")
    if url_remota():
        _git("remote", "set-url", "origin", url)
    else:
        _git("remote", "add", "origin", url)


def revisar() -> Estado:
    estado = Estado(version_local=version_local(), revisado=time.time())
    if not (RAIZ / ".git").exists() or not url_remota():
        estado.error = "No hay repositorio remoto configurado."
        return estado
    estado.configurado = True
    try:
        _git("fetch", "--quiet", "origin", RAMA, timeout=45)
        nuevos = _git("rev-list", "--count", f"HEAD..origin/{RAMA}")
        estado.hay_update = int(nuevos or 0) > 0
        if estado.hay_update:
            estado.version_remota = _version_de(_git("show", f"origin/{RAMA}:trefot/__init__.py"))
            estado.cambios = _git("log", "--format=%s", f"HEAD..origin/{RAMA}").splitlines()
        else:
            estado.version_remota = estado.version_local
    except ErrorActualizacion as e:
        estado.error = str(e)
    return estado


def _respaldar_cambios_locales() -> str | None:
    modificados = [l for l in _git("diff", "--name-only", "HEAD").splitlines() if l.strip()]
    if not modificados:
        return None
    destino = LOGS / f"respaldo_{time.strftime('%Y%m%d_%H%M%S')}"
    for ruta in modificados:
        origen = RAIZ / ruta
        if origen.is_file():
            (destino / ruta).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino / ruta)
    return str(destino)


def actualizar(al_progreso=lambda texto: None) -> str:
    """Aplica la actualizacion. Devuelve un resumen. Lanza ErrorActualizacion si falla."""
    al_progreso("Descargando...")
    _git("fetch", "--quiet", "origin", RAMA, timeout=120)
    req_antes = _git("rev-parse", "HEAD:requirements.txt")
    respaldo = _respaldar_cambios_locales()
    if respaldo:
        al_progreso(f"Cambios locales respaldados en {respaldo}")
    al_progreso("Aplicando cambios...")
    _git("reset", "--hard", f"origin/{RAMA}")
    if _git("rev-parse", "HEAD:requirements.txt") != req_antes:
        al_progreso("Instalando dependencias nuevas...")
        r = subprocess.run(
            [sys.executable.replace("pythonw.exe", "python.exe"), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=RAIZ, capture_output=True, text=True, creationflags=_SIN_VENTANA,
        )
        if r.returncode != 0:
            raise ErrorActualizacion("No se pudieron instalar las dependencias. Ejecuta Instalar.bat.")
    return f"Actualizado a la version {version_local()}." + (f" Respaldo: {respaldo}" if respaldo else "")
