"""Imagenes propias en lugar de las de AutoFarming (lumen/propias.py, 2026-11-22)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2

import entorno  # noqa: F401
from lumen import propias
from lumen.vision import Plantilla

PANTALLA = Path(__file__).with_name("botin_sa") / "victoria_limpia.png"
OK = "ok_buttons/salvage_ok.png"  # era de AutoFarming; en esta pantalla coincide
# La de AutoFarming ya se borro (tiene propia): las pruebas ponen una copia en un assets/imagenes de mentira.
REPO_REAL = propias.CARPETA_REPO
IMAGENES_REALES = propias.IMAGENES


class Propias(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        falsa = raiz / "imagenes" / OK
        falsa.parent.mkdir(parents=True)
        falsa.write_bytes((REPO_REAL / OK).read_bytes())
        import lumen.vision as vision

        for modulo, nombre, valor in ((propias, "CARPETA_LOCAL", raiz / "local"), (propias, "CARPETA_REPO", raiz / "repo"),
                                      (propias, "IMAGENES", raiz / "imagenes"), (vision, "IMAGENES", raiz / "imagenes")):
            p = mock.patch.object(modulo, nombre, valor)
            p.start()
            self.addCleanup(p.stop)
        for nombre in ("_hechas", "_candidatos"):
            p = mock.patch.object(propias, nombre, type(getattr(propias, nombre))())
            p.start()
            self.addCleanup(p.stop)
        self.reloj = [100.0]
        p = mock.patch("time.monotonic", side_effect=lambda: self.reloj[0])
        p.start()
        self.addCleanup(p.stop)
        self.pantalla = cv2.imread(str(PANTALLA))

    def _verla_dos_veces(self, pantalla=None):
        """Dos vistas separadas: la primera queda de candidata y la segunda la confirma."""
        with mock.patch.object(propias, "activo", True):
            Plantilla(OK).esta(self.pantalla if pantalla is None else pantalla)
            self.reloj[0] += propias.SEPARACION_S + 1
            Plantilla(OK).esta(self.pantalla if pantalla is None else pantalla)

    def test_cada_una_es_de_autofarming_o_tiene_propia(self):
        lista = propias.de_autofarming()
        self.assertEqual(len(lista), 145)
        self.assertIn(OK, lista)
        sin_nada = [r for r in lista if not (IMAGENES_REALES / r).is_file()
                    and not (REPO_REAL / Path(r).with_suffix(".png")).is_file()]
        self.assertEqual(sin_nada, [], "borrada sin propia: el bot no la encontraria")
        ambas = [r for r in lista if (IMAGENES_REALES / r).is_file()
                 and (REPO_REAL / Path(r).with_suffix(".png")).is_file()]
        self.assertEqual(ambas, [], "con propia publicada, la de AutoFarming se borra")

    def test_una_sola_vista_no_basta(self):
        with mock.patch.object(propias, "activo", True):
            Plantilla(OK).esta(self.pantalla)
            self.reloj[0] += 2
            Plantilla(OK).esta(self.pantalla)  # demasiado pronto: puede ser la misma animacion
        self.assertFalse(propias.ruta_local(OK).is_file())

    def test_al_reconocerla_farmeando_guarda_el_recorte(self):
        self._verla_dos_veces()
        guardada = propias.ruta_local(OK)
        self.assertTrue(guardada.is_file())
        recorte = cv2.imread(str(guardada))
        original = cv2.imread(str(Path(propias.IMAGENES) / OK))
        self.assertEqual(recorte.shape, original.shape)
        self.assertEqual(propias.pendientes(), [OK])
        self.assertEqual(propias.progreso()[0], 1)

    def test_sin_farmear_o_en_un_recorte_no_guarda_nada(self):
        Plantilla(OK).esta(self.pantalla)  # activo = False: la interfaz, las pruebas
        with mock.patch.object(propias, "activo", True):
            Plantilla(OK).esta(self.pantalla[850:940, 250:500].copy())  # trozo, no pantalla completa
        self.assertFalse(propias.CARPETA_LOCAL.exists())

    def test_publicada_se_usa_en_vez_de_la_de_autofarming(self):
        self._verla_dos_veces()
        destino = propias.ruta_repo(OK)
        destino.parent.mkdir(parents=True)
        destino.write_bytes(propias.ruta_local(OK).read_bytes())
        p = Plantilla(OK)
        self.assertEqual(propias.preferida(p.rutas[0]), destino)
        self.assertGreater(p.confianza(self.pantalla)[0], 0.99, "la propia salio de esta pantalla")
        self.assertEqual(propias.pendientes(), [], "ya publicada: nada que subir")

    def test_las_que_no_son_de_autofarming_no_se_tocan(self):
        with mock.patch.object(propias, "activo", True):
            self.assertFalse(propias.anotar(Path(propias.IMAGENES) / "demons/indura_lumen.png", self.pantalla,
                                            (0, 0, 10, 10), 1.0))

    def test_si_la_segunda_es_distinta_no_se_queda_ninguna(self):
        oscura = cv2.imread(str(PANTALLA.with_name("victoria_oscura.png")))
        with mock.patch.object(propias, "activo", True):
            Plantilla(OK).esta(self.pantalla)
            self.reloj[0] += propias.SEPARACION_S + 1
            Plantilla(OK).esta(oscura)
        self.assertFalse(propias.ruta_local(OK).is_file())

    def test_preparar_copia_lleva_las_pendientes_al_repositorio(self):
        self._verla_dos_veces()
        with tempfile.TemporaryDirectory() as copia:
            original = Path(copia) / "assets" / "imagenes" / OK
            original.parent.mkdir(parents=True)
            original.write_bytes(b"de AutoFarming")
            self.assertEqual(propias.preparar_copia(Path(copia)), [OK])
            self.assertTrue((Path(copia) / "assets" / "propias" / OK).is_file())
            self.assertFalse(original.exists(), "con la propia subida, la de AutoFarming se borra")


class EnUnTrozo(unittest.TestCase):
    """2026-11-22: los huecos de la barra del turno y las estrellas de las cartas se buscan en un trozo de la pantalla
    y nunca se recortaban (salen en cada pelea y seguian siendo de AutoFarming)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        cambios = [mock.patch.object(propias, "CARPETA_LOCAL", raiz / "local"),
                   mock.patch.object(propias, "CARPETA_REPO", raiz / "repo"),
                   mock.patch.object(propias, "_hechas", set()), mock.patch.object(propias, "_candidatos", {}),
                   mock.patch.object(propias, "activo", True)]
        self.reloj = [100.0]
        cambios.append(mock.patch("time.monotonic", side_effect=lambda: self.reloj[0]))
        for c in cambios:
            c.start()
            self.addCleanup(c.stop)
        from lumen import juego

        for plantilla in (juego.espacio_vacio, juego.rango_bronce, juego.rango_plata, juego.rango_oro):
            plantilla.recargar()
            self.addCleanup(plantilla.recargar)

    def test_huecos_y_estrellas_se_recortan_de_la_pantalla_entera(self):
        from lumen import cartas

        if not (propias.IMAGENES / "bronze_card.png").is_file():
            self.skipTest("las estrellas ya tienen imagen propia y la de AutoFarming se borro")
        pantalla = cv2.imread(str(Path(__file__).with_name("rata_f2_tres.png")))
        for _ in range(2):
            cartas.contar_huecos(pantalla)
            cartas.leer_mano(pantalla)
            self.reloj[0] += propias.SEPARACION_S + 1
        guardadas = propias.pendientes()
        self.assertTrue(any(r.startswith("dogs/empty_slot") for r in guardadas), guardadas)
        self.assertIn("bronze_card.png", guardadas)
        for rel in guardadas:  # el recorte es del mismo tamano y se parece a la original
            recorte, original = cv2.imread(str(propias.ruta_local(rel))), cv2.imread(str(propias.IMAGENES / rel))
            self.assertEqual(recorte.shape, original.shape, rel)
            self.assertGreater(cv2.matchTemplate(recorte, original, cv2.TM_CCOEFF_NORMED).max(), propias.UMBRAL, rel)


if __name__ == "__main__":
    unittest.main()
