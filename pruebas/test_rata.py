"""Reglas de Ratatoskr, tal como las explico el usuario jugando una partida (2026-11-09)."""

import unittest

import entorno  # noqa: F401  (antes que lumen)

import cv2
from pathlib import Path

from lumen.modos import bestias_pisos1a3 as B
from lumen.modos import rata as R

C = R.CartaRata


def mano():
    """0 Bleed, 1 Shock, 2 Poison, 3 normal de un objetivo, 4 de area, 5 ulti."""
    return [C(0, {"bleed"}), C(1, {"shock"}), C(2, {"poison"}), C(3), C(4, area=True), C(5, ulti=True)]


class Desventajas(unittest.TestCase):
    def test_solo_las_que_se_aplican(self):
        self.assertEqual(R.desventajas_del_texto("Inflicts damage on one enemy. Shocks for 4 turn(s)."), {"shock"})
        self.assertEqual(R.desventajas_del_texto("Makes target(s) Bleed for 2 turn(s)."), {"bleed"})
        self.assertEqual(R.desventajas_del_texto(
            "Releases 80%. Release: Deals additional damage using remaining damage in Shock, Poison, and Bleed Debuffs."),
            set(), "la definicion de Release las nombra pero no las pone")

    def test_la_que_la_mandaria_donde_ya_esta_no_se_usa(self):
        d = R.decidir(1, 1, 1, {1, 2, 3}, mano(), 4, False)
        self.assertIn(2, d.bloquear, "Poison la manda al 1, donde ya esta")
        self.assertNotIn(0, d.bloquear)


class Piso1(unittest.TestCase):
    def test_a_la_rata_y_al_acabar_el_turno_la_mueve(self):
        d = R.decidir(1, 1, 1, {1, 2, 3}, mano(), 1, True)
        self.assertEqual(d.objetivo, "rata")
        self.assertEqual(d.forzar, {0, 1}, "Bleed o Shock: que no quede en el 1")


class Piso2(unittest.TestCase):
    def test_romper_troncos_sin_moverla(self):
        d = R.decidir(2, 1, 1, {1, 2, 3}, mano(), 4, False)
        self.assertIn(d.objetivo, (2, 3))
        self.assertTrue({0, 1, 2} <= d.bloquear, "no moverla mientras haya troncos")

    def test_sin_troncos_a_la_rata_y_guarda_un_poison(self):
        d = R.decidir(2, 1, 1, {1}, mano(), 4, False)
        self.assertEqual(d.objetivo, "rata")
        self.assertIn(2, d.bloquear, "el unico Poison se guarda")


class Piso3(unittest.TestCase):
    def test_con_las_tres_desventajas_las_lanza(self):
        d = R.decidir(3, 1, 1, {1, 2, 3}, mano(), 4, False)
        self.assertEqual(d.forzar, {0, 1, 2})

    def test_sin_las_tres_las_guarda_y_sin_ultis(self):
        cartas = [c for c in mano() if c.indice != 1]  # falta el Shock
        d = R.decidir(3, 1, 1, {1, 2, 3}, cartas, 4, False)
        self.assertTrue({0, 2, 5} <= d.bloquear, "guardar desventajas; la ulti la moveria al azar")
        self.assertEqual(d.objetivo, 2)

    def test_ulti_de_ultimo_recurso_con_el_tronco_2_roto(self):
        cartas = [c for c in mano() if c.indice != 1]
        d = R.decidir(3, 3, 1, {1, 3}, cartas, 4, False)
        self.assertEqual(d.forzar, {5})

    def test_colocada_rompe_los_otros_sin_pegarle_y_guarda_las_tres(self):
        d = R.decidir(3, 1, 3, {1, 2, 3}, mano(), 4, False)
        self.assertIn(d.objetivo, (1, 2))
        self.assertTrue({4, 5} <= d.bloquear, "area y ulti le pegarian a ella (rebota)")
        self.assertTrue({0, 1, 2} <= d.bloquear, "para la fase siguiente")

    def test_sin_troncos_la_remata(self):
        d = R.decidir(3, 3, 3, {3}, mano(), 4, False)
        self.assertEqual(d.objetivo, "rata")
        self.assertFalse({4, 5} & d.bloquear)


class EnPantalla(unittest.TestCase):
    def leer(self, nombre):
        return cv2.imread(str(Path(__file__).with_name(f"{nombre}.png")))

    def test_donde_esta_la_rata_y_que_troncos_viven(self):
        m = B.RataPisos1a3({"jugar": "Inteligente"})
        self.assertEqual(m.rata_tronco(self.leer("rata_centro")), 1)
        self.assertEqual(m.rata_tronco(self.leer("rata_derecha")), 3)
        p = self.leer("rata_f3")
        self.assertEqual(m.rata_tronco(p), 2)
        self.assertEqual(m.troncos_vivos(p), {1, 2, 3})


if __name__ == "__main__":
    unittest.main()


class CadaTurno(unittest.TestCase):
    def test_marca_el_objetivo_al_empezar_cada_turno(self):
        from unittest import mock

        from lumen import entrada

        m = B.RataPisos1a3({"jugar": "Inteligente"})
        m.piso = 1
        p = cv2.imread(str(Path(__file__).with_name("rata_centro.png")))
        clics = []
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
                mock.patch.object(m, "capturar", lambda: (p, (0, 0))), \
                mock.patch.object(m, "_detectar_fase", lambda p, h: 1), \
                mock.patch.object(B.BestiaPisos1a3, "_empezar_turno", lambda s, p, h: None), \
                mock.patch.object(m, "log", lambda *a, **k: None):
            m._empezar_turno(p, 4)
            m._empezar_turno(p, 4)
        self.assertEqual(clics, [B.RataPisos1a3.ESPIRALES["centro"][1]] * 2, "a la rata, en el tronco del centro")


class Pasivas(unittest.TestCase):
    """La pasiva de Valenti azul: sus ataques de area envenenan (lo senalo el usuario, 2026-11-09)."""

    def test_valenti_azul_y_jormungand_rojo_dan_las_tres(self):
        from lumen.cartas import Carta, Rango, TipoCarta as T

        m = B.RataPisos1a3({"jugar": "Inteligente"})
        nombres = ["valenti_of_obsession_azul.skill_1", "valenti_of_obsession_azul.skill_2",
                   "valenti_of_obsession_azul.ulti", "world_serpent_jormungand_rojo.skill_2"]
        mano = [Carta(i, tipo=T.ULTI if n.endswith("ulti") else T.NORMAL, rango=Rango.ULTI if n.endswith("ulti")
                      else Rango.BRONCE, nombre=n) for i, n in enumerate(nombres)]
        desventajas = [c.desventajas for c in m._cartas_rata(mano)]
        self.assertEqual(desventajas, [{"shock"}, {"poison"}, {"poison"}, {"bleed"}])

    def test_texto_de_la_pasiva(self):
        texto = ("If the hero uses an all-target attack and deals damage, enemies hit by the attack are Poisoned for "
                 "2 turns.")
        self.assertEqual(R.desventajas_de_pasiva(texto), {"area": {"poison"}, "uno": set()})
