"""Floor 4 del pajaro (Hraesvelgr) y del ciervo (Eikthyrnir), 2026-11-10.

Guiones traducidos de AutoFarming (github.com/PhantomPilots/AutoFarming, licencia MIT):
``scripts/utilities/bird_floor4_fighting_strategies.py`` y ``scripts/utilities/deer_floor4_fighting_strategies.py``. AutoFarming
reconoce las cartas con imagenes y modelos que ya no sirven con el diseno actual (lumen/cartas.py); aqui cada
carta se reconoce por su nombre (inteligencia.agrupar_por_dibujo) y lo que hace se lee de su texto (7dshub):
"Heals" = curacion, "Removes Buffs" = quita buffs, "Amplify"/"Power Strike" = contra la inmortalidad.

Cuando el guion no dice nada (o lo que pide no se puede jugar), juega el modo inteligente de Lumen, que usa lo
aprendido en cada pelea ("pajaro_f4", "ciervo_f4").

Equipos (BOTS_README de AutoFarming):
- Pajaro: cualquiera; recomendado Meliodas traidor (o Tyr verde), Thor, Megellda azul y Shion.
- Ciervo: Thor, Jormungand verde, Freyr y Tyr verde (o Hel verde), todos con equipo de ataque. AutoFarming gana
  ~60 % con Tyr y ~30 % con Hel.
"""

import re
from functools import lru_cache

from lumen import entrada, inteligencia, juego, ocr
from lumen import personajes as P
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.modos import bestias_pisos1a3 as B13
from lumen.modos.bestias_pisos1a3 import ATRAS, PUNTO_ATRAS, EstrategiaInteligente
from lumen.modos.perros_piso4 import PerrosPiso4, Reiniciar

# ------------------------------------------------------------------ las cartas


def _base(c: Carta | None) -> str:
    return ((c.nombre if c else "") or "").split("@")[0]


def heroe(c: Carta | None) -> str:
    return _base(c).partition(".")[0]


def habilidad(c: Carta | None) -> str:
    return _base(c).partition(".")[2]


def color(c: Carta | None) -> str:
    """rojo, azul o verde (el final del id del heroe)."""
    h = heroe(c)
    return next((x for x in ("rojo", "azul", "verde") if h.endswith("_" + x)), "")


def _es(c, *claves) -> bool:
    h = f"_{heroe(c)}_"
    return any(f"_{k}_" in h or h.startswith(f"_{k}") for k in claves)


def es_thor(c) -> bool:
    return "thor_the_god_of_thunder" in heroe(c)


def es_tyr(c) -> bool:
    return "god_of_war_tyr" in heroe(c)


def es_hel(c) -> bool:
    return _es(c, "hel")


def es_jorm(c) -> bool:
    return "jormungand" in heroe(c)


def es_freyr(c) -> bool:
    return "freyr" in heroe(c)


def es_meli_traidor(c) -> bool:
    return "traitor_meliodas" in heroe(c)


def es_ulti(c: Carta) -> bool:
    return c.tipo == TipoCarta.ULTI or habilidad(c) == "ulti"


@lru_cache(maxsize=1)
def _textos() -> dict:
    from lumen.ia import decidir as dec

    return dec.textos_por_habilidad()


@lru_cache(maxsize=2048)
def _texto_nombre(nombre: str) -> str:
    from lumen.valor_cartas import nombre_de_habilidad

    pid, _, cid = nombre.partition(".")
    pj = P.cargar().get(pid)
    carta = pj.cartas.get(cid) if pj else None
    return _textos().get(nombre_de_habilidad(carta.descripcion), "") if carta else ""


def texto(c: Carta | None) -> str:
    nombre = _base(c)
    if "." not in nombre:
        return ""
    try:
        return _texto_nombre(nombre)
    except Exception:
        return ""


def es_curacion(c) -> bool:
    return bool(re.search(r"\bheals?\b|restores? the hp|recover", texto(c), re.I))


def quita_buffs(c) -> bool:
    return bool(re.search(r"removes? buffs", texto(c), re.I))


