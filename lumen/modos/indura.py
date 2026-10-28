"""Indura (Boss Battle en tiempo real): se une a las partidas que otros jugadores abren.

Flujo (el de demonios de AutoFarming, MIT; Indura no esta en esa parte publica, asi que su icono es
una captura propia):
1. Taberna -> Battle -> Boss Battle -> Real-time: se abre "Real-time Join Request".
2. Pestana de Indura (la 6.a), el nivel elegido (Chaos por defecto) y OK: el juego busca partida.
3. Llega una invitacion: se acepta JUSTO a los 9.3 s de aparecer. Es un fallo del juego: aceptada en
   ese momento entra a la partida sin gastar entradas de tiempo real. Por eso se cuenta desde el primer
   instante en que se ve, se mira la pantalla muy seguido mientras se espera y, llegado el momento, se
   toca el Accept ya localizado sin volver a capturar.
4. Preparacion: se pulsa "Preparation". En la pelea el bot juega las cartas como el administrador
   (lumen/datos/estrategias.yaml): reconoce el equipo por la mano y en cada casilla libre del turno juega
   la carta de mas prioridad. Si no reconoce el equipo (uno sin estrategia), pone AUTO.
5. Demonio destruido -> OK. Se cuenta la victoria y se vuelve a buscar.

Indura tiene limite diario de peleas (el juego lo dice en la ventana de union): cuando ya no hay
partidas, el bot se queda esperando invitaciones que no llegan; se para con un tiempo maximo de espera.
"""

import time

from lumen import cartas, entrada, estrategias, juego
from lumen.control import Detenido, control
from lumen.motor import Modo, Opcion, TerminarModo
from lumen.vision import Plantilla

P = Plantilla
BOSS_BATTLE = P("demons/demons.jpg")  # menu Boss Battle (AutoFarming, MIT)
TIEMPO_REAL = P("demons/RT.png")
VENTANA_UNION = P("demons/union_tiempo_real.png")  # titulo "Real-time Join Request" (captura propia)
INDURA = P("demons/indura_lumen.png")  # pestana de Indura seleccionada (captura propia)
NIVELES = {"Extreme": P("demons/extreme.png"), "Hell": P("demons/hell.png"), "Chaos": P("demons/chaos.png")}
ACEPTAR = P("demons/accept.png")
CANCELAR_BUSQUEDA = P("demons/cancel.png")
CARGANDO = P("demons/demons_loading_screen.png")
PREPARACION = P("demons/preparation_incomplete.png")
AUTO = P("demons/auto.jpg")
DESTRUIDO = P("demons/demons_destroyed.png")

PESTANA_INDURA = (490, 258)  # la ultima pestana de la ventana de union (medido)
OK_UNION = (277, 869)


