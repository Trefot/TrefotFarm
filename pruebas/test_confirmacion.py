"""Permisos reales de administrador y evidencias de acciones aceptadas."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401
from lumen import admin, reproductor
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import diario, lecciones
from lumen.gui.reproductor import PanelReproductor
from lumen.modos.indura import Indura


class Permisos(unittest.TestCase):
    def test_llave_requerida_en_backend(self):
        with (
            mock.patch.object(admin, "activo", return_value=False),
            mock.patch.object(reproductor, "leer_imagen") as leer,
        ):
            with self.assertRaises(PermissionError):
                reproductor.analizar(Path("no_importa.png"))
        leer.assert_not_called()

    def test_no_basta_marcar_casilla(self):
        with (
            mock.patch.object(
                admin, "_publicada", return_value={"sal": "00", "huella": "00"}
            ),
            mock.patch.object(admin, "_llave_guardada", return_value=""),
            mock.patch("lumen.config.obtener_guardado", return_value=True),
        ):
            with self.assertRaises(PermissionError):
                admin.exigir()

    def test_panel_no_abre_capturas_sin_llave(self):
        app = entorno.app_qt()
        panel = PanelReproductor(lambda: ("perros_piso4", False), lambda: False)
        with mock.patch.object(admin, "activo", return_value=False):
            panel.cargar(["privado.png"])
            panel.revisar()
        self.assertEqual(panel.rutas, [])
        self.assertIn("administrador", panel.estado.text())
        panel.close()
        del app

    def test_revocar_no_entrega_resultado_ni_copia(self):
        entorno.app_qt()
        panel = PanelReproductor(lambda: ("perros_piso4", False), lambda: False)
        panel.detalle.setPlainText("privado")
        panel.ocupado = True
        with (
            mock.patch.object(admin, "activo", return_value=False),
            mock.patch("lumen.gui.reproductor.QApplication.clipboard") as copiar,
        ):
            panel._copiar()
            panel._terminado(object(), "")
        copiar.assert_not_called()
        self.assertEqual(panel.detalle.toPlainText(), "")
        self.assertIsNone(panel.resultado)
        self.assertFalse(panel.ocupado)
        panel.close()


class Confirmacion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        self.d = diario.Diario("prueba", self.carpeta)
        self.d.empezar()
        self.mano = [
            Carta(0, tipo=TipoCarta.NORMAL, rango=Rango.BRONCE, nombre="heroe.skill_1")
        ]

    def proponer(self, diario_=None):
        return (diario_ or self.d).decision(1, 1, 0, self.mano, 0, confirmada=False)

    def test_proponer_no_ensena(self):
        self.proponer()
        self.assertEqual(
            lecciones.aprender(
                {**self.d.pelea, "resultado": "victoria"}, carpeta=self.carpeta
            ),
            [],
        )
        self.assertEqual(lecciones.cargar("prueba", self.carpeta), {})

    def test_confirmar_ensena_una_sola_vez(self):
        paso = self.proponer()
        self.assertTrue(self.d.confirmar(paso, True))
        self.assertFalse(self.d.confirmar(paso, True))
        self.assertTrue(
            lecciones.aprender(
                {**self.d.pelea, "resultado": "victoria"}, carpeta=self.carpeta
            )
        )
        self.assertEqual(
            lecciones.cargar("prueba", self.carpeta)["fases"]["1"][
                "carta:heroe.skill_1"
            ]["veces"],
            1,
        )

    def test_rechazada_no_castiga(self):
        paso = self.proponer()
        self.d.confirmar(paso, False)
        self.assertEqual(paso["estado_accion"], "no_confirmada")
        self.assertEqual(
            lecciones.aprender(
                {**self.d.pelea, "resultado": "derrota"}, carpeta=self.carpeta
            ),
            [],
        )

    def test_no_confirma_paso_de_otra_pelea(self):
        paso = self.proponer()
        self.d.empezar()
        self.assertFalse(self.d.confirmar(paso, True))
        self.assertFalse(paso["confirmada"])

    def test_resumen_solo_cuenta_jugadas_confirmadas(self):
        self.proponer()
        p = self.proponer()
        self.d.confirmar(p, True)
        r = diario.resumen([{**self.d.pelea, "resultado": "victoria"}])
        self.assertEqual(r["jugadas_al_ganar"][1]["heroe.skill_1"], 1)

    def test_indura_confirma_al_bajar_casillas(self):
        modo = Indura({"jugar": "Inteligente"})
        modo.diario = self.d
        modo.turno_diario = 1
        modo._apuntar(self.mano, 0)
        modo.libres_antes = 6
        modo.tocado_en = __import__("time").time()
        modo._confirmar_accion(5)
        self.assertTrue(self.d.pelea["turnos"][0]["confirmada"])
        self.assertIsNone(modo.decision_pendiente)

    def test_indura_no_confirma_timeout_o_turno_nuevo(self):
        for libres in (5, 6):
            modo = Indura({"jugar": "Inteligente"})
            modo.diario = self.d
            modo.turno_diario = 1
            modo._apuntar(self.mano, 0)
            modo.libres_antes = 5
            modo.tocado_en = 0
            modo._confirmar_accion(libres)
            self.assertFalse(self.d.pelea["turnos"][-1]["confirmada"])
            self.assertEqual(
                self.d.pelea["turnos"][-1]["estado_accion"], "no_confirmada"
            )


if __name__ == "__main__":
    unittest.main()
