"""Juego inteligente: reglas de la mano, decisiones, valor de las cartas y uso en Floor 1-3 e Indura."""

import random
import time
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

import numpy as np

from lumen import cartas, entrada, inteligencia as I, personajes as P, valor_cartas as V
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.modos import bestias_pisos1a3 as B
from lumen.modos import indura as M

BR, PL, OR = Rango.BRONCE, Rango.PLATA, Rango.ORO


def mano(*cs):
    """("A", BR) = carta A bronce; ("U",) = ulti; ("x",) = bloqueada."""
    salida = []
    for i, c in enumerate(cs):
        if c[0] == "U":
            salida.append(Carta(i, tipo=T.ULTI, rango=Rango.ULTI, nombre="ulti"))
        elif c[0] == "x":
            salida.append(Carta(i, tipo=T.BLOQUEADA, rango=BR, nombre="bloq"))
        else:
            salida.append(Carta(i, tipo=T.NORMAL, rango=c[1], nombre=c[0]))
    return salida


def fichas(m):
    return tuple(I._ficha(c, {}) for c in m)


def como(t):
    return [(f.nombre, f.rango) for f in t]


class ReglasDeLaMano(unittest.TestCase):
    def test_jugar_la_del_medio_fusiona(self):
        _, resto = I.jugar(fichas(mano(("A", BR), ("C", BR), ("A", BR))), 1)
        self.assertEqual(como(resto), [("A", PL)])

    def test_fusion_en_cadena(self):
        _, resto = I.jugar(fichas(mano(("A", PL), ("A", BR), ("C", BR), ("A", BR))), 2)
        self.assertEqual(como(resto), [("A", OR)])

    def test_oro_no_se_fusiona(self):
        _, resto = I.jugar(fichas(mano(("A", OR), ("C", BR), ("A", OR))), 1)
        self.assertEqual(len(resto), 2)

    def test_distinto_rango_no_se_fusiona(self):
        _, resto = I.jugar(fichas(mano(("A", BR), ("C", BR), ("A", PL))), 1)
        self.assertEqual(len(resto), 2)

    def test_arrastrar_sobre_la_gemela(self):
        resto = I.mover(fichas(mano(("A", BR), ("C", BR), ("D", BR), ("A", BR))), 0, 3)
        self.assertEqual(como(resto), [("C", BR), ("D", BR), ("A", PL)])


class Decisiones(unittest.TestCase):
    def test_con_una_accion_fusiona(self):
        _, plan = I.planear(mano(("A", BR), ("C", BR), ("A", BR), ("D", BR)), 1)
        self.assertEqual(plan[0], ("jugar", 1))

    def test_ulti_antes_que_bronce(self):
        _, plan = I.planear(mano(("A", BR), ("C", BR), ("U",), ("D", BR)), 1)
        self.assertEqual(plan[0], ("jugar", 2))

    def test_sin_nada_jugable_plan_vacio(self):
        self.assertEqual(I.planear(mano(("x",), ("x",)), 2)[1], ())

    def test_planes_legales_y_rapidos(self):
        rng = random.Random(5)
        peor = 0.0
        for _ in range(200):
            cs = []
            for _ in range(8):
                r = rng.random()
                cs.append(("U",) if r < 0.06 else ("x",) if r < 0.12 else (rng.choice("ABCD"), rng.choice([BR, BR, PL, OR])))
            inicio = time.time()
            _, plan = I.planear(mano(*cs), 4)
            peor = max(peor, time.time() - inicio)
            f = fichas(mano(*cs))
            for paso in plan:
                if paso[0] == "jugar":
                    self.assertTrue(f[paso[1]].jugable)
                    _, f = I.jugar(f, paso[1])
                else:
                    self.assertTrue(f[paso[1]].gemela(f[paso[2]]))
                    f = I.mover(f, paso[1], paso[2])
        self.assertLess(peor, 1.0, "una decision no puede tardar ni un segundo")

    def test_sin_arrastrar(self):
        cs = mano(("A", BR), ("B", BR), ("C", BR), ("A", BR), ("B", BR), ("C", BR))
        _, plan = I.planear(cs, 6, {}, arrastrar=False)
        self.assertTrue(all(p[0] == "jugar" for p in plan))


