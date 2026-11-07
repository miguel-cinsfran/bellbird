"""Pruebas de los ganchos de Restream antes de iniciar OBS."""

import json
import logging
import unittest
from types import SimpleNamespace
from unittest import mock

from guyrapu.core import diagnostico
from guyrapu.obs import obs_cliente
from guyrapu.restream import api, ganchos
from guyrapu.restream.api import Canal
from guyrapu.restream.perfiles import Perfil
from guyrapu.youtube.emision import EmisionError


def _perfil(nombre="Uno", orientacion="vertical", canales=(1,), titulo="",
            descripcion=""):
    return Perfil(nombre=nombre, canales=canales, orientacion=orientacion,
                  titulo=titulo, descripcion=descripcion)


def _canal(identificador, plataforma, activo=True, url="", nombre=""):
    return Canal(id=identificador, plataforma_id=0, plataforma=plataforma,
                 nombre=nombre or f"canal {identificador}", url=url,
                 activo=activo)


class CuentaFalsa:

    def __init__(self, canales, clave=None, fallo_clave=None,
                 sesion_conectada=True, fallo_canales=None):
        self._canales = list(canales)
        self._clave = clave or api.ClaveCuenta(
            clave="clave-secreta", servidor=api.SERVIDOR_RTMP)
        self._fallo_clave = fallo_clave
        self._conectada = sesion_conectada
        self._fallo_canales = fallo_canales
        self.llamadas = []
        self.fallar_restauracion = False

    def sesion(self):
        return SimpleNamespace(conectada=lambda: self._conectada)

    def canales(self):
        self.llamadas.append(("canales",))
        if self._fallo_canales is not None:
            raise self._fallo_canales
        return list(self._canales)

    def activar_canal(self, identificador, activo):
        self.llamadas.append(("activar", identificador, activo))
        if self.fallar_restauracion:
            raise api.ErrorApi("No se pudo restaurar el destino.")

    def cambiar_meta(self, identificador, titulo, descripcion):
        self.llamadas.append(("meta", identificador, titulo, descripcion))

    def clave_cuenta(self):
        self.llamadas.append(("clave",))
        if self._fallo_clave is not None:
            raise self._fallo_clave
        return self._clave


class EscritorFalso:

    def __init__(self, fallo=None):
        self.llamadas = []
        self._fallo = fallo

    def __call__(self, cliente, destino, parada=None):
        self.llamadas.append((destino.perfil, destino.servidor, destino.clave))
        if self._fallo is not None:
            raise self._fallo


def _armar(opcion, cuenta, perfil, canales=None, escritor=None):
    if canales is None:
        canales = cuenta.canales()
    anuncios = []
    preparar, restaurar = ganchos.armar(
        opcion, lambda frase, sonido, importante=False: anuncios.append((frase, sonido)),
        canales, cuenta_mod=cuenta, perfiles=[perfil],
        escribir=escritor or EscritorFalso())
    return preparar, restaurar, anuncios


class TestCuentaConectada(unittest.TestCase):

    def test_refleja_la_sesion(self):
        conectada = CuentaFalsa([], sesion_conectada=True)
        sin_cuenta = CuentaFalsa([], sesion_conectada=False)
        self.assertTrue(ganchos.cuenta_conectada(conectada))
        self.assertFalse(ganchos.cuenta_conectada(sin_cuenta))


