"""Oro: al quedarse sin estamina el juego muestra "Auto Repeat Results" y el bot se quedaba mirando 7 min
(captura real, 2026-11-24). Ahora toca su OK."""
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import vision
from lumen.modos import fuerte_solgres as F

CAPTURA = Path(__file__).parent / "oro_sin_estamina.png"
POCION = Path(__file__).parent / "oro_ventana_pocion.png"  # al pulsar Start sin estamina
VICTORIA = Path(__file__).parent / "oro_victoria_tras_resultados.png"  # lo que sale despues de ese OK


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

        # Despues: el Victory con Again y OK. Toca su OK (no Again: con 4 de estamina no llega a 30)
        with mock.patch("lumen.entrada.clic") as clic:
            self.assertIsNone(m.pelea(vision.leer_imagen(VICTORIA), (0, 0)))
        x, y, w, h = clic.call_args[0][0]
        self.assertTrue(x >= 300 and y >= 860, (x, y))

    def test_entre_vueltas_no_toca_el_victory(self):
        m = F.Oro({"victorias": 0, "pociones": False, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        with mock.patch("lumen.entrada.clic") as clic:
            m.pelea(vision.leer_imagen(VICTORIA), (0, 0))
        self.assertEqual(clic.call_count, 0, "la repeticion sigue sola: no se corta")

    def test_sin_pociones_cierra_la_ventana_antes_de_terminar(self):
        from lumen.motor import TerminarModo

        m = F.Oro({"victorias": 0, "pociones": False, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        m.publicar_stats = lambda **k: None
        with mock.patch("lumen.entrada.clic") as clic, self.assertRaises(TerminarModo):
            m.pelea(vision.leer_imagen(POCION), (0, 0))
        self.assertEqual(clic.call_args[0][0], F.CERRAR_POCION)

    def test_al_llegar_a_las_vueltas_para_la_repeticion_y_sale_limpio(self):
        """Oro 2 vueltas: el juego siguio hasta 4 y el pajaro empezo encima de los resultados (2026-11-24)."""
        from entorno import PlantillaFalsa
        from lumen import juego
        from lumen.motor import TerminarModo

        falsas = {n: PlantillaFalsa(n) for n in ("VUELTA_TERMINADA", "OK_RESULTADOS", "OK_VICTORIA", "EMPEZAR",
                                                "RESULTADO", "REPETIR_APAGADO")}
        m = F.Oro({"victorias": 2, "pociones": True, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        m.publicar_stats = lambda **k: None
        with mock.patch.multiple(F, **falsas), mock.patch.object(juego, "pocion_stamina", PlantillaFalsa("pocion")),                 mock.patch.object(juego, "info_mision", PlantillaFalsa("info")),                 mock.patch("lumen.entrada.clic") as clic:
            m.vueltas = 1
            self.assertIsNone(m.pelea({"VUELTA_TERMINADA"}, (0, 0)), "llega a 2: no termina todavia")
            self.assertTrue(m.cerrando)
            self.assertEqual(clic.call_count, 1, "toca la pantalla para parar la repeticion")
            m.pelea({"OK_RESULTADOS"}, (0, 0))
            m.pelea({"OK_VICTORIA"}, (0, 0))
            self.assertEqual(clic.call_count, 3)
            with self.assertRaises(TerminarModo):
                m.pelea({"EMPEZAR"}, (0, 0))
        self.assertEqual(m.vueltas, 2)


if __name__ == "__main__":
    unittest.main()
