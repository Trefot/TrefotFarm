"""Mis equipos (2026-11-22): sale el equipo con el que juegas aunque no este en la lista, y la medida es lo que
tarda una pelea."""
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen.gui.paginas import equipos as E

MIO = frozenset({"freyja_roja", "god_of_war_tyr_verde", "sun_god_freyr_rojo", "thor_the_god_of_thunder_azul"})
LISTA = frozenset({"a", "b", "c", "d"})


def medida(v, d=0, r=0, segundos=0):
    return {"victorias": v, "derrotas": d, "reinicios": r, "segundos": segundos, "por_hora": 1.0, "tasa": 50}


class MisEquipos(unittest.TestCase):
    def test_sale_el_que_juegas_desde_una_pelea_y_no_los_de_la_lista(self):
        """El usuario, 2026-11-24: con 1 intento ya tiene que salir, con su tiempo."""
        uno = frozenset({"x", "y", "z", "w"})
        medidas = {MIO: medida(10, 2, 3), LISTA: medida(5), uno: medida(1), frozenset({"q", "r", "s", "t"}): medida(0)}
        with mock.patch.object(E, "medidas", lambda clave: medidas):
            tuyos = E.equipos_tuyos("ciervo_piso4", "ciervo_piso4", [sorted(LISTA)])
        self.assertEqual({frozenset(d["personajes"]) for d, _ in tuyos}, {MIO, uno})
        self.assertEqual(tuyos[0][0]["nivel"], "tuyo")

    def test_sin_ninguna_victoria_no_sale(self):
        """2026-11-24: la pelea del lio (el ciervo jugado como pajaro, 1 derrota) salia como tu equipo del pajaro."""
        with mock.patch.object(E, "medidas", lambda clave: {MIO: medida(0, 1)}):
            self.assertEqual(E.equipos_tuyos("pajaro_piso4"), [])

    def test_fuerte_solgres_por_nombre_no_se_repite(self):
        with mock.patch.object(E, "medidas", lambda clave: {frozenset({"equipo:Farm.Oro"}): medida(9)}):
            self.assertEqual(E.equipos_tuyos("monedas_sa"), [])

    def test_tiempo_por_pelea(self):
        self.assertEqual(E.texto_por_pelea(medida(8, 1, 1, segundos=3240)), "5 min 24 s por pelea")
        self.assertEqual(E.texto_por_pelea(medida(1, segundos=45)), "45 s por pelea")


if __name__ == "__main__":
    unittest.main()
