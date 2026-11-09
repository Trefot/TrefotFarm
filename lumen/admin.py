"""Modo administrador con contrasena (2026-11-09: el link del bot lo tienen amigos del usuario).

En el repositorio (publico) solo va la HUELLA de la contrasena: una sal y sha256 de la llave. La llave sale de la
contrasena con PBKDF2 (muy lento a proposito) y se guarda en el config.yaml de la PC del admin, que no se sube.
Sin la contrasena no se puede sacar la llave de la huella, asi que en otra PC el modo admin no se abre.

Primera vez: no hay huella publicada. El admin crea su contrasena en Ajustes; Lumen guarda su llave y escribe la
huella (no la contrasena) en logs/huella_admin.txt para publicarla en lumen/datos/admin.yaml. Crearla en otra PC no
sirve de nada: solo vale la huella publicada.

Limite: el codigo se puede leer y editar; esto cierra el modo admin a quien solo tiene el link.
"""

import hashlib
import hmac
import secrets
from pathlib import Path

import yaml

from lumen.rutas import RAIZ

ARCHIVO = Path(__file__).resolve().parent / "datos" / "admin.yaml"
HUELLA_LOCAL = RAIZ / "logs" / "huella_admin.txt"
VUELTAS = 300_000
MINIMO = 8  # letras de la contrasena


def _publicada() -> dict:
    try:
        datos = yaml.safe_load(ARCHIVO.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return datos if datos.get("sal") and datos.get("huella") else {}


def hay_contrasena() -> bool:
    return bool(_publicada())


def llave(contrasena: str, sal_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), bytes.fromhex(sal_hex), VUELTAS).hex()


def huella_de(llave_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(llave_hex)).hexdigest()


def _llave_guardada() -> str:
    from lumen import config

    return str(config.obtener_guardado("admin_llave") or "")


def desbloqueado(llave_hex: str | None = None) -> bool:
    """True si esta PC tiene la llave de la contrasena publicada."""
    datos = _publicada()
    llave_hex = _llave_guardada() if llave_hex is None else llave_hex
    if not datos or not llave_hex:
        return False
    try:
        return hmac.compare_digest(huella_de(llave_hex), str(datos["huella"]))
    except ValueError:
        return False


def activo() -> bool:
    """El modo admin esta encendido: la casilla marcada Y la llave de la contrasena en esta PC."""
    from lumen import config

    return bool(config.obtener_guardado("modo_admin")) and desbloqueado()


def entrar(contrasena: str) -> bool:
    """Comprueba la contrasena con la huella publicada y, si vale, guarda la llave en esta PC."""
    from lumen import config

    datos = _publicada()
    if not datos:
        return False
    k = llave(contrasena, str(datos["sal"]))
    if not desbloqueado(k):
        return False
    config.guardar({"admin_llave": k, "modo_admin": True})
    return True


def crear(contrasena: str) -> str:
    """Primera vez (sin huella publicada): guarda la llave aqui y devuelve el texto de la huella para publicarla."""
    from lumen import config

    if len(contrasena) < MINIMO:
        raise ValueError(f"La contraseña necesita al menos {MINIMO} letras.")
    sal = secrets.token_hex(16)
    k = llave(contrasena, sal)
    texto = (f"# Huella de la contrasena de admin (no es la contrasena). Va en lumen/datos/admin.yaml\n"
             f"sal: {sal}\nhuella: {huella_de(k)}\n")
    config.guardar({"admin_llave": k})
    try:
        HUELLA_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        HUELLA_LOCAL.write_text(texto, encoding="utf-8")
    except OSError:
        pass
    return texto


def salir() -> None:
    from lumen import config

    config.guardar({"admin_llave": "", "modo_admin": False})
