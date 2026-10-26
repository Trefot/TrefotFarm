"""Perros piso 4 con el equipo Trefot: Odin, Gawain, Freyja roja y Thonar azul.

Guion (si algo se sale de el, se rinde y reinicia, que es lo mas rapido con este equipo):
  Fase 1 T1: perro IZQ -> postura de Thonar | perro DER -> otra de Thonar | 2 normales de Freyja.
  Fase 1 T2: talento de Odin | perro IZQ | Freyja (si su ulti aun no esta) o Thonar (si ya esta) |
             single de Odin | single de Gawain | relleno sin gastar lo de la fase 2.
  Fase 2 T1: perro DER | area de Gawain | ulti de Freyja | area de Odin | cualquier carta de G/F/O.
  Fase 3 T1: no se ataca (el golpe secundario de la ulti de Freyja termina la pelea).

Empieza desde cualquier pantalla de la taberna / menu de batalla / bestias demoniacas.
"""

import time
from collections import defaultdict
from collections.abc import Sequence

from trefot import cartas as C
from trefot import entrada, juego
from trefot.cartas import Carta, Rango, TipoCarta
from trefot.control import control
from trefot.equipo import DefCarta, Equipo
from trefot.motor import Modo, Opcion, TerminarModo

# ---------------------------------------------------------------------- el equipo
EQUIPO = Equipo(
    "perros_trefot",
    "Odin, Gawain, Freyja roja, Thonar azul",
    [
        DefCarta("odin_single", "Odin - carta de un objetivo"),
        DefCarta("odin_area", "Odin - carta de area"),
        DefCarta("odin_ulti", "Odin - ulti", obligatoria=False),
        DefCarta("gawain_single", "Gawain - carta de un objetivo"),
        DefCarta("gawain_area", "Gawain - carta de area"),
        DefCarta("gawain_ulti", "Gawain - ulti", obligatoria=False),
        DefCarta("freyja_1", "Freyja roja - carta normal 1", respaldos=("snake/freyja_st.png",)),
        DefCarta("freyja_2", "Freyja roja - carta normal 2", respaldos=("snake/freyja_aoe.png",)),
        DefCarta("freyja_ulti", "Freyja roja - ulti", respaldos=("snake/freyja_ult.png",)),
        DefCarta("thonar_postura", "Thonar azul - carta que quita la postura", respaldos=("dogs/b_thonar_stance.png",)),
        DefCarta("thonar_otra", "Thonar azul - la otra carta", respaldos=("dogs/b_thonar_gauge.png",)),
        DefCarta("thonar_ulti", "Thonar azul - ulti", obligatoria=False),
        DefCarta("odin_talento", "Boton del talento de Odin (pantalla)", obligatoria=False, es_carta=False),
    ],
    grupos={
        "odin": ("odin_single", "odin_area", "odin_ulti"),
        "gawain": ("gawain_single", "gawain_area", "gawain_ulti"),
        "freyja": ("freyja_1", "freyja_2", "freyja_ulti"),
        "thonar": ("thonar_postura", "thonar_otra", "thonar_ulti"),
    },
)

FREYJA_NORMALES = ("freyja_1", "freyja_2")
THONAR_NORMALES = ("thonar_postura", "thonar_otra")
PROTEGIDAS_FASE2 = ("gawain_area", "odin_area", "freyja_ulti")
TURNOS_MAXIMOS = {1: 2, 2: 1, 3: 1}


class Reiniciar(Exception):
    """La estrategia pide rendirse y repetir la pelea."""


