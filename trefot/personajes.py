"""Biblioteca de personajes: ficha de cada personaje y sus capturas, compartidas por todos los modos.

- Base fija (la mantiene el administrador y viaja con las actualizaciones):
  trefot/datos/personajes.yaml (fichas) y assets/personajes/<id>/*.png (cartas y retrato).
- Local de cada jugador (fuera de git): personajes/usuario.yaml ("lo tengo" y cambios) y
  personajes/<id>/*.png (capturas nuevas del administrador antes de publicarlas). Una captura local
  tiene prioridad sobre la de la base.

Una carta se nombra "personaje.carta", p. ej. "odin.single" o "thonar_azul.postura".
"""

import re
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from trefot.rutas import ASSETS, EQUIPO, IMAGENES, RAIZ
from trefot.vision import Plantilla, guardar_imagen

BASE = Path(__file__).resolve().parent / "datos" / "personajes.yaml"
CARPETA = RAIZ / "personajes"
USUARIO = CARPETA / "usuario.yaml"
CARPETA_BASE = ASSETS / "personajes"  # capturas de la base fija

COLORES = ["rojo", "verde", "azul", "claro", "oscuro", "sin definir"]
NOMBRE_COLOR = {"rojo": "Strength", "verde": "HP", "azul": "Speed", "claro": "Light", "oscuro": "Dark", "sin definir": "?"}
RAZAS = ["sin definir", "humano", "gigante", "hada", "diosa", "demonio", "desconocida"]
ROLES = {
    "quita_postura": "Quita posturas",
    "dano_single": "Dano a un objetivo",
    "dano_area": "Dano en area",
    "ulti_remate": "Ulti que remata",
    "talento": "Talento util",
    "buff": "Mejora al equipo",
    "debuff": "Debilita enemigos",
    "curacion": "Curacion",
    "aguante": "Aguanta / protege",
}
RETRATO = "retrato"  # captura de la cara en la pantalla del equipo (no es una carta)
ICONO = "icono"  # icono del heroe en la lista de Heroes del juego: es lo que se muestra en la interfaz

# Cartas sacadas de la ficha del heroe (Heroes -> personaje -> fila "Skills"). Medido con capturas
# reales: la carta de la ficha es mas pequena que en la mano (x1.22 de ancho, x1.26 de alto) y,
# reescalada, reconoce la carta en pelea con 0.60-0.81 frente a <=0.39 de las demas cartas.
SUFIJO_FICHA = "_ficha"
ESCALA_FICHA = (1.22, 1.26)
UMBRAL_PROPIA = 0.7
UMBRAL_FICHA = 0.55

_lock = threading.RLock()


@dataclass
class CartaPj:
    id: str
    descripcion: str
    respaldo: str = ""  # imagen de AutoFarming si no hay captura propia
    boton: bool = False  # True = boton de pantalla, no carta de la mano


