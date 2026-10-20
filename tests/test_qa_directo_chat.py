"""Pruebas de qa/directo_chat.py, sin red ni ventanas."""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "directo_chat.py"
_paquete = importlib.util.spec_from_file_location(
    "directo_chat_qa", _RUTA)
directo_chat = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(directo_chat)


class TestLimitarCorte(unittest.TestCase):

    def test_cero_se_queda_en_cero(self):
        self.assertEqual(directo_chat.limitar_corte(0), 0)

    def test_negativo_es_cero(self):
        self.assertEqual(directo_chat.limitar_corte(-5), 0)

    def test_mas_de_30_es_30(self):
        self.assertEqual(directo_chat.limitar_corte(31), 30)
        self.assertEqual(directo_chat.limitar_corte(300), 30)

    def test_entre_1_y_30_pasa_igual(self):
        self.assertEqual(directo_chat.limitar_corte(8), 8)
        self.assertEqual(directo_chat.limitar_corte(30), 30)

    def test_sin_numero_es_cero(self):
        self.assertEqual(directo_chat.limitar_corte(None), 0)
        self.assertEqual(directo_chat.limitar_corte("ocho"), 0)


class TestLeerHecho(unittest.TestCase):

    def test_cortada_y_reconecta_pasa(self):
        bien, detalle = directo_chat.leer_hecho(
            "cortada 2026-10-20T14:00:00 reconecta 2026-10-20T14:00:08")
        self.assertTrue(bien)
        self.assertIn("cortada", detalle)

    def test_vacio_pide_lanzar_la_tarea(self):
        bien, detalle = directo_chat.leer_hecho("")
        self.assertFalse(bien)
        self.assertIn("BellbirdCorteRed no respondió", detalle)
        self.assertIn("lánzala antes del banco", detalle)

    def test_error_devuelve_el_motivo(self):
        bien, detalle = directo_chat.leer_hecho(
            "error no hay wifi conectado: con cable no se corta")
        self.assertFalse(bien)
        self.assertIn("no hay wifi conectado", detalle)
        self.assertNotIn("error", detalle.split(":")[0])

    def test_otro_texto_falla_nombrandolo(self):
        bien, detalle = directo_chat.leer_hecho("algo raro")
        self.assertFalse(bien)
        self.assertIn("algo raro", detalle)


class TestMensajeEnRespuesta(unittest.TestCase):

    def _respuesta(self, mensajes):
        return {"items": [{"snippet": mensaje} for mensaje in mensajes]}

    def test_en_display_message(self):
        respuesta = self._respuesta(
            [{"displayMessage": "Prueba desde la app 14:05:09"}])
        self.assertTrue(directo_chat.mensaje_en_respuesta(
            respuesta, "Prueba desde la app 14:05:09"))

    def test_en_text_message_details(self):
        respuesta = self._respuesta(
            [{"textMessageDetails": {"messageText": "hola qué tal"}}])
        self.assertTrue(directo_chat.mensaje_en_respuesta(
            respuesta, "hola qué tal"))

    def test_ausente_da_falso(self):
        respuesta = self._respuesta([{"displayMessage": "otro"}])
        self.assertFalse(directo_chat.mensaje_en_respuesta(
            respuesta, "Prueba desde la app 14:05:09"))

    def test_vacio_no_revienta(self):
        self.assertFalse(directo_chat.mensaje_en_respuesta(None, "hola"))
        self.assertFalse(directo_chat.mensaje_en_respuesta({}, "hola"))
        self.assertFalse(directo_chat.mensaje_en_respuesta(
            {"items": None}, "hola"))
        self.assertFalse(directo_chat.mensaje_en_respuesta(
            self._respuesta([{"displayMessage": "hola"}]), ""))


class TestRepetidos(unittest.TestCase):

    def test_sin_repetidos_da_vacio(self):
        lineas = ["10:00 Ana: Comentario de prueba 1",
                  "10:01 Luis: Comentario de prueba 2"]
        self.assertEqual(directo_chat.repetidos(
            lineas, ["Comentario de prueba 1",
                     "Comentario de prueba 2"]), [])

    def test_el_repetido_sale_nombrado(self):
        lineas = ["10:00 Ana: Comentario de prueba 1",
                  "10:01 Luis: Comentario de prueba 1"]
        self.assertEqual(directo_chat.repetidos(
            lineas, ["Comentario de prueba 1"]), ["Comentario de prueba 1"])

    def test_el_ausente_no_es_repetido(self):
        self.assertEqual(directo_chat.repetidos(
            ["algo"], ["Comentario de prueba 1"]), [])

    def test_vacio_no_revienta(self):
        self.assertEqual(directo_chat.repetidos(None, ["a"]), [])
        self.assertEqual(directo_chat.repetidos(["a a"], None), [])
        self.assertEqual(directo_chat.repetidos(["a a"], [""]), [])


