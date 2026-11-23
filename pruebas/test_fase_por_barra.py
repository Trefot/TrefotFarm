"""Pajaro y ciervo Floor 4: la fase tambien por el color de la barra del jefe (2026-11-22). El letrero de la fase no
siempre se ve y se jugaban 1-2 turnos con las reglas de la fase anterior."""
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen.modos import MODOS
from lumen.vida_jefe import Vida


class Corte(Exception):
    pass


def empezar(m, capa, letrero=None):
    """Empieza un turno con la barra de ``capa`` y el letrero ``letrero`` (o ninguno); se corta tras fijar la fase."""
    m._detectar_fase = lambda p, h: letrero
    m._stats = mock.Mock(side_effect=Corte)
    with mock.patch("lumen.vida_jefe.leer", return_value=Vida(capa, 0.95) if capa else None):
        try:
            m._empezar_turno(object(), 4)
        except Corte:
            pass


class FasePorBarra(unittest.TestCase):
    def modo(self, id_):
        m = MODOS[id_]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        return m

    def test_barra_roja_en_la_fase_3_es_la_fase_4(self):
        for id_ in ("pajaro_piso4", "ciervo_piso4"):
            m = self.modo(id_)
            m.fase, m.turno_fase = 3, 2
            empezar(m, "rojo")
            self.assertEqual((m.fase, m.turno_fase), (4, 1), id_)

    def test_ciervo_fase_2_con_la_barra_morada(self):
        m = self.modo("ciervo_piso4")
        m.fase, m.turno_fase = 2, 3
        empezar(m, "morado")
        self.assertEqual((m.fase, m.turno_fase), (3, 1))

    def test_no_salta_dos_fases_ni_retrocede(self):
        m = self.modo("ciervo_piso4")
        m.fase, m.turno_fase = 1, 1
        empezar(m, "rojo")  # un color mal leido
        self.assertEqual((m.fase, m.turno_fase), (1, 2))
        m.fase = 3
        empezar(m, "azul")
        self.assertEqual(m.fase, 3)

    def test_el_letrero_sigue_mandando(self):
        m = self.modo("pajaro_piso4")
        m.fase, m.turno_fase = 2, 2
        empezar(m, "azul", letrero=3)
        self.assertEqual((m.fase, m.turno_fase), (3, 1))
        empezar(m, None)
        self.assertEqual((m.fase, m.turno_fase), (3, 2), "sin barra, como siempre")

    def test_los_perros_no_leen_la_barra(self):
        m = self.modo("perros_piso4")
        m.fase, m.turno_fase = 1, 1
        empezar(m, "azul")
        self.assertEqual(m.fase, 1)


if __name__ == "__main__":
    unittest.main()
