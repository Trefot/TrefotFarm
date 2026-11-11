"""Regresiones de estabilidad: entrada, tickets, botín, reconocimiento y aprendizaje.
Ejecutar desde el repo: python -m unittest discover -s pruebas -t pruebas
No usa red ni juego. Todos los archivos del caso se guardan en una carpeta temporal.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import entorno  # noqa: F401 (simula Windows antes de importar lumen)
import numpy as np
from lumen import recompensas, inteligencia, entrada
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import lecciones
from lumen.modos import fuerte_solgres as fs


class Regresiones(unittest.TestCase):
    def setUp(self):
        from lumen.control import control

        control.reiniciar()
        self.addCleanup(control.reiniciar)

    def test_tickets_presupuesto_parcial(self):
        from lumen.motor import TerminarModo

        modo = fs.Oro({"tickets": True, "max_tickets": 40})
        modo.tickets = 30
        modo.clic_si = mock.Mock()
        with self.assertRaises(TerminarModo):
            modo.usar_tickets(None, None)
        modo.clic_si.assert_not_called()
        self.assertEqual(modo.tickets, 30)

    def test_tickets_tanda_exacta_y_sin_limite(self):
        for limite in (30, 0):
            with self.subTest(limite=limite):
                modo = fs.Oro({"tickets": True, "max_tickets": limite})
                modo.clic_si = mock.Mock(return_value=True)
                with (
                    mock.patch.object(fs.MAX_TICKETS, "esta", return_value=True),
                    mock.patch.object(fs.RESULTADO, "esta", return_value=False),
                ):
                    modo.usar_tickets(None, None)
                self.assertEqual(modo.tickets, 30)
                self.assertEqual(modo.clic_si.call_count, 3)

    def test_ulti_identificada_no_fusiona(self):
        cartas = [
            Carta(
                posicion=i,
                tipo=TipoCarta.ULTI,
                rango=Rango.ULTI,
                imagen=np.ones((100, 65, 3), dtype=np.uint8),
            )
            for i in range(2)
        ]
        inteligencia.agrupar_por_dibujo(cartas, lambda c: "heroe.ulti")
        _, plan = inteligencia.planear(cartas, 2)
        self.assertEqual([paso[0] for paso in plan], ["jugar", "jugar"])

    def test_indura_registra_turnos_y_reintentos(self):
        from lumen.modos.indura import Indura

        modo = Indura({"jugar": "Inteligente"})
        modo.diario.empezar()
        mano = [Carta(posicion=0, nombre="heroe.skill_1", tipo=TipoCarta.NORMAL)]

        def jugar(cartas, libres, origen):
            modo._apuntar(cartas, 0)
            modo.libres_antes = libres

        with (
            mock.patch(
                "lumen.modos.indura.cartas.casillas_libres_demonio",
                side_effect=[6, 5, 5, 0, 6],
            ),
            mock.patch(
                "lumen.modos.indura.cartas.leer_mano_demonio", return_value=mano
            ),
            mock.patch.object(modo, "_jugar_inteligente", side_effect=jugar),
        ):
            for _ in range(5):
                modo._jugar_carta(None, None)
        self.assertEqual(
            [t["turno"] for t in modo.diario.pelea["turnos"]], [1, 1, 1, 2]
        )

    def test_diario_sin_turno_no_refuerza_victoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            pelea = {
                "destino": "indura_chaos",
                "resultado": "victoria",
                "turnos": [
                    {"fase": 1, "turno": None, "jugada": ["jugar", "heroe.skill_1"]}
                ],
            }
            self.assertEqual(lecciones.aprender(pelea, carpeta=Path(tmp)), [])
            self.assertEqual(lecciones.cargar("indura_chaos", Path(tmp)), {})

    def test_detener_arrastre_suelta_boton(self):
        from lumen.control import control, Detenido

        entrada.win32api.mouse_event.reset_mock()
        with (
            mock.patch.object(entrada.pyautogui, "moveTo"),
            mock.patch.object(
                entrada.time, "sleep", side_effect=lambda _: control.detener()
            ),
        ):
            with self.assertRaises(Detenido):
                entrada.arrastrar((0, 0), (10, 10), (0, 0))
        self.assertEqual(
            entrada.win32api.mouse_event.call_args,
            mock.call(entrada.win32con.MOUSEEVENTF_LEFTUP, 0, 0),
        )

    def test_reanalizar_conserva_primera_recompensa(self):
        with tempfile.TemporaryDirectory() as tmp:
            indice = Path(tmp) / "indice.jsonl"
            indice.write_text(
                json.dumps({"ruta": "foto.png", "primera": True, "analizado": False})
                + "\n"
            )
            with (
                mock.patch.object(recompensas, "INDICE", indice),
                mock.patch.object(
                    recompensas,
                    "leer_imagen",
                    return_value=np.zeros((940, 550, 3), dtype=np.uint8),
                ),
                mock.patch.object(
                    recompensas, "_analizar", return_value={"objetos": {}}
                ) as analizar,
            ):
                recompensas.reanalizar_pendientes()
                self.assertTrue(
                    analizar.call_args.kwargs.get("primera", False),
                    "Se debe reenviar primera=True al analizador",
                )

    def test_no_superar_maximo_tickets(self):
        modo = fs.Oro({"tickets": True, "max_tickets": 10})
        modo.clic_si = lambda *a, **k: True
        with (
            mock.patch.object(fs.MAX_TICKETS, "esta", return_value=True),
            mock.patch.object(fs.RESULTADO, "esta", return_value=False),
        ):
            from lumen.motor import TerminarModo

            with self.assertRaises(TerminarModo):
                modo.usar_tickets(None, None)
        self.assertLessEqual(modo.tickets, 10)

    def test_identificar_ultis_del_jugador_generico(self):
        carta = Carta(
            posicion=0,
            tipo=TipoCarta.ULTI,
            rango=Rango.ULTI,
            imagen=np.ones((100, 65, 3), dtype=np.uint8),
        )
        identificar = mock.Mock(return_value="freyja_roja.ulti")
        inteligencia.agrupar_por_dibujo([carta], identificar)
        self.assertIsNotNone(
            carta.nombre,
            "Las ultis necesitan identidad para aplicar mecánicas y aprendizaje",
        )

    def test_indura_castiga_solo_ultimos_turnos(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Esquema real de DemonioTiempoReal._apuntar: turno=None para todas las decisiones.
            pelea = {
                "destino": "indura_chaos",
                "resultado": "derrota",
                "turnos": [
                    {
                        "fase": 1,
                        "turno": None,
                        "accion": i,
                        "jugada": ["jugar", f"heroe.carta{i}"],
                    }
                    for i in range(1, 7)
                ],
            }
            lecciones.aprender(pelea, carpeta=Path(tmp))
            datos = lecciones.cargar("indura_chaos", Path(tmp))
            self.assertNotIn(
                "carta:heroe.carta1",
                datos.get("fases", {}).get("1", {}),
                "No se debe culpar la primera acción por falta de número de turno",
            )

    def test_limpieza_si_falla_al_empezar(self):
        from lumen.motor import Modo

        with mock.patch.object(Modo, "estado_inicial", return_value="inicio"):
            modo = Modo({})
        modo.estados = lambda: {}
        modo._iniciar_vigilante = lambda: setattr(modo, "_vigilante_activo", True)
        modo.al_empezar = mock.Mock(side_effect=RuntimeError("fallo de inicialización"))
        modo.al_terminar = mock.Mock()
        with self.assertRaises(RuntimeError):
            modo.ejecutar()
        self.assertFalse(
            modo._vigilante_activo,
            "El vigilante debe apagarse aunque falle la inicialización",
        )

    def test_arrastre_suelta_boton_tras_excepcion(self):
        entrada.win32api.mouse_event.reset_mock()
        with (
            mock.patch.object(
                entrada.pyautogui,
                "moveTo",
                side_effect=[None, RuntimeError("ratón interrumpido")],
            ),
            mock.patch.object(entrada.time, "sleep", return_value=None),
        ):
            with self.assertRaises(RuntimeError):
                entrada.arrastrar((0, 0), (10, 10), (0, 0))
        self.assertGreaterEqual(
            entrada.win32api.mouse_event.call_count,
            2,
            "LEFTUP tiene que ejecutarse en finally",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
