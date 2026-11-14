"""Ciervo Floor 4 segun lo que pide cada fase (7dshub, 2026-11-13): lo obligatorio siempre, lo demas segun el
estilo (cauteloso, whale, automatico)."""

import unittest

import entorno  # noqa: F401  (antes que lumen)

from lumen import juego
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import requisitos as RQ
from lumen.modos import MODOS
from lumen.modos import bestias_piso4 as B4

R = Rango
THOR, JORM, FREYR, TYR = ("thor_the_god_of_thunder_azul", "world_serpent_jormungand_verde", "sun_god_freyr_rojo",
                          "god_of_war_tyr_verde")
SHION, MELI = "shion_verde", "traitor_meliodas_oscuro"


def mano(*cartas):
    salida = []
    for i, (nombre, rango) in enumerate(cartas):
        ulti = nombre.endswith(".ulti")
        salida.append(Carta(i, (0, 0, 1, 1), None, TipoCarta.ULTI if ulti else TipoCarta.NORMAL,
                            R.ULTI if ulti else rango, nombre))
    return salida


def ciervo(estilo, ve=()):
    e = B4.EstrategiaCiervo4()
    e.estilo = RQ.Estilo(estilo)
    e.ve = lambda plantilla, umbral=0.7: plantilla in ve
    e.por_defecto = lambda *a, **k: None
    return e


class Ficha(unittest.TestCase):
    def test_lo_obligatorio_y_lo_saltable(self):
        self.assertTrue(RQ.saltable("ciervo_piso4", 1))
        self.assertFalse(RQ.saltable("ciervo_piso4", 2), "otro color en el turno bloquea todas (el usuario)")
        self.assertFalse(RQ.saltable("ciervo_piso4", 3), "Fierce Rush mata")
        self.assertFalse(RQ.saltable("ciervo_piso4", 4), "inmortalidad y contraataque")
        req = RQ.pide("ciervo_piso4", 3, "mismo_color")
        self.assertTrue(RQ.aplica(req, 1))
        self.assertFalse(RQ.aplica(req, 2))

    def test_fichas_de_7dshub_de_todas_las_bestias(self):
        import yaml

        datos = yaml.safe_load(RQ.ARCHIVO.with_name("bestias_7dshub.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(datos), 21)
        self.assertIn("Fierce Rush", str(datos["ciervo_f4"]["fases"][3]))


class Estilos(unittest.TestCase):
    def test_automatico_empieza_con_todo_y_luego_con_cautela(self):
        e = RQ.Estilo(RQ.AUTOMATICO)
        self.assertTrue(e.whale("ciervo_piso4", 1, 1))
        self.assertFalse(e.whale("ciervo_piso4", 1, 2), "no cayo en 1 turno")
        self.assertFalse(e.whale("ciervo_piso4", 1, 1), "y lo recuerda en la pelea siguiente")
        self.assertFalse(e.whale("ciervo_piso4", 3, 1), "fase con algo obligatorio: con cautela")

    def test_whale_pega_con_todo_en_la_fase_1(self):
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(ciervo(RQ.WHALE).guion(1, 2, 0, m), 2, "la ulti")

    def test_whale_en_la_fase_2_lo_mas_fuerte_de_un_color(self):
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE),
                 (TYR + ".skill_1", R.BRONCE), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(ciervo(RQ.WHALE).guion(2, 2, 0, m), 2, "verde (3 cartas), la que mas pega")

    def test_fase_3_impar_mismo_color_aunque_sea_whale(self):
        m = mano((JORM + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE), (TYR + ".skill_1", R.BRONCE),
                 (THOR + ".ulti", R.ULTI))
        self.assertIn(ciervo(RQ.WHALE).guion(3, 1, 0, m), (0, 1, 2), "turno impar: verde, o Fierce Rush mata")
        self.assertEqual(ciervo(RQ.WHALE).guion(3, 2, 0, m), 3, "turno par: con todo")

    def test_contraataque_quita_la_postura_o_no_ataca(self):
        e = ciervo(RQ.WHALE, ve=(juego.contraataque,))
        m = mano((THOR + ".skill_1", R.BRONCE), (MELI + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 2, 0, m), 1, "la ulti de Meliodas traidor quita posturas (turnos del semaforo)")
        sin = mano((THOR + ".skill_1", R.BRONCE), (FREYR + ".skill_2", R.BRONCE))
        self.assertNotIsInstance(e.guion(4, 2, 0, sin), tuple, "sin nada que la quite: no se queda moviendo cartas")

    def test_otro_equipo_en_la_fase_1(self):
        e = ciervo(RQ.CAUTELOSO)
        m = mano((SHION + ".skill_1", R.BRONCE), (SHION + ".ulti", R.ULTI), (MELI + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(1, 1, 0, m), 1, "sin Thor ni Tyr: la ulti quita el Torrente")
        self.assertIsInstance(e.guion(1, 1, 3, m), tuple, "la 4.a carga ultis moviendo")

    def test_opcion_del_modo(self):
        m = MODOS["ciervo_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0,
                                   "estilo": "Cauteloso"})
        self.assertEqual(m.estrategia.estilo.nombre, RQ.CAUTELOSO)


if __name__ == "__main__":
    unittest.main()


class Fase2MismoColor(unittest.TestCase):
    """El usuario, 2026-11-13 (perdio en Whale): en la fase 2, una carta de otro color que la primera bloquea todas."""

    def test_whale_no_cambia_de_color(self):
        e = ciervo(RQ.WHALE)
        m = mano((JORM + ".skill_1", R.PLATA), (JORM + ".skill_2", R.PLATA), (FREYR + ".skill_2", R.ORO),
                 (THOR + ".skill_1", R.BRONCE))
        e.jugadas = mano((JORM + ".skill_1", R.PLATA))  # la primera fue verde
        e._contexto_jugadas = None
        jugada = e.guion(2, 2, 1, m)
        self.assertIn(jugada, (0, 1), "otra verde, aunque la roja de oro pegue mas")

    def test_sin_mas_de_ese_color_mueve(self):
        e = ciervo(RQ.WHALE)
        m = mano((FREYR + ".skill_2", R.ORO), (THOR + ".skill_1", R.BRONCE))
        e.jugadas = mano((JORM + ".skill_1", R.PLATA))
        e._contexto_jugadas = None
        self.assertIsInstance(e.guion(2, 2, 1, m), tuple, "mover, no jugar otro color")

    def test_whale_empieza_por_el_color_con_mas_cartas(self):
        e = ciervo(RQ.WHALE)
        m = mano((JORM + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE), (TYR + ".skill_1", R.BRONCE),
                 (FREYR + ".skill_2", R.ORO))
        self.assertIn(e.guion(2, 1, 0, m), (0, 1, 2), "3 verdes frente a 1 roja")

    def test_ahora_es_obligatoria(self):
        self.assertFalse(RQ.saltable("ciervo_piso4", 2))


class ColoresDelEquipo(unittest.TestCase):
    """2026-11-13: la Freyja verde salia "freyja_roja" (roja) y Freyr rojo y azul aparecian a la vez."""

    def test_el_reconocedor_de_los_perros_solo_en_los_perros(self):
        import inspect

        from lumen.modos import perros_piso4 as P4

        fuente = inspect.getsource(P4.PerrosPiso4._jugar_turno)
        self.assertIn("if self.equipo is EQUIPO", fuente)

    def test_aprende_el_equipo_y_solo_mira_sus_cartas(self):
        class Indice:
            equipo = None

            def fijar_equipo(self, heroes):
                self.equipo = set(heroes)

        e = ciervo(RQ.CAUTELOSO)
        e.jugador._indice = Indice()
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (FREYR + ".skill_1", R.BRONCE),
                 (TYR + ".skill_1", R.BRONCE), (THOR + ".skill_2", R.BRONCE), (JORM + ".skill_2", R.BRONCE),
                 (FREYR + ".skill_2", R.BRONCE), ("sun_god_freyr_azul.skill_1", R.BRONCE))
        for _ in range(3):
            e._aprender_equipo(m)
        self.assertEqual(e.jugador._indice.equipo, {THOR, JORM, FREYR, TYR}, "el Freyr azul (1 de 8) fuera")

    def test_indice_con_equipo_no_mira_a_otros(self):
        from lumen.modos.aprender import IndiceCartas

        indice = IndiceCartas.__new__(IndiceCartas)
        indice._memoria = [("x", "y")]
        indice.fijar_equipo({THOR})
        self.assertEqual(indice.equipo, {THOR})
        self.assertEqual(indice._memoria, [], "lo recordado antes se olvida")


