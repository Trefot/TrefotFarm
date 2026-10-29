"""Metas de material: lo que suma el botin, donde farmearlas y la parte de la interfaz (sin ventanas nuevas)."""

import time
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import avisos, botin, metas, premios, recompensas, ventana
from lumen.control import control

CATALOGO = {  # el botin con su objeto de las tablas de premios (recompensas.vincular_premios)
    "objeto_1": {"nombre": "Garra", "premio": "garra_skoll_hati"},
    "objeto_2": {"nombre": "Orbe", "premio": "orbe_skoll_hati"},
    "objeto_3": {"nombre": "Garra leida rara", "unido_a": "objeto_1"},
}


class Base(unittest.TestCase):
    def setUp(self):
        entorno.ajustes()["metas"] = []
        self.registros = []
        for objeto, nombre, valor in ((recompensas, "leer", lambda: self.registros),
                                      (botin, "cargar_catalogo", lambda: CATALOGO)):
            p = mock.patch.object(objeto, nombre, valor)
            p.start()
            self.addCleanup(p.stop)
        metas._cache = (0.0, [])

    def victoria(self, **objetos):
        self.registros.append({"fecha": time.time() + 1, "objetos": objetos})


class Logica(Base):
    def test_suma_el_botin_desde_que_se_puso(self):
        self.victoria(objeto_1=3)  # antes de la meta: no cuenta
        metas.poner("garra_skoll_hati", 10, 40)
        self.registros[0]["fecha"] = time.time() - 60
        self.victoria(objeto_1=2, objeto_2=1)
        self.victoria(objeto_3=4)  # unido a la garra
        m = metas.de("garra_skoll_hati", metas.cargar(fresco=True))
        self.assertEqual((m.actual, m.faltan, m.completa), (16, 24, False))

    def test_cambiar_conserva_el_orden_y_quitar(self):
        metas.poner("garra_skoll_hati", 0, 10)
        metas.poner("orbe_skoll_hati", 0, 5)
        metas.poner("garra_skoll_hati", 3, 20)
        self.assertEqual([m.objeto for m in metas.cargar(fresco=True)], ["garra_skoll_hati", "orbe_skoll_hati"])
        metas.quitar("garra_skoll_hati")
        self.assertEqual([m.objeto for m in metas.cargar()], ["orbe_skoll_hati"])

    def test_donde_farmearla(self):
        self.assertAlmostEqual(premios.esperado("perros_piso4", "garra_skoll_hati"), 2.01)
        self.assertEqual(metas.mejor_destino("garra_skoll_hati")[0], "perros_piso4")
        self.assertEqual(metas.victorias_para(28, 2.01), 14)
        metas.poner("garra_skoll_hati", 0, 40)
        metas.poner("orbe_skoll_hati", 9, 5)  # ya completa
        todas = metas.cargar(fresco=True)
        self.assertEqual([m.objeto for m in metas.del_destino("perros_piso4", todas)], ["garra_skoll_hati"])
        self.assertEqual(metas.del_destino("indura", todas), [])


class Interfaz(Base):
    @classmethod
    def setUpClass(cls):
        cls.app = entorno.app_qt()
        cls.parches = [mock.patch.object(ventana, "ventana_abierta", lambda: False),
                       mock.patch.object(ventana, "tamano_actual", lambda: None),
                       mock.patch.object(ventana, "es_admin", lambda: True),
                       mock.patch.object(avisos, "enviar", lambda *a, **k: None)]
        for p in cls.parches:
            p.start()
        from lumen import actualizador

        cls.parches.append(mock.patch.object(actualizador, "revisar", lambda: actualizador.Estado(version_local="pruebas")))
        cls.parches[-1].start()
        entorno.ajustes().update(asistente_visto=True, acceso_ofrecido=True, ultimo_destino="perros_piso4")
        from lumen.gui.principal import VentanaPrincipal

        cls.v = VentanaPrincipal()

    @classmethod
    def tearDownClass(cls):
        cls.v.close()
        for p in cls.parches:
            p.stop()

    def test_fila_metas_y_franja_en_inicio(self):
        ini, f = self.v.paginas["inicio"], self.v.farmear
        ini.ir_a_destino("perros_piso4")
        self.assertEqual(ini.fila_metas.objetos.count("garra_skoll_hati"), 1, "cada material una sola vez")
        self.assertFalse(ini.b_meta.isEnabled(), "sin metas, el chip Meta no vale")
        ini._tocar_material("garra_skoll_hati")
        self.assertFalse(ini.editor.isHidden())
        self.assertTrue(ini.caja_equipo.isHidden(), "la franja ocupa el sitio del equipo")
        self.assertIsNone(metas.de("garra_skoll_hati", metas.cargar(fresco=True)), "solo mirar no crea la meta")
        ini.editor.tengo.setValue(5)
        ini.editor.quiero.setValue(30)
        ini.editor.b_crear.click()
        m = metas.de("garra_skoll_hati", metas.cargar(fresco=True))
        self.assertEqual((m.actual, m.quiero), (5, 30))
        self.assertTrue(ini.b_meta.isEnabled(), "ahora este destino ayuda a una meta")
        ini._tocar_material("garra_skoll_hati")  # tocarlo otra vez cierra la franja
        self.assertTrue(ini.editor.isHidden())
        self.assertFalse(ini.caja_equipo.isHidden())

    def test_desde_farmear_abre_la_franja_en_inicio(self):
        ini, f = self.v.paginas["inicio"], self.v.farmear
        ini.ir_a_destino("indura")
        f.preparar("perros_piso4", {})
        f.fila_metas.tocado.emit("orbe_skoll_hati")
        self.app.processEvents()
        self.assertIs(self.v.pila.currentWidget(), ini)
        self.assertEqual((ini.modo_id, ini.editor.objeto), ("perros_piso4", "orbe_skoll_hati"))
        ini.editor.cerrar()

    def test_ir_a_farmearla_gira_la_rueda_y_pone_meta(self):
        ini = self.v.paginas["inicio"]
        metas.poner("esencia_azul", 0, 100)  # sale en el pajaro Floor 1-3, pero mas en los perros Floor 4
        ini.abrir_meta("esencia_azul", "pajaro_pisos1a3")
        ini.editor.b_ir.click()
        self.assertEqual(ini.modo_id, "perros_piso4")
        self.assertTrue(ini.b_meta.isChecked())
        self.assertTrue(ini.editor.isHidden())

    def test_para_al_cumplir_la_meta(self):
        f = self.v.farmear
        metas.poner("garra_skoll_hati", 0, 4)
        f.preparar("perros_piso4", {})
        detenido, saltado = [], []
        with mock.patch.object(type(self.v.puente), "corriendo", property(lambda s: True)), \
             mock.patch.object(f, "detener", lambda: detenido.append(1)), \
             mock.patch.object(f, "saltar_tarea", lambda: saltado.append(1)):
            f.parar_en_meta, f.metas_objetivo = True, ["garra_skoll_hati"]
            self.victoria(objeto_1=2)
            metas._cache = (0.0, [])
            f._revisar_metas()
            self.assertEqual(detenido, [], "aun faltan 2")
            self.victoria(objeto_1=2)
            metas._cache = (0.0, [])
            f._revisar_metas()
            self.assertEqual(detenido, [1])
            self.assertFalse(f.parar_en_meta)
            # dentro de un plan: pasa a la siguiente tarea
            f.parar_en_meta, f.plan_paso = True, 0
            f._revisar_metas()
            self.assertEqual(saltado, [1])
        f.plan_paso = None
        control.reiniciar()


if __name__ == "__main__":
    unittest.main()
