"""Base comun para todos los modos de farmeo.

Un modo es una maquina de estados: un diccionario {estado: funcion}. Cada funcion hace UNA
observacion (captura) y como mucho una accion, y devuelve el siguiente estado (o None para
quedarse). El motor se encarga del bucle, la pausa/detener, la reconexion y el vigilante de
atascos.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import lumen
from lumen import avisos, config, entrada, historial, informe, juego, recompensas, ventana
from lumen.control import Detenido, control
from lumen.vision import Plantilla


@dataclass
class Opcion:
    """Una opcion que el modo muestra en la interfaz."""

    clave: str
    etiqueta: str
    tipo: str  # "entero", "texto", "si_no", "lista"
    defecto: Any
    opciones: list = field(default_factory=list)
    ayuda: str = ""
    minimo: int = 0
    maximo: int = 9999


class TerminarModo(Exception):
    """El modo termino su trabajo (p. ej. llego al numero de victorias)."""


class Modo:
    id = "base"
    nombre = "Modo"
    descripcion = ""
    # Para la tarjeta del modo en Inicio (nombres tal como salen en el juego)
    titulo_juego = ""  # p. ej. "Skollandhati & Hati"
    subtitulo_juego = ""  # p. ej. "Demonic Beast · Floor 4"
    imagen = ""  # emblema, relativo a assets/imagenes
    duracion = ""  # duracion aproximada de una pelea, p. ej. "~2,5 min"
    fases = 0  # fases de la pelea (para marcarlas en la pagina Farmear); 0 = no se muestran
    nombres_estados: dict[str, str] = {}  # estado -> texto para el jugador ("pelea" -> "Peleando")
    opciones: list[Opcion] = []
    pausa_entre_pasos = 0.5
    guardar_historial = True  # False en herramientas que no son farmeo (p. ej. la captura de heroes)

    def __init__(self, valores: dict):
        self.valores = {o.clave: valores.get(o.clave, o.defecto) for o in self.opciones}
        self.estado = self.estado_inicial()
        self.stats = {"inicio": time.time()}
        self._vigilante_activo = False

    # ---------------------------------------------------------------- para los modos
    def estado_inicial(self) -> str:
        raise NotImplementedError

    def estados(self) -> dict:
        raise NotImplementedError

    def log(self, mensaje: str, nivel: str = "info"):
        control.log(mensaje, nivel)

    def publicar_stats(self, **cambios):
        self.stats.update(cambios)
        control.al_stats(dict(self.stats))

    @staticmethod
    def capturar():
        return ventana.capturar()

    # Textos de botones que solo cierran o avanzan una pantalla (nunca gastan nada): si una pantalla no tiene
    # imagen guardada, el bot la pasa leyendo el boton. Palabras completas, para no tocar "Cancel" ni "Shop".
    BOTONES_SEGUROS = ("ok", "confirm", "receive", "claim", "close", "next", "continue", "tap to continue",
                       "touch to continue", "aceptar", "recibir", "cerrar", "siguiente", "continuar")

    def clic_boton_por_texto(self, pantalla, origen) -> str:
        """Lee la pantalla y toca el primer boton seguro que encuentre; devuelve su texto ("" si ninguno)."""
        from lumen import ocr

        if not ocr.disponible():
            return ""
        for texto, (x, y, w, h) in ocr.lineas_con_posicion(pantalla):
            limpio = texto.strip().lower().strip(".!")
            if limpio in self.BOTONES_SEGUROS:
                entrada.clic((x + w // 2, y + h // 2), origen, espera=0.8)
                self.log(f"Pantalla sin imagen guardada: toco «{texto.strip()}».", "aviso")
                return texto.strip()
        return ""

    @staticmethod
    def clic_si(plantilla: Plantilla, pantalla, origen, umbral: float = 0.7, punto=None, espera: float = 0.25) -> bool:
        """Si la plantilla esta en pantalla, clic en ella (o en ``punto``). Devuelve si clico."""
        rect = plantilla.buscar(pantalla, umbral)
        if rect is None:
            return False
        entrada.clic(punto or tuple(rect), origen, espera=espera)
        control.log(f"Clic en '{plantilla.nombre}'", "debug")
        return True

    def comprobaciones_globales(self, pantalla, origen) -> bool:
        """Se ejecuta en cada paso antes del estado. True = ya hizo algo, saltar el paso."""
        if self.clic_si(juego.reconectar, pantalla, origen):
            self.log("Conexion perdida: reconectando...", "aviso")
            return True
        if juego.reiniciar_juego.esta(pantalla):
            self.log("El juego pide reiniciar. Detengo el bot para que lo revises.", "error")
            avisos.enviar("LumenFarm: el juego pide reiniciar, bot detenido.", pantalla)
            raise TerminarModo()
        return False

    def al_terminar(self):
        """Resumen final; los modos lo amplian."""

    def guardar_recompensa(self, pantalla, victoria: int) -> None:
        """Foto de la pantalla de recompensas para la pagina Recompensas. Un fallo aqui nunca para el bot."""
        try:
            recompensas.guardar(pantalla, modo=self.id, nombre_modo=self.nombre, sesion=self.stats["inicio"], victoria=victoria)
            self.publicar_stats(fotos_recompensas=self.stats.get("fotos_recompensas", 0) + 1)
            self.log("Foto de recompensas guardada.", "debug")
        except Exception as error:
            self.log(f"No pude guardar la foto de recompensas: {error}", "aviso")

    def en_zona_segura(self) -> bool:
        """True si se puede parar sin dejar nada a medias (los modos con peleas lo redefinen)."""
        return True

    # ------------------------------------------------------------------ bucle principal
    def ejecutar(self):
        estados = self.estados()
        self._iniciar_vigilante()
        self.log(f"Iniciando {self.nombre}.", "ok")
        try:
            while True:
                control.revisar()
                if control.parar_en_zona_segura and self.en_zona_segura():
                    self.log("Parada segura (actualizacion pendiente).", "aviso")
                    raise TerminarModo()
                control.estado(self.estado)
                pantalla, origen = self.capturar()
                if not self.comprobaciones_globales(pantalla, origen):
                    siguiente = estados[self.estado](pantalla, origen)
                    if siguiente and siguiente != self.estado:
                        self.log(f"Estado: {self.estado} -> {siguiente}", "debug")
                        self.estado = siguiente
                control.esperar(self.pausa_entre_pasos)
        except TerminarModo:
            self.log("Modo terminado.", "ok")
        except Detenido:
            self.log("Detenido por el usuario.", "aviso")
        finally:
            self._vigilante_activo = False
            self.al_terminar()
            sesion = {k: v for k, v in self.stats.items() if isinstance(v, (int, float, str))}
            sesion.update(modo=self.id, nombre=self.nombre, fin=time.time(), version=lumen.__version__)
            equipo = getattr(self, "equipo", None)
            if equipo is not None:  # para medir que equipo rinde mas (pagina Equipos)
                sesion["equipo"] = list(equipo.orden)
            if self.guardar_historial and sesion["fin"] - sesion.get("inicio", sesion["fin"]) > 30:  # no guardar arranques en falso
                historial.registrar(sesion)

    # -------------------------------------------------------------- vigilante de atascos
    def _iniciar_vigilante(self):
        self._vigilante_activo = True

        def vigilar():
            avisado = False
            while self._vigilante_activo:
                time.sleep(5)
                if control.en_pausa:
                    continue
                minutos = float(config.obtener("minutos_atasco") or 0)
                parado = time.time() - control.ultima_actividad
                if minutos > 0 and parado > minutos * 60:
                    if not avisado:
                        avisado = True
                        self.log(f"Parece atascado: {parado / 60:.0f} min sin cambios en '{self.estado}'.", "error")
                        try:
                            pantalla, _ = ventana.capturar()
                        except Exception:
                            pantalla = None
                        avisos.enviar(informe.texto_atasco(self, parado / 60), pantalla)
                elif avisado:
                    avisado = False
                    self.log("Ya no esta atascado.", "ok")
                    avisos.enviar("LumenFarm se recupero.")

        threading.Thread(target=vigilar, daemon=True, name="vigilante").start()
