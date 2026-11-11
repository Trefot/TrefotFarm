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
import tempfile
import threading
import time
from dataclasses import dataclass, field

from pathlib import Path

from lumen.archivos import escribir_texto
from lumen.rutas import LOGS, RAIZ

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


def _git(*args: str, timeout: float = 60, exacto: bool = False) -> str:
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
    return r.stdout if exacto else r.stdout.strip()


def _version_de(texto: str) -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', texto)
    return m.group(1) if m else "?"


def version_local() -> str:
    return _version_de((RAIZ / "lumen" / "__init__.py").read_text(encoding="utf-8"))


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
            estado.version_remota = _version_de(_git("show", f"origin/{RAMA}:lumen/__init__.py"))
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
    LOGS.mkdir(parents=True, exist_ok=True)
    destino = Path(tempfile.mkdtemp(prefix=f"respaldo_{time.strftime('%Y%m%d_%H%M%S')}_", dir=LOGS))
    for ruta in modificados:
        origen = RAIZ / ruta
        if origen.is_file():
            (destino / ruta).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino / ruta)
    return str(destino)


_lock_update = threading.Lock()
TIEMPO_PIP = 300


def _pip(*args: str) -> None:
    try:
        r = subprocess.run(
            [sys.executable.replace("pythonw.exe", "python.exe"), "-m", "pip", *args],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=_SIN_VENTANA, timeout=TIEMPO_PIP,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ErrorActualizacion("La instalacion de dependencias fallo o supero los 5 minutos.") from error
    if r.returncode:
        raise ErrorActualizacion("No se pudieron preparar o instalar las dependencias. Ejecuta Instalar.bat si persiste.")


def actualizar(al_progreso=lambda texto: None) -> str:
    """Valida y prepara antes de aplicar; ante un fallo recupera codigo y cambios locales.

    pip no es transaccional: se intenta reinstalar los requisitos anteriores, pero
    si falla esa recuperacion se indica expresamente que hay que ejecutar Instalar.bat.
    """
    if not _lock_update.acquire(blocking=False):
        raise ErrorActualizacion("Ya hay una actualizacion en curso.")
    try:
        return _actualizar(al_progreso)
    finally:
        _lock_update.release()


def _actualizar(al_progreso) -> str:
    al_progreso("Descargando...")
    _git("fetch", "--quiet", "origin", RAMA, timeout=120)
    anterior = _git("rev-parse", "HEAD")
    destino = _git("rev-parse", f"origin/{RAMA}")  # una sola revision durante toda la operacion
    version = _git("show", f"{destino}:lumen/__init__.py")
    if _version_de(version) == "?":
        raise ErrorActualizacion("La version descargada no tiene una version valida.")
    try:
        compile(version, "lumen/__init__.py", "exec")
    except SyntaxError as error:
        raise ErrorActualizacion("El archivo de version descargado no es valido.") from error
    nuevos_archivos = set(_git("ls-tree", "-r", "--name-only", "-z", destino, exacto=True).split("\0"))
    actuales = set(_git("ls-files", "-z", exacto=True).split("\0"))
    if any((RAIZ / ruta).exists() for ruta in nuevos_archivos - actuales if ruta):
        raise ErrorActualizacion("La actualizacion reemplazaria archivos locales sin seguimiento; conservalos antes de actualizar.")
    requisitos = _git("show", f"{destino}:requirements.txt")
    cambiaron = _git("rev-parse", "HEAD:requirements.txt") != _git("rev-parse", f"{destino}:requirements.txt")
    respaldo = _respaldar_cambios_locales()
    if respaldo:
        al_progreso(f"Cambios locales respaldados en {respaldo}")
    # Conservar tambien eliminaciones y el estado de los cambios preparados en Git.
    cambios = _git("diff", "--binary", "HEAD", exacto=True)
    preparados = _git("diff", "--binary", "--cached", exacto=True)
    if respaldo:
        escribir_texto(Path(respaldo) / "_cambios.patch", cambios + "\n", respaldo=False)
    LOGS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="actualizacion_", dir=LOGS) as carpeta:
        temporal = Path(carpeta)
        nuevos = temporal / "requirements.txt"
        escribir_texto(nuevos, requisitos + "\n", respaldo=False)
        paquetes = temporal / "paquetes"
        if cambiaron:
            al_progreso("Preparando dependencias antes de cambiar el programa...")
            _pip("download", "-r", str(nuevos), "--dest", str(paquetes))
        al_progreso("Aplicando cambios...")
        try:
            _git("reset", "--hard", destino)
            if cambiaron:
                al_progreso("Instalando dependencias nuevas...")
                _pip("install", "--no-index", "--find-links", str(paquetes), "-r", "requirements.txt")
            resumen = f"Actualizado a la version {version_local()}."
        except Exception as error:
            problemas = []
            try:
                _git("reset", "--hard", anterior)
                if cambios:
                    parche = temporal / "local.patch"
                    escribir_texto(parche, cambios + "\n", respaldo=False)
                    _git("apply", str(parche))
                if preparados:
                    indice = temporal / "indice.patch"
                    escribir_texto(indice, preparados + "\n", respaldo=False)
                    _git("apply", "--cached", str(indice))
            except Exception:
                problemas.append(f"No se pudo recuperar todo el codigo; respaldo local: {respaldo or 'sin cambios locales'}.")
            else:
                if cambiaron:
                    try:
                        _pip("install", "-r", "requirements.txt")
                    except ErrorActualizacion:
                        problemas.append("No se pudieron restaurar las dependencias anteriores: ejecuta Instalar.bat.")
            if problemas:
                raise ErrorActualizacion("La actualizacion fallo. " + " ".join(problemas)) from error
            raise ErrorActualizacion("La actualizacion fallo; se recuperaron el codigo anterior y tus cambios locales.") from error
    return resumen + (f" Respaldo: {respaldo}" if respaldo else "")