class Fusiones(unittest.TestCase):
    """El usuario, 2026-11-13: "aunque tenga cartas iguales para combinar, no lo hace"."""

    def test_al_mover_fusiona_dos_iguales(self):
        e = ciervo(RQ.CAUTELOSO)
        m = mano((THOR + ".skill_1", R.BRONCE), (FREYR + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE),
                 (THOR + ".skill_1", R.BRONCE))
        self.assertEqual(e._mover_para_ulti(m), (0, 3), "Thor sobre Thor (bronce): sube a plata")

    def test_juega_la_que_junta_dos_iguales(self):
        e = ciervo(RQ.CAUTELOSO)
        e.color_turno = "verde"
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (THOR + ".skill_1", R.BRONCE),
                 (TYR + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(3, 2, 0, m), 1, "la verde de en medio: al jugarla, los dos Thor se fusionan")


class Fase4SinColor(unittest.TestCase):
    """El usuario, 2026-11-13: sin la carta del color que toca rompia la secuencia; dos turnos asi, reiniciar."""

    def test_sin_el_color_que_toca_mueve(self):
        e = ciervo(RQ.CAUTELOSO)
        e.decidir(4, 2, 0, mano((JORM + ".skill_1", R.BRONCE)))  # la primera fue verde: toca azul
        m = mano((FREYR + ".skill_1", R.BRONCE), (FREYR + ".skill_2", R.BRONCE), (JORM + ".skill_2", R.BRONCE))
        self.assertIsInstance(e.decidir(4, 2, 1, m)[0], tuple, "no hay azul: mover, no romper la ruleta")
        self.assertIsNone(e.pedir_reinicio)

    def test_dos_turnos_seguidos_pide_reiniciar(self):
        e = ciervo(RQ.CAUTELOSO, ve=(juego.buff_azul,))
        m = mano((FREYR + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE))
        e.guion(4, 2, 0, m)
        self.assertIsNone(e.pedir_reinicio, "un turno sin azul: aun no")
        e.guion(4, 3, 0, m)
        self.assertIn("dos turnos seguidos", e.pedir_reinicio)

    def test_el_modo_reinicia_al_empezar_el_turno(self):
        m = MODOS["ciervo_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        m.estrategia.pedir_reinicio = "prueba"
        self.assertTrue(m._reiniciar_por_bloqueo(object()))
        self.assertIsNone(m.estrategia.pedir_reinicio)


class Fase4Remate(unittest.TestCase):
    """El usuario, 2026-11-13: semaforo 3 turnos y luego a full dano aguantando el contraataque un turno."""

    def test_desde_el_turno_4_full_dano_aunque_haya_contraataque(self):
        e = ciervo(RQ.CAUTELOSO, ve=(juego.contraataque, juego.buff_azul))
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.PLATA), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 4, 0, m), 2, "la ulti de Freyr: ya no se guarda")
        self.assertIsNone(e.pedir_reinicio, "fuera del semaforo no cuenta que falte un color")

    def test_cumplido_el_semaforo_la_cuarta_carta_tambien_ataca(self):
        """El usuario, 2026-11-13: cumplido el semaforo, 4 cartas a full dano ("full es full")."""
        e = ciervo(RQ.CAUTELOSO)
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.PLATA), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 4, 3, m), 2, "la 4.a accion no mueve: la ulti")

    def test_un_turno_sin_color_alarga_el_semaforo(self):
        e = ciervo(RQ.CAUTELOSO, ve=(juego.buff_azul,))
        e._turnos_sin_color = {2}  # en el turno 2 falto el color: ese no quito inmortalidad
        self.assertFalse(e._semaforo_hecho(4))
        self.assertTrue(e._semaforo_hecho(5))
        m = mano((THOR + ".skill_1", R.BRONCE), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 4, 0, m), 0, "turno 4 aun es semaforo: toca azul, no la ulti roja")

    def test_los_3_primeros_turnos_semaforo(self):
        e = ciervo(RQ.CAUTELOSO, ve=(juego.buff_azul,))
        m = mano((THOR + ".skill_1", R.BRONCE), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 2, 0, m), 0, "toca azul (buff): la de Thor, no la ulti roja")


