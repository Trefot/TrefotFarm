"""Demonios en tiempo real (Boss Battle): se une a las partidas que otros jugadores abren. Un molde para
los 6 (Red, Gray, Howlex, Bellmoth, Original e Indura), como el de los pisos 1-3 de las bestias.

Flujo (el de los demonios; Indura no tenia imagen, asi que su icono es
una captura propia):
1. Taberna -> Battle -> Boss Battle -> Real-time: se abre "Real-time Join Request".
2. Pestana del demonio, el nivel elegido y OK: el juego busca partida. Indura (la 6.a pestana) se toca
   por su posicion y se comprueba que quede elegida; los otros 5, por su icono.
3. Llega una invitacion: se acepta JUSTO a los 9.3 s de aparecer. Es un fallo del juego: aceptada en
   ese momento entra a la partida sin gastar entradas de tiempo real. Por eso se cuenta desde el primer
   instante en que se ve, se mira la pantalla muy seguido mientras se espera y, llegado el momento, se
   toca el Accept ya localizado sin volver a capturar.
4. Preparacion: se pulsa "Preparation". En la pelea, segun la opcion "Como pelear":
   - Inteligente (por defecto): piensa las casillas que quedan del turno y las fusiones
     (lumen/inteligencia.py), con cualquier equipo. No arrastra cartas.
   - Mis cartas: como el administrador (lumen/datos/estrategias.yaml): reconoce el equipo por la mano y en
     cada casilla libre juega la carta de mas prioridad. Si no reconoce el equipo, pone AUTO.
   - AUTO: lo juega el juego.
5. Demonio destruido -> OK. Se cuenta la victoria y se vuelve a buscar.

Solo en Indura, la opcion "Partidas" tiene dos modos mas (capturas del usuario del 2026-11-27):
- Aceptar solicitud: en vez de buscar, se queda donde este (la Taberna) esperando la ventana "X is inviting you to
  Death Match!". Pulsa "Accept Invitation" (nunca "View Later" ni la casilla de rechazar un dia) y juega normal
  desde el paso 4. Al acabar vuelve a esperar.
- Enviar solicitud (Lumen en una segunda cuenta que ayuda a la principal): Death Match -> Indura -> el nivel abre
  una sala propia. Invitar -> pestana Favoritos -> Invite All (en Favoritos se deja solo la cuenta principal).
  Cuando la otra cuenta sale con "Preparation Complete", pulsa el suyo; en la pelea lanza sus 3 cartas, se rinde
  (el boton junto a AUTO) y confirma. El juego no deja abrir otra sala hasta que la otra cuenta acaba su pelea:
  se reintenta cada poco hasta que se abre.

Indura tiene limite diario de peleas (el juego lo dice en la ventana de union): cuando ya no hay
partidas, el bot se queda esperando invitaciones que no llegan; se para con un tiempo maximo de espera.
"""

import time

import cv2

from lumen import avisos, botin, cartas, entrada, estrategias, inteligencia, juego, ocr, ventana
from lumen.control import Detenido, control
from lumen.ia import aprendizaje, diario
from lumen.motor import Modo, Opcion, TerminarModo
from lumen.vision import Plantilla

P = Plantilla
# menu Boss Battle (imagen MIT) y, desde la actualizacion del 2026-11-27, "Death Match" en el menu Battle nuevo
BOSS_BATTLE = P("demons/demons.jpg", "menu_2026/death_match.png", nombre="boss_battle")
TIEMPO_REAL = P("demons/RT.png")
VENTANA_UNION = P("demons/union_tiempo_real.png")  # titulo "Real-time Join Request" (captura propia)
INDURA = P("demons/indura_lumen.png")  # pestana de Indura seleccionada (captura propia)
NIVELES = {"Normal": P("demons/normal.png"), "Hard": P("demons/hard.png"), "Extreme": P("demons/extreme.png"),
           "Hell": P("demons/hell.png"), "Chaos": P("demons/chaos.png")}
# Ventana nueva (actualizacion del 2026-11-27): los niveles son cartas en una fila que se desliza y su nombre tiene
# otra letra. Se leen con OCR en la franja de los nombres; si el que toca no se ve, se desliza hacia el.
ORDEN_NIVELES = ["Normal", "Hard", "Extreme", "Hell", "Chaos"]
FRANJA_NIVELES = (590, 670)  # y de los nombres de las cartas
DESLIZAR_NIVELES = ((450, 500), (130, 500))  # arrastre hacia la izquierda: se ven los niveles mas altos
ACEPTAR = P("demons/accept.png")
ACEPTAR_AMIGO = P("demons/aceptar_invitacion.png")  # "Accept Invitation" de un amigo (foto del usuario, 2026-11-27)
CANCELAR_BUSQUEDA = P("demons/cancel.png")
CARGANDO = P("demons/demons_loading_screen.png")
PREPARACION = P("demons/preparation_incomplete.png")
CANCELAR_PREPARACION = P("demons/cancel_preparation.png")  # el mismo boton ya pulsado (imagen MIT)
ATRAS = P("back.png")  # la flecha de volver, arriba a la izquierda
PUNTO_ATRAS = (39, 64)
AUTO = P("demons/auto.jpg")
DESTRUIDO = P("demons/demons_destroyed.png")

BUSCAR, AMIGOS, ENVIAR = "Buscar partidas", "Aceptar solicitud", "Enviar solicitud"
AMIGOS_ANTES = "Invitaciones de amigos"  # el nombre de la 0.46.0 (puede seguir guardado en la configuracion)

