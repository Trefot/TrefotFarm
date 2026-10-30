"""Fuerte Solgres: Oro (mazmorra de oro, 6.o piso) y Monedas SA (Torre del reloj de la mazmorra especial).

Los dos se juegan con la repeticion automatica del juego ("Auto Repeat"): el bot solo llega, la activa,
pulsa Start y cuenta las vueltas. Flujo de AutoFarming (GoldFarmer y SADungeonFarmer, MIT), con sus
imagenes en assets/imagenes (gold_dungeon/, sa_coin_dungeon/ y otras sueltas).

Monedas SA ademas mira el cofre que deja el jefe: si es peor que el elegido, repite la pelea con "Try Again"
del menu de pausa (sin salir de la torre), para no gastar la vuelta en un cofre de bronce.
"""

import time

import cv2

from lumen import entrada, juego
from lumen.motor import Modo, Opcion, TerminarModo
from lumen.vision import Plantilla

P = Plantilla
MAZMORRA_FS = P("fs_dungeon.png")  # boton de Fuerte Solgres en el menu Battle
EMPEZAR = P("start.png")
REPETIR_APAGADO = P("auto_repeat_off.png")
REPETICION_TERMINADA = P("equipment/auto_repeat_ended.png")
VUELTA_TERMINADA = P("finished_auto_repeat_fight.png")
ATRAS = P("back.png")
TIENDA_ESSETTE = P("essette_shop.png")  # aviso de la tienda de Essette que tapa la pantalla
CARGA_FS = P("fs_loading_screen.png")
RESULTADO = P("dailies/result.png")
# Oro
MAZMORRA_ORO = P("gold_dungeon/gold_dungeon.png")
PISO_6 = P("gold_dungeon/6th_floor.png")
MAX_TICKETS = P("gold_dungeon/max_clears.png")
AUTO_CLEAR = P("dailies/auto_clear.png")
EMPEZAR_AUTO_CLEAR = P("dailies/start_auto_clear.png")
# Monedas SA
ESPECIAL_FS = P("dailies/fs_special.png")
MAZMORRA_EVENTO = P("dailies/event_dungeon.png")
MONEDA_SA = P("sa_coin.png")
TORRE_RELOJ = P("sa_coin_dungeon/clock_tower.png")
PISO_TORRE = P("sa_coin_dungeon/clock_tower_floor.png")
CANDADO = P("sa_coin_dungeon/fs_dungeon_lock.png")
MAZMORRA_MONEDAS = P("sa_coin_dungeon/coin_dungeon.png")  # mazmorras equivocadas: se sale con ESC
TORRE_CAOS = P("sa_coin_dungeon/tower_of_chaos.png")
TORRE_ROTA = P("sa_coin_dungeon/broken_clock_tower.png")
SIN_LLAVES = P("sa_coin_dungeon/no_keys.png")
VIDA_JEFE = P("sa_coin_dungeon/sa_boss_hp.png")
COFRE = P("sa_coin_dungeon/chest.png")
COFRES = {"Bronce": P("sa_coin_dungeon/chest_bronze.png"), "Plata": P("sa_coin_dungeon/chest_silver.png"),
          "Oro": P("sa_coin_dungeon/chest_gold.png")}
ORDEN_COFRES = ["Bronce", "Plata", "Oro"]
# "Try Again" del menu de pausa (captura del 2026-10-29): repite la pelea sin rendirse ni salir de la torre
REINTENTAR = P("sa_coin_dungeon/try_again.png")
# y el boton verde de su confirmacion ("You will not be able to receive the current rewards...")
CONFIRMAR_REINTENTAR = P("sa_coin_dungeon/try_again_confirmar.png")
INTENTOS_REINTENTAR = 4  # pausas sin ver "Try Again": se rinde como antes
MIN_SEGUNDOS_COFRE = 10  # el cofre sale a los 8-9 s: con 7 s el bot casi repite con un cofre de oro (2026-10-29)

