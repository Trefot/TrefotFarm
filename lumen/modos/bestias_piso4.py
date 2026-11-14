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

from functools import lru_cache

from lumen import cartas as C
from lumen import entrada, inteligencia, juego, ocr
from lumen import personajes as P
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.modos import bestias_pisos1a3 as B13
from lumen.modos.bestias_pisos1a3 import ATRAS, PUNTO_ATRAS, EstrategiaInteligente
from lumen.modos.perros_piso4 import PerrosPiso4, Reiniciar
from lumen.motor import Opcion

# ------------------------------------------------------------------ las cartas


def _base(c: Carta | None) -> str:
    return ((c.nombre if c else "") or "").split("@")[0]


def heroe(c: Carta | None) -> str:
    return _base(c).partition(".")[0]


def habilidad(c: Carta | None) -> str:
    return _base(c).partition(".")[2]


@lru_cache(maxsize=1)
def _colores() -> dict:
    try:
        return {pid: pj.color for pid, pj in P.cargar().items()}
    except Exception:
        return {}


def color(c: Carta | None) -> str:
    """rojo, azul o verde: el de la ficha del heroe. Antes salia del final del id y "freyja_roja" (en femenino) se
    quedaba sin color: el ciervo nunca jugaba sus cartas (el usuario, 2026-11-13)."""
    h = heroe(c)
    if not h:
        return ""
    ficha = _colores().get(h)
    if ficha in ("rojo", "azul", "verde"):
        return ficha
    final = h.rsplit("_", 1)[-1]
    return {"rojo": "rojo", "roja": "rojo", "azul": "azul", "verde": "verde"}.get(final, "")


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


@lru_cache(maxsize=1)
def _lector_funcional():
    from lumen.ia.decidir import LectorCartas
    return LectorCartas(biblioteca={}, textos={})


def efectos_carta(c):
    return _lector_funcional().efectos_carta(c) if c is not None else []


def es_curacion(c) -> bool:
    return any(e.tipo == "curar" for e in efectos_carta(c))


def quita_buffs(c) -> bool:
    return any(e.tipo == "quitar_buffs" and e.objetivo in ("uno", "todos") for e in efectos_carta(c))


def contra_inmortalidad(c) -> bool:
    from lumen.ia.resolver import satisface
    return satisface(efectos_carta(c), "amplify_power_strike")


