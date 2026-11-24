"""La prueba del modo en segundo plano: comparar capturas y mandar el clic sin mover el raton."""

import sys
import unittest
from unittest import mock

import entorno  # noqa: F401
import numpy as np

from lumen import segundo_plano as sp


class Comparar(unittest.TestCase):
    def test_misma_imagen_y_falta(self):
        a = np.full((940, 550, 3), 100, np.uint8)
        self.assertEqual(sp.diferencia(a, a.copy()), 0.0)
        self.assertEqual(sp.diferencia(a, None), 255.0)

    def test_tamano_distinto_se_ajusta(self):
        # en pantallas bajas el bot agranda su captura; la de PrintWindow es mas pequena
        a = np.full((940, 550, 3), 100, np.uint8)
        b = np.full((470, 275, 3), 100, np.uint8)
        self.assertLess(sp.diferencia(a, b), 1.0)

    def test_negra(self):
        self.assertTrue(sp.es_negra(np.zeros((10, 10, 3), np.uint8)))
        self.assertTrue(sp.es_negra(None))
        self.assertFalse(sp.es_negra(np.full((10, 10, 3), 90, np.uint8)))

    def test_lparam(self):
        self.assertEqual(sp.lparam(10, 20), (20 << 16) | 10)


class Clic(unittest.TestCase):
    def test_clic_a_la_hija_sin_mover_el_raton(self):
        gui, api = sys.modules["win32gui"], sys.modules["win32api"]
        gui.reset_mock()
        api.reset_mock()
        gui.ScreenToClient.side_effect = lambda h, p: (p[0] - 100, p[1] - 50) if h == 1 else (p[0] - 108, p[1] - 81)
        gui.ChildWindowFromPoint.return_value = 2
        with mock.patch.object(sp.time, "sleep"):
            destino = sp.clic_mensaje(1, 300, 400)
        self.assertEqual(destino, 2)
        mensajes = [c.args for c in api.PostMessage.call_args_list]
        self.assertEqual([m[1] for m in mensajes], [sp.WM_MOUSEMOVE, sp.WM_LBUTTONDOWN, sp.WM_LBUTTONUP])
        self.assertTrue(all(m[0] == 2 and m[3] == sp.lparam(192, 319) for m in mensajes))
        api.SendMessage.assert_not_called()
        api.mouse_event.assert_not_called()
        gui.ScreenToClient.side_effect = None


if __name__ == "__main__":
    unittest.main()