DESLIZAR_DESDE, DESLIZAR_HASTA = (276, 800), (275, 650)  # lista de mazmorras de la especial (AutoFarming)
CENTRO_X = juego.COORD["centro"][0]
EQUIPO_POR_NOMBRE = "equipo:"  # en el historial: el equipo se guarda por su nombre del juego, no por sus heroes
# Flecha amarilla de volver (arriba a la izquierda), no la tecla ESC (como AutoFarming): en la prueba del
# 2026-10-29, al acabarse la repeticion, el bot paso mas de un minuto pulsando ESC sin salir de esa pantalla, y
# en el menu principal ESC abre "salir del juego".
VOLVER = (38, 62)
CADA_VOLVER_S = 2.5


class FuerteSolgres(Modo):
    """Lo comun: pociones de stamina, vueltas contadas y la tienda de Essette."""

    subtitulo_juego = "Fuerte Solgres"
    duracion = "según la mazmorra"

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.vueltas = self.pociones = 0
        self.vuelta_contada_hasta = 0.0
        self.nombre_equipo = ""  # el de la pantalla de preparacion ("Farm.Oro"): para saber que equipo es mas rapido

    def leer_equipo(self, p) -> None:
        """El nombre del equipo, en la pantalla de preparacion (la del boton Start): entre "- 3rd Floor -" y
        "Team List 15/15" (captura del 2026-10-29). Una vez por sesion."""
        if self.nombre_equipo:
            return
        from lumen import ocr

        lineas = [t.strip() for t, _ in ocr.lineas_con_posicion(p[120:240, 60:490])] if ocr.disponible() else []
        for i, linea in enumerate(lineas):
            if linea.lower().startswith("team list") and i > 0 and "floor" not in lineas[i - 1].lower():
                self.nombre_equipo = lineas[i - 1]
                self.log(f"Equipo: {self.nombre_equipo}.", "ok")
                return

    def equipo_de_la_sesion(self) -> list[str] | None:
        return [EQUIPO_POR_NOMBRE + self.nombre_equipo] if self.nombre_equipo else None

    def _stats(self, **mas):
        self.publicar_stats(victorias=self.vueltas, pociones=self.pociones, **mas)

    def comprobaciones_globales(self, pantalla, origen) -> bool:
        if self.clic_si(TIENDA_ESSETTE, pantalla, origen):
            return True
        return super().comprobaciones_globales(pantalla, origen)

    def _estamina(self, p, o) -> bool:
        """Sin estamina: usa una pocion si se puede; si no, termina. True si hizo algo."""
        if not juego.pocion_stamina.esta(p):
            return False
        limite = int(self.valores["max_pociones"])
        if not self.valores["pociones"] or (limite and self.pociones >= limite):
            self.log("Sin estamina y no puedo usar más pociones. Termino.", "aviso")
            self.publicar_stats(motivo_fin="sin_estamina")
            raise TerminarModo()
        if self.clic_si(juego.usar_pocion, p, o, umbral=0.8, espera=1.0):
            self.pociones += 1
            self._stats()
        return True

    def _contar_vuelta(self, p) -> None:
        """Cada pelea terminada de la repeticion automatica (la imagen dura varios fotogramas: 5 s de margen)."""
        if time.monotonic() < self.vuelta_contada_hasta or not VUELTA_TERMINADA.esta(p):
            return
        self.vuelta_contada_hasta = time.monotonic() + 5.0
        self.vueltas += 1
        self.log(f"Vuelta #{self.vueltas} terminada.", "ok")
        self._stats()
        meta = int(self.valores["victorias"])
        if meta and self.vueltas >= meta:
            self.log(f"Llegué a {meta} vueltas.", "ok")
            raise TerminarModo()


def _opciones_comunes() -> list[Opcion]:
    return [
        Opcion("victorias", "Vueltas (0 = sin límite)", "entero", 0, maximo=9999),
        Opcion("pociones", "Usar pociones de stamina", "si_no", False),
        Opcion("max_pociones", "Máximo de pociones (0 = sin límite)", "entero", 0, maximo=999),
    ]


