"""Fallos de disco y de instalacion, siempre en carpetas/repositorios temporales."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401
from lumen import archivos, actualizador


class EscrituraAtomica(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.ruta = self.raiz / "config.yaml"
        self.ruta.write_text("valor: anterior\n", encoding="utf-8")

    def test_guarda_completo_y_respalda(self):
        archivos.escribir_texto(self.ruta, "valor: español\n")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "valor: español\n")
        self.assertEqual(
            self.ruta.with_name("config.yaml.bak").read_text(), "valor: anterior\n"
        )
        self.assertEqual(list(self.raiz.glob("*.tmp")), [])

    def test_reemplazo_fallido_conserva_anterior(self):
        reemplazar = archivos.os.replace

        def fallo(origen, destino):
            if destino == self.ruta:
                raise PermissionError("archivo bloqueado")
            return reemplazar(origen, destino)

        with mock.patch.object(archivos.os, "replace", side_effect=fallo):
            with self.assertRaises(PermissionError):
                archivos.escribir_texto(self.ruta, "valor: nuevo\n")
        self.assertEqual(self.ruta.read_text(), "valor: anterior\n")
        self.assertEqual(list(self.raiz.glob("*.tmp")), [])

    def test_fsync_fallido_no_toca_destino(self):
        with mock.patch.object(
            archivos.os, "fsync", side_effect=OSError("disco lleno")
        ):
            with self.assertRaises(OSError):
                archivos.escribir_texto(self.ruta, "nuevo", respaldo=False)
        self.assertEqual(self.ruta.read_text(), "valor: anterior\n")
        self.assertEqual(list(self.raiz.glob("*.tmp")), [])

    def test_respaldo_fallido_no_toca_destino(self):
        with mock.patch.object(
            archivos.os, "replace", side_effect=OSError("disco lleno")
        ):
            with self.assertRaises(OSError):
                archivos.escribir_texto(self.ruta, "nuevo")
        self.assertEqual(self.ruta.read_text(), "valor: anterior\n")

    def test_primera_escritura_crea_carpeta(self):
        ruta = self.raiz / "nueva" / "archivo.json"
        archivos.escribir_texto(ruta, "{}")
        self.assertEqual(ruta.read_text(), "{}")
        self.assertFalse(ruta.with_name(ruta.name + ".bak").exists())

    def test_config_no_cambia_memoria_si_falla_disco(self):
        # La suite sustituye config.guardar: cargar otra instancia evita alterar sus mocks globales.
        from lumen import config

        spec = importlib.util.spec_from_file_location("config_prueba", config.__file__)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        modulo._datos = {"valor": "anterior"}
        with (
            mock.patch.object(modulo, "CONFIG", self.ruta),
            mock.patch.object(modulo, "escribir_texto", side_effect=OSError()),
        ):
            with self.assertRaises(OSError):
                modulo.guardar({"valor": "nuevo"})
        self.assertEqual(modulo._datos, {"valor": "anterior"})


class ActualizacionRecuperable(unittest.TestCase):
    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.repo = Path(self.temporal.name)
        self.git("init", "-b", "master")
        self.git("config", "user.name", "prueba")
        self.git("config", "user.email", "prueba@example.invalid")
        (self.repo / "lumen").mkdir()
        (self.repo / "lumen/__init__.py").write_text('__version__ = "1.0.0"\n')
        (self.repo / "requirements.txt").write_text("paquete==1\n")
        (self.repo / "editado.txt").write_text("base\n\n")
        (self.repo / "borrado.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-m", "anterior")
        self.anterior = self.git("rev-parse", "HEAD")
        (self.repo / "lumen/__init__.py").write_text('__version__ = "1.0.1"\n')
        (self.repo / "requirements.txt").write_text("paquete==2\n")
        self.git("add", ".")
        self.git("commit", "-m", "nueva")
        self.destino = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/master", self.destino)
        self.git("reset", "--hard", self.anterior)
        self.logs = self.repo / "logs"
        self.original_git = actualizador._git

        def sin_red(*args, **kwargs):
            if args[0] == "fetch":
                return ""
            return self.original_git(*args, **kwargs)

        for parche in (
            mock.patch.object(actualizador, "RAIZ", self.repo),
            mock.patch.object(actualizador, "LOGS", self.logs),
            mock.patch.object(actualizador, "_git", side_effect=sin_red),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def test_exito_descarga_antes_de_cambiar_codigo(self):
        commits = []
        with mock.patch.object(
            actualizador,
            "_pip",
            side_effect=lambda *a: commits.append(
                (a[0], self.git("rev-parse", "HEAD"))
            ),
        ):
            texto = actualizador.actualizar()
        self.assertEqual(
            commits, [("download", self.anterior), ("install", self.destino)]
        )
        self.assertIn("1.0.1", texto)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.destino)

    def test_descarga_fallida_no_toca_codigo(self):
        with mock.patch.object(
            actualizador, "_pip", side_effect=actualizador.ErrorActualizacion("sin red")
        ):
            with self.assertRaises(actualizador.ErrorActualizacion):
                actualizador.actualizar()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.anterior)

    def test_instalacion_fallida_recupera_codigo_ediciones_y_indice(self):
        (self.repo / "editado.txt").write_text("preparado\n\n")
        self.git("add", "editado.txt")
        (self.repo / "editado.txt").write_text("sin preparar\n\n")
        (self.repo / "borrado.txt").unlink()
        antes = self.git("status", "--porcelain", "--untracked-files=no")
        with mock.patch.object(
            actualizador,
            "_pip",
            side_effect=[None, actualizador.ErrorActualizacion("fallo"), None],
        ):
            with self.assertRaisesRegex(
                actualizador.ErrorActualizacion, "se recuperaron"
            ):
                actualizador.actualizar()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.anterior)
        self.assertEqual((self.repo / "editado.txt").read_text(), "sin preparar\n\n")
        self.assertFalse((self.repo / "borrado.txt").exists())
        self.assertEqual(self.git("show", ":editado.txt"), "preparado")
        self.assertEqual(
            self.git("status", "--porcelain", "--untracked-files=no"), antes
        )

    def test_reparacion_dependencias_fallida_se_explica(self):
        with mock.patch.object(
            actualizador,
            "_pip",
            side_effect=[
                None,
                actualizador.ErrorActualizacion("fallo"),
                actualizador.ErrorActualizacion("sin red"),
            ],
        ):
            with self.assertRaisesRegex(
                actualizador.ErrorActualizacion, "ejecuta Instalar.bat"
            ):
                actualizador.actualizar()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.anterior)

    def test_timeout_pip(self):
        with mock.patch.object(
            actualizador.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("pip", 300),
        ) as ejecutar:
            with self.assertRaises(actualizador.ErrorActualizacion):
                actualizador._pip("install", "-r", "requirements.txt")
        self.assertEqual(ejecutar.call_args.kwargs["timeout"], 300)

    def test_no_reemplaza_archivo_sin_seguimiento(self):
        self.git("reset", "--hard", self.destino)
        (self.repo / "nuevo.txt").write_text("remoto")
        self.git("add", "nuevo.txt")
        self.git("commit", "-m", "agrega archivo")
        self.git("update-ref", "refs/remotes/origin/master", "HEAD")
        self.git("reset", "--hard", self.anterior)
        (self.repo / "nuevo.txt").write_text("mio")
        with self.assertRaisesRegex(actualizador.ErrorActualizacion, "sin seguimiento"):
            actualizador.actualizar()
        self.assertEqual((self.repo / "nuevo.txt").read_text(), "mio")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.anterior)

    def test_requisitos_iguales_no_ejecuta_pip(self):
        self.git("reset", "--hard", self.destino)
        (self.repo / "requirements.txt").write_text("paquete==1\n")
        self.git("add", "requirements.txt")
        self.git("commit", "-m", "mismos requisitos")
        destino = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/master", destino)
        self.git("reset", "--hard", self.anterior)
        with mock.patch.object(actualizador, "_pip") as pip:
            actualizador.actualizar()
        pip.assert_not_called()
        self.assertEqual(self.git("rev-parse", "HEAD"), destino)

    def test_version_invalida_se_rechaza_antes_de_aplicar(self):
        self.git("reset", "--hard", self.destino)
        (self.repo / "lumen/__init__.py").write_text(
            '__version__ = "1.0.2"\nesto no es python\n'
        )
        self.git("add", ".")
        self.git("commit", "-m", "version rota")
        self.git("update-ref", "refs/remotes/origin/master", "HEAD")
        self.git("reset", "--hard", self.anterior)
        with mock.patch.object(actualizador, "_pip") as pip:
            with self.assertRaisesRegex(
                actualizador.ErrorActualizacion, "no es valido"
            ):
                actualizador.actualizar()
        pip.assert_not_called()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.anterior)

    def test_actualizacion_simultanea_rechazada(self):
        with actualizador._lock_update:
            with self.assertRaisesRegex(actualizador.ErrorActualizacion, "en curso"):
                actualizador.actualizar()


if __name__ == "__main__":
    unittest.main()
