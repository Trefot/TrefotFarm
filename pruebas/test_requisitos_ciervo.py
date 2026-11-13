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
        self.assertTrue(RQ.saltable("ciervo_piso4", 2))
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
        self.assertTrue(e.whale("ciervo_piso4", 2, 1))
        self.assertFalse(e.whale("ciervo_piso4", 2, 2), "no cayo en 1 turno")
        self.assertFalse(e.whale("ciervo_piso4", 2, 1), "y lo recuerda en la pelea siguiente")
        self.assertFalse(e.whale("ciervo_piso4", 3, 1), "fase con algo obligatorio: con cautela")

    def test_whale_pega_con_todo_en_la_fase_2(self):
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE),
                 (TYR + ".skill_1", R.BRONCE), (FREYR + ".ulti", R.ULTI))
        self.assertEqual(ciervo(RQ.WHALE).guion(2, 2, 0, m), 4, "la ulti, no 3 del mismo color")
        self.assertNotEqual(ciervo(RQ.CAUTELOSO).guion(2, 2, 0, m), 4)

    def test_fase_3_impar_mismo_color_aunque_sea_whale(self):
        m = mano((JORM + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE), (TYR + ".skill_1", R.BRONCE),
                 (THOR + ".ulti", R.ULTI))
        self.assertIn(ciervo(RQ.WHALE).guion(3, 1, 0, m), (0, 1, 2), "turno impar: verde, o Fierce Rush mata")
        self.assertEqual(ciervo(RQ.WHALE).guion(3, 2, 0, m), 3, "turno par: con todo")

    def test_contraataque_quita_la_postura_o_no_ataca(self):
        e = ciervo(RQ.WHALE, ve=(juego.contraataque,))
        m = mano((THOR + ".skill_1", R.BRONCE), (MELI + ".ulti", R.ULTI))
        self.assertEqual(e.guion(4, 2, 0, m), 1, "la ulti de Meliodas traidor quita posturas")
        sin = mano((THOR + ".skill_1", R.BRONCE), (THOR + ".skill_2", R.BRONCE))
        self.assertIsInstance(e.guion(4, 2, 0, sin), tuple, "sin nada que la quite: mover, no atacar")

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
