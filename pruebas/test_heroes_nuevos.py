"""Heroes nuevos de 7dshub: calendario (un jueves de cada dos) y lo que se escribe en la base. Sin internet."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import yaml

import entorno  # noqa: F401
from lumen import heroes_nuevos as H

REPO = Path(__file__).resolve().parents[1]
JUEVES = date(2026, 11, 12)  # salio Cusack (7dshub)


def heroe(hid, nombre="Cusack", titulo="[The Prince's Master]", atributo=2, salida="2026-11-12"):
    return {"id": hid, "name": nombre, "nickname": titulo, "attribute": atributo,
            "release": {"gb": f"{salida}T00:00:00", "jpkr": f"{salida}T00:00:00"}}


def detalle_falso():
    skill = lambda i, n, t: {"id": i, "name": f'"{n}"', "explain": t}
    return {"skillsA": [skill(1, "Golpe", "Inflicts damage equal to [FFAE00]200%[-] of Attack on [FFFFFF]one enemy[-].")] * 3,
            "skillsB": [skill(2, "Barrido", "Inflicts damage on [FFFFFF]all enemies[-].")] * 3,
            "skillsSpecial": [skill(3, "Final", "Inflicts damage on all enemies.\\nWow.")],
            "passive": {"name": "Pasiva", "indexes": [{"explain": "Algo"}]},
            "ability": {"name": "Talento", "indexes": [{"explain": "Otro"}]},
            "crafts": [], "age": "Unknown", "voice": "Alguien"}


def bajar_falso(url):
    if "/api/hero/" in url:
        return json.dumps(detalle_falso()).encode()
    if "/api/hero" in url:
        return json.dumps([heroe(999001)]).encode()
    img = np.full((140, 100, 3), 120, np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()


class Calendario(unittest.TestCase):
    def test_nunca_revisado_toca_ya(self):
        self.assertTrue(H.toca_revisar(date(2026, 11, 13), {}))

    def test_el_jueves_de_descanso_no_mira(self):
        estado = {"ultimo_estreno": "2026-11-12", "revisado": "2026-11-12"}
        self.assertFalse(H.toca_revisar(date(2026, 11, 19), estado))
        self.assertEqual(H.proxima_revision(estado), date(2026, 11, 26))

    def test_el_jueves_que_toca_mira_una_vez_al_dia_hasta_que_salga(self):
        estado = {"ultimo_estreno": "2026-11-12", "revisado": "2026-11-20"}
        self.assertTrue(H.toca_revisar(date(2026, 11, 26), estado))
        estado["revisado"] = "2026-11-26"
        self.assertFalse(H.toca_revisar(date(2026, 11, 26), estado), "una sola vez al dia")
        self.assertTrue(H.toca_revisar(date(2026, 11, 27), estado), "7dshub aun no lo tenia: al dia siguiente")

    def test_heroes_que_aun_no_salen_no_cuentan(self):
        lista = [heroe(1), heroe(2, salida="2026-12-10")]
        self.assertEqual([h["id"] for h in H.faltan(lista, {}, JUEVES)], [1])
        self.assertEqual(H.ultimo_estreno(lista, JUEVES), JUEVES)
        self.assertEqual(H.faltan(lista, {"cusack_verde": 1}, JUEVES), [])


class Preparar(unittest.TestCase):
    def setUp(self):
        self.copia = Path(tempfile.mkdtemp())
        for ruta in (H.PERSONAJES, H.FUENTE, H.FICHAS, H.HABILIDADES):
            (self.copia / ruta).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / ruta, self.copia / ruta)

    def tearDown(self):
        shutil.rmtree(self.copia, ignore_errors=True)

    def test_agrega_el_heroe_con_ficha_cartas_e_icono(self):
        hechos = H.preparar(self.copia, [heroe(999001)], JUEVES, bajar_falso)
        self.assertEqual(hechos, ["[The Prince's Master] Cusack"])
        base = yaml.safe_load((self.copia / H.PERSONAJES).read_text(encoding="utf-8"))
        pid = "cusack_verde" if "cusack_verde" not in yaml.safe_load((REPO / H.PERSONAJES).read_text(encoding="utf-8")) else None
        pid = pid or next(k for k, v in yaml.safe_load((self.copia / H.FUENTE).read_text(encoding="utf-8")).items() if v == 999001)
        self.assertEqual(base[pid]["color"], "verde")
        self.assertEqual(base[pid]["cartas"]["skill_1"]["descripcion"], "Un objetivo (Golpe)")
        self.assertEqual(base[pid]["cartas"]["skill_2"]["descripcion"], "Área (Barrido)")
        fuente = yaml.safe_load((self.copia / H.FUENTE).read_text(encoding="utf-8"))
        self.assertEqual(fuente[pid], 999001)
        self.assertTrue((self.copia / H.FUENTE).read_text(encoding="utf-8").startswith("# Cada heroe"))
        fichas = yaml.safe_load((self.copia / H.FICHAS).read_text(encoding="utf-8"))
        self.assertEqual(len(fichas[pid]["skill_1"]["rangos"]), 3)
        self.assertEqual(fichas[pid]["perfil"], {"voz": "Alguien"})
        habilidades = yaml.safe_load((self.copia / H.HABILIDADES).read_text(encoding="utf-8"))
        self.assertIn("golpe", habilidades)
        for nombre in ("icono_hub.png", "skill_1_hub.png", "skill_2_hub.png", "ulti_hub.png"):
            self.assertTrue((self.copia / H.IMAGENES / pid / nombre).is_file(), nombre)
        carta = cv2.imread(str(self.copia / H.IMAGENES / pid / "skill_1_hub.png"))
        self.assertEqual(carta.shape[:2], (74, 45), "recortada como en la mano")

    def test_un_banner_con_varios_heroes_los_trae_todos(self):
        """El usuario, 2026-11-13: a veces llegan 2 personajes en el mismo banner."""
        dos = [heroe(999001), heroe(999002, nombre="Otra", titulo="[Banner]", atributo=1)]
        hechos = H.preparar(self.copia, dos, JUEVES, bajar_falso)
        self.assertEqual(len(hechos), 2)
        fuente = yaml.safe_load((self.copia / H.FUENTE).read_text(encoding="utf-8"))
        self.assertTrue({999001, 999002} <= set(fuente.values()))
        base = yaml.safe_load((self.copia / H.PERSONAJES).read_text(encoding="utf-8"))
        nuevos = [pid for pid, hid in fuente.items() if hid in (999001, 999002)]
        self.assertEqual({base[p]["estreno"] for p in nuevos}, {"2026-11-12"})

    def test_no_repite_lo_que_otro_pc_ya_publico(self):
        H.preparar(self.copia, [heroe(999001)], JUEVES, bajar_falso)
        self.assertEqual(H.preparar(self.copia, [heroe(999001)], JUEVES, bajar_falso), [])

    def test_no_cambia_los_heroes_que_ya_estaban(self):
        antes = yaml.safe_load((REPO / H.HABILIDADES).read_text(encoding="utf-8"))
        H.preparar(self.copia, [heroe(999001)], JUEVES, bajar_falso)
        despues = yaml.safe_load((self.copia / H.HABILIDADES).read_text(encoding="utf-8"))
        self.assertEqual({k: despues[k] for k in antes}, antes)
        self.assertEqual(yaml.safe_load((REPO / H.FUENTE).read_text(encoding="utf-8")).items()
                         - yaml.safe_load((self.copia / H.FUENTE).read_text(encoding="utf-8")).items(), set())


class Revisar(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.estado = self.carpeta / "estado.json"

    def tearDown(self):
        shutil.rmtree(self.carpeta, ignore_errors=True)

    def test_si_no_toca_no_visita_7dshub(self):
        H.guardar_estado({"ultimo_estreno": "2026-11-12", "revisado": "2026-11-13"}, self.estado)
        def prohibido(url):
            raise AssertionError("no debe visitar 7dshub")
        r = H.revisar(REPO, lambda f: [], hoy=date(2026, 11, 19), bajar=prohibido, archivo_estado=self.estado)
        self.assertFalse(r.revisado)
        self.assertEqual(r.proxima, date(2026, 11, 26))

    def test_con_el_boton_mira_aunque_no_toque_y_publica(self):
        H.guardar_estado({"ultimo_estreno": "2026-11-12", "revisado": "2026-11-13"}, self.estado)
        subidas = []
        def subir(preparar_copia):
            subidas.append(preparar_copia)
            return ["[X] Nuevo"]
        r = H.revisar(REPO, subir, hoy=date(2026, 11, 19), forzar=True, bajar=bajar_falso, archivo_estado=self.estado)
        self.assertEqual(r.nuevos, ["[X] Nuevo"])
        self.assertEqual(len(subidas), 1)
        self.assertEqual(H.leer_estado(self.estado)["revisado"], "2026-11-19")

    def test_sin_nada_nuevo_no_usa_git(self):
        lista = [heroe(hid) for hid in yaml.safe_load((REPO / H.FUENTE).read_text(encoding="utf-8")).values()]
        bajar = lambda url: json.dumps(lista).encode()
        def subir(_):
            raise AssertionError("no debe publicar nada")
        r = H.revisar(REPO, subir, hoy=JUEVES, bajar=bajar, archivo_estado=self.estado)
        self.assertTrue(r.revisado)
        self.assertEqual(H.leer_estado(self.estado)["ultimo_estreno"], "2026-11-12")


class AvisoInicio(unittest.TestCase):
    """Heroes nuevos en Inicio hasta que el jugador dice si los tiene (el usuario, 2026-11-13)."""

    def setUp(self):
        from unittest import mock
        from lumen import personajes as P
        self.P = P
        self.carpeta = Path(tempfile.mkdtemp())
        self.parches = [mock.patch.object(P, "USUARIO", self.carpeta / "usuario.yaml"),
                        mock.patch.object(P, "CARPETA", self.carpeta)]
        for parche in self.parches:
            parche.start()

    def tearDown(self):
        for parche in self.parches:
            parche.stop()
        shutil.rmtree(self.carpeta, ignore_errors=True)

    def test_cusack_sale_hasta_que_se_responde(self):
        pid = "highest_ranking_demon_cusack_verde"
        self.assertIn(pid, self.P.nuevos_sin_responder(date(2026, 11, 13)))
        self.P.marcar_tengo(pid, False)
        self.assertNotIn(pid, self.P.nuevos_sin_responder(date(2026, 11, 13)), "tambien con 'no lo tengo'")
        self.assertFalse(self.P.cargar()[pid].tengo)

    def test_los_viejos_y_los_de_hace_meses_no_salen(self):
        self.assertEqual(self.P.nuevos_sin_responder(date(2027, 3, 1)), [])
        self.assertNotIn("eren_jaeger_verde", self.P.nuevos_sin_responder(date(2026, 11, 13)))

    def test_panel_se_va_al_responder(self):
        from PyQt5.QtWidgets import QApplication, QPushButton
        from unittest import mock
        from lumen.gui import heroes_nuevos as G
        app = QApplication.instance() or QApplication([])
        with mock.patch.object(self.P, "nuevos_sin_responder", side_effect=lambda: [
                p for p in ["highest_ranking_demon_cusack_verde"]
                if "tengo" not in (self.P._leer_yaml(self.P.USUARIO).get(p) or {})]):
            panel = G.PanelHeroesNuevos()
            self.assertFalse(panel.isHidden())
            si = next(b for b in panel.findChildren(QPushButton) if b.text() == "Lo tengo")
            si.click()
            app.processEvents()
            self.assertTrue(panel.isHidden())
        self.assertTrue(self.P.cargar()["highest_ranking_demon_cusack_verde"].tengo)


if __name__ == "__main__":
    unittest.main()