class TestEstadoReconexion(unittest.TestCase):

    def test_perdida_y_reconexion_pasa(self):
        bien, detalle = directo_chat.estado_reconexion(
            "14:00 Se perdió la conexión con el chat. Reintentando en 2 "
            "segundos. 14:01 Chat reconectado.")
        self.assertTrue(bien)
        self.assertIn("1 aviso de pérdida", detalle)

    def test_cuenta_varios_avisos(self):
        bien, detalle = directo_chat.estado_reconexion(
            "Se perdió la conexión con el chat. Uno. "
            "Se perdió la conexión con el chat. Dos. Chat reconectado.")
        self.assertTrue(bien)
        self.assertIn("2 avisos de pérdida", detalle)

    def test_sin_perdida_falla(self):
        bien, detalle = directo_chat.estado_reconexion(
            "14:01 Chat reconectado.")
        self.assertFalse(bien)
        self.assertIn("0 avisos", detalle)

    def test_sin_reconexion_falla(self):
        bien, _ = directo_chat.estado_reconexion(
            "14:00 Se perdió la conexión con el chat. Reintentando.")
        self.assertFalse(bien)

    def test_reconexion_antes_de_la_perdida_falla(self):
        bien, _ = directo_chat.estado_reconexion(
            "Chat reconectado. Después se perdió la conexión con el chat.")
        self.assertFalse(bien)

    def test_final_prohibido_falla_aunque_haya_reconexion(self):
        for final in ("El directo terminó. Chat desconectado.",
                      "Se agotaron los 5 intentos de reconexión.",
                      "La conexión se cerró y la reconexión está "
                      "desactivada."):
            with self.subTest(final=final):
                bien, detalle = directo_chat.estado_reconexion(
                    "Se perdió la conexión con el chat. Chat reconectado. "
                    + final)
                self.assertFalse(bien)
                self.assertIn("se cerró", detalle)


class _CuadroFalso:

    def __init__(self, falla=False):
        self.recibido = None
        self.falla = falla

    def set_edit_text(self, texto):
        if self.falla:
            raise RuntimeError("bloqueado")
        self.recibido = texto


class _BotonFalso:

    def __init__(self):
        self.pulsado = 0

    def invoke(self):
        self.pulsado += 1


class TestPonerTexto(unittest.TestCase):

    def test_escribe_por_set_edit_text(self):
        cuadro = _CuadroFalso()
        directo_chat.poner_texto(cuadro, "hola")
        self.assertEqual(cuadro.recibido, "hola")

    def test_sin_patron_de_valor_falla(self):
        with self.assertRaises(RuntimeError) as contexto:
            directo_chat.poner_texto(object(), "hola")
        self.assertIn("patrón de valor", str(contexto.exception))

    def test_si_falla_lo_dice(self):
        with self.assertRaises(RuntimeError) as contexto:
            directo_chat.poner_texto(_CuadroFalso(falla=True), "hola")
        self.assertIn("bloqueado", str(contexto.exception))


