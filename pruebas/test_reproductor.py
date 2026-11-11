"""Reproduccion offline: decisiones sin entradas al juego, errores y navegacion Qt."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401
import numpy as np

from lumen import entrada, reproductor as R
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.gui.reproductor import PanelReproductor


class Reproductor(unittest.TestCase):
    def setUp(self):
        # Otros tests crean ventanas cuyos QTimer siguen vivos tras close().
        # Los eventos Qt de estos casos tampoco deben alcanzar APIs reales de Windows/red.
        from lumen import actualizador

        permiso = mock.patch("lumen.admin.activo", return_value=True)
        permiso.start()
        self.addCleanup(permiso.stop)
        for parche in (
            mock.patch("lumen.ventana.tamano_actual", return_value=None),
            mock.patch("lumen.ventana.ventana_abierta", return_value=False),
            mock.patch.object(
                actualizador, "revisar", return_value=actualizador.Estado()
            ),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        self.imagen = np.zeros((940, 550, 3), dtype=np.uint8)
        self.mano = [
            Carta(
                0,
                (61, 822, 57, 118),
                tipo=TipoCarta.NORMAL,
                rango=Rango.BRONCE,
                nombre="heroe.skill_1",
            )
        ]

    def resultado(self):
        return R.Resultado(
            self.imagen,
            self.mano,
            ("jugar", 0),
            4,
            "Pantalla sin clasificar",
            {},
            "pajaro_f1",
            1,
            True,
        )

    def test_orden_natural_sin_repetidos(self):
        self.assertEqual(
            [
                p.name
                for p in R.ordenar(["captura10.png", "captura2.png", "captura2.png"])
            ],
            ["captura2.png", "captura10.png"],
        )

    def test_tamano_incorrecto_no_invoca_lector(self):
        with (
            mock.patch.object(
                R, "leer_imagen", return_value=np.zeros((30, 30, 3), dtype=np.uint8)
            ),
            mock.patch.object(R.cartas, "leer_mano") as leer,
        ):
            with self.assertRaisesRegex(ValueError, "550"):
                R.analizar(Path("x.png"))
        leer.assert_not_called()

    def test_imagen_invalida(self):
        with mock.patch.object(R, "leer_imagen", return_value=None):
            with self.assertRaisesRegex(ValueError, "leer"):
                R.analizar(Path("x.png"))

    def test_parametros_invalidos(self):
        for acciones, fase in ((-1, 1), (7, 1), (4, 5), (4, 0)):
            with self.assertRaises(ValueError):
                R.analizar(Path("x.png"), acciones=acciones, fase=fase)

    def test_analisis_sin_clics_ni_diario(self):
        from lumen.ia.diario import Diario

        with (
            mock.patch.object(R, "leer_imagen", return_value=self.imagen),
            mock.patch.object(R.cartas, "leer_mano", return_value=self.mano),
            mock.patch.object(R.cartas, "contar_huecos", return_value=4),
            mock.patch.object(R.inteligencia, "Jugador") as jugador,
            mock.patch.object(entrada, "clic") as clic,
            mock.patch.object(entrada, "arrastrar") as arrastrar,
            mock.patch.object(Diario, "terminar") as diario,
        ):
            jugador.return_value.elegir.return_value = ("jugar", 0)
            jugador.return_value.razones = {}
            resultado = R.analizar(Path("x.png"), destino="pajaro_f1")
        self.assertEqual(resultado.paso, ("jugar", 0))
        self.assertEqual(
            jugador.return_value.elegir.call_args_list,
            [mock.call(self.mano, 4), mock.call(self.mano, 4)],
        )
        clic.assert_not_called()
        arrastrar.assert_not_called()
        diario.assert_not_called()

    def test_sin_turno_no_propone(self):
        with (
            mock.patch.object(R, "leer_imagen", return_value=self.imagen),
            mock.patch.object(R.cartas, "leer_mano", return_value=self.mano),
            mock.patch.object(R.cartas, "contar_huecos", return_value=0),
            mock.patch.object(R.inteligencia, "Jugador") as jugador,
        ):
            jugador.return_value.razones = {}
            resultado = R.analizar(Path("x.png"))
        self.assertIsNone(resultado.paso)
        jugador.return_value.elegir.assert_not_called()

    def test_victoria_no_propone_aunque_se_fuerce_turno(self):
        with (
            mock.patch.object(R, "leer_imagen", return_value=self.imagen),
            mock.patch.object(R.juego.victoria, "confianza", return_value=(0.99, None)),
            mock.patch.object(R.cartas, "leer_mano", return_value=self.mano),
            mock.patch.object(R.cartas, "contar_huecos", return_value=0),
            mock.patch.object(R.inteligencia, "Jugador") as jugador,
        ):
            jugador.return_value.razones = {}
            resultado = R.analizar(Path("x.png"), acciones=4)
        self.assertIsNone(resultado.paso)
        self.assertIn("Victoria", resultado.estado)

    def test_anotacion_no_modifica_original(self):
        salida = R.anotar(self.resultado())
        self.assertFalse(np.array_equal(salida, self.imagen))
        self.assertEqual(np.count_nonzero(self.imagen), 0)
        self.assertIn("jugar carta 1", self.resultado().texto())

    def test_lector_y_planificador_reales_con_captura_sintetica(self):
        from lumen import juego, personajes
        from lumen.vision import guardar_imagen

        imagen = np.full((940, 550, 3), 25, dtype=np.uint8)
        biblioteca = personajes.cargar()
        claves = [
            ("odin", "single"),
            ("gawain", "area"),
            ("freyja_roja", "normal_1"),
            ("thonar_azul", "postura"),
        ] * 2
        x, y, x2, _ = juego.REGION["mano_4"]
        ancho, alto = (x2 - x) // 8, 940 - y
        for i, (pid, cid) in enumerate(claves):
            ref = biblioteca[pid].plantilla(cid)[0].imagenes[0]
            h, w = min(ref.shape[0], alto - 24), min(ref.shape[1], ancho - 12)
            izquierda = x + i * ancho
            imagen[y : y + alto, izquierda : izquierda + ancho] = (190, 160, 105)
            imagen[y + 13 : y + 13 + h, izquierda + 6 : izquierda + 6 + w] = ref[:h, :w]
            rango = juego.rango_bronce.imagenes[0]
            rh, rw = rango.shape[:2]
            imagen[y + alto - rh : y + alto, izquierda + 8 : izquierda + 8 + rw] = rango
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "simulada.png"
            guardar_imagen(ruta, imagen)
            with (
                mock.patch.object(entrada, "clic") as clic,
                mock.patch.object(entrada, "arrastrar") as arrastrar,
            ):
                resultado = R.analizar(ruta, acciones=4)
            self.assertEqual(len(resultado.mano), 8)
            self.assertEqual(
                [c.nombre.split("@")[0] for c in resultado.mano],
                [f"{p}.{c}" for p, c in claves],
            )
            self.assertTrue(
                all(
                    c.tipo == TipoCarta.NORMAL and c.rango == Rango.BRONCE
                    for c in resultado.mano
                )
            )
            self.assertIsNotNone(resultado.paso)
            clic.assert_not_called()
            arrastrar.assert_not_called()

    def test_panel_navega_y_limpia_analisis_anterior(self):
        app = entorno.app_qt()
        panel = PanelReproductor(lambda: ("pajaro_pisos1a3", False), lambda: False)
        with mock.patch("lumen.vision.leer_imagen", return_value=self.imagen):
            panel.cargar(["captura10.png", "captura2.png"])
            panel._terminado(self.resultado(), "")
            self.assertTrue(panel.copiar.isEnabled())
            panel.mover(1)
            self.assertIn("captura10", panel.posicion.text())
            self.assertEqual(panel.detalle.toPlainText(), "")
            self.assertFalse(panel.copiar.isEnabled())
            panel.mover(1)
            self.assertEqual(panel.indice, 1)
        panel.close()
        app.processEvents()

    def test_panel_bloqueado_no_inicia_analisis(self):
        app = entorno.app_qt()
        panel = PanelReproductor(lambda: ("indura", True), lambda: True)
        with (
            mock.patch("lumen.vision.leer_imagen", return_value=self.imagen),
            mock.patch.object(R, "analizar") as analizar,
        ):
            panel.cargar(["x.png"])
            panel.revisar()
        analizar.assert_not_called()
        self.assertIn("Detén", panel.estado.text())
        self.assertFalse(panel.ocupado)
        panel.close()
        app.processEvents()

    def test_hilo_entrega_resultado_y_contexto(self):
        app = entorno.app_qt()
        panel = PanelReproductor(lambda: ("pajaro_pisos1a3", False), lambda: False)
        panel.piso.setValue(2)
        with (
            mock.patch("lumen.vision.leer_imagen", return_value=self.imagen),
            mock.patch.object(R, "analizar", return_value=self.resultado()) as analizar,
        ):
            panel.cargar(["x.png"])
            panel.revisar()
            limite = time.monotonic() + 3
            while panel.ocupado and time.monotonic() < limite:
                app.processEvents()
                time.sleep(0.01)
            self.assertFalse(panel.ocupado)
            self.assertIsNotNone(panel.resultado)
            self.assertEqual(analizar.call_args.kwargs["destino"], "pajaro_f2")
        panel.close()

    def test_error_hilo_se_muestra_y_permite_reintentar(self):
        app = entorno.app_qt()
        panel = PanelReproductor(lambda: ("indura", True), lambda: False)
        with (
            mock.patch("lumen.vision.leer_imagen", return_value=self.imagen),
            mock.patch.object(R, "analizar", side_effect=ValueError("imagen rota")),
        ):
            panel.cargar(["x.png"])
            panel.revisar()
            limite = time.monotonic() + 3
            while panel.ocupado and time.monotonic() < limite:
                app.processEvents()
                time.sleep(0.01)
        self.assertEqual(panel.estado.text(), "imagen rota")
        self.assertTrue(panel.analizar.isEnabled())
        panel.close()


if __name__ == "__main__":
    unittest.main()
