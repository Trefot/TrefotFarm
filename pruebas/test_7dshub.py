"""Datos de 7dshub.com en la base (con permiso de su dueno, 2026-11-08): cartas, textos y jefes."""

import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import personajes as P
from lumen import valor_cartas
from lumen.ia import decidir


class Cartas(unittest.TestCase):
    def test_los_heroes_nuevos_tienen_cartas_para_reconocerlos(self):
        b = P.cargar()
        eren = b["eren_jaeger_verde"]
        self.assertTrue(eren.tiene_datos, "con las cartas de 7dshub el bot ya puede reconocerlo")
        for carta in ("skill_1", "skill_2", "ulti"):
            self.assertEqual(eren.estado_carta(carta), "hub")
            plantilla, umbral = eren.plantilla(carta)
            self.assertTrue(plantilla.disponible)
            self.assertEqual(plantilla.imagenes[0].shape[:2], (74, 45), "al tamano de la carta en la mano")
            self.assertEqual(umbral, P.UMBRAL_HUB)

    def test_lo_capturado_en_el_juego_manda(self):
        enjin = P.cargar()["cleaner_enjin_claro"]
        self.assertEqual(enjin.estado_carta("skill_1"), "ficha")

    def test_todos_los_heroes_tienen_icono_y_cartas(self):
        b = P.cargar()
        self.assertGreaterEqual(len(b), 381)
        sin = [p for p, pj in b.items() if not pj.tiene_datos]
        self.assertEqual(sin, [], "todos se pueden reconocer en pelea")


class Textos(unittest.TestCase):
    def test_textos_de_las_cartas_sin_captura_de_heroes(self):
        """En el PC de un jugador no hay captura de heroes: los textos vienen con el programa."""
        with mock.patch.object(valor_cartas, "CATALOGO_TEXTOS", Path("no_existe.yaml")):
            textos = decidir.textos_por_habilidad()
            self.assertIn("damage", textos["spinning slicer"].lower())
            tasador = valor_cartas.Tasador()
        self.assertTrue(tasador.porcentajes, "las cifras de dano tambien")
        self.assertIn("spinning slicer", tasador.porcentajes)


class Jefes(unittest.TestCase):
    def test_mecanicas_de_las_bestias(self):
        self.assertIn("postura", [m.tipo for m in decidir.mecanicas_de("rata_f1", 1)])
        self.assertIn("inmortalidad", [m.tipo for m in decidir.mecanicas_de("rata_f2", 1)])
        self.assertIn("proteccion", [m.tipo for m in decidir.mecanicas_de("pajaro_piso4", 2)])

    def test_ignore_evasion_no_es_evasion_del_jefe(self):
        """La pasiva "Ignore Evasion" (el jefe ignora la evasion de tus heroes) se leia como evasion del jefe."""
        for piso in (1, 2, 3):
            self.assertNotIn("evasion", [m.tipo for m in decidir.mecanicas_de(f"pajaro_f{piso}", 1)])

    def test_lo_capturado_a_mano_manda(self):
        self.assertIn("torrent", [m.tipo for m in decidir.mecanicas_de("ciervo_piso4", 1)])

    def test_la_ia_de_las_bestias_usa_el_jefe_de_su_piso(self):
        from lumen.modos import bestias_pisos1a3 as B

        modo = B.RataPisos1a3({"jugar": "Inteligente"})
        modo.piso = 2
        modo._nueva_pelea()
        self.assertEqual(modo.estrategia.destino, "rata_f2")
        with mock.patch.object(modo.estrategia.jugador, "elegir", return_value=("jugar", 0)):
            modo.estrategia.decidir(1, 1, 0, [], 4)
        self.assertIn("inmortalidad", [m.tipo for m in modo.estrategia.jugador.mecanicas])


if __name__ == "__main__":
    unittest.main()