class Indura(Modo):
    id = "indura"
    nombre = "Indura"
    titulo_juego = "Indura"
    subtitulo_juego = "Boss Battle · Real-time"
    descripcion = ("Se une a las partidas de Indura que abren otros jugadores y pelea en AUTO. "
                   "Empieza desde la Taberna o el menú Battle.")
    imagen = "demons/indura_lumen.png"  # icono de Indura (captura propia)
    duracion = "según la partida"
    nombres_estados = {
        "ir_a_indura": "Entrando a Boss Battle",
        "elegir": "Eligiendo Indura y el nivel",
        "buscar": "Esperando una invitación",
        "preparar": "Preparando la pelea",
        "pelea": "Peleando (AUTO)",
    }
    opciones = [
        Opcion("nivel", "Nivel", "lista", "Chaos", opciones=["Chaos", "Hell", "Extreme"]),
        Opcion("jugar", "Cómo pelear", "lista", "Mis cartas", opciones=["Mis cartas", "AUTO"],
               ayuda="Mis cartas: el bot juega como tú con la estrategia de tu equipo (si no la reconoce, AUTO)."),
        Opcion("espera", "Segundos antes de aceptar", "texto", "9.3",
               ayuda="Aceptar justo a los 9.3 s entra a la partida sin gastar entradas de tiempo real."),
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=999),
        Opcion("minutos_sin_invitacion", "Parar tras minutos sin invitaciones", "entero", 20, maximo=600),
    ]
    pausa_entre_pasos = 0.05  # buscando invitaciones hay que verlas en cuanto salen (cuenta el tiempo)

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.victorias = self.derrotas = self.perdidas = 0
        self.buscando_desde = time.time()
        self.auto_puesto = False
        self.estrategias = estrategias.cargar(self.id)
        self.estrategia: estrategias.Estrategia | None = None
        self.turnos_sin_equipo = 0
        self.libres_antes = -1  # casillas libres cuando se toco la ultima carta
        self.tocado_en = 0.0

    def estado_inicial(self):
        return "ir_a_indura"

    def estados(self):
        return {"ir_a_indura": self.ir_a_indura, "elegir": self.elegir, "buscar": self.buscar,
                "preparar": self.preparar, "pelea": self.pelea}

    def en_zona_segura(self) -> bool:
        return self.estado in ("ir_a_indura", "elegir", "buscar")

    def _stats(self):
        total = self.victorias + self.derrotas
        self.publicar_stats(victorias=self.victorias, derrotas=self.derrotas, invitaciones_perdidas=self.perdidas,
                            tasa=(100 * self.victorias / total) if total else 0.0)

    # ------------------------------------------------------------- navegacion
    def ir_a_indura(self, p, o):
        if AUTO.esta(p, 0.8):
            self.log("Ya estaba en una pelea: sigo con ella.", "aviso")
            return "pelea"
        if PREPARACION.esta(p, 0.8):
            return "preparar"
        if CANCELAR_BUSQUEDA.esta(p, 0.8):
            self.buscando_desde = time.time()
            return "buscar"
        if VENTANA_UNION.esta(p, 0.85):
            return "elegir"
        self.clic_si(juego.ok, p, o)  # avisos que tapan el menu
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6, espera=1.0)
        self.clic_si(BOSS_BATTLE, p, o, umbral=0.75, espera=1.0)
        self.clic_si(TIEMPO_REAL, p, o, umbral=0.75, espera=1.0)
        return None

    def elegir(self, p, o):
        if not VENTANA_UNION.esta(p, 0.85):
            return "ir_a_indura"
        if not INDURA.esta(p, 0.85):
            self.clic_si(VENTANA_UNION, p, o, punto=PESTANA_INDURA, espera=1.0)
            return None
        nivel = self.valores["nivel"]
        if not self.clic_si(NIVELES[nivel], p, o, umbral=0.8, espera=0.8):
            self.log(f"No veo el nivel {nivel} de Indura.", "aviso")
            return None
        self.clic_si(VENTANA_UNION, p, o, punto=OK_UNION, espera=1.5)  # OK: empieza a buscar
        self.log(f"Buscando partidas de Indura ({nivel}).", "ok")
        self.buscando_desde = time.time()
        return "buscar"

    def buscar(self, p, o):
        rect = ACEPTAR.buscar(p, 0.7)
        if rect is not None:
            visto = time.perf_counter()  # el reloj cuenta desde que se ve la invitacion
            try:
                espera = float(str(self.valores["espera"]).replace(",", "."))
            except ValueError:
                espera = 9.3
            entrada.apuntar(rect, o)  # el raton ya encima de Accept: a los 9.3 s solo falta pulsar
            self.log(f"¡Invitación! La acepto a los {espera:.1f} s.")
            while (falta := espera - (time.perf_counter() - visto)) > 0:
                time.sleep(min(falta, 0.05))  # en trozos cortos: F10 y la pausa siguen respondiendo
                if control.detenido:
                    raise Detenido()
                if control.en_pausa:
                    self.log("En pausa: dejo pasar esta invitación.", "aviso")
                    return None
            # Sin volver a capturar ni mover el raton: pulsar ya (cada centesima cuenta).
            entrada.pulsar()
            self.log(f"Aceptada a los {time.perf_counter() - visto:.2f} s.", "debug")
            control.esperar(3.0)
            p, _ = self.capturar()
            if ACEPTAR.esta(p, 0.7):
                self.perdidas += 1
                self.log("La invitación sigue ahí: el toque no entró.", "aviso")
                self._stats()
                return None
            if TIEMPO_REAL.esta(p, 0.75):  # volvio al menu: la partida ya estaba llena
                self.perdidas += 1
                self.log(f"Invitación perdida (ya llena). Van {self.perdidas}.", "aviso")
                self._stats()
                return "ir_a_indura"
            return "preparar"
        if CARGANDO.esta(p, 0.8) or PREPARACION.esta(p, 0.8):
            return "preparar"
        if not CANCELAR_BUSQUEDA.esta(p, 0.8):
            return "ir_a_indura"  # ya no se esta buscando: volver a pedirlo
        minutos = float(self.valores["minutos_sin_invitacion"])
        if minutos and time.time() - self.buscando_desde > minutos * 60:
            self.log(f"{minutos:.0f} min sin invitaciones (¿se acabó el límite diario de Indura?). Termino.", "aviso")
            raise TerminarModo()
        return None

    def preparar(self, p, o):
        self.clic_si(PREPARACION, p, o, umbral=0.8, espera=1.0)
        if AUTO.esta(p, 0.8):
            self.auto_puesto = False
            self.estrategia = None
            self.turnos_sin_equipo = 0
            self.libres_antes = -1
            self.log("¡Empieza la pelea!", "ok")
            return "pelea"
        if juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75):
            self.log("La partida se deshizo antes de empezar. Vuelvo a buscar.", "aviso")
            return "ir_a_indura"
        return None

    # ------------------------------------------------------------------ pelea
    def _jugar_carta(self, p, o):
        """Si es nuestro turno, juega la carta que toca segun la estrategia del equipo."""
        libres = cartas.casillas_libres_demonio(p)
        if libres == 0:
            return
        # Tras tocar una carta, esperar a que ocupe su casilla antes de elegir la siguiente.
        if libres == self.libres_antes and time.time() - self.tocado_en < 2.0:
            return
        mano = cartas.leer_mano_demonio(p)
        if self.estrategia is None:
            self.estrategia = estrategias.reconocer(self.estrategias, mano)
            if self.estrategia is None:
                self.turnos_sin_equipo += 1
                if self.turnos_sin_equipo >= 3:  # equipo sin estrategia: que juegue el juego
                    self.log("No reconozco este equipo: lo dejo en AUTO.", "aviso")
                    self.auto_puesto = self.clic_si(AUTO, p, o, umbral=0.8)
                return
            self.log(f"Equipo reconocido: {self.estrategia.nombre}. Juego como tú.", "ok")
        self.estrategia.etiquetar(mano)
        carta = self.estrategia.elegir(mano) or estrategias.la_de_mas_rango(mano)
        if carta is None:
            return
        entrada.clic(carta.rect, o, espera=0.3)
        self.libres_antes, self.tocado_en = libres, time.time()
        self.log(f"   juego {carta.nombre} ({carta.rango.name.lower()}, posición {carta.posicion + 1})", "debug")

    def pelea(self, p, o):
        if self.valores.get("jugar") == "AUTO" or self.auto_puesto:
            if not self.auto_puesto and self.clic_si(AUTO, p, o, umbral=0.8):
                self.auto_puesto = True
                self.log("AUTO puesto.", "debug")
        else:
            self._jugar_carta(p, o)
        self.clic_si(juego.saltar, p, o)
        self.clic_si(DESTRUIDO, p, o, umbral=0.6)
        gano = juego.victoria.esta(p, 0.6) or DESTRUIDO.esta(p, 0.6)
        if gano and not getattr(self, "_contada", False):
            self._contada = True
            self.victorias += 1
            self.log(f"¡Indura destruido! Victoria #{self.victorias}.", "ok")
            self.guardar_recompensa(p, self.victorias)
            self._stats()
        if juego.ok.esta(p) or juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75):
            if not getattr(self, "_contada", False):
                self.derrotas += 1
                self.log("No pudimos con Indura esta vez.", "aviso")
                self._stats()
            self.clic_si(juego.ok, p, o, espera=1.0)
            self._contada = False
            meta = int(self.valores["victorias"])
            if meta and self.victorias >= meta:
                self.log(f"Llegué a {meta} victorias.", "ok")
                raise TerminarModo()
            return "ir_a_indura"
        return None

    def al_terminar(self):
        self.log(f"Indura: {self.victorias} victorias, {self.derrotas} derrotas, "
                 f"{self.perdidas} invitaciones perdidas.", "ok")
