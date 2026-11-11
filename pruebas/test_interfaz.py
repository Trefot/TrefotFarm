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
                with mock.patch("lumen.admin.activo", return_value=True):
                    self.v.navegar(clave)
                    self.eventos()
                    self.assertIs(self.v.pila.currentWidget(), self.v.paginas[clave])

    def test_equipos_accesibles_en_ventana_compacta(self):
        tamano = self.v.size()
        try:
            self.v.resize(1100, 740)
            self.v.navegar("farmear")
            f = self.v.farmear
            f._ver_vista(0)
            self.eventos()
            self.assertTrue(f.contenedor_equipos.isHidden())
            f.ver_equipos()
            self.eventos()
            self.assertIs(f.pila_vista.currentWidget(), f.vista_equipos)
            self.assertFalse(f.contenedor_equipos.isHidden())
            self.v.resize(1440, 900)
            f._ver_vista(0)
            self.eventos()
            self.assertFalse(f.equipos_en_tab)
            self.assertTrue(f.contenedor_equipos.isHidden())
        finally:
            self.v.resize(tamano)
            self.v.farmear._ver_vista(0)

    def test_menu_normal(self):
        entorno.ajustes()["modo_admin"] = False
        self.v.aplicar_modo_admin()
        visibles = [c for c, b in self.v.botones.items() if not b.isHidden()]
        self.assertEqual(visibles, ["inicio", "contenidos", "farmear", "plan", "personajes", "mis_equipos", "objetivos", "ajustes", "ayuda"])

    def test_laboratorio_requiere_llave_y_sale_al_revocar(self):
        with mock.patch("lumen.admin.activo", return_value=False):
            self.v.aplicar_modo_admin()
            self.v.navegar("farmear")
            self.v.navegar("laboratorio")
            self.assertIs(self.v.pila.currentWidget(), self.v.farmear)
            self.assertTrue(self.v.botones["laboratorio"].isHidden())
            self.assertNotIn("Capturas", [b.text().strip() for b in self.v.farmear.grupo_vista.buttons()], "el laboratorio no esta en Farmear")
        with mock.patch("lumen.admin.activo", return_value=True):
            self.v.aplicar_modo_admin()
            self.v.navegar("laboratorio")
            self.assertIs(self.v.pila.currentWidget(), self.v.paginas["laboratorio"])
        with mock.patch("lumen.admin.activo", return_value=False):
            self.v.aplicar_modo_admin()
            self.assertIs(self.v.pila.currentWidget(), self.v.paginas["inicio"])
            self.assertEqual(self.v.farmear.reproductor.rutas, [])

    def test_icono_equipo_lleva_a_farmear(self):
        self.v.navegar("inicio")
        self.v.paginas["preparar"].pasos["equipo"].click()
        self.eventos()
        self.assertIs(self.v.pila.currentWidget(), self.v.farmear)

    def test_catalogo_lleva_a_preparacion_y_plan_es_accesible(self):
        pagina = self.v.paginas["contenidos"]
        pagina.catalogo.elegido.emit("pajaro_pisos1a3")
        self.eventos()
        self.assertIs(self.v.pila.currentWidget(), self.v.paginas["preparar"])
        self.assertEqual(self.v.paginas["preparar"].modo_id, "pajaro_pisos1a3")
        self.assertTrue(self.v.botones["contenidos"].isChecked())
        self.v.farmear._ver_vista(1)
        self.assertIs(self.v.pila.currentWidget(), self.v.paginas["plan"])
        self.assertTrue(self.v.paginas["plan"].isAncestorOf(self.v.farmear.panel_plan))

    def test_catalogo_busqueda_y_contenido_no_disponible(self):
        catalogo = self.v.paginas["contenidos"].catalogo
        try:
            catalogo.buscar.setText("contenido inexistente 123")
            self.assertTrue(all(w.isHidden() for _, w in catalogo.tarjetas))
            self.assertFalse(catalogo.vacio.isHidden())
            from lumen.modos import MODOS
            cerrado = next(d.id for c, _ in catalogo.tarjetas for d in c.destinos if d.id not in MODOS)
            catalogo.elegido.emit(cerrado)
            self.assertFalse(self.v.paginas["preparar"].b_empezar.isEnabled())
        finally:
            catalogo.buscar.clear()

    def test_preparacion_apila_columnas_en_ventana_compacta(self):
        from PyQt5.QtWidgets import QBoxLayout, QScrollArea
        tamano = self.v.size()
        try:
            self.v.resize(1100, 740)
            self.v.navegar("preparar")
            self.eventos()
            pagina = self.v.paginas["preparar"]
            self.assertEqual(pagina.columnas_preparacion.direction(), QBoxLayout.TopToBottom)
            area = pagina.findChild(QScrollArea, "area_pagina")
            self.assertLessEqual(area.widget().width(), area.viewport().width())
        finally:
            self.v.resize(tamano)

    def test_selector_destinos_filtra_y_prepara_el_piso_elegido(self):
        from lumen.modos.catalogo import CATALOGO
        catalogo = self.v.paginas["contenidos"].catalogo
        try:
            catalogo.buscar.setText("Hraesvelgr")
            self.assertEqual(len(catalogo.visibles), 1)
            self.assertFalse(catalogo.siguiente.isEnabled())
            self.assertEqual(catalogo.seleccion.id, "pajaro")
            catalogo.pisos.setCurrentIndex(0)
            imagen_base = catalogo.escena.imagen.toImage()
            catalogo.pisos.setCurrentIndex(1)
            self.assertNotEqual(catalogo.escena.imagen.toImage(), imagen_base)
            catalogo.pisos.setCurrentIndex(0)
            self.assertEqual(catalogo.escena.imagen.toImage(), imagen_base)
            catalogo.buscar.clear()
            siguiente = CATALOGO[1]
            next(b for c, b in catalogo.tarjetas if c.id == siguiente.id).click()
            self.assertEqual(catalogo.seleccion.id, siguiente.id)
            catalogo.pisos.setCurrentIndex(0)
            esperado = siguiente.destinos[0].id
            catalogo.preparar.click()
            self.assertIs(self.v.pila.currentWidget(), self.v.paginas["preparar"])
            self.assertEqual(self.v.paginas["preparar"].modo_id, esperado)
            catalogo.buscar.setText("sin resultados 999")
            self.assertIsNone(catalogo.destino_id)
            self.assertTrue(catalogo.escena.isHidden())
        finally:
            catalogo.buscar.clear()

    def test_tamano_definitivo_y_categorias_separadas(self):
        from PyQt5.QtCore import QSize, Qt
        from lumen.modos.catalogo import BESTIAS, DEMONIOS, FUERTE
        self.assertEqual(self.v.size(), QSize(1100, 800))
        self.assertEqual(self.v.minimumSize(), self.v.maximumSize())
        self.assertFalse(self.v.windowFlags() & Qt.WindowMaximizeButtonHint)
        catalogo = self.v.paginas["contenidos"].catalogo
        self.v.navegar("contenidos")
        try:
            for indice, grupo, cantidad in ((0, BESTIAS, 6), (1, DEMONIOS, 6), (2, FUERTE, 2)):
                catalogo.grupo.setCurrentIndex(indice)
                self.eventos()
                self.assertEqual(len(catalogo.visibles), cantidad)
                self.assertTrue(all(c.grupo == grupo for c in catalogo.visibles))
                self.assertEqual(catalogo.tira.horizontalScrollBar().maximum(), 0)
                self.assertTrue(all(b.isHidden() == (c.grupo != grupo) for c, b in catalogo.tarjetas))
            catalogo.buscar.setText("Oro")
            self.assertEqual(len(catalogo.visibles), 1)
            catalogo.grupo.setCurrentIndex(0)
            self.assertEqual(catalogo.buscar.text(), "")
            self.assertEqual(len(catalogo.visibles), 6)
        finally:
            catalogo.grupo.setCurrentIndex(0)
            catalogo.buscar.clear()

    def test_proximamente_se_muestra_en_gris_y_permite_consultar(self):
        from lumen.modos.catalogo import CATALOGO
        catalogo = self.v.paginas["contenidos"].catalogo
        catalogo.grupo.setCurrentIndex(0)
        rata = next(c for c in CATALOGO if c.id == "rata")
        catalogo.seleccionar(rata)
        for pix in (catalogo.escena.imagen, next(b.imagen for c, b in catalogo.tarjetas if c.id == "rata")):
            imagen = pix.toImage()
            for x in range(0, imagen.width(), 11):
                for y in range(0, imagen.height(), 11):
                    color = imagen.pixelColor(x, y)
                    if color.alpha():
                        self.assertEqual(color.red(), color.green())
                        self.assertEqual(color.green(), color.blue())
        self.assertEqual(catalogo.preparar.text(), "Ver detalles  →")
        self.assertTrue(catalogo.preparar.isEnabled())
        catalogo.preparar.click()
        self.assertEqual(self.v.paginas["preparar"].modo_id, rata.destinos[0].id)
        self.assertFalse(self.v.paginas["preparar"].b_empezar.isEnabled())

    def test_actualizaciones_visibles_en_inicio_y_ajustes(self):
        from PyQt5.QtWidgets import QScrollArea
        estado_anterior = self.v.estado_update
        try:
            self.v.estado_update = None
            self.v.revisando = False
            for clave in ("inicio", "ajustes"):
                self.v.navegar(clave)
                self.eventos()
                panel = self.v.paginas[clave].actualizaciones
                self.assertTrue(panel.boton.isVisible())
                self.assertEqual(panel.boton.text(), "Buscar actualizaciones")
                area = self.v.paginas[clave].findChild(QScrollArea, "area_pagina")
                self.assertLessEqual(panel.boton.mapTo(area.viewport(), panel.boton.rect().bottomRight()).y(), area.viewport().height())
                self.assertLessEqual(panel.boton.mapTo(area.viewport(), panel.boton.rect().bottomRight()).x(), area.viewport().width())
                self.assertLessEqual(area.widget().width(), area.viewport().width())
                with mock.patch.object(self.v, "buscar_updates") as buscar:
                    panel.boton.click()
                    buscar.assert_called_once_with(manual=True)
            self.v.revisando = True
            self.v._refrescar_actualizaciones()
            self.assertFalse(self.v.paginas["inicio"].actualizaciones.boton.isEnabled())
            self.v.revisando = False
            self.v.estado_update = actualizador.Estado(error="Sin conexion de prueba")
            self.v._refrescar_actualizaciones()
            for clave in ("inicio", "ajustes"):
                self.assertIn("Sin conexion de prueba", self.v.paginas[clave].actualizaciones.estado.text())
                self.assertEqual(self.v.paginas[clave].actualizaciones.boton.text(), "Reintentar búsqueda")
            self.v.estado_update = actualizador.Estado(hay_update=True, version_remota="0.99.0-prueba")
            self.v._refrescar_actualizaciones()
            panel = self.v.paginas["inicio"].actualizaciones
            self.assertEqual(panel.boton.text(), "Actualizar app")
            with mock.patch.object(self.v, "accion_actualizar") as actualizar:
                panel.boton.click()
                actualizar.assert_called_once_with()
            with mock.patch.object(type(self.v), "reinicio_pendiente", new_callable=mock.PropertyMock, return_value=True):
                panel.refrescar()
                self.assertEqual(panel.boton.text(), "Reiniciar app")
        finally:
            self.v.revisando = False
            self.v.estado_update = estado_anterior
            self.v._refrescar_actualizaciones()

    def test_plan_del_dia(self):
        from lumen.gui import plan, resumen

        f = self.v.farmear
        corriendo = {"v": False}
        arrancados, no_arranca, tarjetas = [], set(), []

        def iniciar(remoto=False, meta=False):
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

        def iniciar(remoto=False, meta=False):
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
        self.assertEqual(len(tareas), 15)  # 4 bestias F1-3 (Ratatoskr cerrado), perros, pajaro y ciervo F4, 6 demonios y 2 de Fuerte Solgres
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
        self.assertEqual(resultados, ["ok", "fallo", "no_empezo", "sin_victoria"] + ["ok"] * 11)
        self.assertIn("no empezó: Juego cerrado", f.plan_resultados[2]["motivo"])
        texto = informes[0]
        self.assertIn("Resultado: 12 de 15 bien", texto)
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