class TestPrepararEmision(unittest.TestCase):

    def test_prepara_canales_titulo_clave_y_perfil_en_orden(self):
        perfil = _perfil("Uno", "vertical", (1, 2), titulo="Un título",
                         descripcion="Una descripción")
        canales = [_canal(1, "YouTube", False),
                   _canal(2, "TikTok", False,
                          url="https://www.tiktok.com/@amigo"),
                   _canal(3, "YouTube", True)]
        cuenta = CuentaFalsa(canales)
        escritor = EscritorFalso()
        preparar, _restaurar, anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor=escritor)

        self.assertIsNone(preparar(None))

        self.assertEqual(anuncios[0],
                         ("Preparando Restream para Uno.", "conectando"))
        self.assertEqual(cuenta.llamadas, [
            ("canales",),
            ("activar", 1, True), ("activar", 2, True),
            ("activar", 3, False),
            ("meta", 1, "Un título", "Una descripción"),
            ("meta", 2, "Un título", "Una descripción"),
            ("clave",),
        ])
        self.assertEqual(escritor.llamadas,
                         [("TikTok", api.SERVIDOR_RTMP, "clave-secreta")])

    def test_el_titulo_no_se_toca_si_el_perfil_no_lo_tiene(self):
        perfil = _perfil(canales=(1,), titulo="")
        canales = [_canal(1, "YouTube", False)]
        cuenta = CuentaFalsa(canales)
        preparar, _restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)
        self.assertNotIn("meta", [llamada[0] for llamada in cuenta.llamadas])

    def test_falla_la_clave_restaura_lo_cambiado_y_no_escribe_obs(self):
        perfil = _perfil(canales=(1, 2))
        canales = [_canal(1, "YouTube", False), _canal(2, "TikTok", False),
                   _canal(3, "YouTube", True)]
        mensaje = ("No se pudo leer la clave de transmisión de Restream. "
                   "Vuelve a intentarlo.")
        cuenta = CuentaFalsa(canales, fallo_clave=api.ErrorApi(mensaje))
        escritor = EscritorFalso()
        preparar, restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor=escritor)

        with self.assertRaises(EmisionError) as contexto_error:
            preparar(None)

        self.assertEqual(str(contexto_error.exception), mensaje)
        self.assertEqual(escritor.llamadas, [])
        self.assertEqual(cuenta.llamadas[-3:], [
            ("activar", 1, False),
            ("activar", 2, False),
            ("activar", 3, True),
        ])
        antes = len(cuenta.llamadas)
        restaurar()
        self.assertEqual(len(cuenta.llamadas), antes)

    def test_falla_obs_despues_de_los_canales_tambien_restaura(self):
        perfil = _perfil(canales=(1,))
        canales = [_canal(1, "YouTube", False)]
        cuenta = CuentaFalsa(canales)
        escritor = EscritorFalso(fallo=obs_cliente.ObsError(
            "OBS no aplicó el destino. Vuelve a intentarlo."))
        preparar, _restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor=escritor)

        with self.assertRaises(EmisionError):
            preparar(None)

        self.assertEqual(cuenta.llamadas[-1], ("activar", 1, False))

    def test_la_clave_no_aparece_en_el_registro_ni_en_el_error(self):
        perfil = _perfil(canales=(1,))
        cuenta = CuentaFalsa([_canal(1, "YouTube", False)])
        escritor = EscritorFalso(fallo=obs_cliente.ObsError(
            "OBS no aplicó el destino. Vuelve a intentarlo."))
        preparar, _restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor=escritor)

        registros = []

        class Captor(logging.Handler):
            def emit(self, record):
                registros.append(record.getMessage())

        captor = Captor()
        loggers = (ganchos.logger, diagnostico.logger)
        niveles = [(logger, logger.level) for logger in loggers]
        for logger in loggers:
            logger.setLevel(logging.DEBUG)
            logger.addHandler(captor)
        try:
            with self.assertRaises(EmisionError) as contexto_error:
                preparar(None)
        finally:
            for logger, nivel in niveles:
                logger.setLevel(nivel)
                logger.removeHandler(captor)

        self.assertEqual(escritor.llamadas[0][2], "clave-secreta")
        self.assertNotIn("clave-secreta", str(contexto_error.exception))
        self.assertNotIn("clave-secreta", "\n".join(registros))


class TestRestauracion(unittest.TestCase):

    def test_restaura_cada_canal_cambiado_una_sola_vez(self):
        perfil = _perfil(canales=(1, 2))
        canales = [_canal(1, "YouTube", False), _canal(2, "TikTok", False),
                   _canal(3, "YouTube", True)]
        cuenta = CuentaFalsa(canales)
        preparar, restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)

        restaurar()
        restaurar()

        self.assertEqual(
            [llamada for llamada in cuenta.llamadas
             if llamada[0] == "activar"][-3:],
            [("activar", 1, False), ("activar", 2, False),
             ("activar", 3, True)])

    def test_si_no_logra_restaurar_lo_registra_y_la_clave_no_aparece(self):
        perfil = _perfil(canales=(1,))
        canales = [_canal(1, "YouTube", False)]
        cuenta = CuentaFalsa(canales)
        preparar, restaurar, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)
        cuenta.fallar_restauracion = True

        with mock.patch.object(ganchos.logger, "warning") as warning, \
                mock.patch.object(ganchos.logger, "error") as error, \
                mock.patch.object(ganchos.logger, "info") as info:
            restaurar()

        self.assertTrue(warning.called or error.called or info.called)
        for llamada in (*warning.call_args_list, *error.call_args_list,
                        *info.call_args_list):
            self.assertNotIn("clave-secreta", str(llamada))


