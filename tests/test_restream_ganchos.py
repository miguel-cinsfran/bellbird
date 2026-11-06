"""Pruebas de los ganchos de Restream antes de iniciar OBS."""

import unittest
from types import SimpleNamespace
from unittest import mock

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
                 sesion_conectada=True):
        self._canales = list(canales)
        self._clave = clave or api.ClaveCuenta(
            clave="clave-secreta", servidor=api.SERVIDOR_RTMP)
        self._fallo_clave = fallo_clave
        self._conectada = sesion_conectada
        self.llamadas = []
        self.fallar_restauracion = False

    def sesion(self):
        return SimpleNamespace(conectada=lambda: self._conectada)

    def canales(self):
        self.llamadas.append(("canales",))
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


def _armar(opcion, cuenta, perfil, escritor=None):
    anuncios = []
    preparar, restaurar, contexto = ganchos.armar(
        opcion, lambda frase, sonido: anuncios.append((frase, sonido)),
        cuenta_mod=cuenta, perfiles=[perfil],
        escribir=escritor or EscritorFalso())
    return preparar, restaurar, contexto, anuncios


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
        preparar, _restaurar, contexto, anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor)

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
        self.assertEqual(contexto.destino, "TikTok")
        self.assertFalse(contexto.sin_tiktok)

    def test_el_titulo_no_se_toca_si_el_perfil_no_lo_tiene(self):
        perfil = _perfil(canales=(1,), titulo="")
        canales = [_canal(1, "YouTube", False)]
        cuenta = CuentaFalsa(canales)
        preparar, _restaurar, _contexto, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)
        self.assertNotIn("meta", [llamada[0] for llamada in cuenta.llamadas])

    def test_el_usuario_sale_del_canal_de_tiktok_del_perfil(self):
        perfil = _perfil("Uno", "vertical", (1, 2))
        canales = [
            _canal(1, "YouTube", False),
            _canal(2, "TikTok", False,
                   url="https://www.tiktok.com/@amigo"),
        ]
        cuenta = CuentaFalsa(canales)
        preparar, _restaurar, contexto, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)
        self.assertEqual(contexto.destino, "TikTok")
        self.assertEqual(contexto.usuario, "amigo")
        self.assertFalse(contexto.sin_tiktok)

    def test_sin_tiktok_usa_el_destino_de_obs_y_usuario_vacio(self):
        perfil = _perfil("Uno", "horizontal", (1,))
        canales = [_canal(1, "YouTube", False)]
        cuenta = CuentaFalsa(canales)
        preparar, _restaurar, contexto, _anuncios = _armar(
            "restream:Uno", cuenta, perfil)
        preparar(None)
        self.assertEqual(contexto.destino, "YouTube")
        self.assertEqual(contexto.usuario, "")
        self.assertTrue(contexto.sin_tiktok)

    def test_falla_la_clave_restaura_lo_cambiado_y_no_escribe_obs(self):
        perfil = _perfil(canales=(1, 2))
        canales = [_canal(1, "YouTube", False), _canal(2, "TikTok", False),
                   _canal(3, "YouTube", True)]
        mensaje = ("No se pudo leer la clave de transmisión de Restream. "
                   "Vuelve a intentarlo.")
        cuenta = CuentaFalsa(canales, fallo_clave=api.ErrorApi(mensaje))
        escritor = EscritorFalso()
        preparar, restaurar, _contexto, _anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor)

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
        preparar, _restaurar, _contexto, _anuncios = _armar(
            "restream:Uno", cuenta, perfil, escritor)

        with self.assertRaises(EmisionError):
            preparar(None)

        self.assertEqual(cuenta.llamadas[-1], ("activar", 1, False))


class TestRestauracion(unittest.TestCase):

    def test_restaura_cada_canal_cambiado_una_sola_vez(self):
        perfil = _perfil(canales=(1, 2))
        canales = [_canal(1, "YouTube", False), _canal(2, "TikTok", False),
                   _canal(3, "YouTube", True)]
        cuenta = CuentaFalsa(canales)
        preparar, restaurar, _contexto, _anuncios = _armar(
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
        preparar, restaurar, _contexto, _anuncios = _armar(
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

    def test_armar_reusa_el_contexto_que_leen_los_avisos(self):
        perfil = _perfil(canales=(1,))
        cuenta = CuentaFalsa([_canal(1, "YouTube", False)])
        anuncios = []
        contexto = ganchos.Contexto()
        envoltura = ganchos.envolver_anunciar(
            lambda frase, sonido: anuncios.append((frase, sonido)), contexto)

        preparar, _restaurar, devuelto = ganchos.armar(
            "restream:Uno", envoltura, cuenta_mod=cuenta, perfiles=[perfil],
            escribir=EscritorFalso(), contexto=contexto)
        preparar(None)
        envoltura("OBS está enviando la señal a YouTube.", "conectado")

        self.assertIs(devuelto, contexto)
        self.assertIn((ganchos._(ganchos.MENSAJE_NO_TIKTOK), "al_aire"),
                      anuncios)

    def test_sin_tiktok_avisa_al_aire_cuando_obs_ya_transmite(self):
        anuncios = []
        contexto = ganchos.Contexto()
        contexto.sin_tiktok = True
        contexto.destino_sup = "YouTube"
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido: anuncios.append((frase, sonido)), contexto)

        anunciar("OBS está enviando la señal a YouTube.", "conectado")

        self.assertIn((ganchos._(ganchos.MENSAJE_NO_TIKTOK), "al_aire"),
                      anuncios)

    def test_con_tiktok_no_avisa_la_conexion_manual(self):
        anuncios = []
        contexto = ganchos.Contexto()
        contexto.sin_tiktok = False
        contexto.destino_sup = "TikTok"
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido: anuncios.append((frase, sonido)), contexto)

        anunciar("OBS está enviando la señal a Restream.", "conectado")

        self.assertEqual(anuncios,
                         [("OBS está enviando la señal a Restream.",
                           "conectado")])

    def test_no_repite_el_anuncio_de_youtube_antes_de_preparar(self):
        anuncios = []
        contexto = ganchos.Contexto()
        contexto.sin_tiktok = True
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido: anuncios.append((frase, sonido)), contexto)

        anunciar("Creando el directo en YouTube.", None)
        anunciar("Preparando Restream para Uno.", "conectando")

        self.assertEqual(anuncios,
                         [("Preparando Restream para Uno.", "conectando")])

    def test_sin_tiktok_en_vertical_descarta_el_aviso_de_usuario(self):
        anuncios = []
        contexto = ganchos.Contexto()
        contexto.sin_tiktok = True
        contexto.destino_sup = "TikTok"
        anunciar = ganchos.envolver_anunciar(
            lambda frase, sonido: anuncios.append((frase, sonido)), contexto)

        anunciar("OBS está enviando la señal a Restream.", "conectado")
        anunciar("No hay usuario de TikTok guardado: conecta el chat "
                 "manualmente.", None)

        self.assertEqual(
            [texto for texto, _sonido in anuncios],
            ["OBS está enviando la señal a Restream.",
             ganchos._(ganchos.MENSAJE_NO_TIKTOK)])


if __name__ == "__main__":
    unittest.main()