def dano(c) -> float:
    return max((e.valor or 0 for e in efectos_carta(c) if e.tipo == "dano"), default=0.0)


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

    MIN_VISTAS_EQUIPO = 24  # cartas reconocidas antes de dar el equipo por sabido
    PARTE_EQUIPO = 0.8  # los 4 heroes mas vistos tienen que ser al menos este tanto de lo reconocido

    def _aprender_equipo(self, mano):
        """Cuenta de que heroe es cada carta reconocida; con los 4 claros, el reconocedor solo mira sus cartas."""
        indice = getattr(self.jugador, "_indice", None)
        if indice is None or getattr(indice, "equipo", None):
            return
        conteo = getattr(self, "_conteo_heroes", None)
        if conteo is None:
            conteo = self._conteo_heroes = {}
        for c in mano:
            h = heroe(c)
            if h and "." in _base(c):
                conteo[h] = conteo.get(h, 0) + 1
        total = sum(conteo.values())
        cuatro = sorted(conteo, key=conteo.get, reverse=True)[:4]
        if total >= self.MIN_VISTAS_EQUIPO and len(cuatro) == 4 and min(conteo[h] for h in cuatro) >= 3                 and sum(conteo[h] for h in cuatro) >= self.PARTE_EQUIPO * total:
            indice.fijar_equipo(cuatro)
            if self.modo is not None:
                try:
                    self.modo.log("Equipo reconocido: " + ", ".join(cuatro) + ". Desde ahora solo comparo sus cartas.",
                                  "info")
                except Exception:
                    pass

    def decidir(self, fase, turno, accion, mano, total=4):
        try:
            inteligencia.agrupar_por_dibujo(mano, self.jugador._identificar)  # nombres de las cartas
            self._aprender_equipo(mano)
        except Exception:
            pass
        self._total_turno = total
        self.jugador.razones = {}
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

    def turno_completado(self, fase, turno):
        """El motor ya observo todas las casillas ocupadas: comprobar el requisito real."""
        if fase != 2:
            return
        from collections import Counter
        from lumen.ia import resolver
        cantidad, minimo = resolver.requisito_rango(self.destino, 2) or (3, 2)
        por_rango = Counter(c.rango for c in self.jugadas if not es_ulti(c) and
                            c.rango in (Rango.BRONCE, Rango.PLATA, Rango.ORO) and c.rango.value + 1 >= minimo)
        self.escudo = any(n >= cantidad for n in por_rango.values())

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
        if self.jugador.observacion.get("senales"):
            from lumen.ia import resolver
            lector = self.jugador._lector or _lector_funcional()
            eleccion = resolver.por_estado(self.destino, fase, mano, self.jugador.observacion, lector)
            if eleccion is not None:
                self.jugador.razones[mano[eleccion.indice].nombre] = [eleccion.motivo]
                return eleccion.indice
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
        from lumen.ia import resolver
        requisito = resolver.requisito_rango(self.destino, 2) or (3, 2)
        cantidad, minimo = requisito
        libres = max(0, getattr(self, "_total_turno", 4) - accion)
        grupo = resolver.grupo_de_rango(mano, self.jugadas, libres, requisito)
        objetivo = grupo[0] if grupo else (Rango.ORO if minimo >= 3 else Rango.PLATA)
        platas = [i for i in indices(mano, lambda c: c.rango == objetivo, orden=lambda c: 0)]
        platas_jugadas = [c for c in self.jugadas if c.rango == objetivo]
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
            if objetivo == Rango.PLATA and len(platas) + len(platas_jugadas) < cantidad and (m := self._plata_por_fusion(mano)) is not None:
                return m
            if min(len(platas), libres) + len(platas_jugadas) >= cantidad and platas and len(platas_jugadas) < cantidad:
                jugada = platas[-1]
                if len(platas_jugadas) + 1 == cantidad and accion == getattr(self, "_total_turno", 4) - 1:
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
    """El ciervo segun lo que pide en cada fase (lumen/datos/requisitos_bestias.yaml, de 7dshub, 2026-11-13): lo
    obligatorio se cumple siempre; lo que se salta con dano depende del estilo (cauteloso, whale o automatico)."""

    destino = "ciervo_piso4"

    def __init__(self):
        from lumen.ia.requisitos import CAUTELOSO, Estilo

        self.estilo = Estilo(CAUTELOSO)  # por defecto, lo de siempre; el modo pone el que elija el usuario
        super().__init__()

    def nueva_pelea(self):
        super().nueva_pelea()
        self.color_turno = None
        self._turnos_sin_color = set()
        self.pedir_reinicio = None

    def _golpe_maximo(self, mano, guardar_ulti_freyr=False):
        """Whale: la ulti (la de mas a la derecha) o la carta que mas dano hace, de mas rango."""
        ultis = indices(mano, lambda c: es_ulti(c) and not (guardar_ulti_freyr and es_freyr(c)), orden=lambda c: 0)
        if ultis:
            return ultis[-1]
        normales = indices(mano, lambda c: not es_ulti(c), orden=lambda c: (rango(c), dano(c)))
        return normales[-1] if normales else None

    @staticmethod
    def _por_rango(mano, cond, ultis_al_final=False):
        clave = (lambda c: -rango(c) if es_ulti(c) else rango(c)) if ultis_al_final else rango
        return indices(mano, cond, orden=clave)

    def _grupos(self, mano, ultis_al_final=False):
        return {col: self._por_rango(mano, lambda c, col=col: color(c) == col, ultis_al_final)
                for col in ("verde", "rojo", "azul")}

    def guion(self, fase, turno, accion, mano):
        from lumen.ia import requisitos

        whale = self.estilo.whale(self.destino, fase, turno)
        if fase == 1:
            return self._golpe_maximo(mano) if whale else self._fase1(turno, accion, mano)
        if fase == 2:
            # Obligatorio (el usuario): todo el turno del color de la primera carta, o se bloquean todas
            jugada = self._golpe_de_un_color(mano, accion) if whale else self._fase2(turno, accion, mano)
            return self._mismo_color_del_turno(jugada, mano, accion)
        if fase == 3:
            # Obligatorio en los turnos impares: si no, Fierce Rush (20000 %) mata a un heroe
            if requisitos.aplica(requisitos.pide(self.destino, 3, "mismo_color"), turno) or not whale:
                return self._fase3(turno, accion, mano)
            return self._golpe_maximo(mano, guardar_ulti_freyr=True)
        return self._fase4(turno, accion, mano)  # inmortalidad y contraataque: obligatorio siempre

    def _avisar(self, texto: str):
        """Al registro, una vez por turno (para saber que vio el bot y que decidio)."""
        clave = (texto, len(self.jugadas))
        if getattr(self, "_ultimo_aviso", None) != clave and self.modo is not None:
            self._ultimo_aviso = clave
            try:
                self.modo.log(texto, "info")
            except Exception:
                pass

    def _color_del_turno(self, accion):
        primera = self.carta_en_accion(0) if accion > 0 else None
        return color(primera) if primera is not None and color(primera) else None

    def _golpe_de_un_color(self, mano, accion):
        """Whale en la fase 2: maximo dano, pero de un solo color (el de la primera carta; al empezar, el color con
        mas cartas y, si empatan, el de la carta mas fuerte)."""
        col = self._color_del_turno(accion)
        if col is None:
            grupos = self._grupos(mano)
            fuerza = lambda k: (len(grupos[k]), max((1000 if es_ulti(mano[i]) else rango(mano[i]) * 100 + dano(mano[i])  # noqa: E731
                                                     for i in grupos[k]), default=-1))
            col = max(grupos, key=fuerza)
            if not grupos[col]:
                return self._golpe_maximo(mano)
        de_color = [i for i, c in enumerate(mano) if jugable(c) and color(c) == col]
        if not de_color:
            return self._mover_para_ulti(mano)
        ultis = [i for i in de_color if es_ulti(mano[i])]
        if ultis:
            return ultis[-1]
        return max(de_color, key=lambda i: (rango(mano[i]), dano(mano[i]), i))

    def _mismo_color_del_turno(self, jugada, mano, accion):
        """Nunca jugar una carta de otro color que la primera del turno (se bloquean todas): una del color o mover."""
        col = self._color_del_turno(accion)
        if col is None or not isinstance(jugada, int) or not (0 <= jugada < len(mano)) or color(mano[jugada]) == col:
            return jugada
        de_color = [i for i, c in enumerate(mano) if jugable(c) and color(c) == col]
        return max(de_color, key=lambda i: (rango(mano[i]), i)) if de_color else self._mover_para_ulti(mano)

    SIGUIENTE = {"verde": "azul", "azul": "rojo", "rojo": "verde"}  # la ruleta de colores de la fase 4
    PRIMER_COLOR = "verde"  # el semaforo empieza siempre por verde (el usuario, 2026-11-13)

    def _color_que_falta(self, turno, accion, rojas, verdes, azules) -> str | None:
        listas = {"rojo": rojas, "verde": verdes, "azul": azules}
        if accion == 0:
            if turno == 1:  # el semaforo empieza por verde (el usuario, 2026-11-13)
                return None if verdes else self.PRIMER_COLOR
            for buff, col in ((juego.buff_azul, "azul"), (juego.buff_rojo, "rojo"), (juego.buff_verde, "verde")):
                if self.ve(buff):
                    return None if listas[col] else col
            return None
        ultima = self._ultima_jugada(accion)
        if ultima is None or not color(ultima) or (es_hel(ultima) and es_ulti(ultima)):
            return None
        toca = self.SIGUIENTE.get(color(ultima))
        return toca if toca and not listas[toca] else None

    def _ultima_jugada(self, accion):
        """La ultima carta JUGADA en el turno (un movimiento en medio no cuenta: antes se perdia la cuenta y volvia a
        jugar otra roja, 2026-11-13)."""
        for a in range(accion - 1, -1, -1):
            c = self.carta_en_accion(a)
            if c is not None:
                return c
        return None

    def _falta_color(self, turno, col):
        turnos = self.__dict__.setdefault("_turnos_sin_color", set())
        if turno not in turnos:
            self._avisar(f"Fase 4: toca {col} y no tengo: muevo para no romper la secuencia de colores.")
        turnos.add(turno)
        if turno - 1 in turnos:
            self.pedir_reinicio = f"fase 4 sin carta {col} dos turnos seguidos: la secuencia no sale"

    def _fase1_general(self, accion, mano):
        """Cualquier equipo: el Torrente se quita usando la ulti; la 4.a accion carga ultis moviendo una carta."""
        if accion == 3:
            return self._mover_para_ulti(mano)
        return self._golpe_maximo(mano)

    def _fase1(self, turno, accion, mano):
        thor = self._por_rango(mano, es_thor)
        tyr_hel = self._por_rango(mano, lambda c: es_tyr(c) or es_hel(c))
        if not thor and not tyr_hel:  # no es el equipo de AutoFarming: lo que pide la fase, con lo que haya
            return self._fase1_general(accion, mano)
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

    @staticmethod
    def _mover_fusionando(mano):
        """Una carta sobre otra igual del mismo rango (bronce o plata): se fusionan, suben de rango y cargan la ulti.
        El usuario (2026-11-13): "aunque tenga cartas iguales para combinar, no lo hace"."""
        pares = [(i, j) for i, a in enumerate(mano) for j, b in enumerate(mano)
                 if i != j and abs(i - j) > 1 and fusionan(a, b)]
        if not pares:
            return None
        return max(pares, key=lambda ij: (rango(mano[ij[0]]), -abs(ij[0] - ij[1])))  # primero las de plata

    @staticmethod
    def _preferir_fusion(candidatas, mano):
        """De las cartas que valen ahora, la que esta entre dos iguales (al jugarla se juntan y se fusionan)."""
        for i in reversed(candidatas):
            if 0 < i < len(mano) - 1 and fusionan(mano[i - 1], mano[i + 1]):
                return i
        return candidatas[-1] if candidatas else None

    def _mover_para_ulti(self, mano):
        """Mover sin atacar: primero una fusion; si no, una carta del heroe que aun no tiene la ulti (asi se carga)."""
        if (fusion := self._mover_fusionando(mano)) is not None:
            return fusion
        todas = list(mano) + list(self.jugadas)
        unidades = [(es_tyr, self._por_rango(mano, es_tyr)), (es_hel, self._por_rango(mano, es_hel)),
                    (es_freyr, self._por_rango(mano, lambda c: color(c) == "rojo")),
                    (es_jorm, self._por_rango(mano, es_jorm)),
                    (es_thor, self._por_rango(mano, lambda c: color(c) == "azul"))]
        for cond, cartas in unidades:
            if cartas and not self._tiene_ulti(todas, cond):
                return self._movimiento_valido(mano, cartas[0])
        # Cualquier equipo: el heroe de la mano que aun no tiene su ulti
        for h in dict.fromkeys(heroe(c) for c in mano if con_carta(c) and heroe(c)):
            if not self._tiene_ulti(todas, lambda c, h=h: heroe(c) == h):
                suyas = self._por_rango(mano, lambda c, h=h: heroe(c) == h)
                if suyas:
                    return self._movimiento_valido(mano, suyas[0])
        cartas = [i for i, c in enumerate(mano) if con_carta(c)]
        if len(cartas) < 2:
            raise Reiniciar("Ciervo: no hay dos cartas para mover sin atacar; espero otra lectura")
        return self._movimiento_valido(mano, cartas[-2])

    def _fase2(self, turno, accion, mano):
        grupos = self._grupos(mano, ultis_al_final=True)
        cura = [i for i in grupos["verde"] if es_jorm(mano[i]) and es_curacion(mano[i])]
        if cura:  # la curacion de Jormungand la primera de las verdes
            grupos["verde"] = [cura[-1]] + [i for i in grupos["verde"] if i != cura[-1]]
        # Todas las cartas del color del turno que haya (el usuario, 2026-11-13: con 4 rojas jugaba 2 y movia; la
        # "doble roja" y el movimiento fijo de la 4.a accion de AutoFarming se quitan). Solo se mueve sin cartas.
        if accion == 0 or self.color_turno is None:
            self.color_turno = self._color_del_turno(accion)
            if self.color_turno is None:
                n = turno - 2
                orden = ["verde", "azul"]
                orden = orden[-n % 2:] + orden[:-n % 2] + ["rojo"]
                self.color_turno = max(orden, key=lambda k: (len(grupos[k]), -orden.index(k)))
        elegidas = grupos[self.color_turno]
        if elegidas:
            if accion == 2 and self.color_turno == "verde":
                curas = self._por_rango(mano, lambda c: es_jorm(c) and es_curacion(c))
                if curas:
                    return curas[-1]
            return self._preferir_fusion(elegidas, mano)
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
            return self._preferir_fusion(elegidas, mano)
        if accion > 2:
            mayor = max(grupos.values(), key=len)
            for i in reversed(mayor):
                if not (es_freyr(mano[i]) and es_ulti(mano[i])):  # la ulti de Freyr se guarda para la fase 4
                    return i
        return None

    TURNOS_SEMAFORO = 3  # fase 4: los turnos de la ruleta de colores; despues, a matar

    def _semaforo_hecho(self, turno) -> bool:
        """Ya hubo 3 turnos de semaforo completos. Un turno en que falto el color (se movio) no quito inmortalidad:
        no cuenta."""
        fallados = sum(1 for t in self.__dict__.get("_turnos_sin_color", ()) if t < turno)
        return turno - 1 - fallados >= self.TURNOS_SEMAFORO

    def _fase4(self, turno, accion, mano):
        if self._semaforo_hecho(turno):
            # El usuario (2026-11-13), con este mismo equipo: cumplido el semaforo (fuera inmortalidades), se le mata
            # a full dano con las 4 cartas (sin guardar ultis ni mover: "full es full") y se aguanta el contraataque.
            if accion == 0:
                self._avisar("Fase 4: semáforo hecho; 4 cartas a full daño, sin guardar nada.")
            return self._golpe_maximo(mano)
        if self.ve(juego.contraataque):
            # Defensive Horn: postura que devuelve 1500 % al atacarle. Quitarle la postura o la ulti de Hel; si no hay
            # nada, se sigue atacando: quedarse quieto (0.38.0) solo le daba tiempo y mataba al equipo igual (el
            # usuario, 2026-11-13: "podia seguir con los danos de cartas rojas y sus ultis").
            from lumen.ia.resolver import satisface

            if quita := indices(mano, lambda c: satisface(efectos_carta(c), "quitar_postura"), orden=lambda c: 0):
                self._avisar(f"Contraataque del ciervo: le quito la postura con {heroe(mano[quita[-1]])}.")
                return quita[-1]
            if hel_ulti := self._por_rango(mano, lambda c: es_hel(c) and es_ulti(c)):
                self._avisar("Contraataque del ciervo: ulti de Hel.")
                return hel_ulti[-1]
            self._avisar("Contraataque del ciervo y nada que le quite la postura: sigo atacando.")
        rojas = self._por_rango(mano, lambda c: color(c) == "rojo")
        azules = self._por_rango(mano, lambda c: color(c) == "azul")
        verdes = self._por_rango(mano, lambda c: color(c) == "verde")
        # El color que toca (buff al empezar el turno, o el siguiente de la ruleta). Si no esta en la mano no se rompe
        # la secuencia: se mueve. Sin ese color dos turnos seguidos, se reinicia (el usuario, 2026-11-13).
        falta = self._color_que_falta(turno, accion, rojas, verdes, azules)
        if falta:
            self._falta_color(turno, falta)
            return self._mover_para_ulti(mano)
        if True:  # mientras dure el semaforo (tambien si se alargo por un turno sin color): las ultis al final
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
            if verdes:  # el semaforo empieza por verde (sin verdes ya se movio arriba)
                return verdes[-1]
        elif accion == 0:
            for buff, lista in ((juego.buff_azul, azules), (juego.buff_rojo, rojas), (juego.buff_verde, verdes)):
                if self.ve(buff) and lista:
                    return lista[-1]
        ultima = self._ultima_jugada(accion) if accion > 0 else None
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

    fases_reinicio_bloqueo: frozenset = frozenset()  # fases donde, con todas las cartas bloqueadas, se reinicia

    def _reiniciar_por_bloqueo(self, p) -> bool:
        motivo = getattr(self.estrategia, "pedir_reinicio", None)
        if motivo:
            self.estrategia.pedir_reinicio = None
            self.log(f"Reinicio: {motivo}.", "aviso")
            self.diario.nota(f"Reinicio: {motivo}")
            return True
        return self._reiniciar_por_fase_bloqueada(p)

    def _reiniciar_por_fase_bloqueada(self, p) -> bool:
        """El usuario (2026-11-13): si en la fase 2 del pajaro salen todas bloqueadas (no se juntaron las 3 de plata),
        la pelea ya esta perdida; reiniciar ahorra 6-9 turnos moviendo cartas hasta perder."""
        if self.fase not in self.fases_reinicio_bloqueo:
            return False
        try:
            mano = [c for c in C.leer_mano(p) if c.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA)]
        except Exception:
            return False
        if len(mano) >= 4 and all(c.tipo == TipoCarta.BLOQUEADA for c in mano):
            self.log(f"Fase {self.fase}: todas las cartas bloqueadas (mala suerte con las de plata). "
                     "Reinicio para no perder tiempo.", "aviso")
            self.diario.nota("Reinicio: todas las cartas bloqueadas")
            return True
        return False

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
    fases_reinicio_bloqueo = frozenset({2})


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
    opciones = PerrosPiso4.opciones + [
        Opcion("estilo", "Cómo pelear", "lista", "Cauteloso", opciones=["Cauteloso", "Automático", "Whale"],
               ayuda="Cauteloso: cumple todo lo que pide cada fase (equipos normales). Whale: máximo daño y solo lo "
                     "obligatorio (inmortalidad, golpe mortal de la fase 3, contraataque). Automático: empieza con "
                     "todo y, si una fase no cae en 1 turno, la juega con cautela."),
    ]

    def __init__(self, valores: dict):
        super().__init__(valores)
        from lumen.ia.requisitos import Estilo

        self.estrategia.estilo = Estilo(str(valores.get("estilo") or "Cauteloso"))


TODOS = (PajaroPiso4, CiervoPiso4)