class TestAvisos(unittest.TestCase):

    def test_sin_tiktok_avisa_al_aire_cuando_obs_ya_transmite(self):
        anuncios = []
        contexto = ganchos.Contexto(destino="Restream")
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido, importante=False: anuncios.append((frase, sonido)), contexto)

        anunciar("OBS está enviando la señal a Restream.", "conectado")

        self.assertIn((ganchos._(ganchos.MENSAJE_NO_TIKTOK), "al_aire"),
                      anuncios)

    def test_con_tiktok_no_avisa_la_conexion_manual(self):
        anuncios = []
        contexto = ganchos.Contexto(destino="TikTok")
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido, importante=False: anuncios.append((frase, sonido)), contexto)

        anunciar("OBS está enviando la señal a Restream.", "conectado")

        self.assertEqual(anuncios,
                         [("OBS está enviando la señal a Restream.",
                           "conectado")])

    def test_no_repite_el_anuncio_de_youtube_antes_de_preparar(self):
        anuncios = []
        contexto = ganchos.Contexto()
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido, importante=False: anuncios.append((frase, sonido)), contexto)

        anunciar("Creando el directo en YouTube.", None)
        anunciar("Preparando Restream para Uno.", "conectando")

        self.assertEqual(anuncios,
                         [("Preparando Restream para Uno.", "conectando")])


class HiloInmediato:

    def __init__(self, target, _nombre=""):
        self.target = target

    def start(self):
        self.target()


class VigiaFalsa:

    instancias = []

    def __init__(self, leer_token, al_recibir, debe_seguir=None):
        self.leer_token = leer_token
        self.al_recibir = al_recibir
        self.debe_seguir = debe_seguir
        self.iniciada = False
        self.detenida = False
        VigiaFalsa.instancias.append(self)

    def iniciar(self):
        self.iniciada = True

    def detener(self):
        self.detenida = True


