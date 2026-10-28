"""Catalogo de todo lo que el bot va a farmear, este hecho o no.

Cada contenido es una parada de la rueda de Inicio (una bestia, un demonio...) con sus destinos
(los pisos de la bestia; o uno solo). Cada destino tiene un id fijo: cuando su modo esta
programado, ese id coincide con el de su clase en MODOS y se puede farmear; si no, sale como
"Próximamente".

Para programar uno: copia modos/perros_piso4.py, usa el mismo id que aqui y anadelo a MODOS.
Para cambiar la foto de un contenido: pon assets/modos/<id del contenido>.png; un destino puede tener la
suya (assets/modos/<id del destino>.png, p. ej. perros_piso4.png con el retrato "trascendente").
"""

from dataclasses import dataclass, field

from lumen.rutas import ASSETS, IMAGENES

CARPETA_FOTOS = ASSETS / "modos"


@dataclass(frozen=True)
class Destino:
    id: str
    nombre: str  # "Floor 4"; vacio si el contenido tiene un solo destino


@dataclass(frozen=True)
class Contenido:
    id: str
    nombre: str  # tal como sale en el juego
    descripcion: str  # una linea corta
    icono: str  # icono si no hay foto (Material Design Icons)
    imagen: str = ""  # foto por defecto, relativa a assets/imagenes
    destinos: tuple[Destino, ...] = field(default=())
    grupo: str = ""  # seccion del Inicio (ver GRUPOS)

    @property
    def foto(self):
        propia = CARPETA_FOTOS / f"{self.id}.png"
        if propia.is_file():
            return propia
        return IMAGENES / self.imagen if self.imagen else None


# Secciones del Inicio, en este orden: cada una con su propia rueda.
BESTIAS, DEMONIOS, FUERTE = "Bestias demoníacas", "Demonios", "Fuerte Solgres"
GRUPOS = [BESTIAS, DEMONIOS, FUERTE]


def _bestia(id_base: str, nombre: str, imagen: str, piso4: bool = True) -> Contenido:
    """Los pisos 1-3 seguidos en una sesion y, si la bestia lo tiene, el piso 4 ("trascendente")."""
    pisos = (Destino(f"{id_base}_pisos1a3", "Floor 1-3"),) + ((Destino(f"{id_base}_piso4", "Floor 4"),) if piso4 else ())
    return Contenido(id_base, nombre, "Bestia demoníaca", "mdi6.paw", imagen, pisos, BESTIAS)


def _unico(id_: str, nombre: str, descripcion: str, icono: str, grupo: str) -> Contenido:
    # La foto va en assets/modos/<id>.png (las de los demonios son capturas propias de la ventana
    # "Real-time Join Request" y, la de Indura, de una pelea).
    return Contenido(id_, nombre, descripcion, icono, destinos=(Destino(id_, ""),), grupo=grupo)


CATALOGO: list[Contenido] = [
    # Las 6 bestias en el orden del juego; solo las 3 primeras tienen piso 4 ("trascendente"), segun
    # capturas del juego (2026-10-28). La foto de cada una esta en assets/modos/<id>.png.
    _bestia("pajaro", "Hraesvelgr", "demonic_beasts/hraesvelgr.png"),
    _bestia("ciervo", "Eikthyrnir", "deer/Eikthyrnir.png"),
    _bestia("perros", "Skollandhati & Hati", "demonic_beasts/skollandhati.png"),
    _bestia("serpiente", "Nidhoggr", "snake/nidhoggr.png", piso4=False),
    _bestia("rata", "Ratatoskr", "rat/ratatoskr.png", piso4=False),
    _bestia("surtr", "Surtr", "", piso4=False),
    # Los 6 demonios en el orden de las pestanas de "Real-time Join Request" (captura del juego, 2026-10-28).
    _unico("demonio_rojo", "Red Demon", "Demonio · tiempo real", "mdi6.fire", DEMONIOS),
    _unico("demonio_gris", "Gray Demon", "Demonio · tiempo real", "mdi6.weather-fog", DEMONIOS),
    _unico("howlex", "Howlex", "Demonio · tiempo real", "mdi6.horse-variant", DEMONIOS),
    _unico("bellmoth", "Bellmoth", "Demonio · tiempo real", "mdi6.butterfly-outline", DEMONIOS),
    _unico("demonio_original", "Original Demon", "Demonio · tiempo real", "mdi6.fire-circle", DEMONIOS),
    _unico("indura", "Indura", "Demonio · tiempo real", "mdi6.skull-crossbones-outline", DEMONIOS),
    _unico("oro", "Oro", "Cofres del tesoro · Fuerte Solgres", "mdi6.gold", FUERTE),
    _unico("monedas_sa", "Monedas SA", "Monedas de superdespertar · Fuerte Solgres", "mdi6.circle-multiple-outline", FUERTE),
]


def foto_de(id_destino: str):
    """La foto de un destino: la suya si la tiene (assets/modos/<id del destino>.png, p. ej. el retrato
    "trascendente" del piso 4) o la de su contenido."""
    propia = CARPETA_FOTOS / f"{id_destino}.png"
    if propia.is_file():
        return propia
    contenido = contenido_de(id_destino)
    return contenido.foto if contenido else None


def contenido_de(id_destino: str) -> Contenido | None:
    for c in CATALOGO:
        if any(d.id == id_destino for d in c.destinos):
            return c
    return None
