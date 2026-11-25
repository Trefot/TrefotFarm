"""Oro: al quedarse sin estamina el juego muestra "Auto Repeat Results" y el bot se quedaba mirando 7 min
(captura real, 2026-11-24). Ahora toca su OK."""
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import vision
from lumen.modos import fuerte_solgres as F

CAPTURA = Path(__file__).parent / "oro_sin_estamina.png"


class OroSinEstamina(unittest.TestCase):
    def test_toca_el_ok_de_los_resultados(self):
        p = vision.leer_imagen(CAPTURA)
        m = F.Oro({"victorias": 0, "pociones": False, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        with mock.patch("lumen.entrada.clic") as clic:
            self.assertIsNone(m.pelea(p, (0, 0)))
        self.assertEqual(clic.call_count, 1)
        x, y, w, h = clic.call_args[0][0]
        self.assertTrue(200 <= x <= 360 and 800 <= y <= 880, (x, y))  # el OK de abajo, no el apagado de detras


if __name__ == "__main__":
    unittest.main()
