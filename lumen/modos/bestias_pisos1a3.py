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

import numpy as np

from lumen import config, entrada, inteligencia, juego, ocr
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.motor import Opcion, TerminarModo
from lumen.vision import Plantilla
from lumen.ia import decidir as decidir_ia
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
    destino = ""  # "<bestia>_f<piso>": de donde salen las mecanicas del jefe (lumen/datos/jefes.yaml)

    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4):
        self.jugador.solo_area = fase in self.fases_area
        # Lo que pide el jefe en esta fase (posturas, inmortalidad...): cambia cuanto vale cada carta (ia/decidir).
        self.jugador.mecanicas = decidir_ia.mecanicas_de(self.destino, fase) if self.destino and fase else []
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
# Nombres escritos de cada bestia en el carrusel, en su orden (juego.ORDEN_BESTIAS) y Surtr al final.
NOMBRES_CARRUSEL = (("hraesvelgr",), ("eikthyrnir",), ("skoll", "hati"), ("nidhoggr",), ("ratatoskr",), ("surtr",))
TITULO_CARRUSEL = (570, 650)  # alto (y) del nombre grande de la bestia del centro, medido con Surtr
FLECHA_ZONA = (15, 150, 95, 820)  # x1, y1, x2, y2: columna de la izquierda donde sale la flecha del piso abierto
FLECHA_MIN_PIXELES = 60  # en una captura real la flecha tiene ~210 pixeles cian
PUNTO_X_PISO = 282  # x del circulo (el retrato de la bestia) de cada piso
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
    opciones: list = []  # cada bestia pone las suyas (_opciones): cambia la forma de jugar por defecto

    def al_empezar(self):
        if isinstance(self.estrategia, EstrategiaInteligente):
            self.estrategia.jugador.precargar()

    def _nueva_pelea(self):
        super()._nueva_pelea()
        if isinstance(getattr(self, "estrategia", None), EstrategiaInteligente):
            self.estrategia.destino = f"{self.id.removesuffix('_pisos1a3')}_f{self.piso}"

    def __init__(self, valores: dict):
        super().__init__(valores)
        jugar = self.valores.get("jugar", "Inteligente")
        self.jugar_auto = jugar == "AUTO"
        inteligente = jugar == "Inteligente"
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
        self.stats["estrategia"] = jugar  # queda en el historial
        self.textos_vistos = False
        self.piso = int(self.valores.get("primer_piso") or 1)
        # Por donde iba esta bestia la ultima vez (piso que toca y si hay que pulsar Reset antes): en la prueba de
        # la 0.7.2 el bot empezaba siempre en el Floor 1 y tocaba los 3 pisos superados antes de pulsar Reset.
        guardado = (config.obtener("pisos_bestias") or {}).get(self.id) or {}
        if self.piso == 1 and guardado:
            self.piso = int(guardado.get("piso", 1))
            self.pedir_reset = bool(guardado.get("reset"))
        self.vuelta = 1  # cuantas veces se ha empezado el ciclo 1 -> 2 -> 3
        self.vueltas_hechas = 0  # Floor 1, 2 y 3 superados = 1 vuelta (la opcion "victorias" cuenta vueltas)
        self.piso_abierto_seguro = False  # se acaba de ganar el piso anterior: el que toca esta abierto
        self.esperando_ok_reset: float | None = None  # se pulso Reset: esperar su OK sin tocar nada mas
        self.reintentos_reset = 0
        self.foto_sin_piso = False
        self._ultimo_flecha = 0.0
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

    def _meta_cumplida(self) -> bool:
        """Lo pidio el usuario (2026-11-09): en Floor 1-3 la meta son VUELTAS (Floor 1, 2 y 3), no peleas."""
        if self.piso != 3:
            return False
        self.vueltas_hechas += 1
        self.log(f"¡Vuelta {self.vueltas_hechas} completa (Floor 1, 2 y 3)!", "ok")
        self.stats["vueltas"] = self.vueltas_hechas
        meta = int(self.valores.get("victorias") or 0)
        if meta and self.vueltas_hechas >= meta:
            self.log(f"Llegue a {meta} vuelta{'s' if meta != 1 else ''}.", "ok")
            return True
        return False

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
            self.piso_abierto_seguro = self.piso != 1  # tras ganar el 1 o el 2, el siguiente esta abierto seguro
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

    def _bestia_en_carrusel(self, p) -> int | None:
        """Posicion en el carrusel de la bestia que se ve: por su imagen o por su nombre escrito (Surtr, la ultima,
        no tiene imagen: el bot no sabia donde estaba y deslizaba sin fin hacia el final, prueba del usuario,
        2026-11-09)."""
        actual = next((i for i, b in enumerate(juego.ORDEN_BESTIAS) if b.esta(p)), None)
        if actual is not None or not ocr.disponible():
            return actual
        lineas = ocr.lineas_con_posicion(p)
        # Primero el titulo grande del centro (a los lados asoman las bestias vecinas con su nombre)
        centrales = [t for t, (x, y, w, h) in lineas if TITULO_CARRUSEL[0] <= y + h // 2 <= TITULO_CARRUSEL[1]]
        for grupo in (centrales, [t for t, _ in lineas]):
            for texto in grupo:
                t = texto.lower()
                for i, nombres in enumerate(NOMBRES_CARRUSEL):
                    if any(n in t for n in nombres):
                        return i
        return None

    def _deslizar_hacia_bestia(self, p, o):
        actual = self._bestia_en_carrusel(p)
        objetivo = juego.ORDEN_BESTIAS.index(self.bestia)
        desde, hasta = juego.COORD["deslizar_der"], juego.COORD["deslizar_izq"]
        self._deslizes_carrusel = getattr(self, "_deslizes_carrusel", 0) + 1
        if actual is not None:
            atras = actual > objetivo
        else:  # no se sabe donde esta: ir y volver (6 hacia un lado, 6 hacia el otro) en vez de quedarse en un extremo
            atras = (self._deslizes_carrusel // 6) % 2 == 1
        if atras:
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
        if self.esperando_ok_reset is not None:
            # Tras pulsar Reset sale una confirmacion: el bot deslizaba la lista y la cerraba sin querer, el Reset no
            # se hacia y daba la vuelta 1 -> 2 -> 3 (prueba del usuario, 2026-11-09). Ahora espera el OK.
            if self.clic_si(juego.ok, p, o, espera=1.5):
                self.log("Reset confirmado.", "debug")
                self.esperando_ok_reset, self.reintentos_reset = None, 0
            elif time.time() - self.esperando_ok_reset > 6:
                self.esperando_ok_reset = None
                if self.reintentos_reset < 2:
                    self.reintentos_reset += 1
                    self.pedir_reset = True  # no salio la confirmacion: volver a pulsar Reset
            return None
        if self.clic_si(juego.ok, p, o):  # confirmar al abrir el piso
            return None
        if self.pedir_reset and self._pulsar_reset(p, o):
            return None
        if self.piso != 1 and not self.piso_abierto_seguro and self._sin_vuelta_empezada(p):
            # "Set Party" en vez de "Reset": no hay ninguna vuelta a medias, asi que el abierto es el Floor 1.
            self.log(f"No hay ninguna vuelta empezada: voy al Floor 1 (no al {self.piso}).", "ok")
            self.piso, self.pedir_reset, self._toques_piso = 1, False, 0
            self._recordar_piso()
            return None
        if self._ir_al_piso_abierto(p, o):
            return None
        rect = self._buscar_piso(p)
        if rect is not None:
            # El piso se abre tocando su circulo (la imagen de la bestia), no su titulo: en la prueba de la
            # 0.2.3 el bot tocaba "Twilight Temple Floor 1" una y otra vez sin abrir nada. El circulo queda
            # ~56 px por debajo del centro del titulo (medido en una captura real).
            x, y, w, h = rect
            punto = (x + w // 2, y + h // 2 + BAJO_TITULO)
            if punto[1] <= LIMITE_CIRCULO:
                if self._toques_piso >= TOQUES_PISO and self.piso_abierto_seguro and self._toques_piso < 3 * TOQUES_PISO:
                    pass  # se acaba de ganar el anterior: este esta abierto, insistir (mas despacio)
                elif self._toques_piso >= TOQUES_PISO:
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
        # Sin el piso a la vista: quiza lo tapa un aviso (prueba del dragon, 2026-11-09: toco el Floor 3, algo salio
        # y el bot deslizaba la lista debajo). Primero intentar aceptarlo.
        if self.buscando_piso_desde and time.time() - self.buscando_piso_desde > 4:
            self._aceptar_aviso(p, o)
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
        if time.time() - self.buscando_piso_desde > SALTAR_PISO_S / 2 and not self.foto_sin_piso:
            self.foto_sin_piso = True  # una por sesion: para ver que habia en pantalla (prueba del dragon, 2026-11-09)
            try:
                from lumen.rutas import LOGS
                from lumen.vision import guardar_imagen

                ruta = LOGS / "sin_piso" / f"{self.id}_f{self.piso}_{time.strftime('%Y%m%d_%H%M%S')}.png"
                guardar_imagen(ruta, p)
                self.log(f"No encuentro el Floor {self.piso}: guardo una captura en logs/sin_piso ({ruta.name}).", "aviso")
            except Exception:
                pass
        # Recien ganado el anterior, el piso que toca esta abierto: antes de darlo por perdido y hacer Reset (el
        # dragon perdio asi el Floor 3), se busca el doble de tiempo.
        limite = SALTAR_PISO_S * (3 if self.piso_abierto_seguro else 1)
        if time.time() - self.buscando_piso_desde > limite:
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
                self.esperando_ok_reset = time.time()
                self.piso_abierto_seguro = False
                self._recordar_piso()
                return True
        return False

    def flechas_piso_abierto(self, p) -> list[int]:
        """Alturas (y) de las flechas cian de los pisos abiertos. El juego marca asi el piso que toca (y su retrato
        sale a color con el coste "x30"; los cerrados, oscuros): lo enseno el usuario (2026-11-09). Puede haber dos:
        el Floor 1-3 que toca y el Floor 4 (Transcendent) si tambien esta abierto."""
        if not isinstance(p, np.ndarray):
            return []
        tira = p[FLECHA_ZONA[1]:FLECHA_ZONA[3], FLECHA_ZONA[0]:FLECHA_ZONA[2]].astype(int)
        cian = ((tira[..., 0] > 200) & (tira[..., 1] > 170) & (tira[..., 2] < 130)).sum(axis=1)
        flechas, inicio, pixeles = [], None, 0
        for y, n in enumerate(list(cian) + [0] * 9):  # filas con cian, separadas por 8 o mas filas sin el = otra flecha
            if n:
                inicio, pixeles, ultima = (y if inicio is None else inicio), pixeles + int(n), y
            elif inicio is not None and y - ultima > 8:
                if pixeles >= FLECHA_MIN_PIXELES:
                    flechas.append((inicio + ultima) // 2 + FLECHA_ZONA[1])
                inicio, pixeles = None, 0
        return flechas

    def _ir_al_piso_abierto(self, p, o) -> bool:
        """Toca directamente el piso que el juego marca como abierto, sin probar los cerrados (antes tocaba el 2 y el
        3 tres veces cada uno cuando estaban cerrados). Si el abierto no es el que el bot esperaba, lo corrige. La
        flecha del Floor 4 (Transcendent) no cuenta: su titulo no dice "Floor N" (lo aviso el usuario)."""
        flechas = [y for y in self.flechas_piso_abierto(p) if y <= LIMITE_CIRCULO]
        if not flechas:
            return False  # sin flecha (todo superado: hace falta Reset) o tapada por la barra del equipo
        elegida, numero = None, None
        if ocr.disponible():
            if time.time() - self._ultimo_flecha < CADA_OCR_S:
                return True  # leido hace nada: esperar a que el toque anterior haga efecto
            self._ultimo_flecha = time.time()
            lineas = [(t, r) for t, r in self._lineas(p) if not _es_premio(t)]
            for y in flechas:
                for texto, (x, ty, w, h) in lineas:
                    numeros = [n for n in numeros_de_piso(texto) if n in (1, 2, 3)]
                    if numeros and 0 < y - (ty + h // 2) < 2 * BAJO_TITULO:
                        elegida, numero = y, numeros[0]
                        break
                if elegida is not None:
                    break
        if elegida is None:
            if len(flechas) != 1 or ocr.disponible():
                return False  # no se sabe cual es la del Floor 1-3: lo de siempre
            elegida = flechas[0]
        if numero and numero != self.piso:
            self.log(f"El piso abierto es el Floor {numero}: voy a ese (esperaba el {self.piso}).", "aviso")
            self.piso, self.pedir_reset = numero, False
            self._recordar_piso()
            self._stats()
        if self._toques_piso >= TOQUES_PISO:
            return False  # tocarlo no lo abre: lo de siempre
        self._toques_piso += 1
        self.log(f"Abro el Floor {self.piso}.")
        entrada.clic((PUNTO_X_PISO, elegida), o, espera=1.0)
        self.buscando_piso_desde = None
        return True

    def _sin_vuelta_empezada(self, p) -> bool:
        """En la pantalla de pisos se lee "Set Party" (y no "Reset") cuando no hay ninguna vuelta a medias."""
        if not ocr.disponible():
            return False
        textos = {t.strip().lower() for t, _ in self._lineas(p)}
        return any(t.startswith("set party") for t in textos) and not any(t.startswith("reset") for t in textos)

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


def _opciones(jugar: str) -> list[Opcion]:
    return [
        Opcion("victorias", "Vueltas (0 = sin límite)", "entero", 1, maximo=999,
               ayuda="1 vuelta = Floor 1, 2 y 3 superados (y Reset). Al acabar las vueltas pedidas, para."),
        Opcion("primer_piso", "Empezar en el Floor", "lista", "1", opciones=["1", "2", "3"]),
        Opcion("jugar", "Cómo jugar", "lista", jugar, opciones=["AUTO", "Inteligente", "Simple"],
               ayuda="AUTO: pone el AUTO del juego y no juega cartas (lo más rápido en los pisos fáciles). "
                     "Inteligente: piensa el turno entero y las fusiones. Simple: ulti y luego la de más rango."),
        Opcion("aprender", "Aprender solo", "si_no", True,
               ayuda="Solo con Inteligente: 1 de cada 10 peleas prueba una variante pequeña y se queda con lo que "
                     "gane más rápido. Apagado: juega siempre con lo ya aprendido."),
        Opcion("talento", "Activar el talento en el turno 1", "si_no", True,
               ayuda="Toca el talento del equipo (el boton redondo sobre las casillas) antes de jugar el primer turno. "
                     "Con AUTO no se toca."),
        Opcion("pociones", "Usar pociones de stamina", "si_no", True),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]


BestiaPisos1a3.opciones = _opciones("Inteligente")


def _bestia(id_base: str, titulo: str, plantilla, imagen: str, piso3=None, enemigos: int = 1, objetivos=None,
            fases_area=(), jugar: str = "Inteligente"):
    """Crea el modo Floor 1-3 de una bestia. ``jugar``: la forma de jugar por defecto."""
    return type(f"Pisos1a3_{id_base}", (BestiaPisos1a3,), {
        "id": f"{id_base}_pisos1a3", "nombre": f"{titulo} · Floor 1-3", "titulo_juego": titulo,
        "subtitulo_juego": "Demonic Beast · Floor 1-3", "imagen": imagen, "bestia": plantilla,
        "piso3_superado": piso3, "enemigos": enemigos, "objetivos": objetivos or {},
        "fases_area": frozenset(fases_area), "opciones": _opciones(jugar),
    })


PerrosPisos1a3 = _bestia("perros", "Skoll & Hati", juego.perros, "demonic_beasts/skollandhati.png",
                         juego.piso3_superado, enemigos=2,  # los dos perros
                         # Como AutoFarming: en la fase 1 el perro claro (derecha), en la 2 y la 3 el oscuro (izquierda).
                         objetivos={1: "der", 2: "izq"},
                         # Fase 3 (lo explico el usuario): los dos perros tienen que caer a la vez, asi que sin
                         # objetivo y todo areas y ultis.
                         fases_area={3}, jugar="AUTO")
PajaroPisos1a3 = _bestia("pajaro", "Hraesvelgr", juego.pajaro, "demonic_beasts/hraesvelgr.png", jugar="AUTO")
CiervoPisos1a3 = _bestia("ciervo", "Eikthyrnir", juego.ciervo, "deer/Eikthyrnir.png", jugar="AUTO")
SerpientePisos1a3 = _bestia("serpiente", "Nidhoggr", juego.serpiente, "snake/nidhoggr.png")
RATA_PELEA = Plantilla("rat/ratatoskr_pelea.png")  # la rata en la pelea (salta de un tronco a otro)


class RataPisos1a3(_bestia("rata", "Ratatoskr", juego.rata, "rat/ratatoskr.png")):
    """Ratatoskr con sus 3 troncos ("Suspicious Wooden Device"): 1 en el centro, 2 a la izquierda y 3 a la derecha
    (lo dijo el usuario, 2026-11-09; se ve el numero sobre cada barra). La pelea acaba al matar a la rata, asi que
    se le apunta a ella; salvo en el Floor 2 (7dshub), donde es inmortal mientras vivan los troncos 2 y 3 (fases 1
    y 2) o el 2 (fase 3): primero se rompe ese tronco. Antes el bot no apuntaba y el juego elegia por su cuenta."""

    PUNTOS = {"tronco 2": (142, 376), "tronco 3": (326, 370)}  # medido en una captura real de 550x940
    BARRAS = {"tronco 2": (118, 308, 180, 326), "tronco 3": (300, 306, 360, 326)}  # su barra de vida (morada)
    RATA_CENTRO = (240, 358)

    def tronco_vivo(self, p, tronco: str) -> bool:
        x1, y1, x2, y2 = self.BARRAS[tronco]
        trozo = p[y1:y2, x1:x2].astype(int)
        morado = (trozo[..., 0] > 130) & (trozo[..., 2] > 110) & (trozo[..., 1] < 110)  # BGR: azul y rojo, poco verde
        return float(morado.mean()) > 0.06

    def donde_rata(self, p) -> tuple[int, int]:
        rect = RATA_PELEA.buscar(p, 0.55)
        if rect is None:
            return self.RATA_CENTRO
        x, y, w, h = rect
        return x + w // 2, y + h // 2

    def objetivo_rata(self, p, fase: int) -> tuple[str, tuple[int, int]]:
        """(a quien, donde tocar) segun el piso y la fase."""
        rata = self.donde_rata(p)
        if self.piso == 2:
            vivos = [t for t in ("tronco 3", "tronco 2") if self.tronco_vivo(p, t)]
            if fase == 3 and "tronco 2" in vivos:
                return "tronco 2", self.PUNTOS["tronco 2"]
            if fase in (1, 2) and len(vivos) == 2:
                # Romper uno basta: el que no tenga a la rata encima (tocar ahi la elegiria a ella).
                tronco = "tronco 2" if abs(rata[0] - self.PUNTOS["tronco 3"][0]) < 50 else "tronco 3"
                return tronco, self.PUNTOS[tronco]
        return "rata", rata

    def _empezar_turno(self, p, huecos: int):
        fase = self._detectar_fase(p, huecos) or self.fase or 1
        quien, punto = self.objetivo_rata(p, fase)
        if quien != self.objetivo_actual:
            self.objetivo_actual = quien
            self.log(f"Apunto a {'la rata' if quien == 'rata' else 'el ' + quien}.")
            entrada.clic(punto, self.capturar()[1], espera=0.3)
        return super()._empezar_turno(p, huecos)
TODAS = (PerrosPisos1a3, PajaroPisos1a3, CiervoPisos1a3, SerpientePisos1a3, RataPisos1a3)
