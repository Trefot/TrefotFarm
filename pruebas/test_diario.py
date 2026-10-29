"""Diario de peleas (IA.md, pieza 5): guardar cada decision y como acabo, resumirlo y engancharlo al modo."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)
from entorno import PlantillaFalsa

from lumen import entrada, juego
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.ia import diario as D
from lumen.modos import bestias_pisos1a3 as B


def mano(*nombres):
    return [Carta(i, tipo=T.NORMAL, rango=Rango.BRONCE, nombre=n) for i, n in enumerate(nombres)]


class Diario(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp(dir=entorno.TEMPORAL))

    def pelea(self, resultado, fase, jugadas=(), notas=(), duracion=150):
        d = D.Diario("ciervo_piso4", self.carpeta)
        d.empezar(equipo=["thor"], estrategia="Inteligente")
        d.pelea["inicio"] -= duracion
        for fase_j, nombre in jugadas:
            m = mano("x.a", nombre)
            d.decision(fase_j, 1, 0, m, 1, razones={nombre: ["quita la postura"], "x.a": ["no se jugo"]})
        for n in notas:
            d.nota(n)
        return d.terminar(resultado, fase)

    def test_guarda_cada_decision_y_el_final(self):
        p = self.pelea("victoria", 4, [(1, "thor.skill_1@2")])
        self.assertEqual(p["turnos"][0]["jugada"], ["jugar", "thor.skill_1@2"])
        self.assertEqual(p["turnos"][0]["razones"], {"thor.skill_1@2": ["quita la postura"]}, "solo la jugada")
        self.assertEqual((p["resultado"], p["fase_final"], p["equipo"]), ("victoria", 4, ["thor"]))
        self.assertGreaterEqual(p["duracion"], 150)
        self.assertEqual(D.leer("ciervo_piso4", carpeta=self.carpeta)[0]["resultado"], "victoria")
        self.assertIsNone(D.Diario("x", self.carpeta).terminar("victoria"), "sin pelea abierta no guarda nada")

    def test_mover_tambien_se_apunta(self):
        d = D.Diario("ciervo_piso4", self.carpeta)
        d.empezar()
        d.decision(2, 1, 3, mano("a.x", "b.y"), (1, 0))
        self.assertEqual(d.pelea["turnos"][0]["jugada"], ["mover", "b.y", "a.x"])

    def test_resumen_y_texto(self):
        self.pelea("victoria", 4, [(1, "thor.skill_1"), (1, "thor.skill_1")], duracion=120)
        self.pelea("victoria", 4, [(1, "tyr.skill_2")], duracion=180)
        self.pelea("derrota", 3)
        self.pelea("reinicio", 1, notas=["Reinicio: F1T1: falta la desventaja"])
        r = D.resumen(D.leer("ciervo_piso4", carpeta=self.carpeta))
        self.assertEqual((r["victorias"], r["derrotas"], r["reinicios"]), (2, 1, 1))
        self.assertEqual(r["tasa"], 50.0)
        self.assertAlmostEqual(r["segundos_victoria"], 150, delta=2)
        self.assertEqual(r["jugadas_al_ganar"][1].most_common(1)[0], ("thor.skill_1", 2))
        texto = D.texto("ciervo_piso4", "Eikthyrnir · Floor 4", carpeta=self.carpeta)
        self.assertIn("Victorias 2 · derrotas 1 · reinicios 1 · gana el 50 % · 2:30 por victoria", texto)
        self.assertIn("Derrotas por fase: F3: 1", texto)
        self.assertIn("Reinicio ×1: Reinicio: F1T1: falta la desventaja", texto)
        self.assertIn("Al ganar, F1: thor.skill_1 (2), tyr.skill_2 (1)", texto)
        self.assertIn("Todavía no hay peleas", D.texto("rata_pisos1a3", carpeta=self.carpeta))


class EnElModo(unittest.TestCase):
    """El modo de las bestias abre la pelea al empezar y la cierra al contarla."""

    def setUp(self):
        for n in ("pocion_stamina", "empezar", "carga_bestias", "carga_taberna", "info_mision", "ok", "cerrar",
                  "piso3_superado"):
            p = mock.patch.object(juego, n, PlantillaFalsa(n))
            p.start()
            self.addCleanup(p.stop)
        for n in ("clic", "arrastrar"):
            p = mock.patch.object(entrada, n, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)

    def test_pelea_que_acaba_en_derrota(self):
        m = B.PerrosPisos1a3({})
        m.equipo_verificado = True
        self.assertIsNone(m.diario.pelea, "crear el modo no abre ninguna pelea")
        self.assertEqual(m.preparar({"carga_bestias"}, (0, 0)), "pelea")
        self.assertIsNotNone(m.diario.pelea)
        m.fase = 2
        m.diario.decision(2, 1, 0, mano("a.x", "b.y"), 0)
        m.derrota({"carga_bestias"}, (0, 0))
        self.assertIsNone(m.diario.pelea)
        guardada = D.leer("perros_pisos1a3")[0]
        self.assertEqual((guardada["resultado"], guardada["fase_final"], guardada["estrategia"]),
                         ("derrota", 2, "Inteligente"))
        self.assertEqual(len(guardada["turnos"]), 1)

    def test_parar_a_media_pelea(self):
        m = B.PerrosPisos1a3({})
        m.equipo_verificado = True
        m.preparar({"carga_bestias"}, (0, 0))
        m.al_terminar()
        self.assertEqual(D.leer("perros_pisos1a3")[0]["resultado"], "abandonada")


if __name__ == "__main__":
    unittest.main()
