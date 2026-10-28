"""La interfaz: se abren todas las paginas y el plan del dia pasa de una tarea a otra."""

import time
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import actualizador, avisos, ventana
from lumen.control import control


class Interfaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = entorno.app_qt()
        cls.parches = [
            mock.patch.object(ventana, "ventana_abierta", lambda: False),
            mock.patch.object(ventana, "tamano_actual", lambda: None),
            mock.patch.object(ventana, "es_admin", lambda: True),
            mock.patch.object(actualizador, "revisar", lambda: actualizador.Estado(version_local="pruebas")),
            mock.patch.object(avisos, "enviar", lambda *a, **k: None),
        ]
        for p in cls.parches:
            p.start()
        entorno.ajustes().update(asistente_visto=True, acceso_ofrecido=True)
        from lumen.gui.principal import VentanaPrincipal

        cls.v = VentanaPrincipal()
        cls.v.resize(1280, 860)
        cls.v.show()

    @classmethod
    def tearDownClass(cls):
        cls.v.close()
        for p in cls.parches:
            p.stop()

    def eventos(self, n=5):
        for _ in range(n):
            self.app.processEvents()

    def test_todas_las_paginas(self):
        for clave in self.v.paginas:
            with self.subTest(pagina=clave):
                self.v.navegar(clave)
                self.eventos()
                self.assertIs(self.v.pila.currentWidget(), self.v.paginas[clave])

    def test_menu_normal(self):
        entorno.ajustes()["modo_admin"] = False
        self.v.aplicar_modo_admin()
        visibles = [c for c, b in self.v.botones.items() if not b.isHidden()]
        self.assertEqual(visibles, ["inicio", "farmear", "personajes", "ayuda", "ajustes"])

    def test_icono_equipo_lleva_a_farmear(self):
        self.v.navegar("inicio")
        self.v.paginas["inicio"].pasos["equipo"].click()
        self.eventos()
        self.assertIs(self.v.pila.currentWidget(), self.v.farmear)

    def test_plan_del_dia(self):
        from lumen.gui import plan, resumen

        f = self.v.farmear
        corriendo = {"v": False}
        arrancados, no_arranca, tarjetas = [], set(), []

        def iniciar(remoto=False):
            arrancados.append(f.modo_cls.id)
            corriendo["v"] = f.modo_cls.id not in no_arranca

        def terminar(por_usuario=False, **stats):
            corriendo["v"] = False
            control.reiniciar()
            if por_usuario:
                control.detener()
            f.inicio, f.ultimas_stats = time.time() - 600, {"victorias": 2, **stats}
            f._terminado()

        tarjeta = type("T", (), {"show": lambda s: None})
        with mock.patch.object(type(self.v.puente), "corriendo", property(lambda s: corriendo["v"])), \
             mock.patch.object(f, "iniciar", iniciar), \
             mock.patch("lumen.gui.paginas.farmear.QTimer.singleShot", lambda ms, fn: fn()), \
             mock.patch.object(resumen, "TarjetaResumen", lambda *a: tarjetas.append(a[1]) or tarjeta()), \
             mock.patch.object(resumen, "enviar_al_movil", lambda *a: None):
            plan.guardar([{"modo": "pajaro_pisos1a3", "victorias": 5}, {"modo": "ciervo_pisos1a3", "victorias": 5},
                          {"modo": "indura", "victorias": 3}])
            # de una tarea a otra, y un solo resumen al final
            f.iniciar_plan()
            terminar()
            terminar()
            terminar()
            self.assertEqual(arrancados, ["pajaro_pisos1a3", "ciervo_pisos1a3", "indura"])
            self.assertIsNone(f.plan_paso)
            self.assertEqual(tarjetas, ["Plan del día (3 tareas)"])
            # detener a mano para el plan entero
            arrancados.clear()
            f.iniciar_plan()
            terminar(por_usuario=True)
            self.assertEqual(arrancados, ["pajaro_pisos1a3"])
            self.assertIsNone(f.plan_paso)
            # una tarea que no puede empezar se salta
            arrancados.clear()
            no_arranca.add("pajaro_pisos1a3")
            control.reiniciar()
            f.iniciar_plan()
            self.assertEqual(arrancados, ["pajaro_pisos1a3", "ciervo_pisos1a3"])
            terminar()
            terminar()
            no_arranca.clear()
            # sin estamina: se saltan las tareas que la usan (Indura sigue)
            arrancados.clear()
            f.iniciar_plan()
            terminar(motivo_fin="sin_estamina")
            self.assertEqual(arrancados, ["pajaro_pisos1a3", "indura"])
            terminar()
            self.assertIsNone(f.plan_paso)
            # "saltar" desde el movil: deja la tarea en curso y el plan sigue
            arrancados.clear()
            f.iniciar_plan()
            with mock.patch.object(f, "detener", lambda: terminar(por_usuario=True)):
                f._orden("saltar")
            self.assertEqual(arrancados, ["pajaro_pisos1a3", "ciervo_pisos1a3"])
            self.assertEqual(f.plan_paso, 1)
            enviados = []
            with mock.patch.object(avisos, "enviar", lambda texto, *a: enviados.append(texto)):
                f._orden("plan ver")
            self.assertIn("tarea 2 de 3", enviados[0])
            self.assertIn("✓ 1.", enviados[0])
            self.assertIn("▶ 2.", enviados[0])
            terminar()
            terminar()
            self.assertIsNone(f.plan_paso)
        control.reiniciar()

    def test_prueba_rapida(self):
        from lumen.gui.paginas import farmear

        f = self.v.farmear
        corriendo = {"v": False}
        arrancados, informes, enviados = [], [], []
        guion = {}  # modo -> como acaba: "ok", "error", "no_arranca" o "sin_victoria"

        def iniciar(remoto=False):
            m = f.modo_cls.id
            arrancados.append(m)
            if guion.get(m) == "no_arranca":
                f._problema("Juego cerrado", "No encuentro la ventana.", remoto)
                return
            corriendo["v"] = True
            self.v.puente.ultimo_error = None
            f.inicio = time.time() - 90

        def terminar():
            m = f.modo_cls.id
            corriendo["v"] = False
            control.reiniciar()
            if guion.get(m) == "error":
                self.v.puente.ultimo_error = "KeyError: 'x' (bestias_pisos1a3.py:12 en elegir_piso)"
            f.ultimas_stats = {"victorias": 0 if guion.get(m) in ("error", "sin_victoria") else 1}
            f._terminado()

        tareas = farmear.tareas_de_prueba()
        self.assertEqual(len(tareas), 7)
        self.assertTrue(all(t["victorias"] == 1 for t in tareas))
        ids = [t["modo"] for t in tareas]
        guion.update({ids[1]: "error", ids[2]: "no_arranca", ids[3]: "sin_victoria"})
        with mock.patch.object(type(self.v.puente), "corriendo", property(lambda s: corriendo["v"])), \
             mock.patch.object(f, "iniciar", iniciar), \
             mock.patch.object(ventana, "ventana_abierta", lambda: True), \
             mock.patch("lumen.gui.paginas.farmear.QTimer.singleShot", lambda ms, fn: fn()), \
             mock.patch.object(farmear, "VentanaInforme", lambda padre, texto: informes.append(texto) or mock.MagicMock()), \
             mock.patch.object(farmear, "LOGS", entorno.TEMPORAL), \
             mock.patch.object(avisos, "enviar", lambda texto, *a: enviados.append(texto)):
            f.iniciar_prueba(remoto=True)
            while corriendo["v"]:
                terminar()
        self.assertEqual(arrancados, ids)
        self.assertIsNone(f.plan_paso)
        self.assertFalse(f.plan_prueba)
        resultados = [r["resultado"] for r in f.plan_resultados]
        self.assertEqual(resultados, ["ok", "fallo", "no_empezo", "sin_victoria", "ok", "ok", "ok"])
        self.assertIn("no empezó: Juego cerrado", f.plan_resultados[2]["motivo"])
        texto = informes[0]
        self.assertIn("Resultado: 4 de 7 bien", texto)
        self.assertIn("✗", texto)
        self.assertIn("KeyError", texto)
        self.assertIn(texto, enviados, "el informe tambien va al movil")
        self.assertEqual(len(list(entorno.TEMPORAL.glob("prueba_*.txt"))), 1)
        control.reiniciar()

    def test_ordenes_del_movil(self):
        from lumen import ordenes

        for texto, orden in (("Plan ver", "plan ver"), ("tareas", "plan ver"), ("plan", "plan"),
                             ("saltar", "saltar"), ("skip", "saltar"), ("pausa", "pausar"), ("prueba", "prueba"),
                             ("hola", None)):
            with self.subTest(texto=texto):
                self.assertEqual(ordenes.interpretar(texto), orden)


if __name__ == "__main__":
    unittest.main()
