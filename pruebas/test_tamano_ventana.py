"""La ventana del juego cambia de tamano a media sesion (2026-11-16: 534x960 tras una pausa, 22 reinicios)."""
import unittest
from unittest import mock

import entorno  # noqa: F401
from lumen import motor, ventana


class Modo(motor.Modo):
    id, nombre = "prueba", "Prueba"

    def estado_inicial(self):
        return "a"

    def estados(self):
        return {"a": lambda p, o: None}


class VigilarTamano(unittest.TestCase):
    def setUp(self):
        self.m = Modo({})
        self.mensajes = []
        self.m.log = lambda texto, nivel="info": self.mensajes.append((nivel, texto))
        self.reloj = [1000.0]
        p = mock.patch.object(motor.time, "time", side_effect=lambda: self.reloj[0])
        p.start()
        self.addCleanup(p.stop)
        for nombre, valor in (("tamano_objetivo", (554, 960)),):
            p = mock.patch.object(ventana, nombre, return_value=valor)
            p.start()
            self.addCleanup(p.stop)

    def _con(self, tam, ajusta=True):
        return (mock.patch.object(ventana, "tamano_actual", return_value=tam),
                mock.patch.object(ventana, "ajustar_tamano", return_value=ajusta))

    def test_bien_no_toca_nada(self):
        a, b = self._con((554, 960))
        with a, b as ajustar:
            self.m._vigilar_tamano()
        ajustar.assert_not_called()
        self.assertEqual(self.mensajes, [])

    def test_mas_estrecha_la_vuelve_a_dejar_bien(self):
        a, b = self._con((534, 960))
        with a, b as ajustar:
            self.m._vigilar_tamano()
        ajustar.assert_called_once()
        self.assertEqual(self.mensajes[0][0], "aviso")
        self.assertIn("534x960", self.mensajes[0][1])
        self.assertIn("554x960", self.mensajes[0][1])

    def test_mira_cada_5_segundos(self):
        a, b = self._con((534, 960))
        with a, b as ajustar:
            self.m._vigilar_tamano()
            self.reloj[0] += 2
            self.m._vigilar_tamano()
            self.reloj[0] += 4
            self.m._vigilar_tamano()
        self.assertEqual(ajustar.call_count, 2)

    def test_si_no_puede_avisa_una_vez(self):
        a, b = self._con((534, 960), ajusta=False)
        with a, b as ajustar:
            for _ in range(4):
                self.m._vigilar_tamano()
                self.reloj[0] += 6
        self.assertEqual(ajustar.call_count, 4)
        self.assertEqual([n for n, _ in self.mensajes], ["error"])

    def test_cerrada_o_minimizada_no_la_toca(self):
        for tam in (None, (160, 28)):
            a, b = self._con(tam)
            with a, b as ajustar:
                self.reloj[0] += 6
                self.m._vigilar_tamano()
            ajustar.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class RachaSinGanar(unittest.TestCase):
    def _modo(self):
        import numpy as np
        from lumen.modos import MODOS
        from lumen.modos import perros_piso4 as PP
        m = MODOS["pajaro_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        m.inicio_pelea = 0.0
        self.p = np.zeros((940, 550, 3), np.uint8)
        for parche in (mock.patch.object(m, "_volvio_a_pisos", return_value=True),
                       mock.patch.object(m, "clic_si", return_value=False),
                       mock.patch.object(PP.avisos, "enviar"),
                       mock.patch.object(PP.ventana, "capturar", return_value=(self.p, (0, 0)))):
            parche.start()
            self.addCleanup(parche.stop)
        return m, PP

    def test_diez_reinicios_seguidos_para_y_avisa(self):
        m, PP = self._modo()
        for _ in range(PP.SIN_GANAR_MAXIMO - 1):
            m.reinicio_pedido = True
            self.assertEqual(m.derrota(self.p, (0, 0)), "elegir_piso")
        PP.avisos.enviar.assert_not_called()
        m.reinicio_pedido = True
        with self.assertRaises(motor.TerminarModo):
            m.derrota(self.p, (0, 0))
        PP.avisos.enviar.assert_called_once()

    def test_una_victoria_pone_la_racha_a_cero(self):
        m, PP = self._modo()
        m.seguidas_sin_ganar = PP.SIN_GANAR_MAXIMO - 1
        m.victorias = 0
        with mock.patch.object(m, "_meta_cumplida", return_value=False), \
             mock.patch.object(m, "_stats"), \
             mock.patch.object(PP.juego.victoria, "esta", return_value=True):
            try:
                m.victoria(self.p, (0, 0))
            except Exception:
                pass
        self.assertEqual(m.seguidas_sin_ganar, 0)