class Oro(FuerteSolgres):
    id = "oro"
    nombre = "Oro"
    titulo_juego = "Gold Dungeon"
    descripcion = ("Farmea oro en el 6.º piso de la mazmorra de oro con la repetición automática. Puede usar "
                   "los tickets de salto. Empieza desde la Taberna o el menú Battle.")
    imagen = "gold_dungeon/gold_dungeon.png"
    nombres_estados = {"ir": "Entrando a la mazmorra de oro", "pelea": "Farmeando", "tickets": "Usando tickets"}
    opciones = _opciones_comunes() + [
        Opcion("tickets", "Usar tickets de salto", "si_no", False,
               ayuda="Con «Auto Use Settings» marcado en el juego. Gasta 30 por vez."),
        Opcion("max_tickets", "Máximo de tickets (0 = sin límite)", "entero", 0, maximo=99999),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.tickets = 0

    def estado_inicial(self):
        return "ir"

    def estados(self):
        return {"ir": self.ir, "pelea": self.pelea, "tickets": self.usar_tickets}

    def en_zona_segura(self) -> bool:
        return self.estado == "ir"

    def ir(self, p, o):
        if AUTO_CLEAR.esta(p) or EMPEZAR.esta(p):
            self.leer_equipo(p)
            self.log("En el 6.º piso de la mazmorra de oro.", "ok")
            return "pelea"
        self.clic_si(PISO_6, p, o, espera=1.0)
        self.clic_si(MAZMORRA_ORO, p, o, espera=1.0)
        self.clic_si(MAZMORRA_FS, p, o, espera=1.0)
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6, espera=1.0)
        return None

    def pelea(self, p, o):
        self._contar_vuelta(p)
        if self.clic_si(RESULTADO, p, o) or self.clic_si(juego.info_mision, p, o):  # al volver de los tickets
            return None
        if self._estamina(p, o):
            return None
        limite = int(self.valores["max_tickets"])
        if self.valores["tickets"] and not (limite and self.tickets >= limite):
            return "tickets"
        if self.clic_si(REPETIR_APAGADO, p, o):
            return None
        self.clic_si(EMPEZAR, p, o, espera=1.0)
        return None

    def usar_tickets(self, p, o):
        if RESULTADO.esta(p):
            return "pelea"
        if MAX_TICKETS.esta(p):  # MAX dos veces y Start del auto-clear (como AutoFarming)
            self.clic_si(MAX_TICKETS, p, o, espera=0.5)
            self.clic_si(MAX_TICKETS, p, o, espera=0.5)
            if self.clic_si(EMPEZAR_AUTO_CLEAR, p, o, espera=1.0):
                self.tickets += 30
                self.log(f"Tickets de salto usados: {self.tickets}.", "ok")
                self._stats(tickets=self.tickets)
            return None
        self.clic_si(AUTO_CLEAR, p, o, espera=1.0)
        return None


