"""Demonios en tiempo real (Boss Battle): se une a las partidas que otros jugadores abren. Un molde para
los 6 (Red, Gray, Howlex, Bellmoth, Original e Indura), como el de los pisos 1-3 de las bestias.

Flujo (el de demonios de AutoFarming, MIT; Indura no esta en esa parte publica, asi que su icono es
una captura propia):
1. Taberna -> Battle -> Boss Battle -> Real-time: se abre "Real-time Join Request".
2. Pestana del demonio, el nivel elegido y OK: el juego busca partida. Indura (la 6.a pestana) se toca
   por su posicion y se comprueba que quede elegida; los otros 5, por su icono (el de AutoFarming).
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

Indura tiene limite diario de peleas (el juego lo dice en la ventana de union): cuando ya no hay
partidas, el bot se queda esperando invitaciones que no llegan; se para con un tiempo maximo de espera.
"""

import time

import cv2

from lumen import avisos, botin, cartas, entrada, estrategias, inteligencia, juego
from lumen.control import Detenido, control
from lumen.motor import Modo, Opcion, TerminarModo
from lumen.vision import Plantilla

P = Plantilla
BOSS_BATTLE = P("demons/demons.jpg")  # menu Boss Battle (AutoFarming, MIT)
TIEMPO_REAL = P("demons/RT.png")
VENTANA_UNION = P("demons/union_tiempo_real.png")  # titulo "Real-time Join Request" (captura propia)
INDURA = P("demons/indura_lumen.png")  # pestana de Indura seleccionada (captura propia)
NIVELES = {"Normal": P("demons/normal.png"), "Hard": P("demons/hard.png"), "Extreme": P("demons/extreme.png"),
           "Hell": P("demons/hell.png"), "Chaos": P("demons/chaos.png")}
ACEPTAR = P("demons/accept.png")
CANCELAR_BUSQUEDA = P("demons/cancel.png")
CARGANDO = P("demons/demons_loading_screen.png")
PREPARACION = P("demons/preparation_incomplete.png")
AUTO = P("demons/auto.jpg")
DESTRUIDO = P("demons/demons_destroyed.png")

PESTANA_INDURA = (490, 258)  # la ultima pestana de la ventana de union (medido)
OK_UNION = (277, 869)


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
        self.turnos_sin_equipo = 0
        self.libres_antes = -1  # casillas libres cuando se toco la ultima carta
        self.ultima_tocada = None  # la ultima carta tocada (por si no entra en su casilla)
        self.rechazadas: list = []  # dibujos de cartas que no entraron este turno
        self.desconocida_desde: float | None = None  # pantalla sin nada conocido desde...
        self.avisado_desconocida = False
        self.tocado_en = 0.0
        self.pestana_elegida = False

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
        if not self.clic_si(NIVELES[nivel], p, o, umbral=0.8, espera=0.8):
            self.log(f"No veo el nivel {nivel} de {self.nombre}.", "aviso")
            return None
        self.clic_si(VENTANA_UNION, p, o, punto=OK_UNION, espera=1.5)  # OK: empieza a buscar
        self.log(f"Buscando partidas de {self.nombre} ({nivel}).", "ok")
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
            self.log(f"¡Invitación! La acepto a los {espera:.1f} s.")
            while (falta := espera - (time.perf_counter() - visto)) > 0:
                time.sleep(min(falta, 0.05))  # en trozos cortos: F10 y la pausa siguen respondiendo
                if control.detenido:
                    raise Detenido()
                if control.en_pausa:
                    self.log("En pausa: dejo pasar esta invitación.", "aviso")
                    return None
            # Igual que AutoFarming (su bot siempre entraba; el nuestro, pulsando justo a los 9.3 s con el
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
            self.log(f"{minutos:.0f} min sin invitaciones (¿se acabó el límite diario?). Termino.", "aviso")
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
        self.estrategia.etiquetar(mano)
        carta = self.estrategia.elegir(mano) or estrategias.la_de_mas_rango(mano)
        if carta is None:
            return
        entrada.clic(carta.rect, o, espera=0.3)
        self.libres_antes, self.tocado_en, self.ultima_tocada = libres, time.time(), carta
        self.log(f"   juego {carta.nombre} ({carta.rango.name.lower()}, posición {carta.posicion + 1})", "debug")

    def _jugar_inteligente(self, mano, libres: int, o):
        """La carta que deja mejor el turno entero (lumen/inteligencia.py), sin arrastrar cartas: en los
        demonios aun no se ha comprobado que se pueda."""
        paso = self.jugador.elegir(mano, libres)
        if paso is None:
            return
        carta = mano[paso[1]]
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
            self._stats()
            self._foto_pendiente, self._previa, self._ok_desde = True, None, None
        if getattr(self, "_foto_pendiente", False) and juego.ok.esta(p):
            # La foto del botin, en la pantalla de recompensas (la del OK) y quieta: antes se sacaba al ver
            # "destroyed" y no salian los objetos. Como mucho se esperan 6 s a que se quede quieta.
            self._ok_desde = self._ok_desde or time.time()
            if not botin.quieta(self._previa, p) and time.time() - self._ok_desde < 6:
                self._previa = p
                return None
            self.guardar_recompensa(p, self.victorias)
            self._foto_pendiente = False
        if juego.ok.esta(p) or juego.menu_batalla.esta(p, 0.6) or TIEMPO_REAL.esta(p, 0.75):
            if not getattr(self, "_contada", False):
                self.derrotas += 1
                self.log(f"No pudimos con {self.nombre} esta vez.", "aviso")
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
        self.log(f"{self.nombre}: {self.victorias} victorias, {self.derrotas} derrotas, "
                 f"{self.perdidas} invitaciones perdidas.", "ok")