def contra_inmortalidad(c) -> bool:
    """Las "amplify" de AutoFarming: Amplify o Power Strike (quitan inmortalidades del pajaro en la fase 3)."""
    return bool(re.search(r"amplify damage|power strike damage", texto(c), re.I))


def dano(c) -> float:
    m = re.findall(r"(\d+)% of attack", texto(c), re.I)
    return max((float(x) for x in m), default=0.0)


def es_fuerte(c) -> bool:
    """Las "hard hitting" de AutoFarming: ultis y golpes grandes."""
    return es_ulti(c) or dano(c) >= 190 or contra_inmortalidad(c)


def jugable(c: Carta) -> bool:
    return c.jugable


def con_carta(c: Carta) -> bool:
    return c.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA)


def rango(c: Carta) -> int:
    return c.rango.value


def fusionan(a: Carta | None, b: Carta | None) -> bool:
    """Dos cartas iguales y del mismo rango (bronce o plata) se fusionan al quedar juntas."""
    if a is None or b is None or not con_carta(a) or not con_carta(b) or es_ulti(a) or es_ulti(b):
        return False
    return bool(_base(a)) and _base(a) == _base(b) and a.rango == b.rango and a.rango in (Rango.BRONCE, Rango.PLATA)


def indices(mano: list[Carta], cond, orden=rango) -> list[int]:
    """Los indices de las cartas jugables que cumplen ``cond``, de menor a mayor ``orden``."""
    return sorted((i for i, c in enumerate(mano) if jugable(c) and cond(c)), key=lambda i: orden(mano[i]))


# ------------------------------------------------------------------ base


class EstrategiaPiso4(EstrategiaInteligente):
    """Primero el guion; si no dice nada (o pide algo imposible), el modo inteligente."""

    def __init__(self):
        super().__init__(enemigos=1)
        self.modo = None  # el modo, para mirar la pantalla (lo pone Piso4)
        self.jugadas: list[Carta] = []  # cartas jugadas en este turno (las "picked_cards" de AutoFarming)
        self.nueva_pelea()

    def nueva_pelea(self):
        self.jugadas = []
        self._contexto_jugadas = None
        self._cartas_por_accion = {}

    def pantalla(self):
        return getattr(self.modo, "_ultima_p", None) if self.modo is not None else None

    def ve(self, plantilla, umbral: float = 0.7) -> bool:
        p = self.pantalla()
        try:
            return p is not None and bool(plantilla.esta(p, umbral))
        except Exception:
            return False

    def guion(self, fase: int, turno: int, accion: int, mano: list[Carta]):
        """idx (jugar), (i, j) (mover i sobre j) o None (que decida el modo inteligente)."""
        return None

    def decidir(self, fase, turno, accion, mano, total=4):
        try:
            inteligencia.agrupar_por_dibujo(mano, self.jugador._identificar)  # nombres de las cartas
        except Exception:
            pass
        contexto = (fase, turno)
        if contexto != self._contexto_jugadas:
            self._cartas_por_accion = {}
            self._contexto_jugadas = contexto
        # Solo cuentan las posiciones anteriores. Reintentar no equivale a jugar
        # otra carta; los movimientos dejan una posicion sin carta, no desplazan colores.
        self._cartas_por_accion = {a: c for a, c in self._cartas_por_accion.items() if a < accion}
        self.jugadas = [self._cartas_por_accion[a] for a in sorted(self._cartas_por_accion)]
        try:
            jugada = self.guion(fase or 1, turno, accion, mano)
        except Reiniciar:
            raise
        except Exception:
            jugada = None
        jugada = self._valida(jugada, mano)
        if jugada is None:
            jugada = self._respaldo(fase, turno, accion, mano, total)
        if isinstance(jugada, int) and 0 <= jugada < len(mano):
            self._cartas_por_accion[accion] = mano[jugada]
            self.jugadas = [self._cartas_por_accion[a] for a in sorted(self._cartas_por_accion)]
        return jugada, None, False

    def _respaldo(self, fase, turno, accion, mano, total):
        return super().decidir(fase, turno, accion, mano, total)[0]

    def carta_en_accion(self, accion):
        if self._contexto_jugadas is not None:
            return self._cartas_por_accion.get(accion)
        # Permite usar el guion aislado con una lista de cartas ya colocadas.
        return self.jugadas[accion] if 0 <= accion < len(self.jugadas) else None

    def por_defecto(self, fase, turno, accion, mano, sin=()):
        """El modo inteligente sin poder jugar las cartas ``sin`` (indices)."""
        antes = {i: mano[i].tipo for i in sin if 0 <= i < len(mano) and jugable(mano[i])}
        for i in antes:
            mano[i].tipo = TipoCarta.BLOQUEADA
        try:
            return super().decidir(fase, turno, accion, mano, 4)[0]
        except Exception:
            return None
        finally:
            for i, tipo in antes.items():
                mano[i].tipo = tipo

    @staticmethod
    def _valida(jugada, mano):
        n = len(mano)
        if jugada is None or n == 0:
            return None
        if isinstance(jugada, (tuple, list)):
            i, j = (int(x) % n for x in jugada)
            return (i, j) if i != j and con_carta(mano[i]) and con_carta(mano[j]) else None
        i = int(jugada) % n
        return i if jugable(mano[i]) else None


