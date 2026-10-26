"""Reconocimiento de las cartas de un equipo con capturas propias.

Cada equipo tiene una carpeta en assets/equipo/<id>/ con un PNG por carta (el interior de la
carta, sin marco, para que valga para cualquier rango). La pestana "Capturas" de la interfaz
las genera.
"""

from dataclasses import dataclass

from trefot.cartas import Carta
from trefot.rutas import EQUIPO, IMAGENES
from trefot.vision import Plantilla

# Recorte interior que se guarda al capturar: deja fuera el marco bronce/plata/oro.
MARGEN_X = 0.15
MARGEN_Y = 0.20
UMBRAL_CARTA = 0.7


def recorte_para_plantilla(imagen_carta):
    alto, ancho = imagen_carta.shape[:2]
    return imagen_carta[int(alto * MARGEN_Y) : int(alto * (1 - MARGEN_Y)), int(ancho * MARGEN_X) : int(ancho * (1 - MARGEN_X))].copy()


@dataclass
class DefCarta:
    nombre: str  # nombre logico, p. ej. "odin_single"
    descripcion: str  # lo que ve el usuario en la interfaz
    obligatoria: bool = True
    respaldos: tuple[str, ...] = ()  # imagenes de assets/imagenes si no hay captura propia
    es_carta: bool = True  # False para botones de pantalla (p. ej. un talento)


class Equipo:
    def __init__(self, id_equipo: str, nombre: str, cartas: list[DefCarta], grupos: dict[str, tuple[str, ...]]):
        self.id = id_equipo
        self.nombre = nombre
        self.defs = {d.nombre: d for d in cartas}
        self.grupos = grupos  # personaje -> nombres de sus cartas
        self.carpeta = EQUIPO / id_equipo
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._plantillas: dict[str, Plantilla | None] = {}
        self.recargar()

    def ruta_propia(self, nombre: str):
        return self.carpeta / f"{nombre}.png"

    def recargar(self):
        self._plantillas = {}
        for nombre, d in self.defs.items():
            rutas = [self.ruta_propia(nombre)] if self.ruta_propia(nombre).is_file() else []
            rutas += [IMAGENES / r for r in d.respaldos if (IMAGENES / r).is_file()]
            self._plantillas[nombre] = Plantilla(*rutas, nombre=nombre) if rutas else None

    def plantilla(self, nombre: str) -> Plantilla | None:
        return self._plantillas.get(nombre)

    def estado(self) -> list[tuple[DefCarta, str]]:
        """Para la interfaz: ('propia' | 'respaldo' | 'falta') por carta."""
        filas = []
        for nombre, d in self.defs.items():
            if self.ruta_propia(nombre).is_file():
                filas.append((d, "propia"))
            elif self._plantillas[nombre] is not None:
                filas.append((d, "respaldo"))
            else:
                filas.append((d, "falta"))
        return filas

    def faltantes(self) -> list[DefCarta]:
        return [d for d, est in self.estado() if est == "falta" and d.obligatoria]

    def reconocer(self, carta: Carta, nombres=None) -> str | None:
        """Nombre de la carta con mayor coincidencia (o None)."""
        if carta.imagen is None or not carta.jugable:
            return None
        mejor, mejor_valor = None, UMBRAL_CARTA
        for nombre in nombres or [n for n, d in self.defs.items() if d.es_carta]:
            p = self._plantillas.get(nombre)
            if p is None:
                continue
            valor, _ = p.confianza(carta.imagen)
            if valor >= mejor_valor:
                mejor, mejor_valor = nombre, valor
        return mejor

    def etiquetar(self, mano: list[Carta]) -> list[Carta]:
        for carta in mano:
            carta.nombre = self.reconocer(carta)
        return mano
