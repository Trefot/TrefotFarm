"""Avisos de los lunes en las bestias (2026-11-24): "Challenge restrictions removed!" se cierra tocandolo."""
import unittest
from pathlib import Path
from unittest import mock

import cv2

import entorno  # noqa: F401  (antes que lumen)

from lumen.modos import MODOS
from lumen.modos import perros_piso4 as P4

PANTALLA = Path(__file__).with_name("restricciones_quitadas.png")


class AvisosLunes(unittest.TestCase):
    def test_cierra_restricciones_quitadas(self):
        m = MODOS["pajaro_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        clics = []
        with mock.patch.object(P4.entrada, "clic", lambda punto, o, espera=0: clics.append(punto)):
            self.assertTrue(m.comprobaciones_globales(cv2.imread(str(PANTALLA)), (0, 0)))
        self.assertEqual(len(clics), 1)

    def test_first_reward_ya_no_espera_6_segundos(self):
        self.assertLessEqual(P4.ESPERA_PRIMERA, 3)


if __name__ == "__main__":
    unittest.main()
