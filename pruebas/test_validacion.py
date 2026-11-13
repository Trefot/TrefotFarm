"""Evidencias visuales y evaluacion offline sin entrenar ni ejecutar el juego."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import entorno  # noqa: F401
import numpy as np
import lumen
from lumen import admin, juego, inteligencia
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import estado, evaluacion as E, equipos as T, perfiles, aprendizaje as A
from lumen.ia.efectos import Efecto, Mecanica

EQUIPO = ["a", "b", "c", "d"]


class Validacion(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.object(admin, "activo", return_value=True)
        parche.start()
        self.addCleanup(parche.stop)

    def pelea(self, **extra):
        return dict(
            destino="ciervo_piso4",
            equipo=EQUIPO,
            resultado="victoria",
            duracion=100,
            version=lumen.__version__,
            origen="juego",
            config=dict(A.DEFECTO),
            conocimiento=perfiles.firma_conocimiento(),
            turnos=[{"confirmada": True}],
            **extra,
        )

    def test_revision_del_motor_cambia_huella_de_memoria(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            for nombre in (
                "personajes.yaml",
                "habilidades.yaml",
                "fichas.yaml",
                "jefes.yaml",
                "conocimiento.yaml",
            ):
                ruta = raiz / "lumen" / "datos" / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text("{}")
            for nombre in (
                "inteligencia.py",
                "valor_cartas.py",
                "ia/decidir.py",
                "ia/resolver.py",
                "ia/efectos.py",
                "ia/estado.py",
                "modos/bestias_piso4.py",
                "modos/perros_piso4.py",
            ):
                ruta = raiz / "lumen" / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text("# base")
            try:
                with mock.patch.object(perfiles, "RAIZ", raiz):
                    perfiles.firma_conocimiento.cache_clear()
                    antes = perfiles.firma_conocimiento()
                    for nombre in ("inteligencia.py", "modos/bestias_piso4.py", "modos/perros_piso4.py", "ia/resolver.py"):
                        (raiz / "lumen" / nombre).write_text("# motor nuevo")
                        perfiles.firma_conocimiento.cache_clear()
                        despues = perfiles.firma_conocimiento()
                        self.assertNotEqual(antes, despues)
                        antes = despues
            finally:
                perfiles.firma_conocimiento.cache_clear()

    def test_intervalos_muestra_pequena_no_da_certeza(self):
        bajo, alto = E.intervalo(1, 1)
        self.assertLess(bajo, 0.5)
        self.assertEqual(alto, 1)
        self.assertEqual(E.intervalo(0, 0), (0, 1))

    def test_no_mezcla_versiones_simulaciones_o_configuraciones(self):
        p = self.pelea()
        filas = [
            p,
            {**p, "origen": "simulacion"},
            {**p, "version": "anterior"},
            {**p, "config": {**A.DEFECTO, "valor_ulti": 5.0}},
        ]
        informe = E.analizar(filas, "ciervo_piso4", EQUIPO)
        self.assertEqual(len(informe["grupos"]), 4)
        self.assertEqual(sum(g["peleas"] for g in informe["grupos"]), 4)
        self.assertIn("simulacion", E.texto(informe))

    def test_filtra_equipo_destino_y_detecta_intentos(self):
        p = self.pelea()
        filas = [
            {**p, "turnos": [{"confirmada": True}, {"confirmada": False}]},
            {**p, "equipo": ["a", "b", "c", "e"]},
            {**p, "destino": "otro"},
        ]
        r = E.analizar(filas, "ciervo_piso4", EQUIPO)
        self.assertEqual(r["seleccionadas"], 1)
        self.assertEqual(r["problemas"]["intentos_sin_confirmar"], 1)

    def test_duracion_y_turnos_invalidos_no_producen_metricas(self):
        p = self.pelea()
        for datos in (
            {**p, "duracion": 0},
            {**p, "duracion": float("nan")},
            {**p, "turnos": None},
        ):
            self.assertEqual(E.analizar([datos], "ciervo_piso4", EQUIPO)["grupos"], [])

    def test_datos_antiguos_o_sin_confirmar_se_etiquetan(self):
        p = {**self.pelea(), "conocimiento": "anterior", "turnos": []}
        r = E.analizar([p], "ciervo_piso4", EQUIPO)
        self.assertFalse(r["grupos"][0]["fiable"])
        self.assertEqual(r["problemas"]["sin_acciones_confirmadas"], 1)

    def test_archivo_invalido_se_cuenta_sin_entrenar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "diario.jsonl"
            ruta.write_text(json.dumps(self.pelea()) + "\nroto\n[]\n", encoding="utf-8")
            with mock.patch.object(perfiles, "aprender") as aprender:
                filas, fallos = E.leer_archivo(ruta)
            self.assertEqual((len(filas), fallos), (1, 2))
            aprender.assert_not_called()

    def test_limite_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "diario.jsonl"
            ruta.write_bytes(b"x" * 20)
            with mock.patch.object(E, "MAX_BYTES", 10):
                with self.assertRaises(ValueError):
                    E.leer_archivo(ruta)

    def test_evaluacion_requiere_llave(self):
        with mock.patch.object(admin, "activo", return_value=False):
            with self.assertRaises(PermissionError):
                E.analizar([], "ciervo_piso4", EQUIPO)
            with self.assertRaises(PermissionError):
                E.leer_archivo(Path("x"))
            with self.assertRaises(PermissionError):
                T.recomendar("x", {}, {}, [])

    def test_ranking_prioriza_disponibilidad_sin_inventar_mediciones(self):
        biblioteca = {h: SimpleNamespace(tengo=True) for h in EQUIPO}
        catalogo = {
            "ciervo_piso4": [
                {"nombre": "Posible", "bot": True, "personajes": EQUIPO},
                {
                    "nombre": "Falta heroe",
                    "bot": True,
                    "personajes": ["a", "b", "c", "e"],
                    "minutos": 0.1,
                },
            ]
        }
        ranking = T.recomendar("ciervo_piso4", biblioteca, catalogo, [])
        self.assertEqual(ranking[0]["nombre"], "Posible")
        self.assertFalse(ranking[0]["medido"])
        self.assertIsNone(ranking[0]["por_hora"])
        self.assertEqual(ranking[1]["faltan"], ["e"])

    def test_ranking_no_cuenta_demos_ni_versiones_anteriores(self):
        biblioteca = {h: SimpleNamespace(tengo=True) for h in EQUIPO}
        catalogo = {
            "ciervo_piso4": [{"nombre": "A", "bot": True, "personajes": EQUIPO}]
        }
        p = self.pelea()
        filas = (
            [p] * 5
            + [{**p, "origen": "simulacion", "duracion": 1}] * 20
            + [{**p, "version": "antigua"}] * 20
        )
        r = T.recomendar("ciervo_piso4", biblioteca, catalogo, filas)[0]
        self.assertEqual(r["peleas"], 5)
        self.assertTrue(r["medido"])
        self.assertEqual(r["por_hora"], 36)

    def test_equipo_fijo_respeta_orden_del_guion(self):
        from lumen.modos import MODOS

        ids = list(MODOS["perros_piso4"].equipo.orden)
        biblioteca = {h: SimpleNamespace(tengo=True) for h in ids}
        catalogo = {
            "perros_piso4": [
                {"nombre": "Bien", "bot": True, "personajes": ids},
                {
                    "nombre": "Otro orden",
                    "bot": True,
                    "personajes": list(reversed(ids)),
                },
            ]
        }
        r = T.recomendar("perros_piso4", biblioteca, catalogo, [])
        self.assertTrue(r[0]["compatible"])
        self.assertFalse(r[1]["compatible"])

    def test_modulo_cerrado_no_se_declara_compatible(self):
        biblioteca = {h: SimpleNamespace(tengo=True) for h in EQUIPO}
        r = T.recomendar(
            "rata_f1",
            biblioteca,
            {"rata": [{"nombre": "A", "bot": True, "personajes": EQUIPO}]},
            [],
        )
        self.assertFalse(r[0]["compatible"])


class Observacion(unittest.TestCase):
    def test_no_inventa_vida_orbes_ni_ausencias(self):
        r = estado.observar(None)
        self.assertEqual(r["senales"], {})
        self.assertIsNone(r["vida"])
        self.assertIsNone(r["orbes"])
        self.assertEqual(estado.mecanicas(r), [])

    def test_detecta_plantilla_real_solo_en_region_superior(self):
        imagen = np.zeros((940, 550, 3), dtype=np.uint8)
        icono = juego.evasion.imagenes[0]
        h, w = icono.shape[:2]
        imagen[200 : 200 + h, 100 : 100 + w] = icono
        r = estado.observar(imagen)
        self.assertIn("evasion", r["senales"])
        self.assertEqual(r["senales"]["evasion"]["rect"][:2], [100, 200])
        otra = np.zeros_like(imagen)
        otra[800 : 800 + h, 100 : 100 + w] = icono
        self.assertNotIn("evasion", estado.observar(otra)["senales"])

    def test_inmortalidad_no_inventa_contramedida(self):
        r = {"senales": {"inmortalidad": {"confianza": 0.99}}}
        self.assertEqual(estado.mecanicas(r)[0].contra, ())
        self.assertEqual(
            estado.mecanicas({"senales": {"evasion": {"confianza": 0.3}}}), []
        )

    def test_icono_en_contexto_desconocido_no_cambia_politica(self):
        r = {"senales": {"evasion": {"confianza": 0.99}}}
        self.assertEqual(estado.mecanicas(r, "indura_chaos", 1), [])
        self.assertEqual(estado.mecanicas(r, "pajaro_piso4", 1), [])
        self.assertTrue(estado.mecanicas(r, "pajaro_piso4", 4))

    def test_observacion_ajusta_decision_real_sin_duplicar_mecanicas(self):
        j = inteligencia.Jugador()
        j.destino, j.fase = "pajaro_piso4", 4
        j._indice = mock.Mock()
        j._tasador = mock.Mock(valores=lambda nombres: {n: 1 for n in nombres})
        j._lector = mock.Mock(
            efectos_de=lambda n: (
                [Efecto("ignora_evasion")] if n == "a.ignora" else [Efecto("dano")]
            ),
            color_de=lambda n: None,
        )
        mano = [
            Carta(0, tipo=TipoCarta.NORMAL, rango=Rango.BRONCE, nombre="a.ignora"),
            Carta(1, tipo=TipoCarta.NORMAL, rango=Rango.BRONCE, nombre="b.dano"),
        ]
        with mock.patch.object(inteligencia, "agrupar_por_dibujo"):
            self.assertEqual(j.elegir(mano, 1), ("jugar", 1))
            j.observacion = {"senales": {"evasion": {"confianza": 0.99}}}
            self.assertEqual(j.elegir(mano, 1), ("jugar", 0))
            j.mecanicas = [Mecanica("evasion")]
            self.assertEqual(j.elegir(mano, 1), ("jugar", 0))
            self.assertEqual(j.razones["a.ignora"], ["ignora la evasión"])


if __name__ == "__main__":
    unittest.main()
