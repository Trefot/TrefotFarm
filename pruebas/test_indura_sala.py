"""Indura: la sala de preparacion que no arranca (sesion del 2026-11-16: 2 derrotas, 5 h esperando en la sala)."""
import unittest
from unittest import mock

import numpy as np

import entorno  # noqa: F401
from lumen.modos import indura as M

P = np.zeros((940, 550, 3), np.uint8)


class Pantalla:
    """Que botones se ven, para no depender de capturas."""

    def __init__(self, *visibles):
        self.visibles = set(visibles)

    def esta(self, nombre):
        return nombre in self.visibles


class SalaQueNoArranca(unittest.TestCase):
    def setUp(self):
        self.m = M.Indura({"nivel": "Chaos", "victorias": 0, "jugar": "Mis cartas", "espera": "9.3",
                           "minutos_sin_invitacion": 0})
        self.m.log = lambda texto, *a, **k: self.mensajes.append(texto)
        self.mensajes, self.clics, self.toques = [], [], []
        self.pantalla = Pantalla("preparar")
        self.reloj = 1000.0
        nombres = {id(M.PREPARACION): "preparar", id(M.CANCELAR_PREPARACION): "cancelar",
                   id(M.AUTO): "auto", id(M.ATRAS): "atras", id(M.juego.ok): "ok",
                   id(M.juego.menu_batalla): "menu", id(M.TIEMPO_REAL): "rt"}

        def esta(plantilla, p, umbral=0.7):
            return self.pantalla.esta(nombres.get(id(plantilla)))

        def clic_si(plantilla, p, o, umbral=0.7, punto=None, espera=0.25):
            if esta(plantilla, p):
                self.clics.append(nombres[id(plantilla)])
                return True
            return False

        for plantilla in (M.PREPARACION, M.CANCELAR_PREPARACION, M.AUTO, M.ATRAS, M.juego.ok,
                          M.juego.menu_batalla, M.TIEMPO_REAL):
            parche = mock.patch.object(plantilla, "esta", lambda p, umbral=0.7, _pl=plantilla: esta(_pl, p, umbral))
            parche.start()
            self.addCleanup(parche.stop)
        for parche in (mock.patch.object(self.m, "clic_si", side_effect=clic_si),
                       mock.patch.object(M.entrada, "clic", side_effect=lambda punto, o, espera=0: self.toques.append(punto)),
                       mock.patch.object(M.avisos, "enviar"),
                       mock.patch.object(M.time, "time", side_effect=lambda: self.reloj)):
            parche.start()
            self.addCleanup(parche.stop)

    def test_espera_normal_sin_salirse(self):
        for _ in range(10):
            self.assertIsNone(self.m.preparar(P, (0, 0)))
            self.reloj += 15
        self.assertNotIn("atras", self.clics)
        self.assertEqual(self.toques, [])

    def test_empieza_la_pelea_dentro_del_tiempo(self):
        self.m.preparar(P, (0, 0))
        self.reloj += 50
        self.pantalla = Pantalla("auto")
        self.assertEqual(self.m.preparar(P, (0, 0)), "pelea")
        self.assertIsNone(self.m.sala_desde)

    def test_a_los_3_min_se_sale_y_vuelve_a_buscar(self):
        self.m.preparar(P, (0, 0))  # pulsa listo: ahora el boton es "Cancel Preparation"
        self.pantalla = Pantalla("cancelar", "atras")
        self.reloj += M.ESPERA_SALA + 1
        self.assertIsNone(self.m.preparar(P, (0, 0)))
        self.assertEqual(self.clics[-2:], ["cancelar", "atras"])
        self.assertTrue(any("me salgo" in t.lower() for t in self.mensajes), self.mensajes)
        # Sale "¿Salir?": se acepta
        self.pantalla = Pantalla("ok")
        self.reloj += 2
        self.assertIsNone(self.m.preparar(P, (0, 0)))
        self.assertEqual(self.clics[-1], "ok")
        # De vuelta en el menu de batalla
        self.pantalla = Pantalla("menu")
        self.assertEqual(self.m.preparar(P, (0, 0)), "ir_a_indura")
        self.assertIsNone(self.m.sala_desde)
        self.assertEqual(self.m.intentos_salida, 0)
        self.assertNotIn("La partida se deshizo antes de empezar. Vuelvo a buscar.", self.mensajes)

    def test_el_lider_se_fue_pulsa_ok_al_momento(self):
        """La foto del usuario: el aviso con OK tapa la sala, con "Cancel Preparation" debajo."""
        self.pantalla = Pantalla("ok", "cancelar", "atras")
        self.assertIsNone(self.m.preparar(P, (0, 0)))
        self.assertEqual(self.clics, ["ok"])
        self.assertTrue(any("líder" in t for t in self.mensajes), self.mensajes)
        self.reloj += 2
        self.m.preparar(P, (0, 0))
        self.assertEqual(sum("líder" in t for t in self.mensajes), 1)  # se dice una vez
        self.pantalla = Pantalla("menu")
        self.assertEqual(self.m.preparar(P, (0, 0)), "ir_a_indura")
        self.assertIn("Fuera de la sala. Vuelvo a buscar partidas.", self.mensajes)
        self.assertEqual(self.toques, [])

    def test_fuera_de_la_sala_en_otra_pantalla_devuelve_la_navegacion(self):
        self.m.preparar(P, (0, 0))  # entra en la sala
        self.reloj += M.ESPERA_SALA + 1
        self.m.preparar(P, (0, 0))
        self.pantalla = Pantalla()
        self.reloj += 2
        self.assertEqual(self.m.preparar(P, (0, 0)), "ir_a_indura")

    def test_sin_flecha_toca_donde_esta(self):
        self.m.preparar(P, (0, 0))  # entra en la sala
        self.reloj += M.ESPERA_SALA + 1
        self.m.preparar(P, (0, 0))
        self.assertEqual(self.toques, [M.PUNTO_ATRAS])

    def test_no_insiste_sin_pausa_y_avisa_si_no_puede(self):
        self.m.preparar(P, (0, 0))  # entra en la sala
        self.reloj += M.ESPERA_SALA + 1
        for _ in range(M.INTENTOS_SALIDA * 4):
            self.m.preparar(P, (0, 0))
            self.reloj += M.CADA_SALIDA / 4 + 0.01
        self.assertEqual(len(self.toques), M.INTENTOS_SALIDA)
        M.avisos.enviar.assert_called_once()

    def test_sala_nueva_empieza_con_el_reloj_a_cero(self):
        self.m.sala_desde = self.reloj - 10_000  # quedo de una sala vieja
        with mock.patch.object(self.m, "_ir_a_indura", return_value="preparar"):
            self.assertEqual(self.m.ir_a_indura(P, (0, 0)), "preparar")
        self.assertIsNone(self.m.preparar(P, (0, 0)))
        self.assertEqual(self.toques, [])


class AvisoSinReconocer(unittest.TestCase):
    def test_pantalla_conocida_pone_el_reloj_a_cero(self):
        m = M.Indura({"nivel": "Chaos", "victorias": 0, "jugar": "Mis cartas", "espera": "9.3",
                      "minutos_sin_invitacion": 0})
        m.desconocida_desde = 1.0  # de hace horas
        with mock.patch.object(m, "_ir_a_indura", return_value="preparar"):
            m.ir_a_indura(P, (0, 0))
        self.assertIsNone(m.desconocida_desde)


if __name__ == "__main__":
    unittest.main()