class TestSupervisarRestream(unittest.TestCase):

    def _supervisar(self, perfil, canales, fallo_canales=None):
        frame = SimpleNamespace(
            _alive=True, _supervisor=None, _config={},
            _actualizar_boton_directo=mock.Mock(),
            _al_terminar_supervisor=mock.Mock())
        cuenta = CuentaFalsa(canales, fallo_canales=fallo_canales)
        anuncios = []
        creados = []
        VigiaFalsa.instancias = []

        class SupervisorFalso:
            def __init__(self, destino, usuario, **kwargs):
                self.destino = destino
                self.usuario = usuario
                self.kwargs = kwargs
                self.iniciado = False
                self.activo = True
                self.deteniendo = False
                creados.append(self)

            def iniciar(self):
                self.iniciado = True

        with mock.patch.object(ganchos, "cargar_perfiles",
                               return_value=[perfil]), \
                mock.patch.object(
                    ganchos, "_anunciar_de_frame",
                    return_value=lambda frase, sonido, importante=False:
                    anuncios.append((frase, sonido))), \
                mock.patch.object(
                    ganchos, "_en_interfaz",
                    side_effect=lambda f, funcion, *args: funcion(*args)), \
                mock.patch.object(ganchos, "_parametros_supervisor",
                                  return_value={}), \
                mock.patch.object(ganchos.diagnostico, "crear_hilo",
                                  side_effect=lambda f, n: HiloInmediato(f)), \
                mock.patch("guyrapu.restream.vigia.VigiaSenal",
                           VigiaFalsa), \
                mock.patch("guyrapu.obs.obs_supervisor.SupervisorTransmision",
                           SupervisorFalso):
            ganchos.supervisar_restream(
                frame, "restream:" + perfil.nombre, cuenta_mod=cuenta)
        frame._vigilas_prueba = VigiaFalsa.instancias
        return frame, cuenta, creados, anuncios

    def test_tiktok_con_usuario_crea_el_supervisor_con_tiktok(self):
        perfil = _perfil("Uno", "vertical", (1,))
        canales = [_canal(1, "TikTok", url="https://www.tiktok.com/@amigo")]
        frame, _cuenta, creados, _anuncios = self._supervisar(perfil, canales)

        self.assertEqual((creados[0].destino, creados[0].usuario),
                         ("TikTok", "amigo"))
        self.assertIs(frame._supervisor, creados[0])
        self.assertTrue(creados[0].iniciado)
        frame._actualizar_boton_directo.assert_called_once_with()

    def test_sin_tiktok_el_destino_del_supervisor_es_restream(self):
        perfil = _perfil("Uno", "horizontal", (1,))
        canales = [_canal(1, "YouTube")]
        _frame, _cuenta, creados, _anuncios = self._supervisar(perfil, canales)

        self.assertEqual((creados[0].destino, creados[0].usuario),
                         ("Restream", ""))

    def test_tiktok_sin_usuario_legible_queda_en_restream(self):
        perfil = _perfil("Uno", "vertical", (1,))
        canales = [_canal(1, "TikTok", url="", nombre="")]
        _frame, _cuenta, creados, _anuncios = self._supervisar(perfil, canales)

        self.assertEqual((creados[0].destino, creados[0].usuario),
                         ("Restream", ""))

    def test_fallo_al_leer_canales_avisa_y_no_crea_el_supervisor(self):
        perfil = _perfil("Uno", "vertical", (1,))
        fallo = api.ErrorApi(
            "No se pudieron leer los destinos de Restream. "
            "Vuelve a intentarlo.")
        frame, _cuenta, creados, anuncios = self._supervisar(
            perfil, [], fallo_canales=fallo)

        self.assertEqual(creados, [])
        self.assertIsNone(frame._supervisor)
        self.assertIn((str(fallo), "transmision_problema"), anuncios)
        frame._actualizar_boton_directo.assert_not_called()

    def test_crear_el_supervisor_arranca_la_vigia_con_el_mapa(self):
        perfil = _perfil("Uno", "horizontal", (1,))
        canales = [_canal(1, "TikTok", nombre="szeiryuGaming")]
        frame, _cuenta, _creados, anuncios = self._supervisar(perfil, canales)

        vigia = frame._vigilas_prueba[0]
        self.assertTrue(vigia.iniciada)
        vigia.al_recibir(
            json.dumps({"action": "updateOutgoing", "channelId": 1,
                        "streaming": {"status": "CONNECTED"}}))
        vigia.al_recibir(
            json.dumps({"action": "updateOutgoing", "channelId": 1,
                        "streaming": {"status": "CONNECTING"}}))

        self.assertIn(("TikTok: szeiryuGaming se desconectó.",
                       "restream_destino_caido"), anuncios)

    def test_al_terminar_detiene_la_vigia(self):
        perfil = _perfil("Uno", "horizontal", (1,))
        canales = [_canal(1, "YouTube")]
        frame, _cuenta, creados, _anuncios = self._supervisar(perfil, canales)

        creados[0].kwargs["al_terminar"]()

        self.assertTrue(frame._vigilas_prueba[0].detenida)

    def test_con_el_supervisor_deteniendo_no_anuncia_la_caida(self):
        perfil = _perfil("Uno", "horizontal", (1,))
        canales = [_canal(1, "YouTube")]
        frame, _cuenta, creados, anuncios = self._supervisar(perfil, canales)
        vigia = frame._vigilas_prueba[0]

        vigia.al_recibir(
            json.dumps({"action": "updateOutgoing", "channelId": 1,
                        "streaming": {"status": "CONNECTED"}}))
        creados[0].deteniendo = True
        vigia.al_recibir(
            json.dumps({"action": "updateOutgoing", "channelId": 1,
                        "streaming": {"status": "CONNECTING"}}))

        self.assertEqual(anuncios, [])
        self.assertFalse(vigia.debe_seguir())

    def test_al_terminar_restaura_los_canales_cambiados(self):
        perfil = _perfil("Uno", "horizontal", (1, 2))
        canales = [_canal(1, "YouTube", False), _canal(2, "TikTok", False),
                   _canal(3, "YouTube", True)]
        with mock.patch.object(ganchos.obs_destinos, "preparar_destino"):
            frame, cuenta, creados, _anuncios = self._supervisar(perfil,
                                                                 canales)
            supervisor = creados[0]
            supervisor.kwargs["preparar_emision"](None)

        self.assertEqual(cuenta.llamadas.count(("canales",)), 1)
        supervisor.kwargs["al_terminar"]()

        self.assertEqual(cuenta.llamadas[-3:], [
            ("activar", 1, False),
            ("activar", 2, False),
            ("activar", 3, True),
        ])
        frame._al_terminar_supervisor.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
