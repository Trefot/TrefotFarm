"""Demonios: aceptar la invitacion de un amigo (foto del usuario del 2026-11-27, Indura Chaos)."""
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import entorno  # noqa: F401
from lumen.modos import indura as M
from lumen.vision import leer_imagen

FOTO = leer_imagen(Path(__file__).with_name("invitacion_amigo.jpg"))
NEGRA = np.zeros((940, 550, 3), np.uint8)


class Reconocer(unittest.TestCase):
    def test_ve_accept_invitation(self):
        rect = M.ACEPTAR_AMIGO.buscar(FOTO, 0.8)
        self.assertIsNotNone(rect)
        x, y, w, h = rect
        self.assertTrue(290 < x + w / 2 < 430 and 750 < y + h / 2 < 800)  # el verde, no "View Later"

    def test_no_la_confunde_con_la_de_tiempo_real(self):
        self.assertFalse(M.ACEPTAR.esta(FOTO, 0.7))


class Esperar(unittest.TestCase):
    def setUp(self):
        self.m = M.Indura({"partidas": M.AMIGOS, "nivel": "Chaos", "victorias": 0, "jugar": "AUTO",
                           "espera": "9.3", "minutos_sin_invitacion": 20})
        self.m.log = lambda *a, **k: None
        self.capturas = []
        self.m.capturar = lambda: (self.capturas.pop(0) if self.capturas else NEGRA, (0, 0))
        self.toques = []
        parche = mock.patch.object(M.entrada, "clic", side_effect=lambda r, o, espera=0: self.toques.append(r))
        parche.start()
        self.addCleanup(parche.stop)
        for p in (mock.patch.object(M.control, "esperar"), mock.patch.object(M.control, "revisar")):
            p.start()
            self.addCleanup(p.stop)

    def test_empieza_esperando_y_vuelve_a_esperar(self):
        self.assertEqual(self.m.estado_inicial(), "buscar")
        self.assertEqual(self.m.estados()["buscar"], self.m.esperar_amigo)
        self.assertEqual(self.m._volver(), "buscar")
        buscar = M.Indura({"partidas": M.BUSCAR, "nivel": "Chaos"})
        self.assertEqual((buscar.estado_inicial(), buscar._volver()), ("ir_a_indura", "ir_a_indura"))

    def test_acepta_y_va_a_la_sala(self):
        self.assertEqual(self.m.esperar_amigo(FOTO, (0, 0)), "preparar")
        self.assertEqual(len(self.toques), 1)

    def test_si_el_toque_no_entra_sigue_esperando(self):
        self.capturas = [FOTO]
        self.assertIsNone(self.m.esperar_amigo(FOTO, (0, 0)))

    def test_sin_invitacion_espera_y_al_final_termina(self):
        self.assertIsNone(self.m.esperar_amigo(NEGRA, (0, 0)))
        self.assertEqual(self.toques, [])
        self.m.buscando_desde -= 21 * 60
        with self.assertRaises(M.TerminarModo):
            self.m.esperar_amigo(NEGRA, (0, 0))


if __name__ == "__main__":
    unittest.main()