@dataclass
class Personaje:
    id: str
    nombre: str
    color: str = "rojo"
    raza: str = "sin definir"
    roles: list[str] = field(default_factory=list)
    cartas: dict[str, CartaPj] = field(default_factory=dict)
    tengo: bool = False
    propio: bool = False  # creado por el usuario (no viene en el catalogo base)

    @property
    def carpeta(self) -> Path:
        return CARPETA / self.id

    def _archivo(self, nombre: str) -> Path:
        """La captura local si existe; si no, la de la base fija; si tampoco, la ruta local."""
        local = self.carpeta / nombre
        if local.is_file():
            return local
        base = CARPETA_BASE / self.id / nombre
        return base if base.is_file() else local

    def ruta(self, carta: str) -> Path:
        return self._archivo(f"{carta}.png")

    def ruta_cara(self) -> Path:
        """Imagen para mostrar: el icono de la lista de Heroes; si no hay, el retrato del equipo.
        (Para comprobar el equipo en pantalla se sigue usando el retrato.)"""
        icono = self.ruta(ICONO)
        return icono if icono.is_file() else self.ruta(RETRATO)

    def ruta_ficha(self, carta: str) -> Path:
        """Carta sacada de la ficha del heroe (ya reescalada al tamano de la mano)."""
        return self._archivo(f"{carta}{SUFIJO_FICHA}.png")

    def ruta_local(self, carta: str) -> Path:
        """Donde se guarda una captura nueva (siempre local; la base solo cambia al publicarla)."""
        return self.carpeta / f"{carta}.png"

    def ruta_ficha_local(self, carta: str) -> Path:
        return self.carpeta / f"{carta}{SUFIJO_FICHA}.png"

    @property
    def tiene_datos(self) -> bool:
        """Tiene al menos una carta capturada (si no, el bot aun no lo conoce)."""
        return any(self.estado_carta(c) != "falta" for c in self.cartas)

    def tiene_captura(self, carta: str) -> bool:
        return self.ruta(carta).is_file()

    def _respaldo(self, carta: str) -> Path | None:
        c = self.cartas.get(carta)
        ruta = IMAGENES / c.respaldo if c and c.respaldo else None
        return ruta if ruta and ruta.is_file() else None

    def estado_carta(self, carta: str) -> str:
        """'propia' (de una pelea) > 'ficha' (de la ficha del heroe) > 'respaldo' (AutoFarming) > 'falta'."""
        if self.tiene_captura(carta):
            return "propia"
        if self.ruta_ficha(carta).is_file():
            return "ficha"
        if self._respaldo(carta):
            return "respaldo"
        return "falta"

    def plantilla(self, carta: str) -> tuple[Plantilla | None, float]:
        """La mejor imagen disponible para reconocer la carta y el umbral con que se compara."""
        estado = self.estado_carta(carta)
        nombre = f"{self.id}.{carta}"
        if estado == "propia":
            return Plantilla(self.ruta(carta), nombre=nombre), UMBRAL_PROPIA
        if estado == "ficha":
            return Plantilla(self.ruta_ficha(carta), nombre=nombre), UMBRAL_FICHA
        if estado == "respaldo":
            return Plantilla(self._respaldo(carta), nombre=nombre), UMBRAL_PROPIA
        return None, UMBRAL_PROPIA


# ------------------------------------------------------------------ carga / guardado
def _leer_yaml(ruta: Path) -> dict:
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _crear(pid: str, datos: dict, propio: bool) -> Personaje:
    cartas = {}
    for cid, c in (datos.get("cartas") or {}).items():
        c = c or {}
        cartas[cid] = CartaPj(cid, c.get("descripcion", cid), c.get("respaldo", ""), bool(c.get("boton", False)))
    return Personaje(
        id=pid,
        nombre=datos.get("nombre", pid),
        color=datos.get("color", "rojo"),
        raza=datos.get("raza", "sin definir"),
        roles=list(datos.get("roles") or []),
        cartas=cartas,
        tengo=bool(datos.get("tengo", False)),
        propio=propio,
    )


