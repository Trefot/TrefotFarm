"""Bestias Floor 1-3 en AUTO: se reconoce el equipo mirando la mano (2026-11-24), para Mis equipos."""
import unittest
from pathlib import Path

import cv2

import entorno  # noqa: F401  (antes que lumen)

from lumen.modos import MODOS

PANTALLA = Path(__file__).with_name("rata_f2_tres.png")


class EquipoEnAuto(unittest.TestCase):
    def test_reconoce_los_4_heroes_sin_jugar_cartas(self):
        m = MODOS["serpiente_pisos1a3"]({"jugar": "AUTO", "victorias": 1})
        m.log = lambda *a, **k: None
        p = cv2.imread(str(PANTALLA))
        for _ in range(6):
            m._mano_auto_en = 0
            m._mirar_equipo_auto(p)
        self.assertEqual(m.equipo_de_la_sesion(), ["gawain", "nightmare_salos_verde", "valenti_of_obsession_azul",
                                                   "world_serpent_jormungand_rojo"])

    def test_no_mira_a_cada_momento(self):
        m = MODOS["serpiente_pisos1a3"]({"jugar": "AUTO", "victorias": 1})
        m._mano_auto_en = 10 ** 12  # acaba de mirar
        m._mirar_equipo_auto(cv2.imread(str(PANTALLA)))
        self.assertEqual(m.heroes_vistos, {})


if __name__ == "__main__":
    unittest.main()
