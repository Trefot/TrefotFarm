"""Pantallas bajas (1366x768): ventana del juego reducida, captura agrandada y clics convertidos."""

import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

import numpy as np

from lumen import entrada, ventana as V


class VentanaReducida(unittest.TestCase):
    def _parchear(self, objeto, nombre, valor):
        p = mock.patch.object(objeto, nombre, valor)
        p.start()
        self.addCleanup(p.stop)

    def _ventana(self, exterior, cliente_xy, cliente_tam, alto_util):
        """Una ventana del juego falsa: rect exterior (izq, arr, der, aba) y zona del juego."""
        self._parchear(V, "buscar_ventana", lambda: 1)
        self._parchear(V, "_alto_util", lambda: alto_util)
        self._parchear(V.win32gui, "GetWindowRect", lambda h: exterior)
        self._parchear(V.win32gui, "GetClientRect", lambda h: (0, 0, *cliente_tam))
        self._parchear(V.win32gui, "ClientToScreen", lambda h, p: cliente_xy)

    def test_en_pantalla_normal_no_cambia_nada(self):
        self._ventana((10, 20, 564, 980), (18, 51), (538, 921), alto_util=1032)
        self.assertEqual(V.tamano_objetivo(), (554, 960))
        self.assertTrue(V.tamano_correcto((554, 960)))
        self.assertIsNone(V._capturar_reducida(1, 550, 940), "con la ventana normal, la captura de siempre")
        o = V.Origen((10, 20))
        self.assertFalse(o.reducida)
        self.assertEqual(entrada._punto((100, 200), o), (110, 220))
        self.assertEqual(entrada._punto((100, 200), (10, 20)), (110, 220), "un origen normal (p. ej. el lanzador)")

    def test_tamano_en_pantalla_de_1366x768(self):
        """Barra de tareas de 40 px: quedan 728. Bordes y barra de titulo de 16 x 39 px."""
        self._ventana((0, 0, 554, 960), (8, 31), (538, 921), alto_util=728)
        ancho, alto = V.tamano_objetivo()
        self.assertEqual(alto, 728)
        escala = (728 - 39) / 921
        self.assertEqual(ancho, round(538 * escala) + 16)
        self.assertFalse(V.tamano_correcto((554, 960)))
        self.assertTrue(V.tamano_correcto((ancho, alto)))

    def test_captura_agrandada_y_clic_convertido(self):
        ancho, alto = 402, 689  # zona del juego con la ventana reducida (escala ~0,748)
        self._ventana((92, 0, 92 + 418, 728), (100, 31), (ancho, alto), alto_util=728)
        juego = np.zeros((alto, ancho, 3), dtype=np.uint8)
        juego[alto // 2 - 5:alto // 2 + 5, ancho // 2 - 5:ancho // 2 + 5] = 255  # un punto blanco en el centro
        self._parchear(V, "_capturar_region", lambda origen, w, h: juego)
        captura, o = V._capturar_reducida(1, 550, 940)
        self.assertEqual(captura.shape, (940, 550, 3), "del tamano de siempre: las plantillas no cambian")
        self.assertTrue(o.reducida)
        # El centro de la zona del juego cae donde caeria en una captura normal...
        cx, cy = 8 + 538 // 2, 31 + 921 // 2
        self.assertGreater(captura[cy, cx].mean(), 200)
        self.assertEqual(captura[10, 10].mean(), 0, "la barra de titulo queda en negro")
        # ...y un clic ahi va al centro real de la ventana pequena.
        x, y = entrada._punto((cx, cy), o)
        self.assertLessEqual(abs(x - (100 + ancho // 2)), 1)
        self.assertLessEqual(abs(y - (31 + alto // 2)), 1)
        self.assertEqual(o.a_ventana(x, y), (cx, cy), "y al reves (Aprender de mi)")

    def test_rectangulo_de_plantilla_en_ventana_reducida(self):
        o = V.Origen((0, 0), cliente=(100, 31), escala=(0.5, 0.5))
        self.assertEqual(entrada._punto((8, 31, 20, 40), o), (105, 41), "el centro del rectangulo, convertido")


if __name__ == "__main__":
    unittest.main()