class ValorDeCartas(unittest.TestCase):
    def test_tipos_y_porcentajes(self):
        self.assertEqual(V.tipo_de("Área (Noxious Blitz)"), "area")
        self.assertEqual(V.tipo_de("Un objetivo (Spinning Slicer)"), "single")
        self.assertEqual(V.nombre_de_habilidad("Área (Noxious Blitz)"), "noxious blitz")
        self.assertEqual(V.porcentaje("Deals damage equal to 200% of Attack to all enemies."), 200)
        self.assertEqual(V.porcentaje("damage equal to 150% of their Attack, then 100% of Attack again"), 250)
        self.assertIsNone(V.porcentaje("Restores HP equal to 30% of max HP"))

    def test_area_vale_mas_con_varios_enemigos(self):
        bib = P.cargar()
        area, single = "cleaner_enjin_claro.skill_2", "cleaner_enjin_claro.skill_1"
        uno, dos = V.Tasador(1, bib, {}), V.Tasador(2, bib, {})
        self.assertEqual((uno.valor(single), uno.valor(area), dos.valor(area)), (1.0, 0.8, 1.6))
        self.assertEqual(V.Tasador(1, bib, {"noxious blitz": 300.0}).valor(area), 2.0)


class EnLosModos(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.dib = {k: rng.integers(0, 255, (123, 57, 3), dtype=np.uint8) for k in "ABCD"}

    def carta(self, i, k, brillo=0):
        img = np.clip(self.dib[k].astype(int) + brillo, 0, 255).astype(np.uint8)
        return Carta(i, rect=(i * 57, 820, 57, 123), imagen=img, tipo=T.NORMAL, rango=BR)

    def test_floor13_posiciones_reales_y_brillo(self):
        m = [Carta(0, tipo=T.SUELO), self.carta(1, "A"), self.carta(2, "C"), self.carta(3, "A", brillo=10), self.carta(4, "D")]
        e = B.EstrategiaInteligente()
        e.jugador._identificar = lambda c: None
        self.assertEqual(e.decidir(1, 1, 3, m, 4)[0], 2, "juega la C para fusionar las A")
        self.assertEqual(m[1].nombre, m[3].nombre)

    def test_floor13_por_defecto_inteligente(self):
        self.assertIsInstance(B.PerrosPisos1a3({"jugar": "Inteligente"}).estrategia, B.EstrategiaInteligente)
        self.assertIsInstance(B.SerpientePisos1a3({}).estrategia, B.EstrategiaInteligente, "serpiente y rata siguen igual")
        self.assertIs(type(B.PerrosPisos1a3({"jugar": "Simple"}).estrategia), B.EstrategiaSimple)

    def test_indura_toca_la_carta_que_fusiona(self):
        m = [self.carta(0, "A"), self.carta(1, "B"), self.carta(2, "A"), self.carta(3, "C"),
             self.carta(4, "D"), self.carta(5, "C"), self.carta(6, "D")]
        clics = []
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
             mock.patch.object(cartas, "casillas_libres_demonio", lambda p: 1), \
             mock.patch.object(cartas, "leer_mano_demonio", lambda p: m):
            ind = M.Indura({})
            ind.jugador._identificar = lambda c: None
            ind._jugar_carta(None, (0, 0))
            ind._jugar_carta(None, (0, 0))  # recien tocada: espera a que ocupe su casilla
        self.assertEqual(len(clics), 1)
        self.assertIn(clics[0][0] // 57, (1, 4, 5))


if __name__ == "__main__":
    unittest.main()


class ObjetivosDeTurno(unittest.TestCase):
    """Lo que pide el jefe para todo el turno: N cartas del mismo rango, o colores seguidos (0.21.0)."""

    PL, OR = Rango.PLATA, Rango.ORO

    def mano(self, cartas):
        return [Carta(i, tipo=T.NORMAL, rango=r, nombre=n) for i, (n, r) in enumerate(cartas)]

    def jugadas(self, plan, mano):
        return [mano[p[1]] for p in plan if p[0] == "jugar"]

    def test_sin_objetivos_juega_lo_que_mas_pega(self):
        mano = self.mano([("a", self.PL), ("b", self.PL), ("c", self.OR), ("d", self.OR), ("e", self.PL)])
        _, plan = I.planear(mano, 2)
        self.assertEqual(sorted(c.nombre for c in self.jugadas(plan, mano)), ["c", "d"], "las dos de oro")

    def test_tres_del_mismo_rango(self):
        """Hraesvelgr F4 fase 2: 3 habilidades del mismo rango (2 o mas) = su proteccion (dano x3)."""
        mano = self.mano([("a", self.PL), ("b", self.OR), ("c", self.PL), ("d", self.OR), ("e", self.PL)])
        _, plan = I.planear(mano, 3, objetivos=(("rango", 3, 2),))
        self.assertEqual(sorted(c.nombre for c in self.jugadas(plan, mano)), ["a", "c", "e"], "las tres de plata")

    def test_cuenta_lo_ya_jugado_en_el_turno(self):
        mano = self.mano([("a", self.PL), ("b", self.OR), ("c", self.OR)])
        ya = ((self.PL, None), (self.PL, None))  # ya se jugaron dos de plata
        _, plan = I.planear(mano, 1, objetivos=(("rango", 3, 2),), jugadas=ya)
        self.assertEqual(self.jugadas(plan, mano)[0].nombre, "a", "falta una de plata: esa, aunque el oro pegue mas")

    def test_bronce_no_cuenta_si_pide_rango_2(self):
        self.assertEqual(I.bono_objetivos(((Rango.BRONCE, None),) * 3, (("rango", 3, 2),)), 0.0)
        self.assertEqual(I.bono_objetivos(((Rango.PLATA, None),) * 3, (("rango", 3, 2),)), I.BONO_RANGO)
        self.assertEqual(I.bono_objetivos(((None, None),) * 3, (("rango", 3, 1),)), 0.0, "las ultis no tienen rango")

    def test_colores_seguidos(self):
        mano = self.mano([("r1", self.PL), ("v1", self.PL), ("r2", self.PL), ("v2", self.PL)])
        colores = {"r1": "rojo", "r2": "rojo", "v1": "verde", "v2": "verde"}
        _, plan = I.planear(mano, 2, colores=colores, objetivos=(("color",),), jugadas=((self.PL, "verde"),))
        self.assertEqual({c.nombre for c in self.jugadas(plan, mano)}, {"v1", "v2"}, "sigue con el verde")

    def test_objetivos_de_los_jefes(self):
        from lumen.ia import decidir

        self.assertIn(("rango", 3, 2), I.objetivos_de(decidir.mecanicas_de("pajaro_piso4", 2)))
        self.assertIn(("color",), I.objetivos_de(decidir.mecanicas_de("ciervo_piso4", 2)))
        self.assertEqual(I.objetivos_de(decidir.mecanicas_de("rata_f1", 1)), ())

    def test_el_jugador_recuerda_lo_jugado_y_empieza_turno_nuevo(self):
        from lumen.ia.efectos import Mecanica

        j = I.Jugador()
        j.mecanicas = [Mecanica("mismo_rango", ("mismo_rango",), "3:2")]
        j._lector = mock.Mock(color_de=lambda n: None)
        mano = self.mano([("a", self.PL), ("b", self.OR), ("c", self.PL), ("d", self.OR), ("e", self.PL)])
        with mock.patch.object(I, "agrupar_por_dibujo", lambda m, f: None):
            j.elegir(mano, 3)
            self.assertEqual(len(j.jugadas_turno), 1)
            j.elegir(mano, 2)
            self.assertEqual(len(j.jugadas_turno), 2)
            j.elegir(mano, 4)  # turno nuevo
            self.assertEqual(len(j.jugadas_turno), 1)
