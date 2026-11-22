"""Monedas SA: la foto del botin de cada vuelta (capturas del usuario, 2026-11-22: el modo no guardaba ninguna)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2

import entorno  # noqa: F401
from lumen import botin
from lumen.modos import fuerte_solgres as F

FOTOS = Path(__file__).with_name("botin_sa")


def foto(nombre):
    img = cv2.imread(str(FOTOS / f"{nombre}.png"))
    assert img is not None, nombre
    return img


class LeerBotin(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        for nombre, valor in (("CARPETA", raiz / "objetos"), ("CATALOGO", raiz / "catalogo.yaml"),
                              ("CATALOGO_BASE", raiz / "base.yaml"), ("GALERIA", raiz / "galeria.yaml")):
            p = mock.patch.object(botin, nombre, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_victoria_limpia_dos_monedas_y_el_oro(self):
        for nombre in ("victoria_limpia", "victoria_fin_cuenta"):
            with self.subTest(nombre):
                r = botin.analizar(foto(nombre), modo="monedas_sa")
                self.assertEqual(r["objetos"], {"galeria_super_awakening_coin": 2})
                self.assertEqual(r["oro"], 12000, '"12,000 (+6000)": solo el primer numero')
                self.assertFalse(r["lectura_incompleta"])

    def test_oscurecida_no_inventa(self):
        r = botin.analizar(foto("victoria_oscura"), modo="monedas_sa")
        self.assertEqual(r["objetos"], {})


class FotoDeCadaVuelta(unittest.TestCase):
    def setUp(self):
        self.m = F.MonedasSA({"victorias": 0, "pociones": True, "max_pociones": 0, "cofre": "Bronce",
                              "segundos_cofre": 12})
        self.m.log = lambda *a, **k: None
        self.fotos = []
        self.cola = []  # lo que devuelve cada captura de la vigilancia rapida
        for parche in (mock.patch.object(self.m, "guardar_recompensa",
                                         side_effect=lambda pant, v, **k: self.fotos.append(v)),
                       mock.patch.object(self.m, "capturar", side_effect=lambda: (foto(self.cola.pop(0)), (0, 0))),
                       mock.patch.object(F.time, "sleep")):
            parche.start()
            self.addCleanup(parche.stop)

    def test_al_acabar_la_pelea_mira_seguido_hasta_la_pantalla_limpia(self):
        """En la sesion real (0.39.7) el bucle normal tardaba ~0,6 s por vuelta y se perdia la pantalla limpia."""
        self.m._foto_botin(foto("pelea"))
        self.cola = ["victoria_limpia"]
        self.m._foto_botin(foto("victoria_sin_ok"))  # la pelea acaba: aun no sale el OK
        self.assertEqual(self.fotos, [1])
        for nombre in ("victoria_oscura", "victoria_fin_cuenta"):
            self.m._foto_botin(foto(nombre))
        self.assertEqual(self.fotos, [1], "una sola por vuelta")

    def test_si_sale_ya_oscurecida_vale_la_del_final_de_la_cuenta_atras(self):
        self.m._foto_botin(foto("pelea"))
        self.cola = ["victoria_oscura"]
        self.m._foto_botin(foto("victoria_sin_ok"))
        self.assertEqual(self.fotos, [])
        self.m.vueltas = 3
        self.m.contada_tras_pelea = True  # "Vuelta #3 terminada" ya salio en lo oscuro
        self.m._foto_botin(foto("victoria_fin_cuenta"))
        self.assertEqual(self.fotos, [3], "es la foto de la vuelta 3, no de la 4")

    def test_ni_oscurecida_ni_resumen_final(self):
        for nombre in ("victoria_oscura", "repeticion_terminada"):
            self.m._foto_botin(foto(nombre))
        self.assertEqual(self.fotos, [])


if __name__ == "__main__":
    unittest.main()


class VolverDesdeElMenu(unittest.TestCase):
    def test_en_el_menu_de_fuerte_solgres_vuelve_a_entrar_en_special(self):
        """2026-11-22: tras una reconexion quedo en el menu de Fuerte Solgres deslizando 4 min."""
        m = F.MonedasSA({"victorias": 0, "pociones": True, "max_pociones": 0, "cofre": "Bronce", "segundos_cofre": 12})
        m.log = lambda *a, **k: None
        with mock.patch.object(F.entrada, "arrastrar") as arrastrar, mock.patch.object(F.entrada, "clic"), \
             mock.patch.object(m, "clic_si", return_value=False):
            self.assertEqual(m.abrir(foto("menu_fuerte_solgres"), (0, 0)), "ir")
        arrastrar.assert_not_called()
