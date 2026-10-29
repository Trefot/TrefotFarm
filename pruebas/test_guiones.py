"""Guiones de pelea: el guion del Floor 4 del ciervo, regla por regla, con manos simuladas."""

import unittest

import entorno  # noqa: F401  (antes que lumen)

from lumen import personajes as P
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.guiones import EstrategiaGuion, Guion
from lumen.modos.perros_piso4 import Reiniciar

BR, PL = Rango.BRONCE, Rango.PLATA
FREYJA, THOR, FREYR, TYR = "freyja_roja", "thor_the_god_of_thunder_azul", "sun_god_freyr_rojo", "god_of_war_tyr_verde"


def mano(*cartas):
    """("freyja_roja.normal_1", BR) = carta; ("freyja_roja.ulti",) = ulti; (None,) = desconocida."""
    salida = []
    for i, c in enumerate(cartas):
        if c[0] and c[0].endswith(".ulti"):
            salida.append(Carta(i, tipo=T.ULTI, rango=Rango.ULTI, nombre=c[0]))
        else:
            salida.append(Carta(i, tipo=T.NORMAL, rango=c[1] if len(c) > 1 else BR, nombre=c[0]))
    return salida


def verde(n=1):
    return (f"{TYR}.skill_{n}",)


def azul(n=1):
    return (f"{THOR}.skill_{n}",)


def roja(n=1):
    return (f"{FREYR}.skill_{n}",)


class Ciervo(unittest.TestCase):
    def setUp(self):
        self.g = Guion.cargar("ciervo_piso4")
        self.e = EstrategiaGuion(self.g)

    def jugar(self, fase, turno, m, acciones=4):
        """Pide las acciones del turno quitando de la mano lo jugado (como hace el juego)."""
        hechas = []
        m = list(m)
        for accion in range(acciones):
            for i, c in enumerate(m):
                c.posicion = i
            idx, _, _ = self.e.decidir(fase, turno, accion, m)
            if isinstance(idx, tuple):
                hechas.append(("mover", m[idx[0]].nombre))
            else:
                hechas.append(m[idx].nombre)
                m.pop(idx)
        return hechas

    def test_colores_y_cartas_del_guion_existen(self):
        bib = P.cargar()
        self.assertEqual(self.g.colores, {FREYJA: "rojo", THOR: "azul", FREYR: "rojo", TYR: "verde"})
        for alias, nombre in self.g.alias.items():
            pid, carta = nombre.split(".")
            with self.subTest(alias=alias):
                self.assertIn(carta, bib[pid].cartas)

    def test_f1_turno_1(self):
        m = mano(azul(2), (f"{FREYJA}.normal_1",), verde(), roja(2), azul(1), roja(1))
        self.assertEqual(self.jugar(1, 1, m),
                         [f"{FREYR}.skill_2", f"{FREYJA}.normal_1", f"{THOR}.skill_1", f"{THOR}.skill_2"])

    def test_f1_sin_la_desventaja_y_sin_fusion_reinicia(self):
        with self.assertRaises(Reiniciar):
            self.e.decidir(1, 1, 0, mano(azul(2), verde(), roja(1)))

    def test_f2_t1_dos_rojas_y_mueve(self):
        hechas = self.jugar(2, 1, mano(roja(1), verde(1), roja(2), azul(1), verde(2)))
        self.assertEqual(hechas[:2], [f"{FREYR}.skill_2", f"{FREYR}.skill_1"])
        self.assertEqual([h[0] for h in hechas[2:]], ["mover", "mover"])

    def test_f2_t2_cuatro_verdes(self):
        hechas = self.jugar(2, 2, mano(verde(1), verde(2), verde(1), verde(2), azul()))
        self.assertTrue(all(h.startswith(TYR) for h in hechas))

    def test_f2_t2_tres_verdes_y_mover(self):
        hechas = self.jugar(2, 2, mano(verde(1), azul(), verde(2), verde(1), roja()))
        self.assertTrue(all(h.startswith(TYR) for h in hechas[:3]))
        self.assertEqual(hechas[3][0], "mover")

    def test_f2_sin_verdes_fusiona_y_espera(self):
        # Solo 1 verde: falla la segunda; hay dos azules iguales -> fusiona y el resto del turno mueve.
        hechas = self.jugar(2, 2, mano(verde(), azul(1), azul(1), roja(2), roja(1)))
        self.assertEqual(hechas[0], f"{TYR}.skill_1")
        self.assertEqual(hechas[1], ("mover", f"{THOR}.skill_1"))
        self.assertTrue(all(h[0] == "mover" for h in hechas[2:]))

    def test_sin_guion_ni_fusion_reinicia(self):
        with self.assertRaises(Reiniciar):
            self.jugar(2, 2, mano(verde(), azul(1), roja(2), roja(1)))

    def test_f3_t1_tres_del_mismo_color(self):
        hechas = self.jugar(3, 1, mano(azul(1), roja(1), azul(2), verde(), azul(1, ), roja(2)))
        self.assertEqual(sum(1 for h in hechas if isinstance(h, str) and h.startswith(THOR)), 3)
        self.assertEqual(hechas[3][0], "mover")

    def test_f3_t2_mata_guardando_el_semaforo(self):
        hechas = self.jugar(3, 2, mano(roja(1), azul(1), roja(2), verde(1), roja(1)))
        jugadas = [h for h in hechas if isinstance(h, str)]
        self.assertEqual(len(jugadas), 2, "solo gasta las rojas que sobran")
        self.assertTrue(all(h.startswith(FREYR) for h in jugadas))

    def test_f4_semaforo_y_guarda_la_ulti_de_freyr(self):
        m = mano((f"{FREYR}.ulti",), roja(1), verde(1), azul(2), verde(2))
        hechas = self.jugar(4, 1, m)
        self.assertEqual(hechas[:3], [f"{TYR}.skill_2", f"{THOR}.skill_2", f"{FREYR}.skill_1"])
        self.assertEqual(hechas[3][0], "mover")

    def test_f4_t3_ulti_de_freyr_y_remate(self):
        hechas = self.jugar(4, 3, mano(verde(1), azul(1), (f"{FREYR}.ulti",), (f"{FREYJA}.ulti",)))
        self.assertEqual(hechas, [f"{TYR}.skill_1", f"{THOR}.skill_1", f"{FREYR}.ulti", f"{FREYJA}.ulti"])
        self.e = EstrategiaGuion(self.g)
        resto = self.jugar(4, 3, mano(verde(1), azul(1), (f"{FREYR}.ulti",), roja(2), azul(2)))
        self.assertEqual(resto[3][0], "mover", "sin verde ni ulti de Freyja: mover y rematar el turno siguiente")

    def test_mover_la_del_que_menos_orbes_tiene(self):
        self.e.orbes.update({FREYJA: 3, THOR: 0, FREYR: 2, TYR: 1})
        m = mano(roja(1), azul(1), verde(1))
        origen, _ = self.e._mover(m)
        self.assertEqual(m[origen].nombre, f"{THOR}.skill_1")

    def test_orbes_suben_y_la_ulti_los_vacia(self):
        self.jugar(4, 3, mano(verde(1), azul(1), (f"{FREYR}.ulti",), (f"{FREYJA}.ulti",)))
        self.assertEqual(self.e.orbes[FREYR], 0)
        self.assertEqual(self.e.orbes[TYR], 1)


if __name__ == "__main__":
    unittest.main()
