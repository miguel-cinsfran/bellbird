"""Pruebas del catálogo reducido de modelos de IA y su descarga."""

import contextlib
import datetime
import http.server
import io
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from scripts import actualizar_catalogo_ia
from bellbird.ai import catalogo
from bellbird.ai import protocolos

OPENCODE_NPM = "@ai-sdk/openai-compatible"
OPENCODE_API = "https://opencode.ai/inference/go/openai/v1"
FECHA = "2026-10-21"


def _modelo(ident, nombre, entradas=("text", "image"), npm=None, api=None,
            costo=(0, 0), piensa=True, tope=1024, estado=None,
            salidas=("text",)):
    datos = {"id": ident, "name": nombre, "reasoning": piensa,
             "modalities": {"input": list(entradas),
                            "output": list(salidas)},
             "provider": {}}
    if npm is not None:
        datos["provider"]["npm"] = npm
    if api is not None:
        datos["provider"]["api"] = api
    if costo is not None:
        datos["cost"] = {"input": costo[0], "output": costo[1]}
    if tope is not None:
        datos["limit"] = {"context": 100000, "output": tope}
    if estado is not None:
        datos["status"] = estado
    return datos


def _modelos_opencode():
    return {
        "minimax-m3.1-flash-free": _modelo(
            "minimax-m3.1-flash-free", "MiniMax M3.1 Flash Free",
            entradas=("text", "image", "video"),
            api=OPENCODE_API, costo=(0, 0), tope=512000),
        "claude-haiku-5-5": _modelo(
            "claude-haiku-5-5", "Claude Haiku 5.5",
            entradas=("text", "image", "pdf"), npm="@ai-sdk/anthropic",
            api="https://opencode.ai/inference/go/anthropic/v1",
            costo=(0.1, 0.5), tope=128000),
        "gemini-4-argon-contributor": _modelo(
            "gemini-4-argon-contributor", "Gemini 4 Argon Contributor",
            entradas=("text", "image", "video", "audio", "pdf"),
            npm="@ai-sdk/google",
            api="https://opencode.ai/inference/go/google/v1beta",
            costo=(4, 20), tope=65536),
        "muse-spark-1.3-contributor": _modelo(
            "muse-spark-1.3-contributor", "Muse Spark 1.3 Contributor",
            npm="@ai-sdk/openai",
            api="https://opencode.ai/inference/go/openai/v1",
            costo=(0.1, 0.2), tope=64000),
        "step-5-preview-free": _modelo(
            "step-5-preview-free", "Step 5 Preview Free",
            api=OPENCODE_API, costo=(0, 0), estado="deprecated"),
        "longcat-2.0": _modelo("longcat-2.0", "Longcat 2.0",
                               entradas=("text",), api=OPENCODE_API,
                               costo=(0, 0)),
        "raro-1": _modelo("raro-1", "Raro Uno", npm="@ai-sdk/inventado",
                          api=OPENCODE_API, costo=(0, 0)),
        "sin-costo-1": _modelo("sin-costo-1", "Sin Costo Uno",
                               api=OPENCODE_API, costo=None, tope=None),
    }


def _muestra():
    return {
        "opencode-go": {
            "id": "opencode-go", "name": "OpenCode Go",
            "npm": OPENCODE_NPM, "api": OPENCODE_API,
            "models": _modelos_opencode()},
        "google": {
            "id": "google", "name": "Google", "npm": "@ai-sdk/google",
            "models": {
                "gemini-directo-1": _modelo(
                    "gemini-directo-1", "Gemini Directo Uno",
                    costo=(0, 0), tope=8192)}},
        "proveedor-ajeno": {
            "id": "proveedor-ajeno", "name": "Ajeno",
            "npm": OPENCODE_NPM, "api": "https://ajeno.example.com/v1",
            "models": {
                "ajeno-1": _modelo("ajeno-1", "Ajeno Uno",
                                   api="https://ajeno.example.com/v1",
                                   costo=(0, 0))}},
    }


