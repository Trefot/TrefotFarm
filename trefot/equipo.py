"""Equipo de un modo: que personajes usa (en orden) y que cartas necesita, tomadas de la biblioteca.

Las capturas viven en la biblioteca de personajes (personajes/<id>/<carta>.png), no en el equipo:
capturar a Odin una vez sirve para todos los modos que lo usen.
"""

from dataclasses import dataclass

from trefot import juego
from trefot import personajes as P
from trefot.cartas import Carta
from trefot.vision import Plantilla

# Recorte interior que se guarda al capturar: deja fuera el marco de rango.
MARGEN_X = 0.15
MARGEN_Y = 0.20
UMBRAL_CARTA = 0.7


UMBRAL_RETRATO = 0.6


def zona_retrato(pantalla, puesto: int):
    """Zona de busqueda del retrato del puesto (0-3), con holgura alrededor del recorte."""
    x1, y1, x2, y2 = juego.RETRATOS[puesto]
    h = juego.HOLGURA_RETRATO
    return pantalla[max(0, y1 - h) : y2 + h, max(0, x1 - h) : x2 + h]


def recorte_retrato(pantalla, puesto: int):
    """Lo que se guarda como retrato del personaje."""
    x1, y1, x2, y2 = juego.RETRATOS[puesto]
    return pantalla[y1:y2, x1:x2].copy()


def quien_esta(zona, biblioteca) -> str | None:
    """Nombre del personaje de la biblioteca cuyo retrato mejor coincide con la zona."""
    mejor, mejor_valor = None, UMBRAL_RETRATO
    for pj in biblioteca.values():
        if pj.tiene_captura(P.RETRATO):
            valor, _ = Plantilla(pj.ruta(P.RETRATO)).confianza(zona)
            if valor >= mejor_valor:
                mejor, mejor_valor = pj.nombre, valor
    return mejor


def recorte_para_plantilla(imagen_carta):
    alto, ancho = imagen_carta.shape[:2]
    return imagen_carta[int(alto * MARGEN_Y) : int(alto * (1 - MARGEN_Y)), int(ancho * MARGEN_X) : int(ancho * (1 - MARGEN_X))].copy()


@dataclass
class DefCarta:
    nombre: str  # "personaje.carta", p. ej. "odin.single"
    descripcion: str  # "Odin - Un objetivo"
    obligatoria: bool
    es_carta: bool


@dataclass
class Puesto:
    """Un hueco del equipo: que funcion cumple y quien lo ocupa en el guion."""

    funcion: str
    roles: tuple[str, ...]
    recomendado: str  # id del personaje


class Equipo:
    def __init__(self, id_equipo: str, nombre: str, puestos: list[Puesto], obligatorias: set[str]):
        self.id = id_equipo
        self.nombre = nombre
        self.puestos = puestos  # en el orden de la pantalla del equipo (izquierda a derecha)
        self.orden = [p.recomendado for p in puestos]
        self.obligatorias = obligatorias
        self.recargar()

    # ---------------------------------------------------------------- biblioteca
    def recargar(self):
        self.biblioteca = P.cargar()
        self.defs: dict[str, DefCarta] = {}
        self._plantillas = {}
        for pid in self.orden:
            pj = self.biblioteca.get(pid)
            if pj is None:
                continue
            for c in pj.cartas.values():
                clave = f"{pid}.{c.id}"
                self.defs[clave] = DefCarta(clave, f"{pj.nombre} - {c.descripcion}", clave in self.obligatorias, not c.boton)
                self._plantillas[clave] = pj.plantilla(c.id)
        self.grupos = {pid: tuple(k for k, d in self.defs.items() if k.startswith(pid + ".") and d.es_carta) for pid in self.orden}

    @property
    def carpeta(self):
        P.CARPETA.mkdir(parents=True, exist_ok=True)
        return P.CARPETA

    def ruta_propia(self, clave: str):
        pid, carta = P.separar(clave)
        return P.CARPETA / pid / f"{carta}.png"

    def plantilla(self, clave: str):
        return self._plantillas.get(clave)

    def estado(self) -> list[tuple[DefCarta, str]]:
        """('propia' | 'respaldo' | 'falta') por carta, para la interfaz."""
        filas = []
        for clave, d in self.defs.items():
            pid, carta = P.separar(clave)
            filas.append((d, self.biblioteca[pid].estado_carta(carta)))
        return filas

    def faltantes(self) -> list[DefCarta]:
        return [d for d, est in self.estado() if est == "falta" and d.obligatoria]

    def personajes_que_faltan(self) -> list[str]:
        """Personajes del equipo que no estan en la biblioteca o que no marcaste como tuyos."""
        return [pid for pid in self.orden if pid not in self.biblioteca or not self.biblioteca[pid].tengo]

    # ---------------------------------------------------------- equipo en pantalla
    def verificar_en_pantalla(self, pantalla) -> tuple[list[str], list[str]]:
        """Compara los retratos de la pantalla del equipo con el orden del guion.

        Devuelve (errores, personajes_sin_retrato). Sin retratos capturados no se puede verificar.
        """
        errores, sin_retrato = [], []
        for puesto, pid in enumerate(self.orden):
            pj = self.biblioteca.get(pid)
            if pj is None or not pj.tiene_captura(P.RETRATO):
                sin_retrato.append(pj.nombre if pj else pid)
                continue
            zona = zona_retrato(pantalla, puesto)
            valor, _ = Plantilla(pj.ruta(P.RETRATO)).confianza(zona)
            if valor < UMBRAL_RETRATO:
                quien = quien_esta(zona, self.biblioteca)
                errores.append(f"puesto {puesto + 1}: esperaba {pj.nombre}" + (f" y esta {quien}" if quien else ""))
        return errores, sin_retrato

    # ------------------------------------------------------------ reconocimiento
    def reconocer(self, carta: Carta, nombres=None) -> str | None:
        """Clave de la carta con mayor coincidencia (o None)."""
        if carta.imagen is None or not carta.jugable:
            return None
        mejor, mejor_valor = None, UMBRAL_CARTA
        for clave in nombres or [k for k, d in self.defs.items() if d.es_carta]:
            p = self._plantillas.get(clave)
            if p is None:
                continue
            valor, _ = p.confianza(carta.imagen)
            if valor >= mejor_valor:
                mejor, mejor_valor = clave, valor
        return mejor

    def etiquetar(self, mano: list[Carta]) -> list[Carta]:
        for carta in mano:
            carta.nombre = self.reconocer(carta)
        return mano