# ------------------------------------------------------------------ pajaro


class EstrategiaPajaro4(EstrategiaPiso4):
    destino = "pajaro_piso4"

    def nueva_pelea(self):
        super().nueva_pelea()
        self.escudo = False  # fase 2: con 3 cartas de plata en un turno el siguiente se pega con todo

    # --- ayudas
    def _plata_por_fusion(self, mano):
        """Mover una carta de bronce sobre su pareja (no contigua) para hacer una de plata."""
        for i, c in enumerate(mano):
            for j in range(i + 2, len(mano)):
                if c.rango == Rango.BRONCE and fusionan(c, mano[j]) and (
                        j != i + 2 or mano[i + 1].rango == Rango.PLATA):
                    return (i, j)
        return None

    def _carta_que_fusiona(self, mano, sin_platas=True):
        for i in range(1, len(mano) - 1):
            if not jugable(mano[i]) or not fusionan(mano[i - 1], mano[i + 1]):
                continue
            if sin_platas and (mano[i - 1].rango == Rango.PLATA or mano[i].rango == Rango.PLATA):
                continue
            return i
        return None

    def _rompe_platas(self, mano, i) -> bool:
        """Jugar la carta i juntaria dos de plata (se fusionarian en oro y se perderian para la fase 2)."""
        return 0 < i < len(mano) - 1 and fusionan(mano[i - 1], mano[i + 1]) and mano[i - 1].rango == Rango.PLATA

    def _limpiar(self, mano, primero_meli=True):
        """El pajaro bloquea habilidades: area de Meliodas traidor y una curacion."""
        meli_area = indices(mano, lambda c: es_meli_traidor(c) and habilidad(c) == "skill_2")
        curas = indices(mano, es_curacion)
        meli_jugada = any(es_meli_traidor(c) and habilidad(c) == "skill_2" for c in self.jugadas)
        cura_jugada = any(es_curacion(c) for c in self.jugadas)
        orden = ((meli_area, meli_jugada), (curas, cura_jugada)) if primero_meli else \
            ((curas, cura_jugada), (meli_area, meli_jugada))
        for lista, ya in orden:
            if lista and not ya:
                return lista[0]
        return None

    def guion(self, fase, turno, accion, mano):
        if fase == 1:
            return self._fase1(turno, accion, mano)
        if fase == 2:
            return self._fase2(turno, accion, mano)
        if fase == 3:
            return self._fase3(turno, accion, mano)
        return self._fase4(turno, accion, mano)

    def _fase1(self, turno, accion, mano):
        platas = [i for i, c in enumerate(mano) if c.rango == Rango.PLATA and con_carta(c)]
        if self.ve(juego.bloqueo_habilidades):
            if (i := self._limpiar(mano)) is not None:
                return i
        elif len(platas) < 3 and accion <= 1 and (m := self._plata_por_fusion(mano)) is not None:
            return m
        for i in range(1, len(mano) - 1):  # una de bronce entre dos iguales de bronce: sale una de plata
            if jugable(mano[i]) and fusionan(mano[i - 1], mano[i + 1]) and mano[i].rango == Rango.BRONCE \
                    and mano[i - 1].rango == Rango.BRONCE:
                return i
        if ultis := indices(mano, es_ulti, orden=lambda c: 0):
            return ultis[-1]
        # Guardar al menos 3 de plata para la fase 2 (se pueden gastar si hay mas de 4)
        candidatas = [i for i in range(len(mano) - 1, -1, -1) if jugable(mano[i])
                      and (mano[i].rango != Rango.PLATA or len(platas) > 4) and not es_curacion(mano[i])
                      and not (es_meli_traidor(mano[i]) and habilidad(mano[i]) == "skill_2")
                      and not self._rompe_platas(mano, i)]
        if not candidatas:
            return (-1, -2) if not fusionan(mano[-1], mano[-2]) else (-1, -3)
        sueltas = [i for i in candidatas
                   if mano[i].rango != Rango.BRONCE or not any(fusionan(mano[i], mano[j]) for j in range(len(mano)) if j != i)]
        return (sueltas or candidatas)[0]

    def _fase2(self, turno, accion, mano):
        platas = [i for i in indices(mano, lambda c: c.rango == Rango.PLATA, orden=lambda c: 0)]
        platas_jugadas = [c for c in self.jugadas if c.rango == Rango.PLATA]
        bloqueadas = any(c.tipo == TipoCarta.BLOQUEADA for c in mano)
        curas = indices(mano, es_curacion)
        if bloqueadas and curas:
            return curas[-1]
        jugada = None
        if self.escudo:  # con escudo: con todo
            ultis = indices(mano, es_ulti, orden=lambda c: 0)
            fuertes = sorted(indices(mano, es_fuerte), key=lambda i: rango(mano[i]), reverse=True)
            jugada = ultis[-1] if ultis else (fuertes[-1] if fuertes else None)
            if accion == 3:
                self.escudo = False
        else:  # sin escudo: 3 de plata en el turno
            if len(platas) + len(platas_jugadas) <= 2 and (m := self._plata_por_fusion(mano)) is not None:
                return m
            libres = 4 - accion
            if min(len(platas), libres) + len(platas_jugadas) >= 3 and platas and len(platas_jugadas) < 3:
                jugada = platas[-1]
                if len(platas_jugadas) + 1 == 3 and accion == 3:
                    self.escudo = True
        if jugada is not None:
            return jugada
        if (i := self._carta_que_fusiona(mano)) is not None:
            return i
        if ultis := indices(mano, es_ulti, orden=lambda c: 0):
            return ultis[-1]
        if curas and not any(es_curacion(c) for c in self.jugadas):
            return curas[-1]
        bronces = [i for i in range(len(mano) - 1, -1, -1) if jugable(mano[i]) and mano[i].rango == Rango.BRONCE]
        if 7 in bronces:
            return 7
        for i in bronces:
            if not self._rompe_platas(mano, i):
                return i
        return None

    def _fase3(self, turno, accion, mano):
        self.escudo = False
        curas = indices(mano, es_curacion)
        if self.ve(juego.bloqueo_habilidades, 0.6) and (i := self._limpiar(mano, primero_meli=False)) is not None:
            return i
        p = self.pantalla()
        try:
            inmortales = len(juego.inmortalidad.buscar_todas(p, 0.7)) if p is not None else 0
        except Exception:
            inmortales = 0
        quedan = inmortales - sum(contra_inmortalidad(c) for c in self.jugadas)
        if quedan > 0 and (amp := indices(mano, contra_inmortalidad, orden=lambda c: 0)):
            return amp[-1]
        if quedan <= 0 and inmortales >= 0 and (ataque := indices(mano, lambda c: not es_ulti(c) and not es_curacion(c),
                                                                    orden=lambda c: 0)):
            return ataque[-1]
        for i in range(1, len(mano) - 1):
            if jugable(mano[i]) and fusionan(mano[i - 1], mano[i + 1]) and not self._ulti_meli(mano[i]):
                return i
        if curas and not any(es_curacion(c) for c in self.jugadas):
            return curas[-1]
        if ultis := indices(mano, lambda c: es_ulti(c) and not self._ulti_meli(c), orden=lambda c: 0):
            return ultis[-1]
        libres = [i for i, c in enumerate(mano) if jugable(c)]
        if len(libres) == 1:
            return libres[0]
        resto = [i for i in libres if not self._ulti_meli(mano[i])]
        return resto[-1] if resto else None

    @staticmethod
    def _ulti_meli(c) -> bool:
        return es_meli_traidor(c) and es_ulti(c)

    def _fase4(self, turno, accion, mano):
        if self.ve(juego.evasion, 0.7):
            # La ulti de Meliodas traidor quita buffs y posturas: la evasion
            if ulti := indices(mano, lambda c: self._ulti_meli(c) or (es_ulti(c) and quita_buffs(c)), orden=lambda c: 0):
                return ulti[-1]
            if not any(self._ulti_meli(c) for c in self.jugadas):
                for cond in (es_curacion, lambda c: es_meli_traidor(c) and habilidad(c) == "skill_2", es_ulti,
                             lambda c: not es_fuerte(c)):
                    if lista := indices(mano, cond, orden=lambda c: 0):
                        return lista[-1]
        curas = indices(mano, es_curacion)
        if curas and not any(es_curacion(c) for c in self.jugadas):
            return curas[-1]
        fuertes = indices(mano, lambda c: es_fuerte(c) and not self._ulti_meli(c), orden=lambda c: 0)
        if fuertes:
            thor = [i for i in fuertes if es_thor(mano[i])]
            otras = [i for i in fuertes if i not in thor]
            if thor and accion == 3:
                return thor[0]
            orden = thor[:1] + otras + thor[1:]
            return orden[-1]
        sin = [i for i, c in enumerate(mano) if self._ulti_meli(c)]
        return self.por_defecto(4, turno, accion, mano, sin=sin)


