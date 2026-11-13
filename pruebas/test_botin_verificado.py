"""Reconocimiento contra la galeria real, sin crear items de recortes inciertos."""

import tempfile
import json
import unittest
from pathlib import Path
from unittest import mock
import cv2
import numpy as np
import entorno  # noqa: F401
from lumen import botin, recompensas
from lumen.vision import leer_imagen


class BotinVerificado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        for nombre, valor in (
            ("CARPETA", self.raiz / "objetos"),
            ("CATALOGO", self.raiz / "catalogo.yaml"),
            ("CATALOGO_BASE", self.raiz / "base.yaml"),
            ("GALERIA", self.raiz / "galeria.yaml"),
        ):
            p = mock.patch.object(botin, nombre, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_reconoce_la_base_y_no_duplica_items_por_captura(self):
        catalogo = {}
        for gid in (
            "skoll_and_hati_s_orb",
            "hraesvelgr_s_feather",
            "eikthyrnir_s_broken_antler",
            "blue_magic_essence",
        ):
            icono = botin._icono_de_ficha(gid)
            oid = botin.identificar_verificado(icono, catalogo)
            self.assertIsNotNone(oid, gid)
            self.assertEqual(catalogo[oid]["galeria"], gid)
            self.assertEqual(botin.identificar_verificado(icono, catalogo), oid)
            self.assertTrue(catalogo[oid]["nombre"])
        self.assertEqual(len(catalogo), 4)

    def test_miniatura_usa_ficha_completa_y_no_recorte_de_reconocimiento(self):
        catalogo = {"orbe": {"galeria": "skoll_and_hati_s_orb"}}
        self.assertEqual(botin.ruta_miniatura("orbe", catalogo), botin.ruta_ficha("skoll_and_hati_s_orb"))
        imagen = leer_imagen(botin.ruta_miniatura("orbe", catalogo))
        self.assertGreater(imagen.shape[0], 35)
        self.assertEqual(botin.ruta_miniatura("sin_ficha", {}), botin.ruta_icono("sin_ficha"))

    def test_recorte_desconocido_no_contamina_el_catalogo(self):
        ruido = np.random.default_rng(4).integers(0, 255, (35, 53, 3), dtype=np.uint8)
        catalogo = {}
        self.assertIsNone(botin.identificar_verificado(ruido, catalogo))
        self.assertEqual(catalogo, {})
        self.assertFalse(botin.CARPETA.exists())

    def test_recompensa_desplazada_se_identifica_sin_rejilla_fija(self):
        pantalla = np.zeros((940, 550, 3), np.uint8)
        celda = cv2.resize(
            leer_imagen(botin.ruta_ficha("skoll_and_hati_s_orb")),
            (63, 63),
            interpolation=cv2.INTER_AREA,
        )
        pantalla[374:437, 102:165] = celda
        datos = botin.analizar(pantalla)
        self.assertEqual(datos["objetos"], {"galeria_skoll_and_hati_s_orb": 1})
        self.assertEqual(datos["pendientes"], [])

    def test_un_fondo_de_color_plano_no_es_un_icono(self):
        icono = np.full((35, 53, 3), (180, 70, 20), dtype=np.uint8)
        self.assertIsNone(botin.en_galeria(icono, botin.cargar_galeria()))

    def test_forma_igual_con_otro_color_no_es_el_mismo_item(self):
        referencia = botin._icono_de_ficha("blue_magic_essence")
        gris = cv2.cvtColor(
            cv2.cvtColor(referencia, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR
        )
        self.assertIsNone(botin.en_galeria(gris, {"blue_magic_essence": {}}))

    def test_empate_entre_identidades_queda_pendiente(self):
        icono = botin._icono_de_ficha("skoll_and_hati_s_orb")
        with (
            mock.patch.object(botin, "_icono_de_ficha", return_value=icono),
            mock.patch.object(
                botin, "ruta_ficha", return_value=self.raiz / "duplicada.png"
            ),
        ):
            self.assertIsNone(
                botin.en_galeria(icono, {"duplicado_a": {}, "duplicado_b": {}})
            )

    def test_cambio_de_ficha_invalida_cache(self):
        ruta = self.raiz / "icono.png"
        imagen = botin._icono_de_ficha("skoll_and_hati_s_orb")
        with (
            mock.patch.object(botin, "ruta_ficha", return_value=ruta),
            mock.patch.object(botin, "_icono_de_ficha", return_value=None),
        ):
            self.assertIsNone(botin.en_galeria(imagen, {"nuevo_local": {}}))
        ruta.write_bytes(b"presente")
        with (
            mock.patch.object(botin, "ruta_ficha", return_value=ruta),
            mock.patch.object(botin, "_icono_de_ficha", return_value=imagen),
        ):
            self.assertEqual(
                botin.en_galeria(imagen, {"nuevo_local": {}}), "nuevo_local"
            )

    def test_casillas_detectadas_no_se_recortan_en_columnas_fijas(self):
        pantalla = np.zeros((960, 554, 3), np.uint8)
        with (
            mock.patch.object(
                botin, "_cajas_por_borde", return_value=[(102, 374), (103, 375)]
            ),
            mock.patch.object(botin, "_hay_objeto", return_value=True),
        ):
            self.assertEqual(botin.casillas(pantalla), [(102, 374)])

    def test_animacion_local_no_se_oculta_en_la_media_de_la_pantalla(self):
        antes = np.zeros((960, 554, 3), np.uint8)
        ahora = antes.copy()
        ahora[405:468, 85:148] = 60
        with mock.patch.object(botin, "casillas", return_value=[(85, 405)]):
            self.assertFalse(botin.quieta(antes, ahora))
            self.assertTrue(botin.quieta(ahora, ahora.copy()))

    def test_captura_inestable_no_se_interpreta_como_items(self):
        with mock.patch.object(botin, "analizar") as analizar:
            datos = recompensas._analizar(None, modo="pajaro_piso4", estable=False)
        analizar.assert_not_called()
        self.assertEqual(datos["objetos"], {})
        self.assertTrue(datos["captura_inestable"])

    def test_foto_semanal_inestable_conserva_su_contexto(self):
        carpeta = self.raiz / "fotos"
        with (
            mock.patch.object(recompensas, "CARPETA", carpeta),
            mock.patch.object(recompensas, "INDICE", carpeta / "indice.jsonl"),
        ):
            recompensas.guardar(
                np.zeros((940, 550, 3), np.uint8),
                modo="pajaro_piso4",
                nombre_modo="Pajaro",
                sesion=1,
                victoria=1,
                primera=True,
                estable=False,
            )
            registro = json.loads(
                (carpeta / "indice.jsonl").read_text().splitlines()[0]
            )
        self.assertTrue(registro["primera"])
        self.assertTrue(registro["captura_inestable"])
        self.assertEqual(registro["objetos"], {})

    def test_casilla_desconocida_permanece_en_foto_no_en_totales(self):
        pantalla = np.zeros((960, 554, 3), np.uint8)
        with (
            mock.patch.object(botin, "casillas", return_value=[(102, 374)]),
            mock.patch.object(botin, "leer_oro", return_value=None),
        ):
            datos = botin.analizar(pantalla)
        self.assertEqual(datos["objetos"], {})
        self.assertEqual(datos["pendientes"], [{"x": 102, "y": 374, "lado": 63}])
        self.assertTrue(datos["lectura_incompleta"])

    def test_premio_semanal_real_se_identifica_contra_la_galeria(self):
        pantalla = leer_imagen(Path(__file__).with_name("first_reward.png"))
        datos = botin.analizar_primera(pantalla, modo="perros_piso4")
        self.assertEqual(
            datos["objetos"],
            {"galeria_wind_source": 1, "galeria_magnificence_of_valhalla": 2},
        )
        self.assertEqual(datos["pendientes"], [])
        self.assertFalse(any(oid.startswith("objeto_") for oid in datos["objetos"]))


class MomentoDeCaptura(unittest.TestCase):
    def test_timeout_con_animacion_guarda_foto_pero_no_da_items_por_validos(self):
        from lumen.modos import perros_piso4 as P4

        m = P4.PerrosPiso4(
            {"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0}
        )
        reloj = [10.0]
        with (
            mock.patch.object(
                P4, "PRIMERA_RECOMPENSA", entorno.PlantillaFalsa("primera")
            ),
            mock.patch.object(P4.juego, "ok", entorno.PlantillaFalsa("ok")),
            mock.patch.object(m, "clic_si", return_value=False),
            mock.patch.object(m, "_volvio_a_pisos", return_value=False),
            mock.patch.object(P4.time, "time", side_effect=lambda: reloj[0]),
            mock.patch.object(botin, "quieta", return_value=False),
            mock.patch.object(m, "guardar_recompensa") as guardar,
        ):
            m.victoria({"ok"}, (0, 0))
            guardar.assert_not_called()
            reloj[0] = 17.0
            m.victoria({"ok"}, (0, 0))
            guardar.assert_called_once_with({"ok"}, 1, estable=False)

    def test_recompensa_semanal_espera_una_captura_quieta_antes_de_cerrar(self):
        from lumen.modos import perros_piso4 as P4

        m = P4.PerrosPiso4(
            {"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0}
        )
        with (
            mock.patch.object(
                P4, "PRIMERA_RECOMPENSA", entorno.PlantillaFalsa("primera")
            ),
            mock.patch.object(P4.time, "time", return_value=10.0),
            mock.patch.object(botin, "quieta_primera", side_effect=[False, True]),
            mock.patch.object(P4.entrada, "clic") as clic,
            mock.patch.object(m, "log"),
            mock.patch.object(m, "guardar_recompensa") as guardar,
        ):
            m.victoria({"primera"}, (0, 0))
            guardar.assert_not_called()
            clic.assert_not_called()
            m.victoria({"primera"}, (0, 0))
            guardar.assert_called_once_with({"primera"}, 1, primera=True, estable=True)
            clic.assert_called_once()