class TestReducir(unittest.TestCase):

    def setUp(self):
        self.reducido = catalogo.reducir(_muestra(), FECHA)

    def _por_id(self, proveedor):
        return {m["id"]: m
                for m in self.reducido["proveedores"][proveedor]["modelos"]}

    def test_solo_los_proveedores_pedidos(self):
        self.assertEqual(self.reducido["version"], 1)
        self.assertEqual(self.reducido["fecha"], FECHA)
        self.assertEqual(set(self.reducido["proveedores"]),
                         {"opencode-go", "google"})

    def test_minimax_chat_con_base_y_gratis(self):
        modelo = self._por_id("opencode-go")["minimax-m3.1-flash-free"]
        self.assertEqual(
            (modelo["protocolo"], modelo["base"], modelo["gratis"]),
            (protocolos.CHAT, OPENCODE_API, True))
        self.assertEqual(
            (modelo["piensa"], modelo["tope_salida"],
             modelo["contributor"]),
            (True, 512000, False))

    def test_haiku_anthropic_con_su_base(self):
        modelo = self._por_id("opencode-go")["claude-haiku-5-5"]
        self.assertEqual(modelo["protocolo"], protocolos.ANTHROPIC)
        self.assertEqual(
            modelo["base"], "https://opencode.ai/inference/go/anthropic/v1")
        self.assertFalse(modelo["gratis"])
        self.assertEqual(modelo["tope_salida"], 128000)

    def test_argon_gemini_y_contributor(self):
        modelo = self._por_id("opencode-go")["gemini-4-argon-contributor"]
        self.assertEqual(modelo["protocolo"], protocolos.GEMINI)
        self.assertEqual(
            modelo["base"], "https://opencode.ai/inference/go/google/v1beta")
        self.assertTrue(modelo["contributor"])

    def test_muse_responses_y_contributor(self):
        modelo = self._por_id("opencode-go")["muse-spark-1.3-contributor"]
        self.assertEqual(modelo["protocolo"], protocolos.RESPONSES)
        self.assertTrue(modelo["contributor"])
        self.assertFalse(modelo["gratis"])

    def test_excluidos_y_ajeno(self):
        quedados = self._por_id("opencode-go")
        for ident in ("step-5-preview-free", "longcat-2.0", "raro-1"):
            self.assertNotIn(ident, quedados)
        self.assertIn("sin-costo-1", quedados)

    def test_sin_costo_no_gratis_y_sin_tope(self):
        modelo = self._por_id("opencode-go")["sin-costo-1"]
        self.assertFalse(modelo["gratis"])
        self.assertIsNone(modelo["tope_salida"])

    def test_google_directo_toma_la_base_por_defecto(self):
        modelo = self._por_id("google")["gemini-directo-1"]
        self.assertEqual(modelo["protocolo"], protocolos.GEMINI)
        self.assertEqual(
            modelo["base"],
            "https://generativelanguage.googleapis.com/v1beta")
        self.assertTrue(modelo["gratis"])

    def test_ordenados_por_nombre_sin_mayusculas(self):
        for ident, entrada in self.reducido["proveedores"].items():
            with self.subTest(proveedor=ident):
                nombres = [m["nombre"] for m in entrada["modelos"]]
                self.assertEqual(nombres, sorted(nombres, key=str.lower))

    def test_propiedad_general_sobre_la_muestra(self):
        muestra = _muestra()
        original = {}
        for proveedor in catalogo.PROVEEDORES:
            entrada = muestra.get(proveedor)
            if isinstance(entrada, dict):
                for ident, datos in entrada["models"].items():
                    original[(proveedor, ident)] = datos
        for proveedor, entrada in self.reducido["proveedores"].items():
            for modelo in entrada["modelos"]:
                with self.subTest(modelo=modelo["id"]):
                    self.assertIn(modelo["protocolo"], (
                        protocolos.CHAT, protocolos.RESPONSES,
                        protocolos.ANTHROPIC, protocolos.GEMINI))
                    self.assertTrue(
                        modelo["base"].startswith("https://"))
                    self.assertFalse(modelo["base"].endswith("/"))
                    crudo = original[(proveedor, modelo["id"])]
                    self.assertNotEqual(crudo.get("status"), "deprecated")
                    self.assertIn("image", crudo["modalities"]["input"])


class TestReducirSalidas(unittest.TestCase):
    """Solo quedan los modelos que devuelven texto y nada más."""

    def _reducido(self):
        muestra = {
            "google": {
                "id": "google", "name": "Google",
                "npm": "@ai-sdk/google",
                "models": {
                    "solo-texto": _modelo(
                        "solo-texto", "Solo Texto", salidas=("text",)),
                    "con-audio": _modelo(
                        "con-audio", "Con Audio",
                        salidas=("text", "audio")),
                    "con-imagen": _modelo(
                        "con-imagen", "Con Imagen",
                        salidas=("text", "image")),
                    "con-video": _modelo(
                        "con-video", "Con Vídeo", salidas=("video",)),
                    "gemini-embedding-2": _modelo(
                        "gemini-embedding-2", "Gemini Embedding 2",
                        salidas=("text",)),
                },
            },
        }
        return catalogo.reducir(muestra, FECHA)

    def test_solo_texto_es_el_unico_que_queda(self):
        entradas = self._reducido()["proveedores"]["google"]["modelos"]
        self.assertEqual([m["id"] for m in entradas], ["solo-texto"])


