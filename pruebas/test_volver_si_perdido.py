"""Al empezar un modo en una pantalla que no conoce (el anterior del plan acabo en la lista de pisos del oro), se
vuelve atras con la flecha (2026-11-24: el pajaro se quedo 4 min quieto)."""
import time
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import entrada, vision
from lumen.modos import MODOS
from lumen.modos import fuerte_solgres as F
from lumen.motor import TerminarModo

LISTA = Path(__file__).parent / "oro_lista_pisos.png"


def modo(id_):
    m = MODOS[id_]({"victorias": 1, "extra": 0, "pociones": True, "max_pociones": 0})
    m.log = lambda *a, **k: None
    return m


class VolverSiPerdido(unittest.TestCase):
    def test_toca_la_flecha_tras_un_rato_sin_hacer_nada(self):
        p = vision.leer_imagen(LISTA)
        m = modo("pajaro_piso4")
        with mock.patch("lumen.entrada.clic") as clic:
            entrada.ultimo_toque = 0.0
            self.assertFalse(m._volver_si_perdido(p, (0, 0)), "recien empezado: espera")
            m._inicial_desde = time.time() - 60
            self.assertTrue(m._volver_si_perdido(p, (0, 0)))
        x, y, w, h = clic.call_args[0][0]
        self.assertTrue(x < 80 and y < 100, (x, y))

    def test_cierra_el_result_de_los_tickets(self):
        """Red Demon empezo sobre el RESULT de los tickets del oro y se quedo 3 min (2026-11-24)."""
        p = vision.leer_imagen(Path(__file__).parent / "resultado_tickets.png")
        m = modo("demonio_rojo")
        m._inicial_desde = time.time() - 60
        entrada.ultimo_toque = 0.0
        with mock.patch("lumen.entrada.clic") as clic:
            self.assertTrue(m._volver_si_perdido(p, (0, 0)))
        x, y, w, h = clic.call_args[0][0]
        self.assertTrue(y < 150, (x, y))

    def test_si_el_modo_esta_tocando_no_interviene(self):
        p = vision.leer_imagen(LISTA)
        m = modo("pajaro_piso4")
        m._inicial_desde = time.time() - 60
        entrada.ultimo_toque = time.time()
        with mock.patch("lumen.entrada.clic") as clic:
            self.assertFalse(m._volver_si_perdido(p, (0, 0)))
        self.assertEqual(clic.call_count, 0)

    def test_oro_con_vueltas_pendientes_vuelve_a_entrar_al_piso_6(self):
        m = F.Oro({"victorias": 5, "pociones": True, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        m.vueltas = 4
        with mock.patch("lumen.entrada.clic") as clic:
            self.assertIsNone(m.pelea(vision.leer_imagen(LISTA), (0, 0)))
        x, y, w, h = clic.call_args[0][0]
        self.assertTrue(250 <= y <= 420, (x, y))  # la fila del 6.º piso

    def test_oro_al_cerrar_termina_en_la_lista_de_pisos(self):
        m = F.Oro({"victorias": 2, "pociones": True, "max_pociones": 0, "tickets": False, "max_tickets": 0})
        m.log = lambda *a, **k: None
        m.cerrando, m.cerrando_desde = True, time.monotonic()
        with mock.patch("lumen.entrada.clic"), self.assertRaises(TerminarModo):
            m.pelea(vision.leer_imagen(LISTA), (0, 0))


if __name__ == "__main__":
    unittest.main()
