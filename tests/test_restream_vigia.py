"""Conexión real con un WebSocket local, reconexión y discreción del token."""

import logging
import socket
import threading
import time
import unittest

from websockets.sync.server import serve

from guyrapu.core import diagnostico
from guyrapu.restream import vigia


class TestVigiaConServidor(unittest.TestCase):

    def test_entrega_los_mensajes_en_orden_y_reconecta(self):
        recibidas = []
        segunda = threading.Event()
        fin = threading.Event()
        candado = threading.Lock()
        conexiones = [0]

        def manejar(conexion):
            with conexion:
                with candado:
                    numero = conexiones[0]
                    conexiones[0] += 1
                if numero == 0:
                    conexion.send("uno")
                    conexion.send("dos")
                    return
                segunda.set()
                fin.wait(5)

        servidor = serve(manejar, "127.0.0.1", 0)
        puerto = servidor.socket.getsockname()[1]
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        prueba = vigia.VigiaSenal(
            lambda: "token", recibidas.append,
            direccion=f"ws://127.0.0.1:{puerto}",
            esperar=lambda segundos: False)
        try:
            prueba.iniciar()
            self.assertTrue(segunda.wait(5), "no reconectó")
            self.assertEqual(recibidas[:2], ["uno", "dos"])
        finally:
            prueba.detener()
            fin.set()
            servidor.shutdown()
            hilo.join(5)


class TestParada(unittest.TestCase):

    def test_la_parada_corta_la_espera(self):
        intentos = []

        def conectar(_direccion):
            intentos.append(True)
            raise RuntimeError("sin servidor")

        prueba = vigia.VigiaSenal(
            lambda: "token", lambda mensaje: None,
            direccion="ws://127.0.0.1:1", conectar_fn=conectar)
        prueba.iniciar()
        for _ in range(100):
            if intentos:
                break
            time.sleep(0.01)
        time.sleep(0.1)

        inicio = time.monotonic()
        prueba.detener()

        self.assertLess(time.monotonic() - inicio, 1.0)


class TestTokenEnElRegistro(unittest.TestCase):

    def test_el_token_no_aparece_al_rechazar_la_conexion(self):
        registros = []
        llegada = threading.Event()
        escucha = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        escucha.bind(("127.0.0.1", 0))
        escucha.listen(1)
        puerto = escucha.getsockname()[1]

        def rechazar():
            try:
                conexion, _ = escucha.accept()
                with conexion:
                    conexion.recv(4096)
                    conexion.sendall(
                        b"HTTP/1.1 401 Unauthorized\r\n"
                        b"Content-Length: 0\r\n\r\n")
            finally:
                escucha.close()

        hilo_servidor = threading.Thread(target=rechazar, daemon=True)
        hilo_servidor.start()

        class Captor(logging.Handler):
            def emit(self, registro):
                registros.append(registro.getMessage())
                llegada.set()

        captor = Captor()
        loggers = (vigia.logger, diagnostico.logger)
        niveles = [(logger, logger.level) for logger in loggers]
        for logger in loggers:
            logger.setLevel(logging.DEBUG)
            logger.addHandler(captor)
        try:
            prueba = vigia.VigiaSenal(
                lambda: "token-secreto", lambda mensaje: None,
                direccion=f"ws://127.0.0.1:{puerto}")
            prueba.iniciar()
            self.assertTrue(llegada.wait(5), "no registró el fallo")
            prueba.detener()
        finally:
            for logger, nivel in niveles:
                logger.setLevel(nivel)
                logger.removeHandler(captor)
            hilo_servidor.join(5)

        self.assertTrue(registros)
        for texto in registros:
            self.assertNotIn("token-secreto", texto)
            self.assertNotIn("accessToken", texto)
            self.assertNotIn("server rejected", texto)


class TestReintento(unittest.TestCase):

    def test_reintenta_con_espera_creciente_hasta_treinta(self):
        esperas = []
        parada = threading.Event()

        def conectar(_direccion):
            raise RuntimeError("sin servidor")

        def esperar(segundos):
            esperas.append(segundos)
            if len(esperas) >= 6:
                parada.set()
                return True
            return False

        prueba = vigia.VigiaSenal(
            lambda: "token", lambda mensaje: None,
            direccion="ws://127.0.0.1:1", conectar_fn=conectar,
            parada=parada, esperar=esperar)
        prueba.iniciar()
        prueba._hilo.join(5)

        self.assertEqual(esperas[:6], [2, 4, 8, 16, 30, 30])


if __name__ == "__main__":
    unittest.main()
