"""Regresiones del ciervo y del ritmo de colocacion; no usan el juego ni el raton."""
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

import entorno  # noqa: F401
from lumen import cartas as C, juego
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.control import control
from lumen.modos import bestias_piso4 as B4
from lumen.modos import perros_piso4 as P4
from test_piso4 import mano, estrategia, TYR, JORM, THOR, FREYR


class CiervoRegresiones(unittest.TestCase):
    def test_fase2_cuarto_hueco_mueve_sin_atacar_aunque_haya_vacios(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", Rango.BRONCE), None,
                 (TYR + ".skill_1", Rango.BRONCE), None)
        with mock.patch.object(e.jugador, "elegir", side_effect=AssertionError("no debe decidir un ataque general")):
            jugada = e.decidir(2, 2, 3, m)[0]
        self.assertIsInstance(jugada, tuple)
        self.assertNotEqual(*jugada)
        self.assertTrue(all(B4.con_carta(m[i]) for i in jugada))

    def test_fase2_sin_dos_cartas_no_sustituye_movimiento_por_ataque(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", Rango.BRONCE), None)
        with mock.patch.object(e.jugador, "elegir", side_effect=AssertionError("no debe atacar")):
            with self.assertRaises(P4.Reiniciar):
                e.decidir(2, 2, 3, m)

    def test_doble_roja_mueve_entre_cartas_reales(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((FREYR + ".skill_1", Rango.BRONCE), None,
                 (FREYR + ".skill_2", Rango.BRONCE))
        self.assertEqual(e.decidir(2, 1, 1, m)[0], (0, 2))

    def test_reintentar_no_duplica_cartas_ni_rompe_la_ruleta(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", Rango.BRONCE), (JORM + ".skill_2", Rango.BRONCE),
                 (FREYR + ".skill_1", Rango.BRONCE))
        self.assertEqual(e.decidir(4, 1, 0, m)[0], 2)
        self.assertEqual(e.decidir(4, 1, 1, m)[0], 1)
        self.assertEqual(e.decidir(4, 1, 1, m)[0], 1)
        self.assertEqual(len(e.jugadas), 2)
        self.assertEqual(e.decidir(4, 1, 2, m)[0], 0)
        self.assertEqual([B4.color(c) for c in e.jugadas], ["rojo", "verde", "azul"])

    def test_movimientos_no_desplazan_los_indices_del_historial(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", Rango.BRONCE), (JORM + ".skill_2", Rango.BRONCE))
        with mock.patch.object(e, "guion", side_effect=[(0, 1), 1]):
            e.decidir(4, 1, 0, m)
            e.decidir(4, 1, 1, m)
        self.assertIsNone(e.carta_en_accion(0))
        self.assertEqual(e.carta_en_accion(1).nombre, JORM + ".skill_2")
        with mock.patch.object(e, "guion", return_value=(0, 1)):
            e.decidir(4, 2, 1, m)
        self.assertEqual(e.jugadas, [], "un turno nuevo no conserva cartas del anterior")


class RitmoCartas(unittest.TestCase):
    def test_acorta_solo_una_normal_confirmada_sin_fusiones(self):
        for confirmada, fusiones, tipo in ((True, 0, TipoCarta.NORMAL), (False, 0, TipoCarta.NORMAL),
                                          (True, 1, TipoCarta.NORMAL), (True, 0, TipoCarta.ULTI)):
            with self.subTest(confirmada=confirmada, fusiones=fusiones, tipo=tipo):
                control.reiniciar()
                modo = P4.PerrosPiso4({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
                modo.fase, modo.turno_fase, modo.huecos_turno = 1, 1, 4
                modo.log = lambda *a: None
                modo.capturar = mock.Mock(side_effect=[({"huecos": 4}, (0, 0)), ({"huecos": 0}, (0, 0))])
                modo.estrategia = SimpleNamespace(decidir=lambda *a: (0, None, False), fusiones_al_jugar=lambda *a: fusiones)
                carta = Carta(0, (0, 0, 1, 1), None, tipo, Rango.ULTI if tipo == TipoCarta.ULTI else Rango.BRONCE, "odin.single")
                with mock.patch.object(juego, "victoria", entorno.PlantillaFalsa("victoria")), \
                     mock.patch.object(juego, "derrota", entorno.PlantillaFalsa("derrota")), \
                     mock.patch.object(C, "contar_huecos", side_effect=lambda p, *a: p['huecos']), \
                     mock.patch.object(C, "leer_mano", return_value=[carta]), \
                     mock.patch.object(P4.EQUIPO, "etiquetar", side_effect=lambda m: m), \
                     mock.patch.object(P4.entrada, "clic") as clic, \
                     mock.patch.object(modo, "_esperar_hueco", return_value=confirmada) as confirmar, \
                     mock.patch.object(modo, "esperar_corto") as esperar:
                    modo._jugar_turno()
                clic.assert_called_once()
                confirmar.assert_called_once_with(4, 4.0 if tipo == TipoCarta.ULTI else 1.6)
                pausa = esperar.call_args.args[0]
                if confirmada and not fusiones and tipo == TipoCarta.NORMAL:
                    self.assertLess(pausa, 0.5)
                else:
                    self.assertGreaterEqual(pausa, 0.5)


class ReintentosMovimientos(unittest.TestCase):
    def test_arrastre_rechazado_no_bloquea_el_ataque_anterior(self):
        control.reiniciar()
        modo = P4.PerrosPiso4({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        modo.fase, modo.turno_fase, modo.huecos_turno = 2, 1, 4
        modo.log = lambda *a: None
        capturas = [{"huecos": n} for n in [4, 3] + [3] * 16 + [0]]
        modo.capturar = mock.Mock(side_effect=[(p, (0, 0)) for p in capturas])
        m = [Carta(i, (i, 0, 1, 1), np.full((12, 12, 3), i * 80, dtype=np.uint8),
                   TipoCarta.NORMAL, Rango.BRONCE, f"a.skill_{i+1}") for i in range(2)]
        tipos = []
        def decidir(fase, turno, accion, mano, total):
            tipos.append(mano[0].tipo)
            return (0 if accion == 0 else (0, 1)), None, False
        modo.estrategia = SimpleNamespace(decidir=decidir, fusiones_al_jugar=lambda *a: 0)
        with mock.patch.object(juego, "victoria", entorno.PlantillaFalsa("victoria")), \
             mock.patch.object(juego, "derrota", entorno.PlantillaFalsa("derrota")), \
             mock.patch.object(C, "contar_huecos", side_effect=lambda p, *a: p['huecos']), \
             mock.patch.object(C, "leer_mano", return_value=m), \
             mock.patch.object(P4.EQUIPO, "etiquetar", side_effect=lambda m: m), \
             mock.patch.object(P4, "_misma_imagen", return_value=True), \
             mock.patch.object(P4.entrada, "clic"), \
             mock.patch.object(P4.entrada, "arrastrar"), \
             mock.patch.object(modo, "_esperar_hueco", side_effect=[True, False, False, False]), \
             mock.patch.object(modo, "esperar_corto"):
            modo._jugar_turno()
        self.assertGreaterEqual(len(tipos), 4)
        self.assertTrue(all(t == TipoCarta.NORMAL for t in tipos))