# ------------------------------------------------------------------ ciervo


class EstrategiaCiervo4(EstrategiaPiso4):
    destino = "ciervo_piso4"

    def nueva_pelea(self):
        super().nueva_pelea()
        self.color_turno = None

    @staticmethod
    def _por_rango(mano, cond, ultis_al_final=False):
        clave = (lambda c: -rango(c) if es_ulti(c) else rango(c)) if ultis_al_final else rango
        return indices(mano, cond, orden=clave)

    def _grupos(self, mano, ultis_al_final=False):
        return {col: self._por_rango(mano, lambda c, col=col: color(c) == col, ultis_al_final)
                for col in ("verde", "rojo", "azul")}

    def guion(self, fase, turno, accion, mano):
        if fase == 1:
            return self._fase1(turno, accion, mano)
        if fase == 2:
            return self._fase2(turno, accion, mano)
        if fase == 3:
            return self._fase3(turno, accion, mano)
        return self._fase4(turno, accion, mano)

    def _fase1(self, turno, accion, mano):
        thor = self._por_rango(mano, es_thor)
        tyr_hel = self._por_rango(mano, lambda c: es_tyr(c) or es_hel(c))
        jorm = self._por_rango(mano, es_jorm)
        freyr = self._por_rango(mano, es_freyr)
        rojas = self._por_rango(mano, lambda c: color(c) == "rojo")
        if turno <= 1:  # apertura: Tyr/Hel baja, Jorm (o Freyr/roja), Thor baja, Tyr/Hel alta
            if accion == 0:
                return tyr_hel[0] if tyr_hel else None
            if accion == 1:
                return (jorm or freyr or rojas or [None])[-1]
            if accion == 2:
                return thor[0] if thor else None
            return tyr_hel[-1] if tyr_hel else None
        if turno == 2 and thor:
            return (thor[0], thor[0] + 1) if accion <= 2 else thor[-1]
        if turno == 3:
            mover = tyr_hel or jorm
            if not mover:
                return None
            if accion < 2:
                return (mover[0], mover[0] + 1)
            if accion == 2:
                return thor[0] if len(thor) > 1 else (mover[0], mover[0] + 1)
            return thor[0] if thor else None
        return None

    def _tiene_ulti(self, cartas, cond) -> bool:
        return any(es_ulti(c) and cond(c) for c in cartas)

    def _respaldo(self, fase, turno, accion, mano, total):
        if fase == 2:
            return self._mover_para_ulti(mano)
        return super()._respaldo(fase, turno, accion, mano, total)

    @staticmethod
    def _movimiento_valido(mano, origen):
        otros = [i for i, c in enumerate(mano) if i != origen and con_carta(c)]
        if not otros:
            raise Reiniciar("Ciervo: no hay dos cartas para mover sin atacar; espero otra lectura")
        return origen, min(otros, key=lambda i: abs(i - origen))

    def _mover_para_ulti(self, mano):
        """Mover una carta del heroe que aun no tiene la ulti (asi se carga)."""
        todas = list(mano) + list(self.jugadas)
        unidades = [(es_tyr, self._por_rango(mano, es_tyr)), (es_hel, self._por_rango(mano, es_hel)),
                    (es_freyr, self._por_rango(mano, lambda c: color(c) == "rojo")),
                    (es_jorm, self._por_rango(mano, es_jorm)),
                    (es_thor, self._por_rango(mano, lambda c: color(c) == "azul"))]
        for cond, cartas in unidades:
            if cartas and not self._tiene_ulti(todas, cond):
                return self._movimiento_valido(mano, cartas[0])
        cartas = [i for i, c in enumerate(mano) if con_carta(c)]
        if len(cartas) < 2:
            raise Reiniciar("Ciervo: no hay dos cartas para mover sin atacar; espero otra lectura")
        return self._movimiento_valido(mano, cartas[-2])

    def _fase2(self, turno, accion, mano):
        grupos = self._grupos(mano, ultis_al_final=True)
        cura = [i for i in grupos["verde"] if es_jorm(mano[i]) and es_curacion(mano[i])]
        if cura:  # la curacion de Jormungand la primera de las verdes
            grupos["verde"] = [cura[-1]] + [i for i in grupos["verde"] if i != cura[-1]]
        rojas_total = sum(color(c) == "rojo" for c in list(mano) + list(self.jugadas))
        if rojas_total > 1 and grupos["rojo"] and turno == 1:  # doble roja
            if accion == 0:
                return grupos["rojo"][0]
            if accion <= 2:
                return self._movimiento_valido(mano, grupos["rojo"][0])
            return grupos["rojo"][0]
        if accion == 0 or self.color_turno is None:
            n = turno - 2
            colores = ["verde", "azul"]
            colores = colores[-n % 2:] + colores[:-n % 2] + ["rojo"]
            self.color_turno = next((c for c in colores if len(grupos[c]) >= 3),
                                    max(("verde", "azul"), key=lambda k: len(grupos[k])))
        elegidas = grupos[self.color_turno]
        if accion <= 2 and elegidas:
            if accion == 2 and self.color_turno == "verde":
                curas = self._por_rango(mano, lambda c: es_jorm(c) and es_curacion(c))
                if curas:
                    return curas[-1]
            return elegidas[-1]
        return self._mover_para_ulti(mano)

    def _fase3(self, turno, accion, mano):
        verdes = self._por_rango(mano, lambda c: color(c) == "verde")
        quita = [i for i in verdes if quita_buffs(mano[i])]
        if quita:  # la que quita buffs, la ultima en elegirse
            verdes = [quita[0]] + [i for i in verdes if i != quita[0]]
        grupos = {"verde": verdes,
                  "rojo": self._por_rango(mano, lambda c: color(c) == "rojo" and not (es_freyr(c) and es_ulti(c))),
                  "azul": self._por_rango(mano, lambda c: color(c) == "azul")}
        verdes_total = sum(color(c) == "verde" for c in list(mano) + list(self.jugadas))
        if turno == 1 and accion <= 2 and verdes_total >= 3 and verdes:
            self.color_turno = "verde"
            return verdes[-1]
        if accion == 0 or self.color_turno is None:
            self.color_turno = max(("rojo", "verde", "azul"), key=lambda k: len(grupos[k]))
        elegidas = grupos[self.color_turno]
        if accion <= 2 and elegidas:
            return elegidas[-1]
        if accion > 2:
            mayor = max(grupos.values(), key=len)
            for i in reversed(mayor):
                if not (es_freyr(mano[i]) and es_ulti(mano[i])):  # la ulti de Freyr se guarda para la fase 4
                    return i
        return None

    def _fase4(self, turno, accion, mano):
        if self.ve(juego.contraataque):
            if hel_ulti := self._por_rango(mano, lambda c: es_hel(c) and es_ulti(c)):
                return hel_ulti[-1]
        rojas = self._por_rango(mano, lambda c: color(c) == "rojo")
        azules = self._por_rango(mano, lambda c: color(c) == "azul")
        verdes = self._por_rango(mano, lambda c: color(c) == "verde")
        if turno <= 3:  # las ultis al final
            azules, verdes = azules[::-1], verdes[::-1]
            if turno <= 2:
                rojas = rojas[::-1]
            primera = self.carta_en_accion(0)
            if accion == 3 and not (primera is not None and es_hel(primera) and es_ulti(primera)):
                return self._mover_para_ulti(mano)
        quita = [i for i in verdes if quita_buffs(mano[i])]
        if quita:
            verdes = [quita[0]] + [i for i in verdes if i != quita[0]]
        if accion == 0 and turno == 1:
            for lista in (rojas, verdes, azules):
                if lista:
                    return lista[-1]
        elif accion == 0:
            for buff, lista in ((juego.buff_azul, azules), (juego.buff_rojo, rojas), (juego.buff_verde, verdes)):
                if self.ve(buff) and lista:
                    return lista[-1]
        ultima = self.carta_en_accion(accion - 1) if accion > 0 else None
        if accion == 1 and ultima is not None and es_hel(ultima) and es_ulti(ultima) and not self.ve(juego.buff_verde):
            ultima = None  # la ulti de Hel no puso el buff verde: se empieza la ruleta otra vez
        if ultima is not None:
            if color(ultima) == "verde" and azules:
                return azules[-1]
            if color(ultima) == "rojo" and verdes:
                if turno == 3 and (q := [i for i in verdes if quita_buffs(mano[i])]):
                    return q[-1]
                return verdes[-1]
            if color(ultima) == "azul" and rojas:
                return rojas[-1]
        sin = [i for i, c in enumerate(mano) if es_ulti(c)]
        return self.por_defecto(4, turno, accion, mano, sin=sin)