class ColorDeLaFicha(unittest.TestCase):
    """2026-11-13: "freyja_roja" (en femenino) se quedaba sin color y el ciervo nunca jugaba sus cartas."""

    def test_freyja_roja_es_roja(self):
        self.assertEqual(B4.color(mano(("freyja_roja.normal_1", R.BRONCE))[0]), "rojo")
        self.assertEqual(B4.color(mano((THOR + ".skill_1", R.BRONCE))[0]), "azul")

    def test_juega_sus_cartas_en_el_turno_rojo(self):
        e = ciervo(RQ.CAUTELOSO)
        e.decidir(2, 2, 0, mano((FREYR + ".skill_1", R.BRONCE)))  # turno rojo
        m = mano((THOR + ".skill_1", R.BRONCE), ("freyja_roja.normal_2", R.PLATA), (JORM + ".skill_1", R.BRONCE))
        self.assertEqual(e.decidir(2, 2, 1, m)[0], 1)


class Fase4Cadena(unittest.TestCase):
    """2026-11-13: empezaba por rojo sin verdes y, tras mover, volvia a jugar otra roja."""

    def test_turno_1_empieza_por_verde(self):
        """El usuario, 2026-11-13: el semaforo inicia por verde."""
        e = ciervo(RQ.CAUTELOSO)
        m = mano((FREYR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (THOR + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(4, 1, 0, m), 1)

    def test_turno_1_sin_verdes_mueve(self):
        e = ciervo(RQ.CAUTELOSO)
        m = mano((FREYR + ".skill_1", R.BRONCE), ("freyja_roja.normal_1", R.BRONCE), (THOR + ".skill_1", R.BRONCE))
        self.assertIsInstance(e.decidir(4, 1, 0, m)[0], tuple, "sin verde no empieza por otro color: mueve")

    def test_tras_un_movimiento_sigue_la_ultima_carta_jugada(self):
        e = ciervo(RQ.CAUTELOSO)
        e.decidir(4, 2, 0, mano((FREYR + ".skill_1", R.BRONCE)))  # roja: toca verde
        m = mano((FREYR + ".skill_2", R.BRONCE), ("freyja_roja.normal_1", R.BRONCE), (THOR + ".skill_1", R.BRONCE))
        self.assertIsInstance(e.decidir(4, 2, 1, m)[0], tuple, "no hay verde: mueve")
        self.assertIsInstance(e.decidir(4, 2, 2, m)[0], tuple, "sigue tocando verde: no otra roja")
