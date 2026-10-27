"""Perros pisos 1, 2 y 3 seguidos (1 -> 2 -> 3 -> 1...): los faciles. Sirve cualquier equipo fuerte.

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


class PerrosPisos1a3(PerrosPiso4):
    id = "perros_pisos1a3"
    nombre = "Skollandhati & Hati · Floor 1-3"
    subtitulo_juego = "Demonic Beast · Floor 1-3"
    descripcion = "Floor 1, 2 y 3 seguidos, y vuelta a empezar. Sirve cualquier equipo fuerte."
    duracion = ""
    fases = 0  # no se sabe aun cuantas fases tienen estos pisos
    equipo = None  # cualquier equipo: el que tengas puesto en el juego
    rendirse_si_bloqueada = False
    nombres_estados = {**PerrosPiso4.nombres_estados, "elegir_piso": "Eligiendo el piso"}
    opciones = [
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=9999),
        Opcion("primer_piso", "Empezar en el Floor", "lista", "1", opciones=["1", "2", "3"]),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.estrategia = EstrategiaSimple()
        self.textos_vistos = False
        self.piso = int(self.valores.get("primer_piso") or 1)

    def victoria(self, p, o):
        siguiente = super().victoria(p, o)  # cuenta la victoria al volver a los pisos
        if siguiente == "elegir_piso":
            self.piso = self.piso % 3 + 1
            self.log(f"Siguiente: Floor {self.piso}.", "ok")
        return siguiente

    # La pantalla de pisos se reconoce por "Floor 3 Cleared", que no sale si aun no se ha pasado el
    # piso 3 en esta vuelta: aqui tambien vale ver el texto del piso que toca.
    def ir_a_perros(self, p, o):
        siguiente = super().ir_a_perros(p, o)
        if siguiente is None and not juego.pantalla_bestias.esta(p) and self._buscar_piso(p) is not None:
            self.log("En la pantalla de pisos de los Perros.", "ok")
            return "elegir_piso"
        return siguiente

    def _volvio_a_pisos(self, p) -> bool:
        return super()._volvio_a_pisos(p) or self._buscar_piso(p) is not None

    def _verificar_equipo(self, p):
        self.equipo_verificado = True  # cualquier equipo vale

    def elegir_piso(self, p, o):
        if juego.empezar.esta(p):
            return "preparar"
        if self.clic_si(juego.ok, p, o):  # confirmar al abrir el piso
            return None
        rect = self._buscar_piso(p)
        if rect is not None:
            self.log(f"Abro el Floor {self.piso}.")
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
