"""Fuerte Solgres: Oro (mazmorra de oro, 6.o piso) y Monedas SA (Torre del reloj de la mazmorra especial).

Los dos se juegan con la repeticion automatica del juego ("Auto Repeat"): el bot solo llega, la activa,
pulsa Start y cuenta las vueltas. Flujo de AutoFarming (GoldFarmer y SADungeonFarmer, MIT), con sus
imagenes en assets/imagenes (gold_dungeon/, sa_coin_dungeon/ y otras sueltas).

Monedas SA ademas mira el cofre que deja el jefe: si es peor que el elegido, rinde la pelea y la repite
(como AutoFarming), para no gastar la vuelta en un cofre de bronce.
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

DESLIZAR_DESDE, DESLIZAR_HASTA = (276, 800), (275, 650)  # lista de mazmorras de la especial (AutoFarming)
CENTRO_X = juego.COORD["centro"][0]


class FuerteSolgres(Modo):
    """Lo comun: pociones de stamina, vueltas contadas y la tienda de Essette."""

    subtitulo_juego = "Fuerte Solgres"
    duracion = "según la mazmorra"

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.vueltas = self.pociones = 0
        self.vuelta_contada_hasta = 0.0

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
                       "reiniciar": "Repitiendo (cofre peor)", "fin": "Vuelta terminada"}
    opciones = _opciones_comunes() + [
        Opcion("cofre", "Cofre mínimo del jefe", "lista", "Bronce", opciones=ORDEN_COFRES,
               ayuda="Si el jefe deja un cofre peor, el bot rinde la pelea y la repite."),
        Opcion("intentos_cofre", "Veces que busca el cofre antes de repetir", "entero", 3, minimo=1, maximo=20),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.reinicios = 0
        self.cofres = {nombre: 0 for nombre in ORDEN_COFRES}
        self._nueva_vuelta()

    def _nueva_vuelta(self):
        self.jefe_visto = self.cofre_visto = False
        self.intentos = 0

    def estado_inicial(self):
        return "ir"

    def estados(self):
        return {"ir": self.ir, "abrir": self.abrir, "piso": self.piso, "preparar": self.preparar,
                "pelea": self.pelea, "reiniciar": self.reiniciar, "fin": self.fin}

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
                entrada.tecla("esc")
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
        if self._estamina(p, o):
            return None
        antes = self.vueltas
        self._contar_vuelta(p)
        if self.vueltas != antes:
            self._nueva_vuelta()
        self.clic_si(EMPEZAR, p, o, espera=1.0)
        # El cofre se mira cuando ya esta el jefe (con la interfaz a la vista) y hasta encontrarlo.
        if VIDA_JEFE.esta(p, 0.7) and juego.pausa.esta(p, 0.7):
            self.jefe_visto = True
        if not self.jefe_visto or self.cofre_visto:
            return None
        tipo = self._cofre(p)
        minimo = self.valores["cofre"]
        if tipo is None:
            self.intentos += 1
            if self.intentos <= int(self.valores["intentos_cofre"]):
                return None
            self.log("No veo el cofre del jefe: repito la pelea.", "aviso")
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
        return "reiniciar"

    def reiniciar(self, p, o):
        """Rendirse y volver a abrir la torre (como AutoFarming: OK, Forfeit o ESC hasta la Taberna)."""
        if juego.carga_taberna.esta(p):
            return "abrir"
        if self.clic_si(juego.ok, p, o, espera=1.0) or self.clic_si(juego.rendirse, p, o, espera=1.0):
            return None
        entrada.tecla("esc")
        return None

    def fin(self, p, o):
        if ATRAS.esta(p) or MONEDA_SA.esta(p):
            self._nueva_vuelta()
            return "ir"
        if not CARGA_FS.esta(p):
            entrada.tecla("esc")
        return None

    def al_terminar(self):
        cofres = ", ".join(f"{v} de {k.lower()}" for k, v in self.cofres.items() if v)
        self.log(f"Monedas SA: {self.vueltas} vueltas, {self.reinicios} repetidas"
                 + (f"; cofres: {cofres}" if cofres else "") + ".", "ok")


TODOS = [Oro, MonedasSA]
