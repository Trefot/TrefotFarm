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

from lumen import config, entrada, inteligencia, juego, ocr
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

    fases_area: frozenset = frozenset()  # fases en que hay que matar a todos a la vez (las pone el modo)

    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4):
        self.jugador.solo_area = fase in self.fases_area
        paso = self.jugador.elegir(mano, total - accion)
        if paso is None:  # nada que jugar ni fusionar: lo de siempre (mover una carta para gastar el hueco)
            return super().decidir(fase, turno, accion, mano, total)
        if paso[0] == "jugar":
            return paso[1], None, False
        return (paso[1], paso[2]), None, False


TOQUES_PISO = 3  # toques al circulo del piso sin que se abra: ya esta superado, pasar al siguiente
SALTAR_PISO_S = 40  # sin encontrar el piso que toca en la pantalla de pisos (ni desplazando): pasar al siguiente
CADA_DESPLAZAR_S = 2.0  # sin ver el piso que toca: deslizar la lista cada 2 s buscandolo
DESPLAZAR_ABAJO = ((270, 720), (270, 420))  # dedo hacia arriba: la lista baja (el Floor 1 esta abajo)
DESPLAZAR_ARRIBA = ((270, 420), (270, 720))
BAJO_TITULO = 56  # del centro del titulo del piso al centro de su circulo (lo que se toca)
LIMITE_CIRCULO = 780  # mas abajo lo tapa la barra del equipo
CADA_OCR_S = 1.0  # leer el texto de la pantalla como mucho una vez por segundo (el OCR gasta CPU)


