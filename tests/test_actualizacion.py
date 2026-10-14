"""Pruebas del motor del actualizador, sin interfaz."""

import hashlib
import http.server
import json
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import main
from ytchat.core import actualizacion
from ytchat.core import instalador
from ytchat.core import paths


def _release(zip="App-2.3.0.zip", etiqueta="2.3.0", cuerpo="novedades",
             base="https://ejemplo.com/bajada"):
    return {
        "tag_name": etiqueta,
        "body": cuerpo,
        "assets": [
            {"name": zip, "browser_download_url": f"{base}/{zip}",
             "size": 10},
            {"name": zip + ".sha256",
             "browser_download_url": f"{base}/{zip}.sha256"},
        ],
    }


class TestVersiones(unittest.TestCase):

    def test_mayor_y_menor_por_componentes(self):
        self.assertEqual(
            actualizacion.version_como_tupla("2.10.0"),
            actualizacion.version_como_tupla("2.10.0"))
        self.assertTrue(actualizacion.hay_version_nueva("2.9.0", "2.10.0"))
        self.assertFalse(actualizacion.hay_version_nueva("2.10.0", "2.9.0"))
        self.assertFalse(actualizacion.hay_version_nueva("2.10.0", "2.10.0"))

    def test_prefijo_v_y_partes_que_faltan(self):
        self.assertEqual(actualizacion.version_como_tupla("v2.2.0"), (2, 2, 0))
        self.assertEqual(actualizacion.version_como_tupla("2.2"), (2, 2, 0))
        self.assertFalse(actualizacion.hay_version_nueva("v2.2.0", "2.2"))

    def test_texto_basura_da_none_y_nunca_hay_nueva(self):
        for basura in ("", "hola", "2.3-beta", "v", None, 42):
            with self.subTest(basura=basura):
                self.assertIsNone(actualizacion.version_como_tupla(basura))
                self.assertFalse(actualizacion.hay_version_nueva(basura, "2.3.0"))
                self.assertFalse(actualizacion.hay_version_nueva("2.3.0", basura))


class TestElegirPaquete(unittest.TestCase):

    def test_paquete_valido(self):
        elegido = actualizacion.elegir_paquete(_release())
        self.assertIsNotNone(elegido)
        self.assertEqual(elegido.version, "2.3.0")
        self.assertEqual(elegido.notas, "novedades")
        self.assertTrue(elegido.url_zip.endswith(".zip"))
        self.assertTrue(elegido.url_firma.endswith(".zip.sha256"))

    def test_sin_firma_no_hay_paquete(self):
        release = _release()
        release["assets"] = release["assets"][:1]
        self.assertIsNone(actualizacion.elegir_paquete(release))

    def test_nombre_con_puntos_por_espacios(self):
        # GitHub cambia los espacios de los activos por puntos.
        elegido = actualizacion.elegir_paquete(_release("Mi.App.2.3.0.zip"))
        self.assertIsNotNone(elegido)
        self.assertTrue(elegido.url_zip.endswith("Mi.App.2.3.0.zip"))

    def test_dos_zip_con_firma_es_ambiguo(self):
        release = _release()
        release["assets"].extend([
            {"name": "Otro-2.3.0.zip",
             "browser_download_url": "https://ejemplo.com/bajada/Otro-2.3.0.zip"},
            {"name": "Otro-2.3.0.zip.sha256",
             "browser_download_url": "https://ejemplo.com/bajada/Otro-2.3.0.zip.sha256"},
        ])
        self.assertIsNone(actualizacion.elegir_paquete(release))

    def test_url_http_no_vale(self):
        release = _release(base="http://ejemplo.com/bajada")
        self.assertIsNone(actualizacion.elegir_paquete(release))

    def test_body_vacio_o_ausente(self):
        for cuerpo in ("", None):
            with self.subTest(cuerpo=cuerpo):
                release = _release(cuerpo=cuerpo)
                elegido = actualizacion.elegir_paquete(release)
                self.assertIsNotNone(elegido)
                self.assertEqual(elegido.notas, "")