# Enviar solicitud: la sala propia de Indura (menu Death Match de la actualizacion del 2026-11-27)
S = "indura_sala/"
DM_INDURA = P(S + "dm_indura.png")  # la tarjeta "Indura of Retribution" del menu Death Match
NIVELES_INDURA = P(S + "indura_niveles.png")  # titulo "Indura of Retribution Death Match" (elegir nivel)
NIVEL_SALA = {"Chaos": P(S + "sala_chaos.png"), "Hell": P(S + "sala_hell.png"), "Extreme": P(S + "sala_extreme.png")}
SALA_INVITAR = P(S + "sala_invitar.png")  # el hexagono verde de invitar (solo en la sala propia)
SALA_PREPARACION = P(S + "sala_preparacion.png")  # el boton grande "Preparation Complete"
AMIGO_LISTO = P(S + "amigo_listo.png")  # "Preparation Complete" debajo de la otra cuenta
INVITAR_VENTANA = P(S + "invitar_cerrar.png")  # la X roja de la ventana de invitar
INVITAR_TODOS = P(S + "invitar_todos.png")  # "Invite All" en amarillo (gris = nadie a quien invitar)
RENDIRSE = P(S + "pelea_rendirse.png")  # el boton junto a AUTO
RENDIRSE_TEXTO = P(S + "rendirse_texto.png")  # "Are you sure you want to forfeit the battle?"
RENDIRSE_OK = P(S + "rendirse_ok.png")
PESTANA_FAVORITOS = (68, 373)
CARTAS_ANTES_DE_SALIR = 3
CADA_INVITACION = 60.0  # s: si la otra cuenta no entra, se vuelve a invitar
CADA_REINTENTO = 15.0  # s entre intentos de abrir la sala mientras la otra cuenta acaba su pelea

PESTANA_INDURA = (490, 258)  # la ultima pestana de la ventana de union (medido)
OK_UNION = (277, 869)

# PC lentos (maquina virtual, prueba de la 0.13.1): mirar la pantalla tarda tanto que el bot veia la invitacion
# tarde y tocaba despues de los 9.3 s. Lo que pase de lo normal en un PC rapido se descuenta de la espera.
RETRASO_NORMAL = 0.3  # s desde que sale la invitacion hasta que el bot la reconoce, en un PC normal
COSTO_NORMAL = 0.15  # s de mirar la pantalla y buscar Accept (se repite justo antes del toque), en un PC normal
ADELANTO_MAX = 3.0
# En la maquina virtual cada vuelta del bot (captura + ~10 imagenes) tardaba mas de 2 s: la invitacion se veia
# tan tarde y con tanta duda que se perdia. Mientras se espera, se mira solo Accept, muy seguido, este rato.
VIGILANCIA = 2.0
# Tras una derrota el juego a veces deja al grupo en la sala para la revancha. Si los demas se van, la sala se
# queda ahi: el 2026-11-16 el bot espero asi 5 h. Lo normal es que la pelea empiece en menos de 1 min.
ESPERA_SALA = 180.0  # s en la sala sin empezar: me salgo y vuelvo a buscar
CADA_SALIDA = 10.0  # s entre intentos de salir (dar tiempo a la pantalla)
INTENTOS_SALIDA = 6  # sin poder salir tras tantos intentos: aviso al movil con la foto
VECES_HEROE = 5  # cartas de un heroe vistas en la sesion para contarlo en el equipo (como en las bestias)


def adelanto_por_lentitud(captura_anterior: float, captura: float, reconocida: float) -> float:
    """Segundos que hay que tocar antes por un PC lento (0 en un PC normal o si no se sabe).

    La invitacion salio entre la captura anterior y la que la vio (se toma la mitad) y se reconocio al acabar de
    buscarla: ese retraso, y el de volver a mirar antes del toque, se descuentan en lo que pasen de lo normal.
    """
    if not captura or not captura_anterior or reconocida < captura:
        return 0.0
    costo = reconocida - captura
    retraso = costo + (captura - captura_anterior) / 2
    return min(ADELANTO_MAX, max(0.0, retraso - RETRASO_NORMAL) + max(0.0, costo - COSTO_NORMAL))


