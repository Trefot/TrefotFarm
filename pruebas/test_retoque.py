"""Lobos, 2026-11-10: el juego a veces no registra el toque de una carta; se toca otra vez antes de darla por
bloqueada (el guion reiniciaba la pelea aunque iba bien)."""

import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

import numpy as np

from lumen import entrada, juego
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.modos import perros_piso4 as P4


class Retoque(unittest.TestCase):
    def jugar(self, toques_que_fallan: int):
        m = P4.PerrosPiso4({})
        m._nueva_pelea()
        m.fase, m.turno_fase, m.huecos_turno = 1, 1, 1
        img = np.full((10, 10, 3), 77, np.uint8)
        clics, estado = [], {"huecos": 1, "fallos": toques_que_fallan}

        def clic(rect, o, **k):
            clics.append(rect)
            if estado["fallos"]:
                estado["fallos"] -= 1
            else:
                estado["huecos"] = 0  # la carta entra y el turno acaba

        def decidir(fase, turno, accion, mano, total):
            jugables = [i for i, c in enumerate(mano) if c.jugable]
            if not jugables:
                raise P4.Reiniciar("falta la postura de Thonar")
            return jugables[0], None, False

        reloj = {"t": 0.0}
        with mock.patch.object(m, "capturar", lambda: (set(), (0, 0))), \
                mock.patch.object(P4.C, "contar_huecos", lambda p, u=0.7: estado["huecos"]), \
                mock.patch.object(P4.C, "leer_mano", lambda p: [Carta(0, (1, 2, 3, 4), img, TipoCarta.NORMAL, Rango.PLATA)]), \
                mock.patch.object(P4.EQUIPO, "etiquetar", lambda mano: mano), \
                mock.patch.object(m.estrategia, "decidir", decidir), \
                mock.patch.object(m.estrategia, "fusiones_al_jugar", lambda mano, i: 0), \
                mock.patch.object(entrada, "clic", clic), \
                mock.patch.object(P4.time, "time", lambda: reloj.__setitem__("t", reloj["t"] + 0.05) or reloj["t"]), \
                mock.patch.object(m, "esperar_corto", lambda s: None), \
                mock.patch.object(m, "log", lambda *a, **k: None), \
                mock.patch.object(juego, "victoria", entorno.PlantillaFalsa("victoria")), \
                mock.patch.object(juego, "derrota", entorno.PlantillaFalsa("derrota")):
            resultado = m._jugar_turno()
        return resultado, len(clics)

    def test_un_toque_perdido_no_reinicia(self):
        self.assertEqual(self.jugar(1), (None, 2), "la toca otra vez y entra")

    def test_bloqueada_de_verdad_si(self):
        resultado, toques = self.jugar(5)
        self.assertEqual(resultado, "rendirse")
        self.assertEqual(toques, 2, "dos intentos y la da por bloqueada")


if __name__ == "__main__":
    unittest.main()