class BestiaPisos1a3(PerrosPiso4):
    """Base: las subclases ponen id, nombres y ``bestia`` (su imagen del carrusel de bestias)."""

    bestia = None  # Plantilla de la bestia en el carrusel
    ciclo_pisos = (1, 2, 3)  # los pisos que recorre (la pagina Farmear los dibuja con el actual marcado)
    enemigos = 1  # enemigos en la pelea (las cartas de area valen mas con varios)
    piso3_superado = None  # Plantilla de "Floor 3 Cleared" de esta bestia, si la hay
    objetivos: dict[int, str] = {}  # fase -> enemigo al que atacar ("izq"/"der"); vacio = el que marque el juego
    fases_area: frozenset = frozenset()  # fases en que todos los enemigos tienen que caer a la vez: areas y ultis
    descripcion = "Floor 1, 2 y 3 seguidos, y vuelta a empezar. Sirve cualquier equipo fuerte."
    duracion = ""
    fases = 0  # no se sabe aun cuantas fases tienen estos pisos
    equipo = None  # cualquier equipo: el que tengas puesto en el juego
    rendirse_si_bloqueada = False
    nombres_estados = {**PerrosPiso4.nombres_estados, "ir_a_perros": "Entrando a Demonic Beasts",
                       "elegir_piso": "Eligiendo el piso"}
    opciones = [
        Opcion("victorias", "Victorias (0 = sin límite)", "entero", 3, maximo=9999,
               ayuda="3 = una pasada: Floor 1, 2 y 3, Reset y para."),
        Opcion("primer_piso", "Empezar en el Floor", "lista", "1", opciones=["1", "2", "3"]),
        Opcion("jugar", "Cómo jugar", "lista", "Inteligente", opciones=["Inteligente", "Simple"],
               ayuda="Inteligente: piensa el turno entero y las fusiones. Simple: ulti y luego la de más rango."),
        Opcion("aprender", "Aprender solo", "si_no", True,
               ayuda="1 de cada 10 peleas prueba una variante pequeña del juego inteligente y se queda con lo que "
                     "gane más rápido. Apagado: juega siempre con lo ya aprendido."),
        Opcion("talento", "Activar el talento en el turno 1", "si_no", True,
               ayuda="Toca el talento del equipo (el boton redondo sobre las casillas) antes de jugar el primer turno."),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        inteligente = self.valores.get("jugar", "Inteligente") != "Simple"
        self.estrategia = EstrategiaInteligente(self.enemigos) if inteligente else EstrategiaSimple()
        if isinstance(self.estrategia, EstrategiaInteligente):
            self.estrategia.fases_area = self.fases_area
        self.pedir_reset = False  # tras el Floor 3 hay que pulsar Reset para volver a abrir el Floor 1
        # Lo pidio el usuario en la prueba de la 0.7.5: el talento se activa siempre en el turno 1, antes de las cartas.
        self.talento_turno_1 = bool(self.valores.get("talento", True))
        self.reset_desde: float | None = None
        if self.objetivos:  # la estrategia no elige enemigo: se le pone el de la fase
            decidir = self.estrategia.decidir

            def con_objetivo(fase, turno, accion, mano, total=4):
                idx, objetivo, talento = decidir(fase, turno, accion, mano, total)
                return idx, objetivo or self.objetivos.get(fase), talento

            self.estrategia.decidir = con_objetivo
        self.stats["estrategia"] = "Inteligente" if inteligente else "Simple"  # queda en el historial
        self.textos_vistos = False
        self.piso = int(self.valores.get("primer_piso") or 1)
        # Por donde iba esta bestia la ultima vez (piso que toca y si hay que pulsar Reset antes): en la prueba de
        # la 0.7.2 el bot empezaba siempre en el Floor 1 y tocaba los 3 pisos superados antes de pulsar Reset.
        guardado = (config.obtener("pisos_bestias") or {}).get(self.id) or {}
        if self.piso == 1 and guardado:
            self.piso = int(guardado.get("piso", 1))
            self.pedir_reset = bool(guardado.get("reset"))
        self.vuelta = 1  # cuantas veces se ha empezado el ciclo 1 -> 2 -> 3
        self.buscando_piso_desde: float | None = None
        self._ultimo_ocr: tuple[float, int, object] = (0.0, 0, None)  # (hora, piso, rectangulo) de la ultima lectura
        self._pisos_vistos: tuple[float, set] = (0.0, set())  # (hora, numeros de piso) de la ultima lectura
        self._desplazamientos = 0  # veces que se deslizo la lista buscando el piso que toca
        self._ultimo_desplazamiento = 0.0
        self._toques_piso = 0  # veces que se toco el piso que toca sin que se abriera
        self.terminar_tras_reset = False  # pasada completa: pulsar Reset y parar
        self.fin_desde: float | None = None
        self.stats.update(piso=self.piso, vuelta=self.vuelta)

    def _siguiente_piso(self):
        self.piso = self.piso % 3 + 1
        if self.piso == 1:
            self.vuelta += 1
            self.pedir_reset = True
        self.buscando_piso_desde = None
        self._desplazamientos = 0
        self._toques_piso = 0
        self._recordar_piso()
        self._stats()

    def _recordar_piso(self):
        pisos = dict(config.obtener("pisos_bestias") or {})
        pisos[self.id] = {"piso": self.piso, "reset": bool(self.pedir_reset)}
        config.guardar({"pisos_bestias": pisos})

    def _stats(self):
        self.stats.update(piso=self.piso, vuelta=self.vuelta)  # para la pagina Farmear
        super()._stats()

    def victoria(self, p, o):
        try:
            siguiente = super().victoria(p, o)  # cuenta la victoria al volver a los pisos
        except TerminarModo:
            # Llego a las victorias pedidas: apuntar el piso que toca (para la proxima vez) y, si acaba de
            # superar el Floor 3, pulsar Reset antes de parar: una pasada es Floor 1, 2, 3 y Reset (lo pidio el
            # usuario tras la prueba de la 0.7.3, en la que paraba sin apuntar nada).
            self._siguiente_piso()
            if not self.pedir_reset:
                raise
            self.log("Pasada completa: pulso Reset y termino.", "ok")
            self.terminar_tras_reset = True
            return "elegir_piso"
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
        if self._en_pisos(p):  # antes que nada: el titulo "Demonic Beast Battle" sigue arriba en los pisos
            self.log(f"En la pantalla de pisos de {self.titulo_juego}.", "ok")
            return "elegir_piso"
        if self.clic_si(juego.ok, p, o) or self.clic_si(juego.cerrar, p, o):
            self.log("Cierro un aviso.")  # p. ej. el que sale al abrir la bestia
            return None
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6)
        self.clic_si(juego.nido_criaturas, p, o)
        if juego.pantalla_bestias.esta(p):
            if not self.bestia.esta(p):
                self._deslizar_hacia_bestia(p, o)
                return None
            self.clic_si(self.bestia, p, o)
            return None
        return None

    def _deslizar_hacia_bestia(self, p, o):
        actual = next((i for i, b in enumerate(juego.ORDEN_BESTIAS) if b.esta(p)), None)
        objetivo = juego.ORDEN_BESTIAS.index(self.bestia)
        desde, hasta = juego.COORD["deslizar_der"], juego.COORD["deslizar_izq"]
        if actual is not None and actual > objetivo:
            desde, hasta = hasta, desde
        entrada.arrastrar(desde, hasta, o)

    def _en_pisos(self, p) -> bool:
        """En la pantalla de pisos: por "Floor 3 Cleared" (si esta bestia tiene esa imagen) o por leer en
        la lista al menos dos pisos distintos (el que toca puede no verse sin desplazar la lista)."""
        if self.piso3_superado is not None and self.piso3_superado.esta(p):
            return True
        return len(self._numeros_de_piso(p)) >= 2

    def _volvio_a_pisos(self, p) -> bool:
        return juego.carga_bestias.esta(p) or self._en_pisos(p)

    def _verificar_equipo(self, p):
        self.equipo_verificado = True  # cualquier equipo vale

    def elegir_piso(self, p, o):
        if self.terminar_tras_reset:
            return self._reset_y_terminar(p, o)
        if juego.empezar.esta(p):
            self.buscando_piso_desde = None
            self._toques_piso = 0
            return "preparar"
        if self.clic_si(juego.ok, p, o):  # confirmar al abrir el piso (o el Reset)
            return None
        if self.pedir_reset and self._pulsar_reset(p, o):
            return None
        rect = self._buscar_piso(p)
        if rect is not None:
            # El piso se abre tocando su circulo (la imagen de la bestia), no su titulo: en la prueba de la
            # 0.2.3 el bot tocaba "Twilight Temple Floor 1" una y otra vez sin abrir nada. El circulo queda
            # ~56 px por debajo del centro del titulo (medido en una captura real).
            x, y, w, h = rect
            punto = (x + w // 2, y + h // 2 + BAJO_TITULO)
            if punto[1] <= LIMITE_CIRCULO:
                if self._toques_piso >= TOQUES_PISO:
                    # Ya superado esta semana (no se abre): en la prueba de la 0.4.0, cada vez que se arrancaba el
                    # bot tocaba el Floor 1 ya superado durante 40 s antes de pasar al siguiente.
                    antes = self.piso
                    self._siguiente_piso()
                    self.log(f"El Floor {antes} no se abre (¿ya superado?): paso al Floor {self.piso}.", "aviso")
                    return None
                self._toques_piso += 1
                self.log(f"Abro el Floor {self.piso}.")
                entrada.clic(punto, o, espera=1.0)
                self._desplazamientos = 0
                return None
            # El circulo aun queda tapado por la barra del equipo: bajar la lista antes de tocar.
            if time.time() - self._ultimo_desplazamiento > CADA_DESPLAZAR_S:
                entrada.arrastrar(*DESPLAZAR_ABAJO, o)
                self._ultimo_desplazamiento = time.time()
                self._ultimo_ocr = (0.0, 0, None)
            return None
        # Sin el piso a la vista: deslizar la lista (4 veces hacia abajo, 4 hacia arriba...).
        if time.time() - self._ultimo_desplazamiento > CADA_DESPLAZAR_S:
            abajo = (self._desplazamientos // 4) % 2 == 0
            self.log(f"No veo el Floor {self.piso}: deslizo la lista hacia {'abajo' if abajo else 'arriba'}.", "debug")
            entrada.arrastrar(*(DESPLAZAR_ABAJO if abajo else DESPLAZAR_ARRIBA), o)
            self._desplazamientos += 1
            self._ultimo_desplazamiento = time.time()
            self._ultimo_ocr = (0.0, 0, None)  # la lista se movio: volver a leer
        # Sin el piso ni desplazando (p. ej. una bestia sin Floor 3, o aun no desbloqueado): no quedarse ahi.
        self.buscando_piso_desde = self.buscando_piso_desde or time.time()
        if time.time() - self.buscando_piso_desde > SALTAR_PISO_S:
            antes = self.piso
            self._siguiente_piso()
            self.log(f"No encuentro el Floor {antes}: paso al Floor {self.piso}.", "aviso")
        return None

    def _reset_y_terminar(self, p, o):
        """Fin de la pasada: Reset, su OK de confirmacion y parar (como mucho 5 s esperando el OK)."""
        if self.pedir_reset:
            self._pulsar_reset(p, o)
            return None
        if self.clic_si(juego.ok, p, o, espera=1.0):
            raise TerminarModo()
        self.fin_desde = self.fin_desde or time.time()
        if time.time() - self.fin_desde > 5:
            raise TerminarModo()
        return None

    def _pulsar_reset(self, p, o) -> bool:
        """Tras superar el Floor 3 los pisos quedan cerrados hasta pulsar "Reset" (lo dijo el usuario en la
        prueba de la 0.2.4: el bot intentaba abrir el Floor 1 sin mas). Se busca el boton por su texto."""
        self.reset_desde = self.reset_desde or time.time()
        if time.time() - self.reset_desde > 15:  # sin boton Reset a la vista: quiza no hace falta
            self.log("No veo el botón Reset; sigo con el Floor 1.", "aviso")
            self.pedir_reset, self.reset_desde = False, None
            return False
        if not ocr.disponible():
            return False
        for texto, (x, y, w, h) in self._lineas(p):
            t = texto.strip().lower()
            if t in ("reset", "restablecer", "reiniciar") or t.startswith("reset "):
                self.log("Pulso Reset para volver a empezar desde el Floor 1.", "ok")
                entrada.clic((x + w // 2, y + h // 2), o, espera=1.5)
                self.pedir_reset, self.reset_desde = False, None
                self._recordar_piso()
                return True
        return False

    def _buscar_piso(self, p):
        """Rectangulo del texto del piso que toca en la pantalla de pisos (sin contar "Floor N Cleared").
        Cada bestia nombra sus pisos a su manera ("Piso 1 del templo del ocaso", "Salón del Génesis
        (piso 1)"...): se busca "floor N" o "piso N" en cualquier parte de la linea."""
        if not ocr.disponible():
            self.log("Para elegir el piso necesito el lector de texto de Windows: ejecuta Instalar.bat.", "error")
            raise TerminarModo()
        hora, piso, rect = self._ultimo_ocr
        if piso == self.piso and time.time() - hora < CADA_OCR_S:  # leido hace menos de 1 s: vale lo mismo
            return rect
        rect = self._leer_piso(p)
        self._ultimo_ocr = (time.time(), self.piso, rect)
        return rect

    def _numeros_de_piso(self, p) -> set[int]:
        """Los numeros de piso que se leen en pantalla (como mucho una lectura por segundo)."""
        if not ocr.disponible():
            return set()
        hora, numeros = self._pisos_vistos
        if time.time() - hora < CADA_OCR_S:
            return numeros
        numeros = {n for texto, _ in self._lineas(p) if not _es_premio(texto) for n in numeros_de_piso(texto)}
        self._pisos_vistos = (time.time(), numeros)
        return numeros

    def _lineas(self, p):
        return ocr.lineas_con_posicion(p) + ocr.lineas_con_posicion(p, invertir=True)

    def _leer_piso(self, p):
        lineas = self._lineas(p)
        if not self.textos_vistos and lineas:  # una vez por sesion, para poder ajustar si no lo encuentra
            self.textos_vistos = True
            self.log("Texto en la pantalla de pisos: " + " | ".join(t for t, _ in lineas), "debug")
        for texto, rect in lineas:
            t = texto.lower()
            if _es_premio(t):
                continue
            if self.piso in numeros_de_piso(t):
                return rect
        return None


def numeros_de_piso(texto: str) -> list[int]:
    """Los numeros tras "floor" o "piso". El lector de texto suele leer el 1 como I, l o |
    ("Twilight Temple Floor I"): por eso nunca encontraba el Floor 1 (prueba de la 0.2.1)."""
    encontrados = re.findall(r"(?:floor|piso)\s*([0-9il|]+)(?![a-z0-9])", texto, flags=re.IGNORECASE)
    numeros = []
    for n in encontrados:
        n = n.lower().replace("i", "1").replace("l", "1").replace("|", "1")
        if n.isdigit():
            numeros.append(int(n))
    return numeros


def _es_premio(texto: str) -> bool:
    """Lineas que nombran un piso pero no son su boton: "Floor 3 Cleared" y, en la pantalla de elegir
    bestia, la lista de recompensas ("Obtain Floor 1 First Clear Reward"). Contarlas hacia creer al bot
    que ya estaba en los pisos sin haber entrado a la bestia (primera prueba de la 0.2.1)."""
    t = texto.lower()
    return any(palabra in t for palabra in ("clear", "superad", "reward", "recompensa", "obtain", "obten"))


def _bestia(id_base: str, titulo: str, plantilla, imagen: str, piso3=None, enemigos: int = 1, objetivos=None,
            fases_area=()):
    """Crea el modo Floor 1-3 de una bestia."""
    return type(f"Pisos1a3_{id_base}", (BestiaPisos1a3,), {
        "id": f"{id_base}_pisos1a3", "nombre": f"{titulo} · Floor 1-3", "titulo_juego": titulo,
        "subtitulo_juego": "Demonic Beast · Floor 1-3", "imagen": imagen, "bestia": plantilla,
        "piso3_superado": piso3, "enemigos": enemigos, "objetivos": objetivos or {},
        "fases_area": frozenset(fases_area),
    })


PerrosPisos1a3 = _bestia("perros", "Skollandhati & Hati", juego.perros, "demonic_beasts/skollandhati.png",
                         juego.piso3_superado, enemigos=2,  # los dos perros
                         # Como AutoFarming: en la fase 1 el perro claro (derecha), en la 2 y la 3 el oscuro (izquierda).
                         objetivos={1: "der", 2: "izq"},
                         # Fase 3 (lo explico el usuario): los dos perros tienen que caer a la vez, asi que sin
                         # objetivo y todo areas y ultis.
                         fases_area={3})
PajaroPisos1a3 = _bestia("pajaro", "Hraesvelgr", juego.pajaro, "demonic_beasts/hraesvelgr.png")
CiervoPisos1a3 = _bestia("ciervo", "Eikthyrnir", juego.ciervo, "deer/Eikthyrnir.png")
SerpientePisos1a3 = _bestia("serpiente", "Nidhoggr", juego.serpiente, "snake/nidhoggr.png")
RataPisos1a3 = _bestia("rata", "Ratatoskr", juego.rata, "rat/ratatoskr.png")
TODAS = (PerrosPisos1a3, PajaroPisos1a3, CiervoPisos1a3, SerpientePisos1a3, RataPisos1a3)