def _primera_vez():
    """Al estrenar la biblioteca: un jugador nuevo empieza sin ningun personaje marcado (los marca
    en la pagina Personajes). Tambien mueve capturas de la version anterior (assets/equipo/perros_trefot)."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    if not USUARIO.is_file():
        USUARIO.write_text("{}\n", encoding="utf-8")
    viejo = EQUIPO / "perros_trefot"
    nombres_viejos = {
        "odin_single": ("odin", "single"), "odin_area": ("odin", "area"), "odin_ulti": ("odin", "ulti"),
        "odin_talento": ("odin", "talento"), "gawain_single": ("gawain", "single"), "gawain_area": ("gawain", "area"),
        "gawain_ulti": ("gawain", "ulti"), "freyja_1": ("freyja_roja", "normal_1"), "freyja_2": ("freyja_roja", "normal_2"),
        "freyja_ulti": ("freyja_roja", "ulti"), "thonar_postura": ("thonar_azul", "postura"),
        "thonar_otra": ("thonar_azul", "otra"), "thonar_ulti": ("thonar_azul", "ulti"),
    }
    if viejo.is_dir():
        for archivo in viejo.glob("*.png"):
            destino = nombres_viejos.get(archivo.stem)
            if destino:
                ruta = CARPETA / destino[0] / f"{destino[1]}.png"
                if not ruta.exists():
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(archivo), ruta)


def cargar() -> dict[str, Personaje]:
    with _lock:
        _primera_vez()
        base = _leer_yaml(BASE)
        usuario = _leer_yaml(USUARIO)
        resultado = {}
        for pid in list(base) + [p for p in usuario if p not in base]:
            datos = dict(base.get(pid) or {})
            cambios = usuario.get(pid) or {}
            cartas = {cid: dict(c or {}) for cid, c in (datos.get("cartas") or {}).items()}
            for cid, c in (cambios.get("cartas") or {}).items():  # cartas nuevas o renombradas
                cartas[cid] = {**cartas.get(cid, {}), **(c or {})}
            for cid in cambios.get("cartas_quitadas") or []:  # cartas que el usuario quito
                cartas.pop(cid, None)
            datos.update({k: v for k, v in cambios.items() if k not in ("cartas", "cartas_quitadas")})
            datos["cartas"] = cartas
            resultado[pid] = _crear(pid, datos, propio=pid not in base)
        return resultado


def guardar(p: Personaje) -> None:
    """Guarda la ficha en personajes/usuario.yaml (solo lo que difiere del catalogo base)."""
    with _lock:
        usuario = _leer_yaml(USUARIO)
        base = (_leer_yaml(BASE).get(p.id) or {})
        registro = {"nombre": p.nombre, "color": p.color, "raza": p.raza, "roles": list(p.roles), "tengo": p.tengo}
        cartas_base = base.get("cartas") or {}
        # Solo lo que difiere del catalogo base: cartas nuevas, renombradas o quitadas.
        extra = {
            c.id: {"descripcion": c.descripcion, **({"boton": True} if c.boton else {})}
            for c in p.cartas.values()
            if c.id not in cartas_base or (cartas_base[c.id] or {}).get("descripcion") != c.descripcion
        }
        if extra:
            registro["cartas"] = extra
        quitadas = [cid for cid in cartas_base if cid not in p.cartas]
        if quitadas:
            registro["cartas_quitadas"] = quitadas
        usuario[p.id] = registro
        CARPETA.mkdir(parents=True, exist_ok=True)
        USUARIO.write_text(yaml.safe_dump(usuario, allow_unicode=True, sort_keys=False), encoding="utf-8")


def marcar_tengo(pid: str, tengo: bool) -> None:
    """Lo unico que cambia un jugador normal: si tiene o no el personaje."""
    with _lock:
        usuario = _leer_yaml(USUARIO)
        usuario.setdefault(pid, {})["tengo"] = bool(tengo)
        CARPETA.mkdir(parents=True, exist_ok=True)
        USUARIO.write_text(yaml.safe_dump(usuario, allow_unicode=True, sort_keys=False), encoding="utf-8")


def borrar_propio(pid: str) -> None:
    """Quita de la biblioteca un personaje creado por el usuario (sus capturas se conservan en disco)."""
    with _lock:
        usuario = _leer_yaml(USUARIO)
        if pid in usuario and pid not in _leer_yaml(BASE):
            del usuario[pid]
            USUARIO.write_text(yaml.safe_dump(usuario, allow_unicode=True, sort_keys=False), encoding="utf-8")


def nuevo_id(nombre: str, existentes) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", nombre.lower().strip()).strip("_") or "personaje"
    pid, n = base, 2
    while pid in existentes:
        pid, n = f"{base}_{n}", n + 1
    return pid


def ruta_anterior(ruta: Path) -> Path:
    return ruta.with_name(f"{ruta.stem}_anterior{ruta.suffix}")


def guardar_con_respaldo(ruta: Path, imagen) -> None:
    """Guarda una captura; si ya habia una, la deja como <nombre>_anterior.png para poder deshacer."""
    if ruta.is_file():
        shutil.copy2(ruta, ruta_anterior(ruta))
    guardar_imagen(ruta, imagen)


def volver_a_anterior(ruta: Path) -> bool:
    """Intercambia la captura actual con la anterior (deshacer / rehacer)."""
    anterior = ruta_anterior(ruta)
    if not anterior.is_file():
        return False
    temporal = ruta.with_name(f"{ruta.stem}_tmp{ruta.suffix}")
    if ruta.is_file():
        ruta.replace(temporal)
    anterior.replace(ruta)
    if temporal.is_file():
        temporal.replace(anterior)
    return True


def separar(clave: str) -> tuple[str, str]:
    """'odin.single' -> ('odin', 'single')."""
    pid, _, carta = clave.partition(".")
    return pid, carta