class TestEscribirDesdeApp(unittest.TestCase):

    def _control(self, controles):
        def buscar(raiz, nombre, tipo=None, segundos=20):
            return controles[nombre]
        return buscar

    def test_escribe_pulsa_y_encuentra(self):
        cuadro, boton = _CuadroFalso(), _BotonFalso()
        controles = {directo_chat.NOMBRE_CUADRO: cuadro,
                     directo_chat.NOMBRE_BOTON: boton}
        bien, detalle = directo_chat.escribir_desde_app(
            "principal", "Prueba 1", "anuncios.txt", 0,
            leer_anuncios=lambda ruta: "",
            esperar_anuncio=lambda *args: directo_chat.ANUNCIO_ENVIADO,
            control=self._control(controles),
            leer_respuesta=lambda: {"items": [
                {"snippet": {"displayMessage": "Prueba 1"}}]})
        self.assertTrue(bien)
        self.assertIn("Prueba 1", detalle)
        self.assertEqual(cuadro.recibido, "Prueba 1")
        self.assertEqual(boton.pulsado, 1)

    def test_sin_anuncio_de_enviado_falla(self):
        controles = {directo_chat.NOMBRE_CUADRO: _CuadroFalso(),
                     directo_chat.NOMBRE_BOTON: _BotonFalso()}
        bien, detalle = directo_chat.escribir_desde_app(
            "principal", "Prueba 1", "anuncios.txt", 0,
            leer_anuncios=lambda ruta: "",
            esperar_anuncio=lambda *args: None,
            control=self._control(controles),
            leer_respuesta=lambda: {"items": []})
        self.assertFalse(bien)
        self.assertIn(directo_chat.ANUNCIO_ENVIADO, detalle)

    def test_si_no_vuelve_por_api_falla(self):
        from unittest import mock
        reloj = [1000.0]
        controles = {directo_chat.NOMBRE_CUADRO: _CuadroFalso(),
                     directo_chat.NOMBRE_BOTON: _BotonFalso()}
        with mock.patch.object(directo_chat.time, "time",
                               lambda: reloj[0]), \
             mock.patch.object(directo_chat.time, "sleep",
                               lambda s: reloj.__setitem__(0, reloj[0] + s)):
            bien, detalle = directo_chat.escribir_desde_app(
                "principal", "Prueba 1", "anuncios.txt", 0,
                leer_anuncios=lambda ruta: "",
                esperar_anuncio=lambda *args: directo_chat.ANUNCIO_ENVIADO,
                control=self._control(controles),
                leer_respuesta=lambda: {"items": []})
        self.assertFalse(bien)
        self.assertIn("no volvió por la API", detalle)


class TestPasoCorte(unittest.TestCase):

    def _carpeta(self):
        import shutil
        import tempfile
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        return carpeta

    def _tarea_falsa(self, pedido, hecho, contenido):
        """Hilo que imita la tarea: responde cuando ve el pedido."""
        import os
        import threading
        import time

        def responder():
            for _ in range(200):
                if os.path.exists(pedido):
                    break
                time.sleep(0.05)
            with open(hecho, "w", encoding="utf-8") as f:
                f.write(contenido)

        hilo = threading.Thread(target=responder)
        hilo.start()
        self.addCleanup(hilo.join)
        return hilo

    def test_pide_y_lee_el_hecho(self):
        import os
        carpeta = self._carpeta()
        pedido = os.path.join(carpeta, "p.txt")
        hecho = os.path.join(carpeta, "h.txt")
        self._tarea_falsa(pedido, hecho, "cortada ayer reconecta hoy")
        bien, detalle, marca = directo_chat.paso_corte(
            8, "anuncios.txt", lambda ruta: "x" * 12,
            ruta_pedido=pedido, ruta_hecho=hecho)
        self.assertTrue(bien)
        self.assertIn("cortada", detalle)
        self.assertEqual(marca, 12)
        with open(pedido, encoding="utf-8") as f:
            self.assertEqual(f.read(), "8")

    def test_error_de_la_tarea_falla_con_su_motivo(self):
        import os
        carpeta = self._carpeta()
        pedido = os.path.join(carpeta, "p.txt")
        hecho = os.path.join(carpeta, "h.txt")
        self._tarea_falsa(pedido, hecho, "error sin wifi")
        bien, detalle, _ = directo_chat.paso_corte(
            8, "anuncios.txt", lambda ruta: "",
            ruta_pedido=pedido, ruta_hecho=hecho)
        self.assertFalse(bien)
        self.assertIn("sin wifi", detalle)