class MonedasSA(FuerteSolgres):
    id = "monedas_sa"
    nombre = "Monedas SA"
    titulo_juego = "Clock Tower"
    descripcion = ("Farmea monedas de superdespertar en la Torre del reloj de Fuerte Solgres (especial) con la "
                   "repetición automática. Gasta llaves de la mazmorra. Empieza desde la Taberna o el menú Battle.")
    imagen = "sa_coin.png"
    nombres_estados = {"ir": "Entrando a Fuerte Solgres", "abrir": "Abriendo la Torre del reloj",
                       "piso": "Eligiendo el piso", "preparar": "Preparando", "pelea": "Farmeando",
                       "reintentar": "Repitiendo (Try Again)", "reiniciar": "Repitiendo (cofre peor)",
                       "fin": "Vuelta terminada"}
    opciones = _opciones_comunes() + [
        Opcion("cofre", "Cofre mínimo del jefe", "lista", "Bronce", opciones=ORDEN_COFRES,
               ayuda="Si el jefe deja un cofre peor, el bot rinde la pelea y la repite."),
        Opcion("segundos_cofre", "Segundos de pelea sin cofre antes de repetir", "entero", 12, minimo=MIN_SEGUNDOS_COFRE,
               maximo=60,
               ayuda="El cofre sale a los 8-9 s de empezar la pelea, arriba a la izquierda. Si no sale, se repite: "
                     "sin cofre se pierde material."),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.reinicios = self.derrotas = self.sin_ver = 0
        self.ultimo_volver = 0.0
        self.pausas, self.reintentado_en = 0, None
        self.cofres = {nombre: 0 for nombre in ORDEN_COFRES}
        self._nueva_vuelta()

    def _nueva_vuelta(self):
        self.jefe_visto = self.cofre_visto = False
        self.jefe_desde: float | None = None
        self.pelea_desde: float | None = None  # cuando se vio la interfaz de esta pelea

    def estado_inicial(self):
        return "ir"

    def estados(self):
        return {"ir": self.ir, "abrir": self.abrir, "piso": self.piso, "preparar": self.preparar,
                "pelea": self.pelea, "reintentar": self.reintentar, "reiniciar": self.reiniciar, "fin": self.fin}

    def en_zona_segura(self) -> bool:
        return self.estado in ("ir", "abrir", "piso")

    def ir(self, p, o):
        self.clic_si(juego.menu_batalla, p, o, umbral=0.6, espera=1.0)
        self.clic_si(MAZMORRA_FS, p, o, espera=1.0)
        self.clic_si(ESPECIAL_FS, p, o, espera=1.0)
        if MONEDA_SA.esta(p) or TORRE_RELOJ.esta(p) or CANDADO.esta(p):
            return "abrir"
        return None

    def abrir(self, p, o):
        for equivocada, nombre in ((MAZMORRA_MONEDAS, "la de monedas"), (TORRE_CAOS, "la Torre del caos"),
                                   (TORRE_ROTA, "la Torre rota")):
            if equivocada.esta(p, 0.85):  # salir sin gastar una llave en otra mazmorra
                self.log(f"Abrí {nombre} por error: vuelvo atrás.", "aviso")
                self._volver(o)
                return None
        if SIN_LLAVES.esta(p, 0.9):
            self.log("No quedan llaves de la mazmorra. Termino.", "aviso")
            self.publicar_stats(motivo_fin="sin_llaves")
            raise TerminarModo()
        if PISO_TORRE.esta(p):
            return "piso"
        if self.clic_si(juego.ok, p, o, espera=1.0):  # abrir la torre con una llave
            self.vuelta_contada_hasta = 0.0
            self._nueva_vuelta()
            return None
        rect = MONEDA_SA.buscar(p, 0.7)
        if rect is not None:  # la Torre del reloj: se toca su fila
            entrada.clic((CENTRO_X, int(rect[1] + rect[3] / 2)), o, espera=1.0)
            return None
        if ATRAS.esta(p):  # en la lista de mazmorras sin ver la torre: deslizar
            candado = CANDADO.buscar(p)
            hacia_abajo = MAZMORRA_EVENTO.esta(p)
            if candado is not None:
                desde = (int(candado[0]), int(candado[1]))
                hasta = (desde[0], desde[1] - 150) if hacia_abajo else (desde[0], desde[1] + 150)
            else:
                desde, hasta = (DESLIZAR_DESDE, DESLIZAR_HASTA) if hacia_abajo else (DESLIZAR_HASTA, DESLIZAR_DESDE)
            entrada.arrastrar(desde, hasta, o)
        return None

    def piso(self, p, o):
        if EMPEZAR.esta(p):
            return "preparar"
        rect = PISO_TORRE.buscar(p)
        if rect is not None:
            entrada.clic((CENTRO_X, int(rect[1] + rect[3] / 2)), o, espera=1.0)
        return None

    def preparar(self, p, o):
        if EMPEZAR.esta(p):
            self.leer_equipo(p)
        if self.clic_si(REPETIR_APAGADO, p, o, umbral=0.8):
            return None
        if EMPEZAR.esta(p):
            self.log("¡A farmear la Torre del reloj!", "ok")
            return "pelea"
        return None

    def _cofre(self, p) -> str | None:
        """'Bronce', 'Plata' u 'Oro' segun el cofre que deja el jefe; None si no se ve o no esta claro."""
        rect = COFRE.buscar(p, 0.6)
        if rect is None:
            return None
        x, y, w, h = (int(v) for v in rect[:4])
        zona = p[max(0, y - 6):y + h + 6, max(0, x - 6):x + w + 6]
        mejor, valor = None, 0.7
        for nombre, plantilla in COFRES.items():
            for img in plantilla.imagenes:
                if zona.shape[0] < img.shape[0] or zona.shape[1] < img.shape[1]:
                    continue
                v = float(cv2.matchTemplate(zona, img, cv2.TM_CCOEFF_NORMED).max())
                if v > valor:
                    mejor, valor = nombre, v
        return mejor

    def pelea(self, p, o):
        if REPETICION_TERMINADA.esta(p, 0.8):
            self.log("Se acabó la repetición: vuelvo a abrir la torre.", "aviso")
            return "fin"
        if juego.derrota.esta(p) or juego.menu_batalla.esta(p, 0.6):
            if self._fuera_de_la_pelea(p):
                return "ir"
        if self._estamina(p, o):
            return None
        antes = self.vueltas
        self._contar_vuelta(p)
        if self.vueltas != antes:
            self._nueva_vuelta()
        self.clic_si(EMPEZAR, p, o, espera=1.0)
        # El cofre se busca desde el principio de la pelea (lo pidio el usuario: esperar al jefe dejaba poco tiempo
        # y el piso terminaba antes de repetir). Si llega el jefe y en unos segundos no hay cofre, se repite: sin
        # cofre se pierde material, que vale mas que la stamina.
        # Grabacion de 8 runs (2026-10-29): el cofre sale siempre 8-9 s despues de verse la interfaz de la pelea,
        # arriba a la izquierda. Si a los segundos_cofre (12) no ha salido, no va a salir: se repite ya.
        if juego.pausa.esta(p, 0.7):
            self.pelea_desde = self.pelea_desde or time.time()
        if VIDA_JEFE.esta(p, 0.7) and juego.pausa.esta(p, 0.7):
            self.jefe_visto = True
            self.jefe_desde = self.jefe_desde or time.time()
        if self.cofre_visto:
            return None
        tipo = self._cofre(p)
        minimo = self.valores["cofre"]
        if tipo is None:
            espera = max(MIN_SEGUNDOS_COFRE, int(self.valores["segundos_cofre"]))
            if self.pelea_desde is None or time.time() - self.pelea_desde < espera:
                return None
            self.sin_ver += 1
            self.publicar_stats(cofres_sin_ver=self.sin_ver)
            self.log(f"A los {espera} s no hay cofre: repito la pelea.", "aviso")
            return self._repetir()
        self.cofre_visto = True
        if ORDEN_COFRES.index(tipo) < ORDEN_COFRES.index(minimo):
            self.log(f"Cofre de {tipo.lower()} (quiero {minimo.lower()} o mejor): repito la pelea.", "aviso")
            return self._repetir()
        self.cofres[tipo] += 1
        self.log(f"Cofre de {tipo.lower()}: me lo quedo.", "ok")
        self._stats(**{f"cofres_{k.lower()}": v for k, v in self.cofres.items()})
        return None

    def _repetir(self):
        self.reinicios += 1
        self._nueva_vuelta()
        self.publicar_stats(reinicios=self.reinicios)
        self.pausas, self.reintentado_en = 0, None
        return "reintentar"

    def reintentar(self, p, o):
        """Pausa -> "Try Again": la pelea vuelve a empezar sin salir de la torre (lo enseno el usuario: ya no
        hace falta rendirse como en AutoFarming). Si "Try Again" no aparece, se rinde como antes."""
        if VUELTA_TERMINADA.esta(p) or REPETICION_TERMINADA.esta(p, 0.8):
            # La pelea termino sola antes de repetirla: se cobra la vuelta y se sigue
            self.log("La pelea terminó antes de repetirla: sigo farmeando.", "aviso")
            self._nueva_vuelta()
            return "pelea"
        # Ultimo vistazo antes de abrir la pausa (con la pausa abierta el cofre queda oscurecido): si aparecio un
        # cofre bueno (uno de oro casi se pierde, 2026-10-29), no se repite.
        if self.pausas == 0 and self.reintentado_en is None and self._cofre_que_sirve(p):
            return "pelea"
        if REINTENTAR.esta(p, 0.85):
            self.clic_si(REINTENTAR, p, o, umbral=0.85, espera=1.5)
            self.reintentado_en = time.time()
            return None
        if self.reintentado_en is not None:
            # El juego pide confirmar (prueba del 2026-10-29: el bot se quedo quieto en esta ventana)
            if self.clic_si(CONFIRMAR_REINTENTAR, p, o, umbral=0.85, espera=2.0) or self.clic_si(juego.ok, p, o, espera=1.0):
                self.reintentado_en = time.time()
                return None
            if (juego.pausa.esta(p, 0.7) and not CONFIRMAR_REINTENTAR.esta(p, 0.85)) or time.time() - self.reintentado_en > 30:
                self.log("Pelea repetida con «Try Again».", "ok")
                return "pelea"
            return None
        if self._fuera_de_la_pelea(p):
            return "ir"
        if self.pausas >= INTENTOS_REINTENTAR:
            self.log("No veo «Try Again»: me rindo y vuelvo a abrir la torre.", "aviso")
            return "reiniciar"
        if self.clic_si(juego.pausa, p, o, umbral=0.7, espera=1.0):
            self.pausas += 1
        return None

    def _cofre_que_sirve(self, p) -> bool:
        """Si a ultima hora se ve un cofre igual o mejor que el minimo, se cancela la repeticion y se cobra."""
        tipo = self._cofre(p)
        if tipo is None or ORDEN_COFRES.index(tipo) < ORDEN_COFRES.index(self.valores["cofre"]):
            return False
        self.reinicios -= 1  # al final no se repitio
        self.cofre_visto = True
        self.cofres[tipo] += 1
        self.log(f"¡Cofre de {tipo.lower()} justo a tiempo! No repito: me lo quedo.", "ok")
        self._stats(reinicios=self.reinicios, **{f"cofres_{k.lower()}": v for k, v in self.cofres.items()})
        return True

    def _fuera_de_la_pelea(self, p) -> bool:
        """La pelea ya termino (el equipo murio, 2026-10-29) y el juego volvio a un menu: no hay pausa que tocar.
        Se cuenta como derrota y se vuelve a entrar a la torre."""
        if not (juego.menu_batalla.esta(p, 0.6) or MAZMORRA_FS.esta(p) or ATRAS.esta(p) or juego.derrota.esta(p)):
            return False
        self.derrotas += 1
        self.log(f"La pelea terminó sin el cofre (¿el equipo murió?). Vuelvo a la torre. Derrotas: {self.derrotas}.", "aviso")
        self.publicar_stats(derrotas=self.derrotas)
        self._nueva_vuelta()
        return True

    def _volver(self, o):
        """Un paso atras con la flecha de volver (como mucho cada CADA_VOLVER_S, para dar tiempo a la pantalla)."""
        if time.time() - self.ultimo_volver >= CADA_VOLVER_S:
            entrada.clic(VOLVER, o, espera=1.0)
            self.ultimo_volver = time.time()

    def reiniciar(self, p, o):
        """Rendirse y volver a abrir la torre (OK, Forfeit o la flecha de volver hasta la lista de mazmorras)."""
        if juego.carga_taberna.esta(p) or ATRAS.esta(p) or MONEDA_SA.esta(p):
            return "abrir"
        if self.clic_si(juego.ok, p, o, espera=1.0) or self.clic_si(juego.rendirse, p, o, espera=1.0):
            return None
        if self.clic_si(juego.pausa, p, o, umbral=0.7, espera=1.0):  # en la pelea: el Forfeit esta en la pausa
            return None
        self._volver(o)
        return None

    def fin(self, p, o):
        if ATRAS.esta(p) or MONEDA_SA.esta(p) or juego.menu_batalla.esta(p, 0.6):
            self._nueva_vuelta()
            return "ir"
        if CARGA_FS.esta(p):
            return None
        if self.clic_si(juego.ok, p, o, espera=1.0) or self.clic_si(RESULTADO, p, o, espera=1.0):
            return None
        self._volver(o)
        return None

    def al_terminar(self):
        cofres = ", ".join(f"{v} de {k.lower()}" for k, v in self.cofres.items() if v)
        self.log(f"Monedas SA: {self.vueltas} vueltas, {self.reinicios} repetidas, {self.derrotas} derrotas"
                 + (f"; cofres: {cofres}" if cofres else "") + ".", "ok")


TODOS = [Oro, MonedasSA]