# ----------------------------------------------------------------- estrategia pura
class Estrategia:
    """Decide UNA carta por llamada. No toca la pantalla: pide objetivo/talento al bot.

    ``decidir`` devuelve (indice_en_mano, objetivo, usar_talento). objetivo es "izq", "der" o None.
    """

    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta]) -> tuple[int, str | None, bool]:
        limite = TURNOS_MAXIMOS.get(fase)
        if limite is not None and turno > limite:
            raise Reiniciar(f"la fase {fase} va por el turno {turno} y debia acabar en {limite}")
        if fase == 1 and turno <= 1:
            return self._f1t1(mano, accion)
        if fase == 1:
            return self._f1t2(mano, accion)
        if fase == 2:
            return self._f2(mano, accion)
        return self._f3(mano), None, False

    def _f1t1(self, mano, accion):
        if accion == 0:
            return self._o_reiniciar(mano, ("thonar_postura",), "F1T1: falta la postura de Thonar"), "izq", False
        if accion == 1:
            return self._o_reiniciar(mano, ("thonar_otra",), "F1T1: falta la otra carta de Thonar"), "der", False
        return self._o_reiniciar(mano, FREYJA_NORMALES, "F1T1: faltan cartas normales de Freyja"), None, False

    def _f1t2(self, mano, accion):
        if accion == 0:
            if self.mejor(mano, ("freyja_ulti",)) is not None:
                preferidas, alternativa = THONAR_NORMALES, FREYJA_NORMALES  # la ulti se guarda para la fase 2
            else:
                preferidas, alternativa = FREYJA_NORMALES, THONAR_NORMALES  # cargar la ulti
            idx = self.mejor(mano, preferidas)
            if idx is None:
                idx = self.mejor(mano, alternativa)
            if idx is None:
                raise Reiniciar("F1T2: no hay cartas de Freyja ni de Thonar")
            return idx, "izq", True
        if accion == 1:
            return self._o_reiniciar(mano, ("odin_single",), "F1T2: falta la single de Odin"), None, False
        if accion == 2:
            return self._o_reiniciar(mano, ("gawain_single",), "F1T2: falta la single de Gawain"), None, False
        for grupo in (THONAR_NORMALES, FREYJA_NORMALES, ("odin_single",), ("gawain_single",)):
            idx = self.mejor(mano, grupo)
            if idx is not None:
                return idx, None, False
        for carta in reversed(mano):
            if carta.jugable and carta.nombre not in PROTEGIDAS_FASE2:
                return carta.posicion, None, False
        raise Reiniciar("F1T2: solo quedan cartas que se necesitan en la fase 2")

    def _f2(self, mano, accion):
        if accion == 0:
            return self._o_reiniciar(mano, ("gawain_area",), "F2: falta el area de Gawain"), "der", False
        if accion == 1:
            return self._o_reiniciar(mano, ("freyja_ulti",), "F2: falta la ulti de Freyja"), None, False
        if accion == 2:
            return self._o_reiniciar(mano, ("odin_area",), "F2: falta el area de Odin"), None, False
        g = EQUIPO.grupos
        idx = self.mejor(mano, g["gawain"] + g["freyja"] + g["odin"])
        return (idx if idx is not None else self.derecha_jugable(mano)), None, False

    def _f3(self, mano):
        """Gastar cartas sin atacar: primero las bloqueadas, luego las que no hacen dano."""
        for tipos in ((TipoCarta.BLOQUEADA,), (TipoCarta.BUFF, TipoCarta.POSTURA, TipoCarta.CURACION, TipoCarta.DEBUFF)):
            ids = [c.posicion for c in mano if c.tipo in tipos]
            if ids:
                return ids[-1]
        return self.derecha_jugable(mano)

    # ------------------------------------------------------------------ ayudantes
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
class PerrosPiso4(Modo):
    id = "perros_piso4"
    nombre = "Perros piso 4 - Trefot"
    descripcion = (
        "Odin, Gawain, Freyja roja y Thonar azul (izquierda a derecha). Arranca desde la taberna, "
        "el menu de batalla o la pantalla de pisos de los Perros."
    )
    equipo = EQUIPO
    opciones = [
        Opcion("victorias", "Victorias (0 = sin limite)", "entero", 0, maximo=9999),
        Opcion("extra", "Usar 'extra' en las primeras N", "entero", 0, maximo=99),
        Opcion("pociones", "Usar pociones de estamina", "si_no", True),
        Opcion("max_pociones", "Maximo de pociones (0 = sin limite)", "entero", 0, maximo=999),
    ]
    pausa_entre_pasos = 0.45

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.estrategia = Estrategia()
        self.victorias = self.derrotas = self.reinicios = self.pociones = self.extras = 0
        self.derrotas_por_fase = defaultdict(int)
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
        self.inicio_pelea = time.time()

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
                raise TerminarModo()
            if self.clic_si(juego.usar_pocion, p, o, umbral=0.8):
                self.pociones += 1
                self._stats()
                return None
        self.clic_si(juego.empezar, p, o)
        if juego.carga_bestias.esta(p) or juego.carga_taberna.esta(p):
            self._nueva_pelea()
            self.log("¡A pelear!", "ok")
            return "pelea"
        return None

    # ------------------------------------------------------------------ pelea
    def pelea(self, p, o):
        self.clic_si(juego.saltar, p, o)
        self.clic_si(juego.mision_semanal, p, o, punto=juego.COORD["mision_semanal"])
        self.clic_si(juego.info_mision, p, o)
        self.clic_si(juego.criatura_destruida, p, o)
        if juego.derrota.esta(p) or juego.cerrar.esta(p):
            return "derrota"
        if juego.victoria.esta(p):
            return "victoria"
        if juego.piso3_superado.esta(p):
            self.log("Volvi a la pantalla de pisos sin ver el final de la pelea.", "aviso")
            return "elegir_piso"
        if time.time() - self.inicio_pelea > 8 * 60:
            self.log("La pelea dura demasiado; me rindo.", "aviso")
            return "rendirse"

        talento = self._talento_visible(p)
        huecos = C.contar_huecos(p, 0.8)
        if self.turno_abierto:
            return self._jugar_turno() if huecos > 0 else None
        if talento or huecos >= 3:
            self.lecturas_turno += 1
            if talento or self.lecturas_turno >= 2:  # dos lecturas seguidas: evita arrancar en una animacion
                self.lecturas_turno = 0
                return self._empezar_turno(p, max(huecos, 4 if talento and huecos <= 0 else huecos))
        else:
            self.lecturas_turno = 0
        return None

    def _detectar_fase(self, p, huecos: int) -> int | None:
        if juego.fase_3_perros.esta(p, 0.8):
            return 3
        if juego.fase_2.esta(p, 0.8):
            return 2
        if juego.fase_1.esta(p, 0.8) and huecos > 1:
            return 1
        return None

    def _empezar_turno(self, p, huecos: int):
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
        if self.fase != 3 and juego.mano_bloqueada.esta(p, 0.6):
            self.log("Mano bloqueada desde el inicio: reinicio.", "aviso")
            return "rendirse"
        return self._jugar_turno()

    def _jugar_turno(self):
        """Juega cartas hasta llenar los huecos. Se puede retomar si se corta a medias."""
        ultima_accion, repeticiones = None, 0
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
                self.log("El hueco no se lleno; repito la accion.", "aviso")
            repeticiones = 0

            mano = EQUIPO.etiquetar(C.leer_mano(p))
            self.log("Mano: " + " ".join(str(c) for c in mano), "debug")
            try:
                idx, objetivo, talento = self.estrategia.decidir(self.fase, self.turno_fase, accion, mano)
            except Reiniciar as motivo:
                self.log(f"Reinicio: {motivo}", "aviso")
                self.turno_abierto = False
                return "rendirse"
            if talento and not self.talento_usado:
                self._activar_talento_odin()
                self.talento_usado = True
            if objetivo:
                self._apuntar(objetivo)
            carta = mano[idx]
            self.log(f"Accion {accion + 1}: juego {carta}")
            entrada.clic(carta.rect, o, espera=0.1)
            fusiones = self.estrategia.fusiones_al_jugar(mano, idx)
            self.esperar_corto(0.35 + (0.6 if fusiones == 1 else 1.1 if fusiones > 1 else 0))
            ultima_accion = accion
            if accion + 1 >= self.huecos_turno:
                self.turno_abierto = False  # ultima carta enviada
                return None
        self.log("El turno tardo demasiado; lo retomo en el siguiente paso.", "aviso")
        return None

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
        plantilla = EQUIPO.plantilla("odin_talento")
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
        self.clic_si(juego.ok, p, o)
        if juego.carga_bestias.esta(p):
            self.victorias += 1
            minutos = (time.time() - self.inicio_pelea) / 60
            self.log(f"¡VICTORIA #{self.victorias}! ({minutos:.1f} min)", "ok")
            self._stats()
            meta = int(self.valores["victorias"])
            if meta and self.victorias >= meta:
                self.log(f"Llegue a {meta} victorias.", "ok")
                raise TerminarModo()
            return "elegir_piso"
        return None

    def derrota(self, p, o):
        self.clic_si(juego.info_mision, p, o)
        self.clic_si(juego.ok, p, o)
        self.clic_si(juego.cerrar, p, o)
        if juego.carga_bestias.esta(p):
            if self.reinicio_pedido:
                self.reinicios += 1
            else:
                self.derrotas += 1
                self.derrotas_por_fase[self.fase or 0] += 1
                self.log(f"Derrota en la fase {self.fase}.", "error")
            self._stats()
            return "elegir_piso"
        return None

    def rendirse(self, p, o):
        self.reinicio_pedido = True
        if juego.ok.esta(p):
            return "derrota"
        if self.clic_si(juego.rendirse, p, o):
            return None
        self.clic_si(juego.pausa, p, o)
        return None

    def al_terminar(self):
        total = self.victorias + self.derrotas + self.reinicios
        self.log(
            f"Resumen: {self.victorias} victorias, {self.derrotas} derrotas, {self.reinicios} reinicios "
            f"de {total} peleas; {self.pociones} pociones.",
            "ok",
        )
        if self.derrotas_por_fase:
            self.log("Derrotas por fase: " + ", ".join(f"F{f}: {n}" for f, n in sorted(self.derrotas_por_fase.items())))