class TestEsperarReconexion(unittest.TestCase):

    def test_con_perdida_y_vuelta_pasa(self):
        anuncios = ("14:00 Se perdió la conexión con el chat. Reintentando. "
                    "14:01 Chat reconectado.")
        bien, detalle = directo_chat.esperar_reconexion(
            "anuncios.txt", 0, 8, lambda ruta: anuncios)
        self.assertTrue(bien)
        self.assertIn("1 aviso", detalle)

    def test_con_final_prohibido_falla_rapido(self):
        anuncios = ("Se perdió la conexión con el chat. "
                    "El directo terminó. Chat desconectado.")
        bien, detalle = directo_chat.esperar_reconexion(
            "anuncios.txt", 0, 8, lambda ruta: anuncios)
        self.assertFalse(bien)
        self.assertIn("se cerró", detalle)

    def test_lo_anterior_a_la_marca_no_cuenta(self):
        from unittest import mock
        previo = ("Se perdió la conexión con el chat. Chat reconectado. ")
        anuncios = previo + "Nada nuevo por aquí."
        reloj = [1000.0]
        with mock.patch.object(directo_chat.time, "time",
                               lambda: reloj[0]), \
             mock.patch.object(directo_chat.time, "sleep",
                               lambda s: reloj.__setitem__(0, reloj[0] + s)):
            bien, _ = directo_chat.esperar_reconexion(
                "anuncios.txt", len(previo), 0, lambda ruta: anuncios)
        self.assertFalse(bien)

    def test_el_final_anterior_a_la_marca_no_cuenta(self):
        previo = "El directo terminó. Chat desconectado. "
        anuncios = (previo + "Se perdió la conexión con el chat. "
                    "Chat reconectado.")
        bien, _ = directo_chat.esperar_reconexion(
            "anuncios.txt", len(previo), 8, lambda ruta: anuncios)
        self.assertTrue(bien)


class _ClienteFalso:

    def __init__(self, falla=False):
        self.enviados = []
        self.falla = falla

    def enviar_mensaje_live(self, id_chat, texto):
        if self.falla:
            raise RuntimeError("cuota")
        self.enviados.append((id_chat, texto))


class TestLeerDespues(unittest.TestCase):

    def test_comenta_y_lo_ve_en_la_app(self):
        cliente = _ClienteFalso()
        bien, detalle = directo_chat.leer_despues(
            cliente, "chat123", "chat.txt", "Comentario después",
            comentario_faltante=lambda *args: (None, ["a"]),
            detalle_lista=lambda leidos: "detalle")
        self.assertTrue(bien)
        self.assertEqual(cliente.enviados, [("chat123", "Comentario después")])
        self.assertIn("Comentario después", detalle)

    def test_si_no_aparece_falla_con_el_detalle(self):
        bien, detalle = directo_chat.leer_despues(
            _ClienteFalso(), "chat123", "chat.txt", "Ausente",
            comentario_faltante=lambda *args: ("Ausente", ["a", "b"]),
            detalle_lista=lambda leidos: f"{len(leidos)} elementos")
        self.assertFalse(bien)
        self.assertIn("2 elementos", detalle)

    def test_si_la_api_falla_lo_dice(self):
        bien, detalle = directo_chat.leer_despues(
            _ClienteFalso(falla=True), "chat123", "chat.txt", "Hola",
            comentario_faltante=lambda *args: (None, []),
            detalle_lista=lambda leidos: "detalle")
        self.assertFalse(bien)
        self.assertIn("cuota", detalle)


class TestComprobarSinRepetidos(unittest.TestCase):

    def _ruta_con(self, lineas):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + ("\n" if lineas else ""))
        self.addCleanup(os.remove, ruta)
        return ruta

    def test_sin_repetidos_pasa(self):
        ruta = self._ruta_con(["10:00 Ana: Comentario de prueba 1"])
        bien, detalle = directo_chat.comprobar_sin_repetidos(
            ruta, ["Comentario de prueba 1"])
        self.assertTrue(bien)
        self.assertIn("sin repetir", detalle)

    def test_repetido_falla_nombrandolo(self):
        ruta = self._ruta_con(["10:00 Ana: Comentario de prueba 1",
                               "10:01 Ana: Comentario de prueba 1"])
        bien, detalle = directo_chat.comprobar_sin_repetidos(
            ruta, ["Comentario de prueba 1"])
        self.assertFalse(bien)
        self.assertIn("Comentario de prueba 1", detalle)

    def test_sin_archivo_falla(self):
        import os
        import shutil
        import tempfile
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        bien, detalle = directo_chat.comprobar_sin_repetidos(
            os.path.join(carpeta, "chat.txt"), ["a"])
        self.assertFalse(bien)
        self.assertIn("no se pudo leer", detalle)


if __name__ == "__main__":
    unittest.main()
