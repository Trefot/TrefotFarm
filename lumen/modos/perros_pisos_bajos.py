"""Perros pisos 1, 2 y 3: los faciles. Sirve cualquier equipo fuerte.

Reutiliza todo el modo del piso 4 (llegar a los pisos, pelear, botin, derrotas) y cambia dos cosas:
  - El piso se busca leyendo el texto "Floor N" de la pantalla (OCR de Windows), porque no hay
    imagenes de esos botones.
  - La estrategia es sencilla y no depende del equipo: en cada hueco juega una ulti si hay; si no,
    la carta de mas rango. Si no hay ninguna jugable, mueve una carta sobre otra para gastar el hueco.
"""

import re

from lumen import entrada, juego, ocr
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.motor import Opcion, TerminarModo
from lumen.modos.perros_piso4 import Estrategia, PerrosPiso4, Reiniciar


class EstrategiaSimple(Estrategia):
    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4):
        jugables = [c for c in mano if c.jugable]
        ultis = [c for c in jugables if c.tipo == TipoCarta.ULTI]
        if ultis:
            return ultis[-1].posicion, None, False
        if jugables:
            mejor = max(jugables, key=lambda c: (c.rango.value if c.rango not in (Rango.NINGUNO, Rango.ULTI) else -1, c.posicion))
            return mejor.posicion, None, False
        for izq, der in zip(mano, mano[1:]):  # todo bloqueado: mover una carta gasta el hueco sin atacar
            if izq.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA) and der.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA):
                return (der.posicion, izq.posicion), None, False
        raise Reiniciar("no hay cartas que jugar ni mover")


class PerrosPisoBajo(PerrosPiso4):
    piso = 0
    descripcion = "Piso fácil de los Perros. Sirve cualquier equipo fuerte: juega primero las ultis y luego las cartas de más rango."
    duracion = ""
    fases = 0  # no se sabe aun cuantas fases tienen estos pisos
    equipo = None  # cualquier equipo: el que tengas puesto en el juego
    rendirse_si_bloqueada = False
    opciones = [
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=9999),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.estrategia = EstrategiaSimple()
        self.textos_vistos = False

    def _verificar_equipo(self, p):
        self.equipo_verificado = True  # cualquier equipo vale

    def elegir_piso(self, p, o):
        if juego.empezar.esta(p):
            return "preparar"
        if self.clic_si(juego.ok, p, o):  # confirmar al abrir el piso
            return None
        rect = self._buscar_piso(p)
        if rect is not None:
            self.log(f"Abro el Floor {self.piso}.", "debug")
            entrada.clic(rect, o, espera=1.0)
        return None

    def _buscar_piso(self, p):
        """Rectangulo del texto "Floor N" en la pantalla de pisos (sin contar "Floor N Cleared")."""
        if not ocr.disponible():
            self.log("Para elegir el piso necesito el lector de texto de Windows: ejecuta Instalar.bat.", "error")
            raise TerminarModo()
        lineas = ocr.lineas_con_posicion(p) + ocr.lineas_con_posicion(p, invertir=True)
        if not self.textos_vistos:  # una vez por sesion, para poder ajustar si no lo encuentra
            self.textos_vistos = True
            self.log("Texto en la pantalla de pisos: " + " | ".join(t for t, _ in lineas), "debug")
        for texto, rect in lineas:
            limpio = re.sub(r"[^a-z0-9]", "", texto.lower())
            if limpio.startswith(f"floor{self.piso}") and "clear" not in limpio:
                return rect
        return None


def _estados(piso: int) -> dict:
    return {**PerrosPiso4.nombres_estados, "elegir_piso": f"Eligiendo el Floor {piso}"}


class PerrosPiso1(PerrosPisoBajo):
    id = "perros_piso1"
    piso = 1
    nombre = "Skollandhati & Hati · Floor 1"
    subtitulo_juego = "Demonic Beast · Floor 1"
    nombres_estados = _estados(1)


class PerrosPiso2(PerrosPisoBajo):
    id = "perros_piso2"
    piso = 2
    nombre = "Skollandhati & Hati · Floor 2"
    subtitulo_juego = "Demonic Beast · Floor 2"
    nombres_estados = _estados(2)


class PerrosPiso3(PerrosPisoBajo):
    id = "perros_piso3"
    piso = 3
    nombre = "Skollandhati & Hati · Floor 3"
    subtitulo_juego = "Demonic Beast · Floor 3"
    nombres_estados = _estados(3)