# ------------------------------------------------------------------ los modos


class Piso4(PerrosPiso4):
    """Floor 4 de una bestia con guion propio (la navegacion y la pelea, las de los perros del Floor 4)."""

    fases = 4
    MINUTOS_PELEA = 15
    equipo = None  # se juega con el equipo puesto (el guion reconoce las cartas por su nombre)
    rendirse_si_bloqueada = False
    talento_turno_1 = True
    equipo_recomendado = ""
    clase_estrategia = EstrategiaPiso4

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.estrategia = self.clase_estrategia()
        self.estrategia.modo = self
        self._ultima_p = None

    def capturar(self):
        p, o = super().capturar()
        self._ultima_p = p
        return p, o

    def _nueva_pelea(self):
        super()._nueva_pelea()
        if getattr(self, "estrategia", None) is not None and hasattr(self.estrategia, "nueva_pelea"):
            self.estrategia.nueva_pelea()

    # ------------------------------------------------------------- navegacion
    def _otros_pisos4(self):
        return [x for x in (juego.piso3_superado, juego.piso3_superado_pajaro, juego.piso3_superado_ciervo)
                if x is not self._piso4()]

    def ir_a_perros(self, p, o):
        """Como los perros, pero sabiendo salir de los pisos de OTRA bestia (el plan del dia venia de los perros y el
        pajaro se quedaba quieto en sus pisos, 2026-11-10)."""
        if self.clic_si(juego.cancelar, p, o):
            self.log("Habia una pelea a medias; la doy por perdida y empiezo de nuevo.", "aviso")
            return None
        if self._piso4().esta(p):
            self.log(f"En la pantalla de pisos de {self.titulo_juego}.", "ok")
            return "elegir_piso"
        mia = juego.ORDEN_BESTIAS.index(self.bestia)
        en_pisos = ATRAS.esta(p, 0.75) or any(x.esta(p) for x in self._otros_pisos4())
        if en_pisos:
            cabecera = B13.BestiaPisos1a3._bestia_de_los_pisos(self, p)
            if cabecera == mia:
                self.log(f"En la pantalla de pisos de {self.titulo_juego}.", "ok")
                return "elegir_piso"
            if cabecera is not None or any(x.esta(p) for x in self._otros_pisos4()):
                self.log(f"Estoy en los pisos de otra bestia: vuelvo atrás para ir a {self.titulo_juego}.", "aviso")
                if not self.clic_si(ATRAS, p, o, umbral=0.75, espera=1.5):
                    entrada.clic(PUNTO_ATRAS, o, espera=1.5)
                return None
        return super().ir_a_perros(p, o)

    def elegir_piso(self, p, o):
        siguiente = super().elegir_piso(p, o)
        if siguiente is None and not juego.ok.esta(p) and not juego.empezar.esta(p) and not self._piso4().esta(p):
            self._tocar_piso4_por_texto(p, o)  # por si su imagen de "Floor 3 Cleared" ya no coincide
        return siguiente

    def _tocar_piso4_por_texto(self, p, o) -> bool:
        """El Floor 4 es el panel de arriba, "Transcendent <bestia>": se busca por su texto."""
        if not ocr.disponible():
            return False
        for texto, (x, y, w, h) in ocr.lineas_con_posicion(p):
            if "transcend" in texto.lower():
                self.log("Abro el Floor 4 (por su nombre).", "debug")
                entrada.clic((x + w // 2, y + h + 50), o, espera=1.0)
                return True
        return False

    def _verificar_equipo(self, p):
        self.equipo_verificado = True
        if self.equipo_recomendado:
            self.log(f"Equipo recomendado: {self.equipo_recomendado}. Juego con el que tengas puesto.", "info")

    def _detectar_fase(self, p, huecos: int) -> int | None:
        for numero, plantilla in ((4, juego.fase_4), (3, juego.fase_3), (2, juego.fase_2)):
            if plantilla.esta(p, 0.8):
                return numero
        if juego.fase_1.esta(p, 0.8) and huecos > 1:
            return 1
        return None


class PajaroPiso4(Piso4):
    id = "pajaro_piso4"
    nombre = "Hraesvelgr · Floor 4"
    titulo_juego = "Hraesvelgr"
    subtitulo_juego = "Demonic Beast · Floor 4"
    imagen = "demonic_beasts/hraesvelgr.png"
    duracion = "~4 min por pelea"
    descripcion = ("Floor 4 del pájaro con el guion de AutoFarming. Recomendado: Meliodas traidor (o Tyr verde), "
                   "Thor, Megellda azul y Shion. Puede empezar desde la Tavern, el menú Battle o la pantalla de Floors.")
    equipo_recomendado = "Meliodas traidor (o Tyr verde), Thor, Megellda azul y Shion"
    bestia = juego.pajaro
    piso3_superado = juego.piso3_superado_pajaro
    clase_estrategia = EstrategiaPajaro4


class CiervoPiso4(Piso4):
    id = "ciervo_piso4"
    nombre = "Eikthyrnir · Floor 4"
    titulo_juego = "Eikthyrnir"
    subtitulo_juego = "Demonic Beast · Floor 4"
    imagen = "deer/Eikthyrnir.png"
    duracion = "~4 min por pelea"
    descripcion = ("Floor 4 del ciervo con el guion de AutoFarming. Equipo: Thor, Jormungand verde, Freyr y Tyr "
                   "verde (o Hel verde), con equipo de ataque. Gana ~60 % con Tyr: los reinicios son normales.")
    equipo_recomendado = "Thor, Jormungand verde, Freyr y Tyr verde (o Hel verde)"
    bestia = juego.ciervo
    piso3_superado = juego.piso3_superado_ciervo
    clase_estrategia = EstrategiaCiervo4


TODOS = (PajaroPiso4, CiervoPiso4)