class DemonioTiempoReal(Modo):
    """El molde: cada demonio pone su id, nombre, pestana y niveles (ver _demonio)."""

    id = "demonio"
    nombre = "Demonio"
    subtitulo_juego = "Boss Battle · Real-time"
    duracion = "según la partida"
    pestana: Plantilla | None = None  # icono de la pestana en la ventana de union (se toca)
    punto_pestana: tuple[int, int] | None = None  # o su posicion, si no hay icono
    pestana_elegida_img: Plantilla | None = None  # la pestana ya elegida (para comprobarlo), si se tiene
    nombres_estados = {
        "ir_a_indura": "Entrando a Boss Battle",
        "elegir": "Eligiendo el demonio y el nivel",
        "buscar": "Esperando una invitación",
        "preparar": "Preparando la pelea",
        "pelea": "Peleando",
        "abrir_sala": "Abriendo la sala",
        "sala_propia": "Esperando a la otra cuenta",
        "pelea_corta": "Lanzando 3 cartas",
    }
    opciones: list[Opcion] = []
    pausa_entre_pasos = 0.05  # buscando invitaciones hay que verlas en cuanto salen (cuenta el tiempo)

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.victorias = self.derrotas = self.perdidas = 0
        self.buscando_desde = time.time()
        self.auto_puesto = False
        self.estrategias = estrategias.cargar(self.id)
        self.estrategia: estrategias.Estrategia | None = None
        self.jugador = inteligencia.Jugador(enemigos=1, arrastrar=False)
        self.jugador.equipo = ()
        self.turnos_sin_equipo = 0
        self.turno_diario = 0
        self.libres_observados = 0
        self.decision_pendiente = None
        self.libres_antes = -1  # casillas libres cuando se toco la ultima carta
        self.ultima_tocada = None  # la ultima carta tocada (por si no entra en su casilla)
        self.rechazadas: list = []  # dibujos de cartas que no entraron este turno
        self.desconocida_desde: float | None = None  # pantalla sin nada conocido desde...
        self.avisado_desconocida = False
        self.tocado_en = 0.0
        self.pestana_elegida = False
        self.sala_desde: float | None = None  # en la sala de preparacion desde...
        self.salida_en = 0.0
        self.intentos_salida = 0
        self.avisado_lider = False
        self.t_captura = self.t_captura_anterior = 0.0  # cuando se miraron las dos ultimas pantallas
        # Diario de cada pelea (IA.md, pieza 5) y, jugando "Inteligente", aprender solo (pieza 6), como en las
        # bestias. Un archivo por demonio; cada pelea apunta su nivel y se aprende por separado en cada uno.
        self.diario = diario.Diario(self.id)
        self.aprendizaje_dicho = False
        # Con que equipo se jugo (para medirlo y recomendarlo en Mejores equipos): el de la estrategia de
        # "Mis cartas" o, jugando Inteligente, los 4 heroes cuyas cartas mas se vieron.
        self.equipo_usado: list[str] | None = None
        self.heroes_vistos: dict[str, int] = {}

    def al_empezar(self):
        if self.valores.get("jugar") == "Inteligente":
            self.jugador.precargar()

    def capturar(self):
        self.t_captura_anterior, self.t_captura = self.t_captura, time.perf_counter()
        return ventana.capturar()

    @property
    def de_amigos(self) -> bool:
        return self.valores.get("partidas") in (AMIGOS, AMIGOS_ANTES)

    @property
    def enviando(self) -> bool:
        return self.valores.get("partidas") == ENVIAR

    def estado_inicial(self):
        if self.enviando:
            return "abrir_sala"
        return "buscar" if self.de_amigos else "ir_a_indura"

    def _volver(self) -> str:
        """A donde se va al acabar una pelea o deshacerse una sala: a esperar al amigo, o a buscar otra partida."""
        return "buscar" if self.de_amigos else "ir_a_indura"

    def estados(self):
        return {"ir_a_indura": self.ir_a_indura, "elegir": self.elegir,
                "buscar": self.esperar_amigo if self.de_amigos else self.buscar,
                "preparar": self.preparar, "pelea": self.pelea,
                "abrir_sala": self.abrir_sala, "sala_propia": self.sala_propia, "pelea_corta": self.pelea_corta}

    def en_zona_segura(self) -> bool:
        return self.estado in ("ir_a_indura", "elegir", "buscar", "abrir_sala", "sala_propia")

    def _stats(self):
        total = self.victorias + self.derrotas
        self.publicar_stats(victorias=self.victorias, derrotas=self.derrotas, invitaciones_perdidas=self.perdidas,
                            tasa=(100 * self.victorias / total) if total else 0.0)

    # ------------------------------------------------------------- navegacion
    def ir_a_indura(self, p, o):
        siguiente = self._ir_a_indura(p, o)
        if siguiente:  # pantalla conocida: el reloj de "sin reconocer" vuelve a cero
            self.desconocida_desde, self.avisado_desconocida = None, False
        if siguiente == "preparar":
            self._fuera_de_sala()  # sala nueva: su reloj empieza ahora
        return siguiente

    def _ir_a_indura(self, p, o):
        if AUTO.esta(p, 0.8):
            self.log("Ya estaba en una pelea: sigo con ella.", "aviso")
            return "pelea"
        if PREPARACION.esta(p, 0.8):
            return "preparar"
        if CANCELAR_BUSQUEDA.esta(p, 0.8):
            self.buscando_desde = time.time()
            return "buscar"
        if VENTANA_UNION.esta(p, 0.85):
            self.pestana_elegida = False
            return "elegir"
        conocida = (self.clic_si(juego.ok, p, o)  # avisos que tapan el menu
                    | self.clic_si(juego.menu_batalla, p, o, umbral=0.6, espera=1.0)
                    | self.clic_si(BOSS_BATTLE, p, o, umbral=0.75, espera=1.0)
                    | self.clic_si(TIEMPO_REAL, p, o, umbral=0.75, espera=1.0))
        if conocida:
            self.desconocida_desde, self.avisado_desconocida = None, False
            return None
        # Nada conocido en pantalla: en una prueba el bot se quedo asi 6 min sin decir nada. A los 3 min,
        # aviso al movil con la foto (una vez) para que el jugador mire que paso.
        self.desconocida_desde = self.desconocida_desde or time.time()
        if not self.avisado_desconocida and time.time() - self.desconocida_desde > 180:
            self.avisado_desconocida = True
            self.log("Llevo 3 min sin reconocer la pantalla. Te mando una foto al móvil.", "aviso")
            avisos.enviar(f"LumenFarm ({self.nombre}): llevo 3 min sin reconocer la pantalla del juego.", p)
        return None

    def elegir(self, p, o):
        if not VENTANA_UNION.esta(p, 0.85):
            return "ir_a_indura"
        if self.pestana_elegida_img is not None:
            self.pestana_elegida = self.pestana_elegida_img.esta(p, 0.85)
        if not self.pestana_elegida:
            if self.punto_pestana:
                self.clic_si(VENTANA_UNION, p, o, punto=self.punto_pestana, espera=1.0)
            elif self.pestana is not None and self.clic_si(self.pestana, p, o, umbral=0.75, espera=1.0):
                self.pestana_elegida = self.pestana_elegida_img is None  # sin imagen de "elegida": se da por hecha
            else:
                # El icono de la pestana elegida puede verse distinto (Red Demon sale elegido al abrir): tras
                # unos intentos se sigue con la que haya, mejor que quedarse parado.
                self.intentos_pestana = getattr(self, "intentos_pestana", 0) + 1
                self.log(f"No veo la pestaña de {self.nombre}.", "aviso")
                if self.intentos_pestana >= 5:
                    self.pestana_elegida, self.intentos_pestana = True, 0
            return None
        nivel = self.valores["nivel"]
        if not self.clic_si(NIVELES[nivel], p, o, umbral=0.8, espera=0.8) and not self._nivel_por_texto(p, o, nivel):
            return None
        self.clic_si(VENTANA_UNION, p, o, punto=OK_UNION, espera=1.5)  # OK: empieza a buscar
        self.log(f"Buscando partidas de {self.nombre} ({nivel}).", "ok")
        self.buscando_desde = time.time()
        return "buscar"

    def _nivel_por_texto(self, p, o, nivel) -> bool:
        """Ventana nueva: busca el nombre del nivel con OCR y lo toca; si no se ve, desliza la fila hacia el (antes
        se quedaba repitiendo "No veo el nivel Normal de Red Demon", 2026-11-27). True si lo toco."""
        if not ocr.disponible():
            self.log(f"No veo el nivel {nivel} de {self.nombre}.", "aviso")
            return False
        vistos = {}
        for texto, (x, y, w, h) in ocr.lineas_con_posicion(p):
            if FRANJA_NIVELES[0] <= y + h // 2 <= FRANJA_NIVELES[1]:
                for n in ORDEN_NIVELES:
                    if n.lower() in texto.lower():
                        vistos[n] = (x + w // 2, y + h // 2)
        if nivel in vistos:
            entrada.clic(vistos[nivel], o, espera=0.8)
            self.deslizes_nivel = 0
            return True
        objetivo = ORDEN_NIVELES.index(nivel)
        self.deslizes_nivel = getattr(self, "deslizes_nivel", 0) + 1
        if vistos:
            hacia_altos = max(ORDEN_NIVELES.index(n) for n in vistos) < objetivo
        else:  # no se lee nada: ir y volver
            hacia_altos = (self.deslizes_nivel // 4) % 2 == 0
        desde, hasta = DESLIZAR_NIVELES if hacia_altos else DESLIZAR_NIVELES[::-1]
        self.log(f"No veo el nivel {nivel} de {self.nombre}: deslizo la fila.", "debug")
        entrada.arrastrar(desde, hasta, o)
        return False

    def _vigilar_aceptar(self):
        """Mira solo el boton Accept, lo mas seguido posible, durante VIGILANCIA s. Devuelve (rect, origen)."""
        fin = time.perf_counter() + VIGILANCIA
        while time.perf_counter() < fin:
            control.revisar()
            try:
                p, o = self.capturar()
            except ventana.VentanaNoEncontrada:
                return None, None  # el bucle principal se encarga
            rect = ACEPTAR.buscar(p, 0.7)
            if rect is not None:
                return rect, o
        return None, None

    def buscar(self, p, o):
        rect = ACEPTAR.buscar(p, 0.7)
        if rect is None:
            if CARGANDO.esta(p, 0.8) or PREPARACION.esta(p, 0.8):
                self._fuera_de_sala()
                return "preparar"
            if not CANCELAR_BUSQUEDA.esta(p, 0.8):
                return "ir_a_indura"  # ya no se esta buscando: volver a pedirlo
            minutos = float(self.valores["minutos_sin_invitacion"])
            if minutos and time.time() - self.buscando_desde > minutos * 60:
                self.log(f"{minutos:.0f} min sin invitaciones (¿se acabó el límite diario?). Termino.", "aviso")
                raise TerminarModo()
            rect, o = self._vigilar_aceptar()
        if rect is not None:
            visto = time.perf_counter()  # el reloj cuenta desde que se ve la invitacion
            try:
                espera = float(str(self.valores["espera"]).replace(",", "."))
            except ValueError:
                espera = 9.3
            self.log(f"¡Invitación! La acepto a los {espera:.1f} s.")
            adelanto = adelanto_por_lentitud(self.t_captura_anterior, self.t_captura, visto)
            if adelanto >= 0.05:
                self.log(f"PC lento: la vi con retraso (miro cada {self.t_captura - self.t_captura_anterior:.2f} s); "
                         f"toco {adelanto:.2f} s antes para no pasarme.")
                espera -= adelanto
            while (falta := espera - (time.perf_counter() - visto)) > 0:
                time.sleep(min(falta, 0.05))  # en trozos cortos: F10 y la pausa siguen respondiendo
                if control.detenido:
                    raise Detenido()
                if control.en_pausa:
                    self.log("En pausa: dejo pasar esta invitación.", "aviso")
                    return None
            # (otro bot siempre entraba; el nuestro, pulsando justo a los 9.3 s con el
            # raton ya encima, perdia ~la mitad): volver a capturar, buscar Accept y clic rapido. Asi el
            # toque llega hacia los 9.5 s de verla.
            p, o = self.capturar()
            rect = ACEPTAR.buscar(p, 0.7)
            if rect is None:
                self.perdidas += 1
                self.log("La invitación desapareció antes de aceptarla.", "aviso")
                self._stats()
                return None
            entrada.clic_rapido(rect, o)
            self.log(f"Aceptada a los {time.perf_counter() - visto:.2f} s de verla.")
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
            self._fuera_de_sala()
            return "preparar"
        return None

    def esperar_amigo(self, p, o):
        """Esperar la invitacion de un amigo donde se este (la Taberna) y aceptarla."""
        if AUTO.esta(p, 0.8):
            self.log("Ya estaba en una pelea: sigo con ella.", "aviso")
            return "pelea"
        if CARGANDO.esta(p, 0.8) or PREPARACION.esta(p, 0.8):
            self._fuera_de_sala()
            return "preparar"
        if self.clic_si(ACEPTAR_AMIGO, p, o, umbral=0.8, espera=2.0):
            p, _ = self.capturar()
            if ACEPTAR_AMIGO.esta(p, 0.8):
                self.log("La invitación sigue ahí: el toque no entró. Lo intento otra vez.", "aviso")
                return None
            self.log("¡Invitación de un amigo! Aceptada.", "ok")
            self.buscando_desde = time.time()
            self._fuera_de_sala()
            return "preparar"
        self.clic_si(juego.ok, p, o)  # avisos que taparian la invitacion
        minutos = float(self.valores["minutos_sin_invitacion"])
        if minutos and time.time() - self.buscando_desde > minutos * 60:
            self.log(f"{minutos:.0f} min sin invitaciones de amigos. Termino.", "aviso")
            raise TerminarModo()
        return None

    # ------------------------------------------------------------- enviar solicitud
    def abrir_sala(self, p, o):
        """Death Match -> Indura -> el nivel: la sala propia. Mientras la otra cuenta acaba su pelea el juego no la
        abre; se reintenta cada CADA_REINTENTO s."""
        if AUTO.esta(p, 0.8):
            return "pelea_corta"
        if self._en_sala_propia(p):
            self.log("Sala abierta. Invito a la otra cuenta.", "ok")
            self.invitado_en, self.sala_desde_envio = 0.0, time.time()
            return "sala_propia"
        if time.time() - getattr(self, "listo_en", 0.0) < 30.0:
            return None  # los dos listos: la pelea esta cargando, no tocar nada
        if self.clic_si(juego.ok, p, o, espera=1.0):  # "no puedes abrir otra pelea todavia" y otros avisos
            return None
        ahora = time.time()
        if NIVELES_INDURA.esta(p, 0.8):
            nivel = self.valores.get("nivel", "Chaos")
            if ahora - getattr(self, "reintento_en", 0.0) >= CADA_REINTENTO:
                self.reintento_en = ahora
                if not self.clic_si(NIVEL_SALA.get(nivel, NIVEL_SALA["Chaos"]), p, o, umbral=0.75, espera=2.0):
                    self.log(f"No veo el nivel {nivel} de Indura.", "aviso")
            return None
        if self.clic_si(DM_INDURA, p, o, umbral=0.75, espera=1.5):
            return None
        conocida = (self.clic_si(juego.menu_batalla, p, o, umbral=0.6, espera=1.0)
                    | self.clic_si(BOSS_BATTLE, p, o, umbral=0.75, espera=1.0))
        minutos = float(self.valores["minutos_sin_invitacion"])
        if minutos and ahora - self.buscando_desde > minutos * 60:
            self.log(f"{minutos:.0f} min sin poder abrir la sala de Indura. Termino.", "aviso")
            raise TerminarModo()
        if not conocida:
            self.clic_si(ATRAS, p, o, umbral=0.75, espera=1.0)  # un menu de mas: volver hacia la Taberna
        return None

    @staticmethod
    def _en_sala_propia(p) -> bool:
        return (SALA_INVITAR.esta(p, 0.8) or SALA_PREPARACION.esta(p, 0.8) or INVITAR_VENTANA.esta(p, 0.85)
                or AMIGO_LISTO.esta(p, 0.75))

    def sala_propia(self, p, o):
        """Invitar (Favoritos -> Invite All), esperar a que la otra cuenta este lista y empezar."""
        if AUTO.esta(p, 0.8):
            self._empezar_pelea_corta()
            return "pelea_corta"
        ahora = time.time()
        if INVITAR_VENTANA.esta(p, 0.85):
            if ahora - self.invitado_en >= CADA_INVITACION:
                entrada.clic(PESTANA_FAVORITOS, o, espera=1.0)
                p, o = self.capturar()
                if self.clic_si(INVITAR_TODOS, p, o, umbral=0.9, espera=1.0):
                    self.invitado_en = ahora
                    self.log("Invitación enviada a Favoritos.", "ok")
                else:
                    self.invitado_en = ahora  # no reintentar sin parar: se prueba otra vez en CADA_INVITACION
                    self.log("No puedo invitar (¿la cuenta principal no está en Favoritos o no está conectada?).",
                             "aviso")
            self.clic_si(INVITAR_VENTANA, p, o, umbral=0.85, espera=1.0)
            return None
        if AMIGO_LISTO.esta(p, 0.75):
            if ahora - getattr(self, "listo_en", 0.0) >= 15.0:  # una vez: pulsarlo otra vez lo quitaria
                self.log("La otra cuenta está lista. Empiezo.", "ok")
                if self.clic_si(SALA_PREPARACION, p, o, umbral=0.75, espera=2.0):
                    self.listo_en = ahora
            return None
        if not self._en_sala_propia(p):
            return "abrir_sala"  # se cerro la sala o esta cargando la pelea (abrir_sala sabe esperar)
        if ahora - self.invitado_en >= CADA_INVITACION:
            self.clic_si(SALA_INVITAR, p, o, umbral=0.8, espera=1.5)
        minutos = float(self.valores["minutos_sin_invitacion"])
        if minutos and ahora - self.sala_desde_envio > minutos * 60:
            self.log(f"{minutos:.0f} min sin que entre la otra cuenta. Termino.", "aviso")
            raise TerminarModo()
        return None

    def _empezar_pelea_corta(self):
        self.lanzadas, self.libres_vistas = 0, None
        self.libres_antes, self.tocado_en, self.ultima_tocada, self.rechazadas = -1, 0.0, None, []
        self.log("¡Empieza la pelea! Lanzo 3 cartas y me salgo.", "ok")

    def pelea_corta(self, p, o):
        """Lanzar 3 cartas (Inteligente, o la de mas rango; nunca AUTO) y rendirse."""
        if RENDIRSE_TEXTO.esta(p, 0.8):
            if self.clic_si(RENDIRSE_OK, p, o, umbral=0.8, espera=2.0):
                self.victorias += 1  # cada ayuda completada cuenta como una
                self.log(f"Me rendí tras lanzar las cartas. Ayudas: {self.victorias}.", "ok")
                self._stats()
                self.buscando_desde, self.reintento_en = time.time(), 0.0
                del self.lanzadas
                meta = int(self.valores["victorias"])
                if meta and self.victorias >= meta:
                    self.log(f"Llegué a {meta} ayudas.", "ok")
                    raise TerminarModo()
                return "abrir_sala"
            return None
        if not AUTO.esta(p, 0.8):
            if DM_INDURA.esta(p, 0.75) or NIVELES_INDURA.esta(p, 0.8):
                self.__dict__.pop("lanzadas", None)
                return "abrir_sala"  # la pelea ya acabo
            return None
        if not hasattr(self, "lanzadas"):
            self._empezar_pelea_corta()
        libres = cartas.casillas_libres_demonio(p)
        if self.libres_vistas is None:
            if libres > 0:
                self.libres_vistas = libres  # empieza nuestro turno
        elif libres > self.libres_vistas:
            self.libres_vistas = libres  # turno nuevo (no deberia pasar antes de las 3)
        elif libres < self.libres_vistas:
            self.lanzadas += self.libres_vistas - libres  # entraron en su casilla
            self.libres_vistas = libres
        if self.lanzadas >= CARTAS_ANTES_DE_SALIR:
            self.clic_si(RENDIRSE, p, o, umbral=0.8, espera=1.5)
            return None
        if libres <= 0:
            return None
        ahora = time.time()
        if libres == self.libres_antes and ahora - self.tocado_en < 2.0:
            return None  # la carta tocada aun esta entrando
        if libres == self.libres_antes and self.ultima_tocada is not None:
            self.rechazadas.append(self.ultima_tocada.imagen)  # no entro: se aparta
        mano = [c for c in cartas.leer_mano_demonio(p)
                if c.tipo != cartas.TipoCarta.BLOQUEADA and not any(
                    c.imagen is not None and r is not None and c.imagen.shape == r.shape
                    and float(cv2.absdiff(c.imagen, r).mean()) < 12 for r in self.rechazadas)]
        carta = None
        if self.valores.get("jugar") == "Inteligente" and mano:
            paso = self.jugador.elegir(mano, libres)
            carta = mano[paso[1]] if paso else None
        carta = carta or estrategias.la_de_mas_rango(mano)
        if carta is None:
            return None
        entrada.clic(carta.rect, o, espera=0.3)
        self.libres_antes, self.tocado_en, self.ultima_tocada = libres, ahora, carta
        self.log(f"   juego {carta.nombre} ({self.lanzadas + 1} de {CARTAS_ANTES_DE_SALIR})", "debug")
        return None

    def preparar(self, p, o):
        ahora = time.time()
        self.sala_desde = self.sala_desde or ahora
        # "The party leader has left. Cannot proceed with battle." [OK] (foto del usuario, 2026-11-16): tapa la sala
        # y no se va solo. Antes nadie lo pulsaba y el bot se quedo ahi 5 h.
        if self.clic_si(juego.ok, p, o, espera=1.5):
            if not self.avisado_lider:
                self.avisado_lider = True
                self.log("El líder del grupo se fue y la pelea no puede empezar. Acepto y vuelvo a buscar.", "aviso")
            return None
        if not AUTO.esta(p, 0.8) and not (juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75)):
            if ahora - self.sala_desde > ESPERA_SALA:
                return self._salir_de_sala(p, o, ahora)
        self.clic_si(PREPARACION, p, o, umbral=0.8, espera=1.0)
        if AUTO.esta(p, 0.8):
            self._fuera_de_sala()
            self.auto_puesto = False
            self.estrategia = None
            self.turnos_sin_equipo = 0
            self.libres_antes = -1
            self.log("¡Empieza la pelea!", "ok")
            self._abrir_diario()
            return "pelea"
        if juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75):
            if self.intentos_salida or self.avisado_lider:
                self.log("Fuera de la sala. Vuelvo a buscar partidas.", "ok")
            else:
                self.log("La partida se deshizo antes de empezar. Vuelvo a buscar.", "aviso")
            self._fuera_de_sala()
            return self._volver()
        return None

    def _fuera_de_sala(self):
        self.sala_desde, self.salida_en, self.intentos_salida = None, 0.0, 0
        self.avisado_lider = False

    def _salir_de_sala(self, p, o, ahora):
        """La sala no arranca (los demas se fueron tras una derrota): quitar el listo, volver atras y confirmar."""
        en_sala = PREPARACION.esta(p, 0.8) or CANCELAR_PREPARACION.esta(p, 0.8)
        if not en_sala and self.intentos_salida:
            self.log("Fuera de la sala. Vuelvo a buscar partidas.", "ok")
            self._fuera_de_sala()
            return self._volver()  # la navegacion normal sabe volver desde cualquier menu
        if ahora - self.salida_en < CADA_SALIDA:
            return None
        self.salida_en = ahora
        self.intentos_salida += 1
        if self.intentos_salida == 1:
            self.log(f"Llevo {(ahora - self.sala_desde) / 60:.0f} min en la sala y la pelea no empieza "
                     "(¿se fueron los demás?). Me salgo y vuelvo a buscar.", "aviso")
        self.clic_si(CANCELAR_PREPARACION, p, o, umbral=0.8, espera=1.0)
        if not self.clic_si(ATRAS, p, o, umbral=0.75, espera=1.5):
            entrada.clic(PUNTO_ATRAS, o, espera=1.5)
        if self.intentos_salida == INTENTOS_SALIDA:
            self.log("No consigo salir de la sala. Te mando una foto al móvil.", "error")
            avisos.enviar(f"LumenFarm ({self.nombre}): no consigo salir de la sala de preparación.", p)
        return None

    # ------------------------------------------------------------------ diario y aprendizaje
    def peleas_del_nivel(self) -> list[dict]:
        nivel = self.valores.get("nivel")
        return [p for p in diario.leer(self.id, 1000) if p.get("nivel") == nivel]

    def _abrir_diario(self):
        self.turno_diario = 0
        self.libres_observados = 0
        self.decision_pendiente = None
        self._cerrar_diario("abandonada")  # la anterior acabo sin verse el final
        jugar = self.valores.get("jugar")
        self.jugador.equipo = self.equipo_de_la_sesion() or ()
        extra = {"nivel": self.valores.get("nivel"), "jugar": jugar, "memoria_por_equipo": True,
                 "lecciones": f"{self.id}_{str(self.valores.get('nivel', '')).lower()}"}
        self.jugador.destino, self.jugador.fase = extra["lecciones"], 1  # lo aprendido en este demonio y nivel
        if jugar == "Inteligente":
            from lumen.ia import perfiles
            peleas = perfiles.filtrar(self.peleas_del_nivel(), extra["lecciones"], self.jugador.equipo)
            config, prueba = perfiles.elegir(peleas, extra["lecciones"], self.jugador.equipo, explorar=bool(self.valores.get("aprender", True)))
            self.jugador.params = config
            extra.update(config=config, prueba=prueba)
            if not self.aprendizaje_dicho:
                self.aprendizaje_dicho = True
                self.log(aprendizaje.texto(peleas).splitlines()[0] + ".")
            if prueba:
                self.log(f"Aprendiendo: esta pelea pruebo {aprendizaje.diferencia(config) or 'lo de siempre'}.")
        self.diario.empezar(**extra)

    def equipo_de_la_sesion(self) -> list[str] | None:
        if self.equipo_usado:
            return sorted(self.equipo_usado)
        vistos = sorted(((n, h) for h, n in self.heroes_vistos.items() if n >= VECES_HEROE), reverse=True)[:4]
        return sorted(h for _, h in vistos) if len(vistos) == 4 else None

    def _cerrar_diario(self, resultado: str):
        if self.diario.pelea is not None and not self.diario.pelea.get("equipo"):
            self.diario.pelea["equipo"] = self.equipo_de_la_sesion() or []
        self.diario.terminar(resultado)

    def _contar_heroes(self, mano):
        for c in mano:
            if c.nombre and "." in c.nombre:
                heroe = c.nombre.split(".")[0]
                self.heroes_vistos[heroe] = self.heroes_vistos.get(heroe, 0) + 1

    def _apuntar(self, mano, idx):
        self._contar_heroes(mano)
        if self.diario.pelea is not None:
            self.diario.confirmar(self.decision_pendiente, False)
            self.decision_pendiente = self.diario.decision(
                1, self.turno_diario or None, len(self.diario.pelea["turnos"]) + 1, mano, idx,
                getattr(self.jugador, "razones", None), confirmada=False)
            if self.decision_pendiente is not None:
                self.decision_pendiente["observacion"] = self.jugador.observacion

    # ------------------------------------------------------------------ pelea
    def _confirmar_accion(self, libres):
        if self.decision_pendiente is None:
            return
        if 0 <= libres < self.libres_antes:
            self.diario.confirmar(self.decision_pendiente, True)
            self.decision_pendiente = None
        elif libres > self.libres_antes or time.time() - self.tocado_en >= 2.0:
            self.diario.confirmar(self.decision_pendiente, False)
            self.decision_pendiente = None

    def _jugar_carta(self, p, o):
        """Si es nuestro turno, juega la carta que toca segun la estrategia del equipo."""
        libres = cartas.casillas_libres_demonio(p)
        self._confirmar_accion(libres)
        if libres > 0 and (self.libres_observados == 0 or libres > self.libres_observados):
            self.turno_diario += 1
        self.libres_observados = libres
        if libres == 0:
            return
        # Tras tocar una carta, esperar a que ocupe su casilla antes de elegir la siguiente.
        if libres == self.libres_antes and time.time() - self.tocado_en < 2.0:
            return
        if libres > self.libres_antes:  # turno nuevo: se olvidan las cartas rechazadas
            self.rechazadas = []
        elif libres == self.libres_antes and self.ultima_tocada is not None:
            # La carta no entro en su casilla (bloqueada aunque no se vea oscura): en una prueba el bot toco
            # la misma 7 veces seguidas, perdio el turno y la pelea. Se aparta el resto del turno.
            self.rechazadas.append(self.ultima_tocada.imagen)
            self.log(f"   {self.ultima_tocada.nombre} no entra: la aparto este turno.", "aviso")
        self.ultima_tocada = None
        mano = cartas.leer_mano_demonio(p)
        for c in mano:
            if c.imagen is not None and any(c.imagen.shape == r.shape and float(cv2.absdiff(c.imagen, r).mean()) < 12
                                            for r in self.rechazadas):
                c.tipo = cartas.TipoCarta.BLOQUEADA
        if self.valores.get("jugar") == "Inteligente":
            from lumen.ia import estado as estado_ia
            self.jugador.observacion = estado_ia.observar(p)
            self._jugar_inteligente(mano, libres, o)
            return
        if self.estrategia is None:
            self.estrategia = estrategias.reconocer(self.estrategias, mano)
            if self.estrategia is None:
                self.turnos_sin_equipo += 1
                if self.turnos_sin_equipo >= 3:  # equipo sin estrategia: que juegue el juego
                    self.log("No reconozco este equipo: lo dejo en AUTO.", "aviso")
                    self.auto_puesto = self.clic_si(AUTO, p, o, umbral=0.8)
                return
            self.log(f"Equipo reconocido: {self.estrategia.nombre}. Juego como tú.", "ok")
            self.equipo_usado = list(self.estrategia.equipo)
            if self.diario.pelea is not None:
                self.diario.pelea["estrategia"] = self.estrategia.nombre
        self.estrategia.etiquetar(mano)
        carta = self.estrategia.elegir(mano) or estrategias.la_de_mas_rango(mano)
        if carta is None:
            return
        self._apuntar(mano, next((i for i, c in enumerate(mano) if c is carta), carta.posicion))
        entrada.clic(carta.rect, o, espera=0.3)
        self.libres_antes, self.tocado_en, self.ultima_tocada = libres, time.time(), carta
        self.log(f"   juego {carta.nombre} ({carta.rango.name.lower()}, posición {carta.posicion + 1})", "debug")

    def _jugar_inteligente(self, mano, libres: int, o):
        """La carta que deja mejor el turno entero (lumen/inteligencia.py), sin arrastrar cartas: en los
        demonios aun no se ha comprobado que se pueda."""
        self.jugador.equipo = self.equipo_de_la_sesion() or ()
        paso = self.jugador.elegir(mano, libres)
        if paso is None:
            return
        carta = mano[paso[1]]
        self._apuntar(mano, paso[1])
        entrada.clic(carta.rect, o, espera=0.3)
        self.libres_antes, self.tocado_en, self.ultima_tocada = libres, time.time(), carta
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
            self.log(f"¡{self.nombre} destruido! Victoria #{self.victorias}.", "ok")
            self._cerrar_diario("victoria")
            self._stats()
            self._foto_pendiente, self._previa, self._ok_desde = True, None, None
        if getattr(self, "_foto_pendiente", False) and juego.ok.esta(p):
            # La foto del botin, en la pantalla de recompensas (la del OK) y quieta: antes se sacaba al ver
            # "destroyed" y no salian los objetos. Como mucho se esperan 6 s a que se quede quieta.
            self._ok_desde = self._ok_desde or time.time()
            estable = botin.quieta(self._previa, p)
            if not estable and time.time() - self._ok_desde < 6:
                self._previa = p
                return None
            self.guardar_recompensa(p, self.victorias, estable=estable)
            self._foto_pendiente = False
        if juego.ok.esta(p) or juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75):
            if not getattr(self, "_contada", False):
                self.derrotas += 1
                self.log(f"No pudimos con {self.nombre} esta vez.", "aviso")
                self._cerrar_diario("derrota")
                self._stats()
            self.clic_si(juego.ok, p, o, espera=1.0)
            self._contada = False
            meta = int(self.valores["victorias"])
            if meta and self.victorias >= meta:
                self.log(f"Llegué a {meta} victorias.", "ok")
                raise TerminarModo()
            if self.de_amigos:
                self.buscando_desde = time.time()  # el reloj de "sin invitaciones" empieza al acabar la pelea
            return self._volver()
        return None

    def al_terminar(self):
        self._cerrar_diario("abandonada")  # se paro el bot a media pelea
        self.log(f"{self.nombre}: {self.victorias} victorias, {self.derrotas} derrotas, "
                 f"{self.perdidas} invitaciones perdidas.", "ok")