class TestLeerFirma(unittest.TestCase):

    def test_con_nombre_al_lado(self):
        firma = "ab12" * 16
        self.assertEqual(
            actualizacion.leer_firma(f"{firma}  App-2.3.0.zip\n"), firma)

    def test_sin_nombre_y_en_mayusculas(self):
        firma = "AB12" * 16
        self.assertEqual(actualizacion.leer_firma(firma + "\n"), firma.lower())

    def test_nombre_con_espacios_no_importa(self):
        firma = "cd34" * 16
        texto = f"{firma} *Mi App 2.3.0.zip\n"
        self.assertEqual(actualizacion.leer_firma(texto), firma)

    def test_basura_da_vacio(self):
        for texto in ("", "sin firma acá", "z" * 64, None):
            with self.subTest(texto=texto):
                self.assertEqual(actualizacion.leer_firma(texto), "")


def _hacer_zip(ruta: Path, entradas: dict) -> None:
    with zipfile.ZipFile(ruta, "w") as archivo:
        for nombre, contenido in entradas.items():
            archivo.writestr(nombre, contenido)


class TestExtraerPaquete(unittest.TestCase):

    def test_carpeta_unica_devuelve_esa(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _hacer_zip(tmp / "p.zip", {"app/App.exe": "exe",
                                       "app/leeme.txt": "hola"})
            raiz = actualizacion.extraer_paquete(tmp / "p.zip", tmp / "nueva")
            self.assertEqual(raiz, tmp / "nueva" / "app")
            self.assertTrue((raiz / "App.exe").is_file())

    def test_varias_carpetas_devuelve_destino(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _hacer_zip(tmp / "p.zip", {"a/uno.txt": "1", "b/dos.txt": "2"})
            raiz = actualizacion.extraer_paquete(tmp / "p.zip", tmp / "nueva")
            self.assertEqual(raiz, tmp / "nueva")

    def test_extrae_subcarpetas_con_contenido(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _hacer_zip(tmp / "p.zip", {
                "app/sounds/themes/default/a.wav": b"sonido nuevo",
                "app/sub/fondo.txt": "hola",
                "app/raiz.txt": "r",
            })
            raiz = actualizacion.extraer_paquete(tmp / "p.zip", tmp / "nueva")
            self.assertEqual(raiz, tmp / "nueva" / "app")
            self.assertEqual(
                (raiz / "sounds" / "themes" / "default" / "a.wav"
                 ).read_bytes(), b"sonido nuevo")
            self.assertEqual((raiz / "sub" / "fondo.txt").read_text(
                encoding="utf-8"), "hola")
            self.assertEqual((raiz / "raiz.txt").read_text(
                encoding="utf-8"), "r")

    def test_rechaza_puntos_y_absoluta_sin_dejar_nada_fuera(self):
        import tempfile
        for mala in ("../fuera.txt", "app/../../fuera.txt", "/absoluta.txt"):
            with self.subTest(mala=mala), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                _hacer_zip(tmp / "p.zip", {"app/bueno.txt": "ok",
                                           mala: "maldad"})
                with self.assertRaises(actualizacion.PaqueteInvalido):
                    actualizacion.extraer_paquete(tmp / "p.zip", tmp / "nueva")
                self.assertFalse((tmp / "fuera.txt").exists())
                self.assertFalse((tmp / "absoluta.txt").exists())
                # Nada a medio extraer adentro tampoco.
                dentro = list((tmp / "nueva").iterdir()) if (tmp / "nueva").exists() else []
                self.assertEqual(dentro, [])


class TestValidarPaquete(unittest.TestCase):

    def _paquete(self, base: Path, manifiesto: dict | None,
                 archivos: tuple = ("App.exe",)) -> Path:
        carpeta = base / "paquete"
        carpeta.mkdir()
        for nombre in archivos:
            (carpeta / nombre).write_bytes(b"exe")
        if manifiesto is not None:
            (carpeta / paths.NOMBRE_MANIFIESTO).write_text(
                json.dumps(manifiesto), encoding="utf-8")
        return carpeta

    def test_valido_devuelve_ejecutable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = self._paquete(
                Path(tmp), {"version": "2.3.0", "ejecutable": "App.exe"})
            self.assertEqual(
                actualizacion.validar_paquete(carpeta, "2.3.0"), "App.exe")

    def test_version_equivalente_con_menos_partes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = self._paquete(
                Path(tmp), {"version": "2.3", "ejecutable": "App.exe"})
            self.assertEqual(
                actualizacion.validar_paquete(carpeta, "2.3.0"), "App.exe")

    def test_casos_invalidos(self):
        import tempfile
        casos = {
            "sin manifiesto": (None, ("App.exe",), "2.3.0"),
            "versión distinta": ({"version": "2.4.0",
                                  "ejecutable": "App.exe"}, ("App.exe",), "2.3.0"),
            "ejecutable con barra": ({"version": "2.3.0",
                                      "ejecutable": "sub/App.exe"},
                                     ("App.exe",), "2.3.0"),
            "ejecutable inexistente": ({"version": "2.3.0",
                                        "ejecutable": "Otro.exe"},
                                       ("App.exe",), "2.3.0"),
        }
        for nombre, (manifiesto, archivos, esperada) in casos.items():
            with self.subTest(nombre), tempfile.TemporaryDirectory() as tmp:
                carpeta = self._paquete(Path(tmp), manifiesto, archivos)
                with self.assertRaises(actualizacion.PaqueteInvalido):
                    actualizacion.validar_paquete(carpeta, esperada)

    def test_paquete_con_data_no_vale(self):
        import tempfile
        for prohibido in ("data", "Descargas"):
            with self.subTest(prohibido=prohibido), tempfile.TemporaryDirectory() as tmp:
                carpeta = self._paquete(
                    Path(tmp), {"version": "2.3.0", "ejecutable": "App.exe"})
                (carpeta / prohibido).mkdir()
                with self.assertRaises(actualizacion.PaqueteInvalido):
                    actualizacion.validar_paquete(carpeta, "2.3.0")


class ServidorFirmas(http.server.BaseHTTPRequestHandler):
    contenido_zip = b""
    firma = ""

    def do_GET(self):
        if self.path == "/paquete.zip":
            cuerpo = type(self).contenido_zip
        elif self.path == "/paquete.zip.sha256":
            cuerpo = type(self).firma.encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


class TestDescargarPaquete(unittest.TestCase):

    def _servidor(self):
        servidor = http.server.HTTPServer(("127.0.0.1", 0), ServidorFirmas)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        # LIFO: primero se apaga el bucle y después se cierra el socket.
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor

    def _urls(self, servidor):
        base = f"http://127.0.0.1:{servidor.server_port}"
        return f"{base}/paquete.zip", f"{base}/paquete.zip.sha256"

    def test_firma_correcta(self):
        import tempfile
        ServidorFirmas.contenido_zip = b"zip de verdad"
        ServidorFirmas.firma = hashlib.sha256(b"zip de verdad").hexdigest()
        servidor = self._servidor()
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "paquete.zip"
            resultado = actualizacion.descargar_paquete(
                *self._urls(servidor), destino, permitir_http=True)
            self.assertTrue(resultado.correcta, resultado.motivo)
            self.assertEqual(destino.read_bytes(), b"zip de verdad")
            temporales = [p for p in Path(tmp).iterdir()
                           if p.name.startswith(".paquete-")]
            self.assertEqual(temporales, [])

    def test_firma_equivocada_no_deja_nada(self):
        import tempfile
        ServidorFirmas.contenido_zip = b"zip de verdad"
        ServidorFirmas.firma = "00" * 32
        servidor = self._servidor()
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "paquete.zip"
            resultado = actualizacion.descargar_paquete(
                *self._urls(servidor), destino, permitir_http=True)
            self.assertFalse(resultado.correcta)
            self.assertIn("firma", resultado.motivo.lower())
            self.assertFalse(destino.exists())
            temporales = [p for p in Path(tmp).iterdir()
                           if p.name.startswith(".paquete-")]
            self.assertEqual(temporales, [])

    def test_sin_firma(self):
        import tempfile
        ServidorFirmas.contenido_zip = b"zip de verdad"
        ServidorFirmas.firma = "sin firma acá"
        servidor = self._servidor()
        with tempfile.TemporaryDirectory() as tmp:
            resultado = actualizacion.descargar_paquete(
                *self._urls(servidor), Path(tmp) / "paquete.zip",
                permitir_http=True)
            self.assertFalse(resultado.correcta)
            self.assertFalse(Path(tmp, "paquete.zip").exists())

    def test_cancelacion(self):
        import tempfile
        ServidorFirmas.contenido_zip = b"zip de verdad"
        ServidorFirmas.firma = hashlib.sha256(b"zip de verdad").hexdigest()
        servidor = self._servidor()
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "paquete.zip"
            resultado = actualizacion.descargar_paquete(
                *self._urls(servidor), destino, cancelar=lambda: True,
                permitir_http=True)
            self.assertFalse(resultado.correcta)
            self.assertIn("cancelada", resultado.motivo.lower())
            self.assertFalse(destino.exists())
            temporales = [p for p in Path(tmp).iterdir()
                           if p.name.startswith(".paquete-")]
            self.assertEqual(temporales, [])

    def test_por_defecto_exige_https(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            resultado = actualizacion.descargar_paquete(
                "http://ejemplo.com/p.zip", "http://ejemplo.com/p.zip.sha256",
                Path(tmp) / "paquete.zip")
            self.assertFalse(resultado.correcta)
            self.assertIn("https", resultado.motivo.lower())


class TestEstado(unittest.TestCase):

    def test_confirmar_arranque(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (paths.carpeta_actualizacion_en(base)).mkdir(parents=True)
            paths.actualizacion_pendiente_en(base).write_text(
                json.dumps({"desde": "2.2.0", "hacia": "2.3.0"}),
                encoding="utf-8")
            actualizacion.confirmar_arranque("2.3.0", base)
            self.assertTrue(paths.arranque_confirmado_en(base).is_file())
            paths.arranque_confirmado_en(base).unlink()
            # Hacia otra versión: no hace nada.
            actualizacion.confirmar_arranque("9.9.9", base)
            self.assertFalse(paths.arranque_confirmado_en(base).exists())

    def test_confirmar_sin_pendiente_no_hace_nada(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            actualizacion.confirmar_arranque("2.3.0", Path(tmp))
            self.assertFalse(
                paths.arranque_confirmado_en(Path(tmp)).exists())

    def test_confirmar_nunca_lanza(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths.carpeta_actualizacion_en(base).mkdir(parents=True)
            # Pendiente corrupto: no debe levantar ni confirmar.
            paths.actualizacion_pendiente_en(base).write_text(
                "{basura", encoding="utf-8")
            actualizacion.confirmar_arranque("2.3.0", base)
            self.assertFalse(paths.arranque_confirmado_en(base).exists())

    def test_tomar_resultado(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths.carpeta_actualizacion_en(base).mkdir(parents=True)
            paths.resultado_actualizacion_en(base).write_text(
                json.dumps({"resultado": "ok", "desde": "2.2.0",
                            "hacia": "2.3.0"}), encoding="utf-8")
            paths.paquete_extraido_en(base).mkdir(parents=True)
            (paths.paquete_extraido_en(base) / "resto.txt").write_text(
                "x", encoding="utf-8")
            datos = actualizacion.tomar_resultado(base)
            self.assertEqual(datos["resultado"], "ok")
            self.assertFalse(
                paths.resultado_actualizacion_en(base).exists())
            self.assertFalse(paths.paquete_extraido_en(base).exists())

    def test_tomar_resultado_corrupto_devuelve_none_y_borra(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths.carpeta_actualizacion_en(base).mkdir(parents=True)
            paths.resultado_actualizacion_en(base).write_text(
                "{esto no es json", encoding="utf-8")
            self.assertIsNone(actualizacion.tomar_resultado(base))
            self.assertFalse(
                paths.resultado_actualizacion_en(base).exists())

    def test_carpeta_admite_escritura(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(actualizacion.carpeta_admite_escritura(tmp))
            self.assertFalse(actualizacion.carpeta_admite_escritura(
                Path(tmp) / "no-existe" / "tampoco"))


class TestRamaMain(unittest.TestCase):

    def test_modo_instalador_no_migra_ni_pide_mutex(self):
        argumentos = ["main.py", "--instalar-actualizacion", "inst", "1234",
                      "Viejo.exe", "2.1.0"]
        with mock.patch.object(main.sys, "argv", argumentos), \
                mock.patch.object(instalador, "principal_instalador",
                                  return_value=0) as principal, \
                mock.patch.object(main.migracion_datos, "migrar") as migrar, \
                mock.patch.object(main, "_verificar_instancia_unica") as mutex:
            with self.assertRaises(SystemExit) as salida:
                main.main()
        self.assertEqual(salida.exception.code, 0)
        principal.assert_called_once_with()
        migrar.assert_not_called()
        mutex.assert_not_called()

    def test_sin_argumento_no_es_instalador(self):
        class _Corte(Exception):
            pass
        with mock.patch.object(main.sys, "argv", ["main.py"]), \
                mock.patch.object(instalador, "principal_instalador") as principal, \
                mock.patch.object(main.migracion_datos, "migrar",
                                  return_value=None), \
                mock.patch.object(main, "configurar_logging",
                                  side_effect=_Corte):
            with self.assertRaises(_Corte):
                main.main()
        principal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
