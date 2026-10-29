"""Aprender solo (IA.md, pieza 6): elegir la configuracion de cada pelea a partir del diario."""

import random
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)
from entorno import PlantillaFalsa

from lumen import entrada, inteligencia as I, juego
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.ia import aprendizaje as A, diario as D
from lumen.modos import bestias_pisos1a3 as B

ULTI_ALTA = {**A.DEFECTO, "valor_ulti": 5.0}


def peleas(config, victorias, derrotas=0, segundos=150):
    return ([{"config": config, "resultado": "victoria", "duracion": segundos}] * victorias
            + [{"config": config, "resultado": "derrota", "duracion": segundos}] * derrotas)


class Rng:
    """random.Random de mentira: random() da lo que se le diga; choice, el primero."""

    def __init__(self, valor):
        self.valor = valor

    def random(self):
        return self.valor

    def choice(self, lista):
        return lista[0]


class Base(unittest.TestCase):
    def test_sin_datos_lo_de_siempre(self):
        self.assertEqual(A.base([]), A.DEFECTO)

    def test_cambia_solo_si_es_claramente_mejor(self):
        historia = peleas(A.DEFECTO, 5, segundos=150)  # 24 victorias/h
        self.assertEqual(A.base(historia + peleas(ULTI_ALTA, 5, segundos=140)), ULTI_ALTA, "un 7 % mas rapida")
        self.assertEqual(A.base(historia + peleas(ULTI_ALTA, 5, segundos=147)), A.DEFECTO, "un 2 %: puede ser suerte")
        self.assertEqual(A.base(historia + peleas(ULTI_ALTA, 4, segundos=100)), A.DEFECTO, "aun pocas peleas")

    def test_las_derrotas_cuentan_su_tiempo(self):
        historia = peleas(A.DEFECTO, 5, segundos=150) + peleas(ULTI_ALTA, 5, derrotas=2, segundos=140)
        self.assertEqual(A.base(historia), A.DEFECTO, "mas rapida pero pierde: menos victorias por hora")


class Explorar(unittest.TestCase):
    def test_variantes_de_un_paso(self):
        vs = A.variantes(A.DEFECTO)
        self.assertEqual(len(vs), 6)
        for v in vs:
            self.assertEqual(sum(v[k] != A.DEFECTO[k] for k in A.PARAMETROS), 1)

    def test_una_de_cada_diez(self):
        self.assertEqual(A.elegir([], rng=Rng(0.5)), (A.DEFECTO, False))
        config, prueba = A.elegir([], rng=Rng(0.05))
        self.assertTrue(prueba)
        self.assertIn(config, A.variantes(A.DEFECTO))
        self.assertEqual(A.elegir([], explorar=False, rng=Rng(0.05)), (A.DEFECTO, False), "apagado: nunca prueba")
        veces = sum(A.elegir([], rng=random.Random(i))[1] for i in range(2000))
        self.assertTrue(120 < veces < 280, veces)

    def test_descarta_las_malas_y_prueba_la_menos_probada(self):
        primera = A.variantes(A.DEFECTO)[0]
        historia = peleas(A.DEFECTO, 5) + peleas(primera, 1, derrotas=2)  # 3 peleas, gana 1: descartada
        config, prueba = A.elegir(historia, rng=Rng(0.0))
        self.assertTrue(prueba)
        self.assertNotEqual(config, primera)
        segunda = A.variantes(A.DEFECTO)[1]
        config, _ = A.elegir(historia + peleas(segunda, 2), rng=Rng(0.0))
        self.assertNotIn(config, (primera, segunda), "primero las que aun no se probaron")

    def test_texto(self):
        historia = peleas(A.DEFECTO, 5) + peleas(ULTI_ALTA, 5, segundos=120)
        texto = A.texto(historia)
        self.assertIn("Aprendizaje: juega con valor de la ulti 5 (5 peleas, 30,0 victorias/h)", texto)
        self.assertIn("Probado: lo de siempre: 5 peleas, 24,0/h", texto)


class EnElJuego(unittest.TestCase):
    def test_los_parametros_cambian_la_jugada(self):
        m = [Carta(0, tipo=T.ULTI, rango=Rango.ULTI, nombre="a.ulti"), Carta(1, tipo=T.NORMAL, rango=Rango.ORO, nombre="b.x")]
        self.assertEqual(I.planear(m, 1)[1][0], ("jugar", 0), "lo de siempre: la ulti vale mas que un oro")
        self.assertEqual(I.planear(m, 1, params={"valor_ulti": 2.0})[1][0], ("jugar", 1))
        self.assertEqual(I.planear(m, 1)[1][0], ("jugar", 0), "y vuelve a lo de siempre (sin cache vieja)")

    def test_el_modo_juega_y_apunta_su_configuracion(self):
        for n in ("pocion_stamina", "empezar", "carga_bestias", "carga_taberna"):
            p = mock.patch.object(juego, n, PlantillaFalsa(n))
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(entrada, "clic", lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)
        m = B.CiervoPisos1a3({})
        m.equipo_verificado = True
        with mock.patch.object(A, "elegir", lambda peleas, explorar=True: (ULTI_ALTA, True)):
            m.preparar({"carga_bestias"}, (0, 0))
        self.assertEqual(m.estrategia.jugador.params, ULTI_ALTA)
        self.assertEqual((m.diario.pelea["config"], m.diario.pelea["prueba"]), (ULTI_ALTA, True))
        m2 = B.CiervoPisos1a3({"aprender": False})
        m2.equipo_verificado = True
        with mock.patch.object(A, "elegir", lambda peleas, explorar=True: (A.DEFECTO, explorar)):
            m2.preparar({"carga_bestias"}, (0, 0))
        self.assertFalse(m2.diario.pelea["prueba"], "con 'Aprender solo' apagado no prueba nada")
        self.assertIsNone(B.PerrosPiso4({})._configuracion()[0], "el guion de los perros F4 no se toca")


if __name__ == "__main__":
    unittest.main()