def _opciones(nivel: str, niveles: list[str], jugar: str, solicitudes: bool = False) -> list[Opcion]:
    partidas = [Opcion("partidas", "Partidas", "lista", BUSCAR, opciones=[BUSCAR, AMIGOS, ENVIAR],
                       ayuda="Buscar partidas: se une a las de cualquiera. Aceptar solicitud: se queda en la Taberna y "
                             "acepta las invitaciones que te manden, y juega normal. Enviar solicitud: abre la sala, "
                             "invita a Favoritos (deja ahí solo tu cuenta principal), lanza 3 cartas y se sale.")]
    return (partidas if solicitudes else []) + [
        Opcion("nivel", "Nivel", "lista", nivel, opciones=niveles),
        Opcion("jugar", "Cómo pelear", "lista", jugar, opciones=["Inteligente", "Mis cartas", "AUTO"],
               ayuda="Inteligente: piensa las 6 cartas del turno y las fusiones, con cualquier equipo. "
                     "Mis cartas: tu lista de prioridades (si no reconoce el equipo, AUTO). AUTO: lo juega el juego."),
        Opcion("aprender", "Aprender solo", "si_no", True,
               ayuda="Solo con Inteligente: 1 de cada 10 peleas prueba una variante pequeña y se queda con lo que "
                     "gane más rápido, en cada nivel por separado. Apagado: juega siempre con lo ya aprendido."),
        Opcion("espera", "Segundos antes de aceptar", "texto", "9.3",
               ayuda="Aceptar justo a los 9.3 s entra a la partida sin gastar entradas de tiempo real."),
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=999),
        Opcion("minutos_sin_invitacion", "Parar tras minutos sin invitaciones", "entero", 20, maximo=600),
    ]


