"""Floor 1, 2 y 3 seguidos (1 -> 2 -> 3 -> 1...) de cualquier Demonic Beast. Sirve cualquier equipo fuerte.

Reutiliza todo el modo de Perros piso 4 (llegar a los pisos, pelear, botin, derrotas) y cambia:
  - La bestia: cada una es una subclase con su imagen del carrusel (juego.ORDEN_BESTIAS).
  - El piso se busca leyendo el texto "Floor N" de la pantalla (OCR de Windows), porque no hay
    imagenes de esos botones.
  - La estrategia es sencilla y no depende del equipo: en cada hueco juega una ulti si hay; si no,
    la carta de mas rango. Si no hay ninguna jugable, mueve una carta sobre otra para gastar el hueco.
"""

import re
import time

from lumen import entrada, inteligencia, juego, ocr
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


class EstrategiaInteligente(EstrategiaSimple):
    """Piensa el turno entero (lumen/inteligencia.py): que jugar ahora y que dejar para el siguiente,
    contando las fusiones. Funciona con cualquier equipo: las cartas iguales se reconocen por su dibujo,
    y cada carta se busca en la base de heroes para saber cuanto vale (lumen/valor_cartas.py)."""

    def __init__(self, enemigos: int = 1):
        self.jugador = inteligencia.Jugador(enemigos)

    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4):
        paso = self.jugador.elegir(mano, total - accion)
        if paso is None:  # nada que jugar ni fusionar: lo de siempre (mover una carta para gastar el hueco)
            return super().decidir(fase, turno, accion, mano, total)
        if paso[0] == "jugar":
            return paso[1], None, False
        return (paso[1], paso[2]), None, False


SALTAR_PISO_S = 25  # sin encontrar el piso que toca en la pantalla de pisos: pasar al siguiente


