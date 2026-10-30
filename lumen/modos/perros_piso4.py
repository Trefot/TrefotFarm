"""Perros piso 4 con Odin, Gawain, Freyja roja y Thonar azul.

Guion (si algo se sale de el, se rinde y reinicia, que es lo mas rapido con este equipo):
  Siempre se selecciona el perro que NO esta en la burbuja (la burbuja es su postura y no se puede
  seleccionar): el DERECHO en la fase 1 y el lobo azul IZQUIERDO en la fase 2. Las cartas que quitan
  postura se la quitan al de la burbuja igualmente.
  Fase 1 T1: postura de Thonar | otra de Thonar | 2 normales de Freyja.
  Fase 1 T2: talento de Odin | Freyja (si su ulti aun no esta) o Thonar (si ya esta; primero la otra,
             la postura se guarda para la fase 2) | single de Gawain | relleno (nunca Odin) |
             single de Odin, SIEMPRE como cuarta y ultima carta.
  Fase 2 T1: quitar la postura (postura de Thonar, single de Odin o area de Gawain) | area de Gawain
             o de Odin | ulti de Freyja | area de Odin o cualquier carta de G/F/O.
  Fase 3 T1: no se lanza ninguna carta: solo se mueven cartas (el golpe
             secundario de la ulti de Freyja termina la pelea).

Empieza desde cualquier pantalla de la taberna / menu de batalla / bestias demoniacas.
"""

import time
from collections import defaultdict
from collections.abc import Sequence

from lumen import cartas as C
from lumen import botin, entrada, juego
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.control import control
from lumen.ia.diario import Diario
from lumen.equipo import Equipo, Puesto
from lumen.motor import Modo, Opcion, TerminarModo
from lumen.rutas import LOGS
from lumen.vision import guardar_imagen

# ---------------------------------------------------------------------- el equipo
EQUIPO = Equipo(
    "perros_odin",
    "Odin, Gawain, Freyja roja, Thonar azul",
    # En el orden de la pantalla del equipo (izquierda a derecha)
    [
        Puesto("Daño a un objetivo (F1) y en área (F2), con su Talent", ("dano_single", "dano_area"), "odin"),
        Puesto("Daño a un objetivo (F1) y en área (F2)", ("dano_single", "dano_area"), "gawain"),
        Puesto("Ulti en F2 cuyo golpe extra remata la F3", ("ulti_remate",), "freyja_roja"),
        Puesto("Quitar la postura del perro izquierdo (F1)", ("quita_postura",), "thonar_azul"),
    ],
    obligatorias={
        "odin.single", "odin.area", "gawain.single", "gawain.area",
        "freyja_roja.normal_1", "freyja_roja.normal_2", "freyja_roja.ulti",
        "thonar_azul.postura", "thonar_azul.otra",
    },
)

FREYJA_NORMALES = ("freyja_roja.normal_1", "freyja_roja.normal_2")
THONAR_POSTURA = ("thonar_azul.postura",)
THONAR_OTRA = ("thonar_azul.otra",)
PROTEGIDAS_FASE2 = ("gawain.area", "odin.area", "freyja_roja.ulti", "thonar_azul.postura")
TURNOS_MAXIMOS = {1: 2, 2: 1, 3: 1}
PAUSA_ENTRE_CARTAS = 0.5  # tras colocarse una carta, antes de la siguiente (animacion)


class Reiniciar(Exception):
    """La estrategia pide rendirse y repetir la pelea."""