def _opciones(nivel: str, niveles: list[str], jugar: str) -> list[Opcion]:
    return [
        Opcion("nivel", "Nivel", "lista", nivel, opciones=niveles),
        Opcion("jugar", "Cómo pelear", "lista", jugar, opciones=["Inteligente", "Mis cartas", "AUTO"],
               ayuda="Inteligente: piensa las 6 cartas del turno y las fusiones, con cualquier equipo. "
                     "Mis cartas: tu lista de prioridades (si no reconoce el equipo, AUTO). AUTO: lo juega el juego."),
        Opcion("espera", "Segundos antes de aceptar", "texto", "9.3",
               ayuda="Aceptar justo a los 9.3 s entra a la partida sin gastar entradas de tiempo real."),
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=999),
        Opcion("minutos_sin_invitacion", "Parar tras minutos sin invitaciones", "entero", 20, maximo=600),
    ]


def _demonio(id_: str, nombre: str, imagen: str, *, pestana=None, punto_pestana=None, pestana_elegida_img=None,
             nivel: str = "Hell", niveles=("Hell", "Extreme", "Hard", "Normal"), jugar: str = "AUTO",
             descripcion: str = "") -> type:
    return type(f"Demonio_{id_}", (DemonioTiempoReal,), {
        "id": id_, "nombre": nombre, "titulo_juego": nombre, "imagen": imagen,
        "descripcion": descripcion or (f"Se une a las partidas de {nombre} que abren otros jugadores y pelea en AUTO "
                                       "(como AutoFarming). Empieza desde la Taberna o el menú Battle."),
        "pestana": pestana, "punto_pestana": punto_pestana, "pestana_elegida_img": pestana_elegida_img,
        "opciones": _opciones(nivel, list(niveles), jugar),
    })


# Los 5 demonios de AutoFarming: pelean en AUTO (asi los farmea su bot) y en Hell, su nivel por defecto.
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
                  descripcion="Se une a las partidas de Indura que abren otros jugadores y pelea pensando cada turno. "
                              "Empieza desde la Taberna o el menú Battle.")

TODOS = [DemonioRojo, DemonioGris, Howlex, Bellmoth, DemonioOriginal, Indura]