class BestiaPisos1a3(PerrosPiso4):
    """Base: las subclases ponen id, nombres y ``bestia`` (su imagen del carrusel de bestias)."""

    bestia = None  # Plantilla de la bestia en el carrusel
    enemigos = 1  # enemigos en la pelea (las cartas de area valen mas con varios)
    piso3_superado = None  # Plantilla de "Floor 3 Cleared" de esta bestia, si la hay
    descripcion = "Floor 1, 2 y 3 seguidos, y vuelta a empezar. Sirve cualquier equipo fuerte."
    duracion = ""
    fases = 0  # no se sabe aun cuantas fases tienen estos pisos
    equipo = None  # cualquier equipo: el que tengas puesto en el juego
    rendirse_si_bloqueada = False
    nombres_estados = {**PerrosPiso4.nombres_estados, "ir_a_perros": "Entrando a Demonic Beasts",
                       "elegir_piso": "Eligiendo el piso"}
    opciones = [
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=9999),
        Opcion("primer_piso", "Empezar en el Floor", "lista", "1", opciones=["1", "2", "3"]),
        Opcion("jugar", "Cómo jugar", "lista", "Inteligente", opciones=["Inteligente", "Simple"],
               ayuda="Inteligente: piensa el turno entero y las fusiones. Simple: ulti y luego la de más rango."),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        inteligente = self.valores.get("jugar", "Inteligente") != "Simple"
        self.estrategia = EstrategiaInteligente(self.enemigos) if inteligente else EstrategiaSimple()
        self.stats["estrategia"] = "Inteligente" if inteligente else "Simple"  # queda en el historial
        self.textos_vistos = False
        self.piso = int(self.valores.get("primer_piso") or 1)
        self.buscando_piso_desde: float | None = None

    def _siguiente_piso(self):
        self.piso = self.piso % 3 + 1
        self.buscando_piso_desde = None

    def victoria(self, p, o):
        siguiente = super().victoria(p, o)  # cuenta la victoria al volver a los pisos
        if siguiente == "elegir_piso":
            self._siguiente_piso()
            self.log(f"Siguiente: Floor {self.piso}.", "ok")
        return siguiente

    # ------------------------------------------------------------- navegacion
    def ir_a_perros(self, p, o):
        """Taberna -> Battle -> Demonic Beasts -> esta bestia -> su pantalla de pisos."""
        if self.clic_si(juego.cancelar, p, o):
            self.log("Habia una pelea a medias; la doy por perdida y empiezo de nuevo.", "aviso")
            return None
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6)
        self.clic_si(juego.nido_criaturas, p, o)
        if juego.pantalla_bestias.esta(p):
            if not self.bestia.esta(p):
                self._deslizar_hacia_bestia(p, o)
                return None
            self.clic_si(self.bestia, p, o)
            return None
        if self._en_pisos(p):
            self.log(f"En la pantalla de pisos de {self.titulo_juego}.", "ok")
            return "elegir_piso"
        return None

    def _deslizar_hacia_bestia(self, p, o):
        actual = next((i for i, b in enumerate(juego.ORDEN_BESTIAS) if b.esta(p)), None)
        objetivo = juego.ORDEN_BESTIAS.index(self.bestia)
        desde, hasta = juego.COORD["deslizar_der"], juego.COORD["deslizar_izq"]
        if actual is not None and actual > objetivo:
            desde, hasta = hasta, desde
        entrada.arrastrar(desde, hasta, o)

    def _en_pisos(self, p) -> bool:
        """En la pantalla de pisos: por "Floor 3 Cleared" (si esta bestia tiene esa imagen) o, como eso
        no sale si aun no se ha pasado el piso 3 en esta vuelta, por el texto del piso que toca."""
        if self.piso3_superado is not None and self.piso3_superado.esta(p):
            return True
        return not juego.pantalla_bestias.esta(p) and self._buscar_piso(p) is not None

    def _volvio_a_pisos(self, p) -> bool:
        return juego.carga_bestias.esta(p) or self._en_pisos(p)

    def _verificar_equipo(self, p):
        self.equipo_verificado = True  # cualquier equipo vale

    def elegir_piso(self, p, o):
        if juego.empezar.esta(p):
            self.buscando_piso_desde = None
            return "preparar"
        if self.clic_si(juego.ok, p, o):  # confirmar al abrir el piso
            return None
        rect = self._buscar_piso(p)
        if rect is not None:
            self.log(f"Abro el Floor {self.piso}.")
            entrada.clic(rect, o, espera=1.0)
            return None
        # Sin el piso a la vista (p. ej. una bestia sin Floor 3, o aun no desbloqueado): no quedarse ahi.
        self.buscando_piso_desde = self.buscando_piso_desde or time.time()
        if time.time() - self.buscando_piso_desde > SALTAR_PISO_S:
            antes = self.piso
            self._siguiente_piso()
            self.log(f"No encuentro el Floor {antes}: paso al Floor {self.piso}.", "aviso")
        return None

    def _buscar_piso(self, p):
        """Rectangulo del texto del piso que toca en la pantalla de pisos (sin contar "Floor N Cleared").
        Cada bestia nombra sus pisos a su manera ("Piso 1 del templo del ocaso", "Salón del Génesis
        (piso 1)"...): se busca "floor N" o "piso N" en cualquier parte de la linea."""
        if not ocr.disponible():
            self.log("Para elegir el piso necesito el lector de texto de Windows: ejecuta Instalar.bat.", "error")
            raise TerminarModo()
        lineas = ocr.lineas_con_posicion(p) + ocr.lineas_con_posicion(p, invertir=True)
        if not self.textos_vistos and lineas:  # una vez por sesion, para poder ajustar si no lo encuentra
            self.textos_vistos = True
            self.log("Texto en la pantalla de pisos: " + " | ".join(t for t, _ in lineas), "debug")
        for texto, rect in lineas:
            t = texto.lower()
            if "clear" in t or "superad" in t:
                continue
            if any(int(n) == self.piso for n in re.findall(r"(?:floor|piso)\s*(\d+)", t)):
                return rect
        return None


def _bestia(id_base: str, titulo: str, plantilla, imagen: str, piso3=None, enemigos: int = 1):
    """Crea el modo Floor 1-3 de una bestia."""
    return type(f"Pisos1a3_{id_base}", (BestiaPisos1a3,), {
        "id": f"{id_base}_pisos1a3", "nombre": f"{titulo} · Floor 1-3", "titulo_juego": titulo,
        "subtitulo_juego": "Demonic Beast · Floor 1-3", "imagen": imagen, "bestia": plantilla,
        "piso3_superado": piso3, "enemigos": enemigos,
    })


PerrosPisos1a3 = _bestia("perros", "Skollandhati & Hati", juego.perros, "demonic_beasts/skollandhati.png",
                         juego.piso3_superado, enemigos=2)  # los dos perros
PajaroPisos1a3 = _bestia("pajaro", "Hraesvelgr", juego.pajaro, "demonic_beasts/hraesvelgr.png")
CiervoPisos1a3 = _bestia("ciervo", "Eikthyrnir", juego.ciervo, "deer/Eikthyrnir.png")
SerpientePisos1a3 = _bestia("serpiente", "Nidhoggr", juego.serpiente, "snake/nidhoggr.png")
RataPisos1a3 = _bestia("rata", "Ratatoskr", juego.rata, "rat/ratatoskr.png")
TODAS = (PerrosPisos1a3, PajaroPisos1a3, CiervoPisos1a3, SerpientePisos1a3, RataPisos1a3)
