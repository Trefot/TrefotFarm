"""Paso 5: aprender de una sola pelea, gane o pierda (lo pidio el usuario, 2026-11-09)."""

import tempfile
import unittest
from pathlib import Path

import entorno  # noqa: F401  (antes que lumen)

from lumen.ia import lecciones as L


def jugada(fase, turno, carta):
    return {"fase": fase, "turno": turno, "jugada": ["jugar", carta]}


class Lecciones(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())

    def test_una_derrota_ensena_a_no_repetir(self):
        pelea = {"destino": "rata_f2", "resultado": "reinicio", "fase_final": 2, "notas": [],
                 "turnos": [jugada(1, 1, "a.skill_1"), jugada(2, 1, "b.skill_1"), jugada(2, 2, "c.skill_2@1"),
                            jugada(2, 3, "d.ulti"), jugada(2, 3, "dibujo_2")]}
        frases = L.aprender(pelea, carpeta=self.carpeta)
        self.assertTrue(frases)
        valores, motivos = L.aplicar({"c.skill_2@1": 1.0, "d.ulti": 1.0, "a.skill_1": 1.0}, "rata_f2", 2,
                                     carpeta=self.carpeta)
        self.assertLess(valores["c.skill_2@1"], 1.0, "lo de los ultimos turnos antes de perder vale menos")
        self.assertLess(valores["d.ulti"], 1.0)
        self.assertEqual(valores["a.skill_1"], 1.0, "otra fase: nada")
        self.assertEqual(L.aplicar({"c.skill_2": 1.0}, "rata_f2", 1, carpeta=self.carpeta)[0]["c.skill_2"], 1.0)

    def test_una_victoria_rapida_refuerza(self):
        rapida = {"destino": "pajaro_f1", "resultado": "victoria",
                  "turnos": [jugada(1, 1, "a.skill_1"), jugada(1, 2, "a.skill_2")]}
        L.aprender(rapida, carpeta=self.carpeta)
        valores, _ = L.aplicar({"a.skill_1": 1.0}, "pajaro_f1", 1, carpeta=self.carpeta)
        self.assertGreater(valores["a.skill_1"], 1.0)
        lenta = {**rapida, "turnos": rapida["turnos"] + [jugada(1, 3, "b.skill_1")]}
        L.aprender(lenta, carpeta=self.carpeta)
        self.assertEqual(L.aplicar({"b.skill_1": 1.0}, "pajaro_f1", 1, carpeta=self.carpeta)[0]["b.skill_1"], 1.0,
                         "mas lenta que la mejor: no se refuerza")

    def test_por_tardar_mas_dano_y_abandonadas_no_cuentan(self):
        tardona = {"destino": "x", "resultado": "reinicio", "fase_final": 1, "notas": ["Reinicio: la pelea dura demasiado"],
                   "turnos": [jugada(1, 1, "a.skill_1")]}
        L.aprender(tardona, carpeta=self.carpeta)
        self.assertGreater(L.aplicar({"z.ulti": 1.0}, "x", 1, carpeta=self.carpeta)[0]["z.ulti"], 1.0)
        self.assertEqual(L.aprender({**tardona, "destino": "y", "resultado": "abandonada"}, carpeta=self.carpeta), [])

    def test_con_limites(self):
        pelea = {"destino": "z", "resultado": "derrota", "fase_final": 1, "notas": [], "turnos": [jugada(1, 1, "a.skill_1")]}
        for _ in range(20):
            L.aprender(pelea, carpeta=self.carpeta)
        self.assertGreaterEqual(L.aplicar({"a.skill_1": 1.0}, "z", 1, carpeta=self.carpeta)[0]["a.skill_1"], L.MINIMO)

    def test_el_jugador_las_usa(self):
        from unittest import mock

        from lumen import inteligencia as I

        L.aprender({"destino": "q", "resultado": "derrota", "fase_final": 1, "notas": [],
                    "turnos": [jugada(1, 1, "a.skill_1")]}, carpeta=self.carpeta)
        j = I.Jugador()
        j.destino, j.fase = "q", 1
        j._tasador = mock.Mock(valores=lambda nombres: {n: 1.0 for n in nombres}, es_area=lambda n: False)
        j._indice = mock.Mock()
        from lumen.cartas import Carta, Rango, TipoCarta as T

        mano = [Carta(0, tipo=T.NORMAL, rango=Rango.BRONCE, nombre="a.skill_1"),
                Carta(1, tipo=T.NORMAL, rango=Rango.BRONCE, nombre="b.skill_1")]
        with mock.patch.object(I, "agrupar_por_dibujo", lambda m, f: None), \
                mock.patch.object(L, "CARPETA", self.carpeta):
            paso = j.elegir(mano, 1)
        self.assertEqual(paso, ("jugar", 1), "la que llevo a perder ya no es la primera opcion")


if __name__ == "__main__":
    unittest.main()