# ----------------------------------------------------------------- estrategia pura
class Estrategia:
    """Decide UNA carta por llamada. No toca la pantalla: pide objetivo/talento al bot.

    ``decidir`` devuelve (indice_en_mano, objetivo, usar_talento). objetivo es "izq", "der" o None.
    """

    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4) -> tuple[int, str | None, bool]:
        limite = TURNOS_MAXIMOS.get(fase)
        if limite is not None and turno > limite:
            raise Reiniciar(f"la fase {fase} va por el turno {turno} y debia acabar en {limite}")
        if fase == 1 and turno <= 1:
            return self._f1t1(mano, accion)
        if fase == 1:
            return self._f1t2(mano, accion, max(total, 4))
        if fase == 2:
            return self._f2(mano, accion)
        return self._f3(mano), None, False

    def _f1t1(self, mano, accion):
        if accion == 0:
            return self._o_reiniciar(mano, ("thonar_azul.postura",), "F1T1: falta la postura de Thonar"), "der", False
        if accion == 1:
            return self._o_reiniciar(mano, ("thonar_azul.otra",), "F1T1: falta la otra carta de Thonar"), "der", False
        return self._o_reiniciar(mano, FREYJA_NORMALES, "F1T1: faltan cartas normales de Freyja"), None, False

    def _f1t2(self, mano, accion, total=4):
        if accion == 0:
            if self.mejor(mano, ("freyja_roja.ulti",)) is not None:
                orden = (THONAR_OTRA, FREYJA_NORMALES, THONAR_POSTURA)  # la ulti se guarda para la fase 2
            else:
                orden = (FREYJA_NORMALES, THONAR_OTRA, THONAR_POSTURA)  # cargar la ulti
            idx = self.primera(mano, orden)
            if idx is None:
                raise Reiniciar("F1T2: no hay cartas de Freyja ni de Thonar")
            return idx, "der", True
        if accion >= total - 1:
            # La single de Odin va SIEMPRE como ultima carta del turno (cuarta).
            return self._o_reiniciar(mano, ("odin.single",), "F1T2: falta la single de Odin"), None, False
        if accion == 1:
            return self._o_reiniciar(mano, ("gawain.single",), "F1T2: falta la single de Gawain"), None, False
        # Relleno: nunca una carta de Odin (su single va al final) ni lo que se necesita en la fase 2.
        idx = self.primera(mano, (THONAR_OTRA, FREYJA_NORMALES, ("gawain.single",), THONAR_POSTURA))
        if idx is not None:
            return idx, None, False
        for carta in reversed(mano):
            if carta.jugable and carta.nombre not in PROTEGIDAS_FASE2 and not (carta.nombre or "").startswith("odin."):
                return carta.posicion, None, False
        raise Reiniciar("F1T2: solo quedan cartas de Odin o que se necesitan en la fase 2")

    def _f2(self, mano, accion):
        if accion == 0:
            # Primero quitar la postura (la burbuja roja del perro derecho), apuntando al lobo azul.
            idx = self.primera(mano, (THONAR_POSTURA, ("odin.single",), ("gawain.area",)))
            if idx is None:
                raise Reiniciar("F2: no hay carta para quitar la postura (Thonar, single de Odin o area de Gawain)")
            return idx, "izq", False
        if accion == 1:
            idx = self.primera(mano, (("gawain.area",), ("odin.area",)))
            if idx is None:
                raise Reiniciar("F2: no queda area de Gawain ni de Odin")
            return idx, None, False
        if accion == 2:
            return self._o_reiniciar(mano, ("freyja_roja.ulti",), "F2: falta la ulti de Freyja"), None, False
        idx = self.primera(mano, (("odin.area",), ("gawain.area",)))
        if idx is not None:
            return idx, None, False
        g = EQUIPO.grupos
        idx = self.mejor(mano, g["gawain"] + g["freyja_roja"] + g["odin"])
        return (idx if idx is not None else self.derecha_jugable(mano)), None, False

    def _f3(self, mano):
        """No se pone ninguna carta (ni siquiera las que parecen bloqueadas): el golpe extra de la ulti
        de Freyja termina la pelea. Los huecos se gastan MOVIENDO cartas: arrastrar una carta sobre
        la de su izquierda gasta un hueco sin atacar. Devuelve (origen, destino).

        (En la segunda pelea real se puso una "bloqueada" que en realidad era la ulti de Thonar,
        que tiene el dibujo gris, y ataco. Por eso aqui ya no se pone nada.)
        """
        for izq, der in zip(mano, mano[1:]):
            if izq.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA) and der.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA):
                return (der.posicion, izq.posicion)
        raise Reiniciar("F3: no hay cartas que mover")

    # ------------------------------------------------------------------ ayudantes
    def primera(self, mano: list[Carta], grupos) -> int | None:
        """La mejor carta del primer grupo (en orden de preferencia) que tenga alguna en la mano."""
        for grupo in grupos:
            idx = self.mejor(mano, grupo)
            if idx is not None:
                return idx
        return None

    @staticmethod
    def mejor(mano: list[Carta], nombres: Sequence[str]) -> int | None:
        """La carta de mayor rango con alguno de esos nombres (la mas a la derecha si empatan)."""
        candidatas = [c for c in mano if c.jugable and c.nombre in nombres]
        if not candidatas:
            return None
        return max(candidatas, key=lambda c: (c.rango.value if c.rango != Rango.NINGUNO else -1, c.posicion)).posicion

    def _o_reiniciar(self, mano, nombres, motivo) -> int:
        idx = self.mejor(mano, nombres)
        if idx is None:
            raise Reiniciar(motivo)
        return idx

    @staticmethod
    def derecha_jugable(mano: list[Carta]) -> int:
        for carta in reversed(mano):
            if carta.jugable:
                return carta.posicion
        return len(mano) - 1

    @staticmethod
    def fusiones_al_jugar(mano: list[Carta], idx: int) -> int:
        """Cuantas fusiones automaticas provoca jugar esta carta (para esperar la animacion)."""
        resto = [[c.nombre, c.rango] for c in mano if c.posicion != idx and c.tipo not in (TipoCarta.NINGUNA, TipoCarta.SUELO)]
        fusiones, i = 0, 0
        while i < len(resto) - 1:
            (na, ra), (nb, rb) = resto[i], resto[i + 1]
            if na is not None and na == nb and ra == rb and ra in (Rango.BRONCE, Rango.PLATA):
                resto[i] = [na, Rango.PLATA if ra == Rango.BRONCE else Rango.ORO]
                del resto[i + 1]
                fusiones += 1
                i = max(0, i - 1)
                continue
            i += 1
        return fusiones