def _demonio(id_: str, nombre: str, imagen: str, *, pestana=None, punto_pestana=None, pestana_elegida_img=None,
             nivel: str = "Hell", niveles=("Hell", "Extreme", "Hard", "Normal"), jugar: str = "AUTO",
             descripcion: str = "", solicitudes: bool = False) -> type:
    return type(f"Demonio_{id_}", (DemonioTiempoReal,), {
        "id": id_, "nombre": nombre, "titulo_juego": nombre, "imagen": imagen,
        "descripcion": descripcion or (f"Se une a las partidas de {nombre} que abren otros jugadores y pelea en AUTO "
                                       "Empieza desde la Taberna o el menú Battle."),
        "pestana": pestana, "punto_pestana": punto_pestana, "pestana_elegida_img": pestana_elegida_img,
        "opciones": _opciones(nivel, list(niveles), jugar, solicitudes),
    })


# Los 5 demonios de siempre: pelean en AUTO y en Hell, su nivel por defecto.
# Los ids son los del catalogo de Inicio (lumen/modos/catalogo.py) y los de las tablas de premios.
DemonioRojo = _demonio("demonio_rojo", "Red Demon", "demons/red_demon.png", pestana=P("demons/red_demon.png"))
DemonioGris = _demonio("demonio_gris", "Gray Demon", "demons/gray_demon.png", pestana=P("demons/gray_demon.png"))
Howlex = _demonio("howlex", "Howlex", "demons/crimson_demon.png", pestana=P("demons/crimson_demon.png"))
Bellmoth = _demonio("bellmoth", "Bellmoth", "demons/bell_demon.png", pestana=P("demons/bell_demon.png"))
DemonioOriginal = _demonio("demonio_original", "Original Demon", "demons/og_demon.png",
                           pestana=P("demons/og_demon.png"), niveles=("Hell", "Chaos", "Extreme", "Hard", "Normal"))
# Indura: la 6.a pestana (por su posicion; se comprueba con una captura propia), Chaos y pensando cada turno.
Indura = _demonio("indura", "Indura", "demons/indura_lumen.png", punto_pestana=PESTANA_INDURA,
                  pestana_elegida_img=INDURA, nivel="Chaos", niveles=("Chaos", "Hell", "Extreme"), jugar="Inteligente",
                  solicitudes=True,
                  descripcion="Se une a las partidas de Indura que abren otros jugadores y pelea pensando cada turno. "
                              "Empieza desde la Taberna o el menú Battle.")

TODOS = [DemonioRojo, DemonioGris, Howlex, Bellmoth, DemonioOriginal, Indura]