class TestCargar(unittest.TestCase):

    def test_prefiere_datos_y_cae_al_paquete(self):
        reducido = catalogo.reducir(_muestra(), FECHA)
        respaldo = {"google": {"nombre": "Google", "modelos": []}}
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos.json"
            paquete = Path(tmp) / "paquete.json"
            paquete.write_text(json.dumps(
                {"version": 1, "fecha": FECHA,
                 "proveedores": respaldo}), encoding="utf-8")
            datos.write_text(json.dumps(reducido), encoding="utf-8")
            self.assertEqual(catalogo.cargar(
                datos, paquete)["proveedores"], reducido["proveedores"])
            datos.write_text("{roto", encoding="utf-8")
            with self.assertLogs(catalogo.logger, level="WARNING"):
                self.assertEqual(catalogo.cargar(
                    datos, paquete)["proveedores"], respaldo)
            datos.write_text(json.dumps(
                {"version": 999, "fecha": FECHA,
                 "proveedores": {}}), encoding="utf-8")
            self.assertEqual(catalogo.cargar(
                datos, paquete)["proveedores"], respaldo)

    def test_sin_las_dos_da_vacio_y_sin_registro(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos.json"
            paquete = Path(tmp) / "paquete.json"
            with self.assertNoLogs(catalogo.logger, level="WARNING"):
                vacio = catalogo.cargar(datos, paquete)
            self.assertEqual(
                vacio, {"version": 1, "fecha": None, "proveedores": {}})


class TestVencido(unittest.TestCase):

    def test_seis_dias_no_ocho_si(self):
        ahora = datetime.datetime(2026, 10, 21, 12, 0, 0)
        joven = {"version": 1, "fecha": "2026-10-15", "proveedores": {}}
        viejo = {"version": 1, "fecha": "2026-10-13", "proveedores": {}}
        self.assertFalse(catalogo.vencido(joven, ahora))
        self.assertTrue(catalogo.vencido(viejo, ahora))

    def test_sin_fecha_o_ilegible(self):
        ahora = datetime.datetime(2026, 10, 21, 12, 0, 0)
        self.assertTrue(catalogo.vencido(
            {"version": 1, "fecha": None, "proveedores": {}}, ahora))
        self.assertTrue(catalogo.vencido(
            {"version": 1, "fecha": "no-fecha", "proveedores": {}}, ahora))


class TestModelos(unittest.TestCase):

    def test_orden_y_solo_gratis(self):
        reducido = catalogo.reducir(_muestra(), FECHA)
        guardados = reducido["proveedores"]["opencode-go"]["modelos"]
        todos = catalogo.modelos(reducido, "opencode-go")
        self.assertEqual([m.id for m in todos],
                         [m["id"] for m in guardados])
        gratis = catalogo.modelos(reducido, "opencode-go", solo_gratis=True)
        self.assertEqual([m.id for m in gratis],
                         ["minimax-m3.1-flash-free"])
        primero = todos[0]
        self.assertIsInstance(primero, catalogo.Modelo)
        self.assertEqual(primero.id, "claude-haiku-5-5")
        self.assertEqual(
            (primero.protocolo, primero.gratis, primero.contributor,
             primero.piensa, primero.tope_salida),
            (protocolos.ANTHROPIC, False, False, True, 128000))

    def test_proveedor_desconocido_da_vacia(self):
        reducido = catalogo.reducir(_muestra(), FECHA)
        self.assertEqual(catalogo.modelos(reducido, "otro"), [])


class ServidorCatalogo(http.server.BaseHTTPRequestHandler):
    estado = 200
    cuerpo = "{}"

    def do_GET(self):
        cuerpo = type(self).cuerpo.encode("utf-8")
        try:
            self.send_response(type(self).estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


class TestDescargar(unittest.TestCase):

    def _servidor(self, estado=200, cuerpo="{}"):
        ServidorCatalogo.estado = estado
        ServidorCatalogo.cuerpo = cuerpo
        servidor = http.server.HTTPServer(("127.0.0.1", 0),
                                          ServidorCatalogo)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor

    def _url(self, servidor):
        return f"http://127.0.0.1:{servidor.server_port}/api.json"

    def test_200_escribe_reducido_y_cargar_lo_lee(self):
        muestra = _muestra()
        servidor = self._servidor(estado=200, cuerpo=json.dumps(muestra))
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "nueva" / "catalogo_ia.json"
            with mock.patch.object(catalogo, "URL", self._url(servidor)):
                bajado = catalogo.descargar(destino, FECHA)
            self.assertEqual(bajado, catalogo.reducir(muestra, FECHA))
            leido = catalogo.cargar(destino, Path(tmp) / "no-existe.json")
            self.assertEqual(leido["proveedores"], bajado["proveedores"])
            self.assertEqual(leido["fecha"], FECHA)

    def test_fallo_no_toca_destino_y_no_deja_temporales(self):
        casos = [(500, "caído", protocolos.SERVIDOR, True),
                 (200, "esto no es json", protocolos.RESPUESTA_VACIA, True),
                 (200, "[1, 2]", protocolos.RESPUESTA_VACIA, False)]
        for estado, cuerpo, tipo, previo in casos:
            with self.subTest(estado=estado, cuerpo=cuerpo):
                servidor = self._servidor(estado=estado, cuerpo=cuerpo)
                with tempfile.TemporaryDirectory() as tmp:
                    destino = Path(tmp) / "catalogo_ia.json"
                    if previo:
                        destino.write_text("previo", encoding="utf-8")
                    with mock.patch.object(
                            catalogo, "URL", self._url(servidor)):
                        with self.assertRaises(
                                protocolos.ErrorIA) as salida:
                            catalogo.descargar(destino, FECHA)
                    self.assertEqual(salida.exception.tipo, tipo)
                    if previo:
                        self.assertEqual(
                            destino.read_text(encoding="utf-8"), "previo")
                        self.assertEqual(
                            sorted(p.name for p in Path(tmp).iterdir()),
                            [destino.name])
                    else:
                        self.assertFalse(destino.exists())
                        self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_puerto_cerrado_es_sin_red(self):
        with socket.socket() as sondeo:
            sondeo.bind(("127.0.0.1", 0))
            puerto = sondeo.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "catalogo_ia.json"
            with mock.patch.object(
                    catalogo, "URL",
                    f"http://127.0.0.1:{puerto}/api.json"):
                with self.assertRaises(protocolos.ErrorIA) as salida:
                    catalogo.descargar(destino, FECHA)
            self.assertEqual(salida.exception.tipo, protocolos.SIN_RED)
            self.assertFalse(destino.exists())


class TestScript(unittest.TestCase):

    def _salida_de_main(self, descargar):
        with tempfile.TemporaryDirectory() as tmp:
            instala = mock.patch(
                "bellbird.core.paths.carpeta_instalacion",
                return_value=Path(tmp))
            baja = mock.patch("bellbird.ai.catalogo.descargar", descargar)
            with instala, baja, io.StringIO() as texto:
                with contextlib.redirect_stdout(texto):
                    codigo = actualizar_catalogo_ia.main()
                return codigo, texto.getvalue()

    def test_imprime_una_linea_por_proveedor(self):
        reducido = catalogo.reducir(_muestra(), FECHA)
        codigo, salida = self._salida_de_main(lambda *a, **k: reducido)
        self.assertEqual(codigo, 0)
        lineas = {l.split(":")[0].strip(): l
                  for l in salida.splitlines() if ":" in l}
        self.assertEqual(set(lineas), {"opencode-go", "google"})
        self.assertIn("5 modelos", lineas["opencode-go"])
        self.assertIn("1 gratis", lineas["opencode-go"])
        self.assertIn("1 modelos", lineas["google"])
        self.assertIn("1 gratis", lineas["google"])

    def test_error_imprime_el_tipo_y_sale_con_uno(self):
        def falla(*args, **kwargs):
            raise protocolos.ErrorIA(protocolos.SIN_RED, "x")
        codigo, salida = self._salida_de_main(falla)
        self.assertEqual(codigo, 1)
        self.assertIn(protocolos.SIN_RED, salida)

    def test_arranca_como_script_sin_la_raiz_en_sys_path(self):
        script = str(Path(__file__).resolve().parent.parent
                     / "scripts" / "actualizar_catalogo_ia.py")
        with tempfile.TemporaryDirectory() as tmp:
            proceso = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import runpy; runpy.run_path(r'" + script
                 + "', run_name='prueba')"],
                cwd=tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(proceso.returncode, 0, msg=proceso.stderr)


if __name__ == "__main__":
    unittest.main()