# ----------------------------------------------------------------------- el modo
def _misma_imagen(a, b) -> bool:
    """La misma carta de la mano (para recordar una que el juego no acepto)."""
    import cv2

    return a.shape == b.shape and float(cv2.absdiff(a, b).mean()) < 12


VECES_HEROE = 5  # cartas de un heroe vistas en la sesion para contarlo en el equipo


class PerrosPiso4(Modo):
    id = "perros_piso4"
    nombre = "Skollandhati & Hati · Floor 4"
    descripcion = (
        "Demonic Beast de los perros, Floor 4, con Odin, Gawain, Freyja (Strength) y Thonar (Speed). "
        "Puede empezar desde la Tavern, el menú Battle o la pantalla de Floors."
    )
    titulo_juego = "Skollandhati & Hati"
    subtitulo_juego = "Demonic Beast · Floor 4"
    imagen = "demonic_beasts/skollandhati.png"
    duracion = "~2,5 min por pelea"
    fases = 3
    nombres_estados = {
        "ir_a_perros": "Entrando a Demonic Beasts",
        "elegir_piso": "Eligiendo el Floor 4",
        "preparar": "Revisando el equipo",
        "pelea": "Peleando",
        "victoria": "¡Victoria! Guardando el botín",
        "derrota": "Derrota: volviendo a intentar",
        "rendirse": "Rindiéndose para repetir la pelea",
    }
    equipo = EQUIPO
    opciones = [
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 0, maximo=9999),
        Opcion("extra", "Marcar 'Extra' al abrir el piso (primeras N)", "entero", 0, maximo=99),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]
    pausa_entre_pasos = 0.45
    rendirse_si_bloqueada = True  # mano bloqueada al empezar un turno: rendirse y repetir
    talento_turno_1 = False  # activar el talento del equipo al empezar la pelea (las bestias Floor 1-3, opcion)

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.estrategia = Estrategia()
        self.victorias = self.derrotas = self.reinicios = self.pociones = self.extras = 0
        self.heroes_vistos: dict[str, int] = {}  # heroe -> cartas suyas vistas (para saber el equipo)
        self.derrotas_por_fase = defaultdict(int)
        self.equipo_verificado = False
        self.diario = Diario(self.id)  # cada decision y como acabo la pelea (IA.md, pieza 5)
        self._nueva_pelea()

    def estado_inicial(self):
        return "ir_a_perros"

    def estados(self):
        return {
            "ir_a_perros": self.ir_a_perros,
            "elegir_piso": self.elegir_piso,
            "preparar": self.preparar,
            "pelea": self.pelea,
            "victoria": self.victoria,
            "derrota": self.derrota,
            "rendirse": self.rendirse,
        }

    def en_zona_segura(self) -> bool:
        return self.estado in ("ir_a_perros", "elegir_piso", "preparar")

    def _nueva_pelea(self):
        self.fase: int | None = None
        self.turno_fase = 0
        self.turno_abierto = False
        self.huecos_turno = 0
        self.lecturas_turno = 0
        self.reinicio_pedido = False
        self.objetivo_actual: str | None = None
        self.talento_usado = False
        self.talento_inicial_usado = False
        self.inicio_pelea = time.time()
        self.ultimo_turno = time.time()  # para guardar una captura si no llega ningun turno
        self.foto_sin_turno_hecha = False
        self.foto_recompensa = False
        self.destruida_desde: float | None = None  # cuando se vio "Creature Destroyed" (fin de la pelea)
        self.ultimo_boton_texto = 0.0
        self.ultima_pantalla_victoria = None
        self.previa_recompensa = None  # captura anterior de la pantalla de recompensas (para verla quieta)
        self.ok_visto_desde: float | None = None

    def _stats(self):
        total = self.victorias + self.derrotas + self.reinicios
        self.publicar_stats(
            victorias=self.victorias,
            derrotas=self.derrotas,
            reinicios=self.reinicios,
            pociones=self.pociones,
            tasa=(100 * self.victorias / total) if total else 0.0,
            fase=self.fase or 0,
        )

    # ------------------------------------------------------------- navegacion
    def ir_a_perros(self, p, o):
        if self.clic_si(juego.cancelar, p, o):
            self.log("Habia una pelea a medias; la doy por perdida y empiezo de nuevo.", "aviso")
            return None
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6)
        self.clic_si(juego.nido_criaturas, p, o)
        if juego.pantalla_bestias.esta(p) and not juego.perros.esta(p):
            self._deslizar_hacia_perros(p, o)
            return None
        self.clic_si(juego.perros, p, o)
        if juego.piso3_superado.esta(p):
            self.log("En la pantalla de pisos de los Perros.", "ok")
            return "elegir_piso"
        return None

    def _deslizar_hacia_perros(self, p, o):
        actual = next((i for i, b in enumerate(juego.ORDEN_BESTIAS) if b.esta(p)), None)
        objetivo = juego.ORDEN_BESTIAS.index(juego.perros)
        hacia_derecha = actual is None or actual < objetivo
        desde, hasta = juego.COORD["deslizar_der"], juego.COORD["deslizar_izq"]
        if not hacia_derecha:
            desde, hasta = hasta, desde
        entrada.arrastrar(desde, hasta, o)

    def elegir_piso(self, p, o):
        if juego.ok.esta(p):  # hay que abrir el piso 4
            if self.extras < int(self.valores["extra"]) and self.clic_si(juego.extra, p, o, espera=1.0):
                self.extras += 1
                self.log(f"Usado 'extra' {self.extras}/{self.valores['extra']}.")
            self.clic_si(juego.ok, p, o)
            return None
        self.clic_si(juego.piso3_superado, p, o)
        if juego.empezar.esta(p):
            return "preparar"
        return None

    def preparar(self, p, o):
        if juego.pocion_stamina.esta(p):
            limite = int(self.valores["max_pociones"])
            if not self.valores["pociones"] or (limite and self.pociones >= limite):
                self.log("Sin estamina y no puedo usar mas pociones. Termino.", "aviso")
                self.publicar_stats(motivo_fin="sin_estamina")  # el plan del dia salta las tareas con estamina
                raise TerminarModo()
            if self.clic_si(juego.usar_pocion, p, o, umbral=0.8):
                self.pociones += 1
                self._stats()
                return None
        if not self.equipo_verificado and juego.empezar.esta(p):
            self._verificar_equipo(p)  # puede terminar el modo si el equipo no es el del guion
        self.clic_si(juego.empezar, p, o)
        if juego.carga_bestias.esta(p) or juego.carga_taberna.esta(p):
            self._nueva_pelea()
            self.diario.terminar("abandonada")  # la anterior acabo sin verse el final
            config, prueba = self._configuracion()
            self.diario.empezar(equipo=getattr(self.equipo, "orden", None), estrategia=self.stats.get("estrategia", ""),
                                **({"config": config, "prueba": prueba} if config else {}))
            self.log("¡A pelear!", "ok")
            return "pelea"
        return None

    def _configuracion(self) -> tuple[dict | None, bool]:
        """Con que parametros juega el juego inteligente esta pelea (IA.md, pieza 6). Solo si lo usa."""
        jugador = getattr(self.estrategia, "jugador", None)
        if jugador is None:
            return None, False
        from lumen.ia import aprendizaje, diario

        config, prueba = aprendizaje.elegir(diario.leer(self.id, 1000), explorar=bool(self.valores.get("aprender", True)))
        jugador.params = config
        if prueba:
            self.log(f"Aprendiendo: esta pelea pruebo {aprendizaje.diferencia(config) or 'lo de siempre'}.")
        return config, prueba

    def _verificar_equipo(self, p):
        """Una vez por sesion, antes del primer Start: el equipo en pantalla debe ser el del guion."""
        self.equipo_verificado = True
        errores, sin_retrato = EQUIPO.verificar_en_pantalla(p)
        if errores:
            self.log("El equipo no es el del guion: " + "; ".join(errores) + ".", "error")
            self.log("Pon a Odin, Gawain, Freyja roja y Thonar azul (izquierda a derecha) y vuelve a iniciar.", "error")
            raise TerminarModo()
        if sin_retrato:
            self.log(
                "No puedo comprobar el equipo: faltan los retratos de " + ", ".join(sin_retrato)
                + " (pagina Personajes -> Retratos del equipo).", "aviso")
        else:
            self.log("Equipo comprobado: Odin, Gawain, Freyja roja y Thonar azul.", "ok")

    # ------------------------------------------------------------------ pelea
    def pelea(self, p, o):
        self.clic_si(juego.saltar, p, o)
        self.clic_si(juego.mision_semanal, p, o, punto=juego.COORD["mision_semanal"])
        self.clic_si(juego.info_mision, p, o)
        if self.clic_si(juego.criatura_destruida, p, o):
            self.destruida_desde = self.destruida_desde or time.time()
        if juego.derrota.esta(p) or juego.cerrar.esta(p):
            return "derrota"
        if juego.victoria.esta(p):
            return "victoria"
        # Tras destruir la bestia puede salir una pantalla sin imagen guardada (las recompensas aseguradas de la
        # semana): en la prueba de la 0.2.2 el bot se quedo ahi 2 minutos. A los 5 s se lee y se toca su boton.
        if self.destruida_desde and time.time() - self.destruida_desde > 5 and time.time() - self.ultimo_boton_texto > 2:
            self.ultimo_boton_texto = time.time()
            self.clic_boton_por_texto(p, o)
        if juego.piso3_superado.esta(p):
            self.log("Volvi a la pantalla de pisos sin ver el final de la pelea.", "aviso")
            return "elegir_piso"
        if time.time() - self.inicio_pelea > 8 * 60:
            self.log("La pelea dura demasiado; me rindo.", "aviso")
            return "rendirse"

        talento = self._talento_visible(p)
        # 0.75 y no 0.8: el boton del talento tapa un poco la 2.a casilla y con Nidhoggr (fase 2) el ultimo hueco
        # libre daba 0.79; el bot no veia su turno y se quedaba quieto (captura de la prueba de la 0.7.5).
        huecos = C.contar_huecos(p, 0.75)
        if self.turno_abierto:
            return self._jugar_turno() if huecos > 0 else None
        # El boton del talento de Odin solo vale si tambien hay huecos: con Nidhoggr (prueba de la 0.4.0) se veia
        # sin huecos y el bot "empezaba" un turno por segundo sin jugar nada durante toda la fase 2.
        talento = talento and huecos > 0
        if talento or huecos >= 1:
            self.lecturas_turno += 1
            # Lecturas seguidas antes de empezar (evita arrancar en una animacion): 2 con 3 o mas huecos y 3 con
            # menos. Antes hacian falta 3 huecos: con Nidhoggr (fase 2) y Ratatoskr, que dejan menos, el bot jugaba
            # el primer turno y se quedaba quieto hasta rendirse (prueba de la 0.7.4).
            if talento or self.lecturas_turno >= (2 if huecos >= 3 else 3):
                self.lecturas_turno = 0
                return self._empezar_turno(p, max(huecos, 4) if talento else huecos)
        else:
            self.lecturas_turno = 0
        self._foto_sin_turno(p)
        return None

    def _foto_sin_turno(self, p):
        """Si pasa 1 min sin ningun turno, guarda una captura (una por pelea) para ver que hay en pantalla."""
        if self.foto_sin_turno_hecha or time.time() - self.ultimo_turno < 60:
            return
        self.foto_sin_turno_hecha = True
        ruta = LOGS / "sin_turno" / f"{self.id}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        try:
            guardar_imagen(ruta, p)
            self.log(f"1 min sin ver mi turno: guardo una captura en logs/sin_turno ({ruta.name}).", "aviso")
        except Exception:
            pass

    def _detectar_fase(self, p, huecos: int) -> int | None:
        if juego.fase_3_perros.esta(p, 0.8):
            return 3
        if juego.fase_2.esta(p, 0.8):
            return 2
        if juego.fase_1.esta(p, 0.8) and huecos > 1:
            return 1
        return None

    def _anotar_heroes(self, mano):
        """Cuenta de que heroe es cada carta reconocida ("thor_the_god_of_thunder_azul.skill_1@4" -> el heroe):
        con eso se sabe con que equipo se jugo aunque el modo valga para cualquiera (bestias Floor 1-3)."""
        for c in mano:
            if c.nombre and "." in c.nombre:
                heroe = c.nombre.split(".")[0]
                self.heroes_vistos[heroe] = self.heroes_vistos.get(heroe, 0) + 1

    def equipo_de_la_sesion(self) -> list[str] | None:
        fijo = super().equipo_de_la_sesion()
        if fijo:
            return fijo
        # Los 4 heroes cuyas cartas mas se vieron (al menos VECES_HEROE veces: no una carta mal reconocida)
        vistos = sorted(((n, h) for h, n in self.heroes_vistos.items() if n >= VECES_HEROE), reverse=True)[:4]
        return sorted(h for _, h in vistos) if len(vistos) == 4 else None

    def _empezar_turno(self, p, huecos: int):
        self.ultimo_turno = time.time()
        detectada = self._detectar_fase(p, huecos)
        if self.fase is None:
            self.fase = detectada or 1
        elif detectada and detectada > self.fase:  # solo hacia delante
            self.fase = detectada
            self.turno_fase = 0
            self.objetivo_actual = None
            self.log(f"Fase {self.fase}.", "ok")
        self.turno_fase += 1
        self.turno_abierto = True
        self.huecos_turno = huecos
        self.talento_usado = False
        self._stats()
        self.log(f"Fase {self.fase}, turno {self.turno_fase}: {huecos} cartas por jugar.")
        if self.rendirse_si_bloqueada and self.fase != 3 and juego.mano_bloqueada.esta(p, 0.6):
            self.log("Mano bloqueada desde el inicio: reinicio.", "aviso")
            return "rendirse"
        if self.talento_turno_1 and self.fase == 1 and self.turno_fase == 1 and not self.talento_inicial_usado:
            self.talento_inicial_usado = True
            self.log("Turno 1: activo el talento antes de jugar.")
            entrada.clic(juego.COORD["talento"], self.capturar()[1], espera=0.1)
            self.esperar_corto(2.5)  # la animacion del talento
        return self._jugar_turno()

    def _jugar_turno(self):
        """Juega cartas hasta llenar los huecos. Se puede retomar si se corta a medias."""
        ultima_accion, repeticiones = None, 0
        # Cartas que se jugaron y no entraron en su hueco: el juego no las acepta (bloqueadas aunque no se vean
        # oscuras). Se tratan como bloqueadas el resto del turno en vez de repetirlas (prueba de la 0.2.4).
        ultima_carta, rechazadas = None, []
        limite = time.time() + 45
        while time.time() < limite:
            p, o = self.capturar()
            if juego.victoria.esta(p) or juego.derrota.esta(p):
                self.turno_abierto = False
                return None
            huecos = C.contar_huecos(p, 0.7)
            if huecos == 0:
                self.turno_abierto = False
                self.log("Turno terminado.", "debug")
                return None
            self.huecos_turno = max(self.huecos_turno, huecos)
            accion = self.huecos_turno - huecos
            if accion == ultima_accion:
                # La carta anterior aun no ocupa su hueco (animacion/fusion): esperar un poco.
                repeticiones += 1
                if repeticiones < 8:
                    self.esperar_corto(0.25)
                    continue
                if ultima_carta is not None and ultima_carta.imagen is not None:
                    rechazadas.append(ultima_carta.imagen)
                    self.log(f"{ultima_carta} no entra en su hueco: la trato como bloqueada este turno.", "aviso")
                else:
                    self.log("El hueco no se lleno; repito la accion.", "aviso")
            repeticiones = 0

            mano = EQUIPO.etiquetar(C.leer_mano(p))
            for c in mano:
                if c.imagen is not None and any(_misma_imagen(c.imagen, r) for r in rechazadas):
                    c.tipo = TipoCarta.BLOQUEADA
            self.log("Mano: " + " ".join(str(c) for c in mano), "debug")
            try:
                idx, objetivo, talento = self.estrategia.decidir(self.fase, self.turno_fase, accion, mano, self.huecos_turno)
                self._anotar_heroes(mano)
            except Reiniciar as motivo:
                self.log(f"Reinicio: {motivo}", "aviso")
                self.diario.nota(f"Reinicio: {motivo}")
                self.turno_abierto = False
                return "rendirse"
            if talento and not self.talento_usado:
                self._activar_talento_odin()
                self.talento_usado = True
            self.diario.decision(self.fase, self.turno_fase, accion, mano, idx,
                                 getattr(getattr(self.estrategia, "jugador", None), "razones", None))
            if objetivo:
                self._apuntar(objetivo)
            if isinstance(idx, tuple):  # mover una carta sobre otra (gasta el hueco sin atacar)
                origen, destino = mano[idx[0]], mano[idx[1]]
                self.log(f"Accion {accion + 1}: muevo {origen} sobre {destino}")
                entrada.arrastrar(origen.rect, destino.rect, o)
            else:
                carta = mano[idx]
                self.log(f"Accion {accion + 1}: juego {carta}")
                entrada.clic(carta.rect, o, espera=0)
                ultima_carta = carta
            if self._esperar_hueco(huecos):
                self.log("Carta colocada.", "debug")
            else:
                self.log("La carta aun no ocupa su hueco; lo vuelvo a comprobar.", "debug")
            fusiones = 0 if isinstance(idx, tuple) else self.estrategia.fusiones_al_jugar(mano, idx)
            self.esperar_corto(PAUSA_ENTRE_CARTAS + (0.6 if fusiones == 1 else 1.1 if fusiones > 1 else 0))
            ultima_accion = accion
            # Tambien la ultima carta se comprueba: el turno solo acaba cuando no quedan huecos.
            # (En la primera pelea real la ultima carta a veces no entraba y el bot no se enteraba.)
        self.log("El turno tardo demasiado; lo retomo en el siguiente paso.", "aviso")
        return None

    def _esperar_hueco(self, huecos_antes: int, limite: float = 1.6) -> bool:
        """Tras clicar una carta: espera a que ocupe su hueco (quedan menos huecos libres)."""
        fin = time.time() + limite
        while time.time() < fin:
            self.esperar_corto(0.15)
            p, _ = self.capturar()
            if C.contar_huecos(p, 0.7) < huecos_antes:
                return True
        return False

    @staticmethod
    def esperar_corto(segundos: float):
        control.esperar(segundos)

    # ---------------------------------------------------------- objetivo y talento
    def _lados_seleccionados(self, p) -> set[str]:
        lados = set()
        if juego.perro_izq_seleccionado.esta(p, 0.8):
            lados.add("izq")
        if juego.perro_der_seleccionado.esta(p, 0.8):
            lados.add("der")
        return lados

    def _apuntar(self, lado: str):
        if self.objetivo_actual == lado:
            return
        punto = juego.COORD["perro_izquierdo" if lado == "izq" else "perro_derecho"]
        for intento in range(3):
            p, o = self.capturar()
            if lado in self._lados_seleccionados(p):
                self.objetivo_actual = lado
                return
            self.log(f"Apuntando al perro {lado} ({intento + 1}/3).", "debug")
            entrada.clic(punto, o, espera=0.1)
            fin = time.time() + 0.8
            while time.time() < fin:
                p, _ = self.capturar()
                if lado in self._lados_seleccionados(p):
                    self.objetivo_actual = lado
                    return
                self.esperar_corto(0.08)
        self.log(f"No pude confirmar el perro {lado}; sigo igual.", "aviso")
        self.objetivo_actual = lado

    def _talento_visible(self, p) -> bool:
        plantilla = EQUIPO.plantilla("odin.talento")
        return plantilla is not None and plantilla.esta(p, 0.75)

    def _activar_talento_odin(self):
        p, o = self.capturar()
        confirmable = self._talento_visible(p)
        for intento in range(3):
            self.log(f"Talento de Odin ({intento + 1}/3).")
            entrada.clic(juego.COORD["talento"], o, espera=0.1)
            if not confirmable:
                self.esperar_corto(2.5)  # sin captura del talento no se puede confirmar
                return
            fin = time.time() + 1.2
            while time.time() < fin:
                self.esperar_corto(0.08)
                p, _ = self.capturar()
                if not self._talento_visible(p):
                    self.esperar_corto(2.5)
                    return
        self.log("No pude confirmar el talento de Odin; sigo igual.", "aviso")

    # ----------------------------------------------------------------- finales
    def victoria(self, p, o):
        self.clic_si(juego.info_mision, p, o)
        if not self.foto_recompensa and juego.ok.esta(p):
            # La pantalla con el boton OK tras ganar es la que lista las recompensas: foto antes de cerrarla,
            # pero con la pantalla quieta (si no, salen cofres a medio abrir como objetos). Maximo 6 s.
            self.ok_visto_desde = self.ok_visto_desde or time.time()
            if not botin.quieta(self.previa_recompensa, p) and time.time() - self.ok_visto_desde < 6:
                self.previa_recompensa = p
                return None
            self.guardar_recompensa(p, self.victorias + 1)
            self.foto_recompensa = True
        self.clic_si(juego.ok, p, o)
        if self._volvio_a_pisos(p):
            if not self.foto_recompensa and self.ultima_pantalla_victoria is not None:
                # No se vio el OK: la ultima pantalla antes de la carga es lo mas parecido.
                self.guardar_recompensa(self.ultima_pantalla_victoria, self.victorias + 1)
                self.foto_recompensa = True
            self.victorias += 1
            self.diario.terminar("victoria", self.fase)
            minutos = (time.time() - self.inicio_pelea) / 60
            self.log(f"¡VICTORIA #{self.victorias}! ({minutos:.1f} min)", "ok")
            self._stats()
            meta = int(self.valores["victorias"])
            if meta and self.victorias >= meta:
                self.log(f"Llegue a {meta} victorias.", "ok")
                raise TerminarModo()
            return "elegir_piso"
        self.ultima_pantalla_victoria = p
        return None

    def derrota(self, p, o):
        self.clic_si(juego.info_mision, p, o)
        self.clic_si(juego.ok, p, o)
        self.clic_si(juego.cerrar, p, o)
        if self._volvio_a_pisos(p):
            self.diario.terminar("reinicio" if self.reinicio_pedido else "derrota", self.fase)
            if self.reinicio_pedido:
                self.reinicios += 1
            else:
                self.derrotas += 1
                self.derrotas_por_fase[self.fase or 0] += 1
                self.log(f"Derrota en la fase {self.fase}.", "error")
            self._stats()
            return "elegir_piso"
        return None

    @staticmethod
    def _volvio_a_pisos(p) -> bool:
        """La pelea termino del todo: pantalla de carga de las bestias o ya en la pantalla de pisos.
        (Tras rendirse, el juego puede volver a los pisos sin que el bot llegue a ver la carga.)"""
        return juego.carga_bestias.esta(p) or juego.piso3_superado.esta(p)

    def rendirse(self, p, o):
        self.reinicio_pedido = True
        if juego.ok.esta(p):
            return "derrota"
        if self.clic_si(juego.rendirse, p, o):
            return None
        self.clic_si(juego.pausa, p, o)
        return None

    def al_terminar(self):
        self.diario.terminar("abandonada", self.fase)  # se paro el bot a media pelea
        total = self.victorias + self.derrotas + self.reinicios
        self.log(
            f"Resumen: {self.victorias} victorias, {self.derrotas} derrotas, {self.reinicios} reinicios "
            f"de {total} peleas; {self.pociones} pociones.",
            "ok",
        )
        if self.derrotas_por_fase:
            self.log("Derrotas por fase: " + ", ".join(f"F{f}: {n}" for f, n in sorted(self.derrotas_por_fase.items())))
