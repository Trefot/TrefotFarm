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


class RellenoTurno2(unittest.TestCase):
    """Lobos, 2026-11-10: con 2 singles de Odin y 2 areas de Gawain reiniciaba ("solo quedan cartas de Odin...")."""

    def mano(self, nombres_rangos):
        T, R = TipoCarta, Rango
        return [Carta(i, (0, 0, 1, 1), None, T.SUELO if n is None else T.NORMAL, R.NINGUNO if n is None else r, n)
                for i, (n, r) in enumerate(nombres_rangos)]

    def test_usa_la_copia_de_sobra(self):
        R = Rango
        mano = self.mano([(None, None), (None, None), ("gawain.area", R.BRONCE), ("odin.area", R.BRONCE),
                          ("odin.single", R.BRONCE), ("odin.single", R.PLATA), ("odin.area", R.PLATA),
                          ("gawain.area", R.PLATA)])
        idx, _, _ = P4.Estrategia()._f1t2(mano, 2, 4)
        self.assertEqual(idx, 4, "la single de Odin de bronce; la de plata queda para la cuarta")

    def test_sin_copias_sigue_reiniciando(self):
        R = Rango
        mano = self.mano([(None, None), (None, None), ("gawain.area", R.BRONCE), ("odin.area", R.BRONCE),
                          ("odin.single", R.PLATA), (None, None), (None, None), (None, None)])
        with self.assertRaises(P4.Reiniciar):
            P4.Estrategia()._f1t2(mano, 2, 4)


class CasillasQueSuben(unittest.TestCase):
    """Lobos, 2026-11-10: tras la ulti de Freyja leyo 2 casillas libres (ya no quedaba ninguna), volvio a pedir
    "la 3.a carta" y reinicio con la pelea bien."""

    def test_una_lectura_que_sube_no_repite_cartas(self):
        m = P4.PerrosPiso4({})
        m._nueva_pelea()
        m.fase, m.turno_fase, m.huecos_turno = 2, 1, 4
        img = np.full((10, 10, 3), 77, np.uint8)
        lecturas = iter([4, 3, 2, 1, 2, 2, 0])  # tras la 4.a carta, una mala lectura (2) y despues 0
        estado = {"huecos": 4}
        pedidas = []

        def capturar():
            estado["huecos"] = next(lecturas, 0)
            return set(), (0, 0)

        def decidir(fase, turno, accion, mano, total):
            pedidas.append(accion)
            return 0, None, False

        with mock.patch.object(m, "capturar", capturar), \
                mock.patch.object(P4.C, "contar_huecos", lambda p, u=0.7: estado["huecos"]), \
                mock.patch.object(P4.C, "leer_mano", lambda p: [Carta(0, (1, 2, 3, 4), img, TipoCarta.NORMAL, Rango.PLATA)]), \
                mock.patch.object(P4.EQUIPO, "etiquetar", lambda mano: mano), \
                mock.patch.object(m.estrategia, "decidir", decidir), \
                mock.patch.object(m.estrategia, "fusiones_al_jugar", lambda mano, i: 0), \
                mock.patch.object(m, "_esperar_hueco", lambda h, limite=1.6: True), \
                mock.patch.object(entrada, "clic", lambda *a, **k: None), \
                mock.patch.object(m, "esperar_corto", lambda s: None), \
                mock.patch.object(m, "log", lambda *a, **k: None), \
                mock.patch.object(juego, "victoria", entorno.PlantillaFalsa("victoria")), \
                mock.patch.object(juego, "derrota", entorno.PlantillaFalsa("derrota")):
            m._jugar_turno()
        self.assertEqual(pedidas, [0, 1, 2, 3], "cada carta una vez; la lectura que sube se ignora")
