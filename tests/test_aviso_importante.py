"""Avisos importantes: decisión, sonido, cuadro y cableado de cada acción.

Las pruebas que abren ventanas se saltan fuera de Windows. La del cuadro real
usa el mismo patrón que `tests.test_confirmar.TestCuadrosReales`.
"""

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import wx

from guyrapu.core import config
from guyrapu.core import config_predeterminada
from guyrapu.core.idioma import _
from guyrapu.music import anuncios as anuncios_musica
from guyrapu.ui import aviso_importante
from guyrapu.ui import boton_directo
from guyrapu.ui import buscador_acciones
from guyrapu.ui import confirmar
from guyrapu.ui import control_grabacion
from guyrapu.ui import gui
from guyrapu.ui import gui_comentarios
from guyrapu.ui import gui_directo_huerfano
from guyrapu.ui import gui_musica
from guyrapu.ui import operaciones_obs
from guyrapu.ui import preferencias_api
from guyrapu.restream import ganchos
from tests import cuadros_reales_permitidos
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import app_de_prueba

if sys.platform == "win32":
    from tests.test_confirmar import (
        _botones, _cerrar_con_escape, _hwnd_del_cuadro)


def _limpiar_cuadro():
    aviso_importante._cuadro_abierto = False


class TestDecision(unittest.TestCase):
    """La parte pura que decide entre cuadro y anuncio."""

    def test_casilla_apagada_anuncia_aunque_no_haya_cuadro(self):
        self.assertEqual(aviso_importante.decidir(False, False), "anuncio")
        self.assertEqual(aviso_importante.decidir(False, True), "anuncio")

    def test_casilla_encendida_sin_cuadro_abre_cuadro(self):
        self.assertEqual(aviso_importante.decidir(True, False), "cuadro")

    def test_casilla_encendida_con_cuadro_abierto_anuncia(self):
        self.assertEqual(aviso_importante.decidir(True, True), "anuncio")


class TestAvisar(unittest.TestCase):

    def setUp(self):
        _limpiar_cuadro()
        self.addCleanup(_limpiar_cuadro)

    def _llamar(self, **opciones):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=opciones.get("casilla", False)), \
                mock.patch.object(aviso_importante, "anunciar") as anunciar, \
                mock.patch.object(aviso_importante.sound_player,
                                  "reproducir") as sonar, \
                mock.patch.object(confirmar, "avisar") as cuadro, \
                mock.patch.object(aviso_importante.wx, "CallAfter") as diferir:
            aviso_importante.avisar(
                opciones.get("texto", "Listo."),
                opciones.get("sonido", "copiar"),
                error=opciones.get("error", False))
        return anunciar, sonar, cuadro, diferir

    def test_casilla_apagada_suena_y_anuncia_sin_cuadro(self):
        anunciar, sonar, cuadro, diferir = self._llamar(casilla=False)
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Listo.")
        cuadro.assert_not_called()
        diferir.assert_not_called()

    def test_casilla_encendida_suena_y_abre_cuadro_sin_anunciar(self):
        anunciar, sonar, cuadro, diferir = self._llamar(casilla=True)
        sonar.assert_called_once_with("copiar")
        anunciar.assert_not_called()
        cuadro.assert_not_called()
        diferir.assert_called_once()
        self.assertTrue(aviso_importante._cuadro_abierto)

    def test_cuadro_se_arma_con_titulo_aceptar_e_icono(self):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=True), \
                mock.patch.object(aviso_importante.sound_player,
                                  "reproducir"), \
                mock.patch.object(confirmar, "avisar") as cuadro, \
                mock.patch.object(aviso_importante.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            aviso_importante.avisar("Falló.", "error", error=True)
        padre, texto, titulo, etiqueta = cuadro.call_args.args
        self.assertEqual(texto, "Falló.")
        self.assertEqual(titulo, "Guyrapu")
        self.assertEqual(etiqueta, "Aceptar")
        self.assertEqual(cuadro.call_args.kwargs["icono"],
                         confirmar.ICON_ERROR)

    def test_segundo_aviso_con_el_cuadro_abierto_se_anuncia(self):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=True), \
                mock.patch.object(aviso_importante, "anunciar") as anunciar, \
                mock.patch.object(aviso_importante.sound_player,
                                  "reproducir") as sonar, \
                mock.patch.object(aviso_importante.wx, "CallAfter") as diferir:
            aviso_importante.avisar("Primero.")
            aviso_importante.avisar("Segundo.")
        sonar.assert_not_called()
        self.assertEqual(anunciar.call_args_list,
                         [mock.call("Segundo.")])
        self.assertEqual(diferir.call_count, 1)

    def test_lee_la_casilla_de_la_ventana_principal(self):
        with mock.patch.object(confirmar, "avisar") as cuadro,                 mock.patch.object(aviso_importante, "anunciar") as anunciar,                 mock.patch.object(aviso_importante.sound_player,
                                  "reproducir"),                 mock.patch.object(aviso_importante.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            with mock.patch.object(
                    gui, "_gui_frame",
                    SimpleNamespace(_config={"avisos_cuadro": True})):
                aviso_importante.avisar("Listo.")
            anunciar.assert_not_called()
            cuadro.assert_called_once()
            _limpiar_cuadro()
            with mock.patch.object(
                    gui, "_gui_frame",
                    SimpleNamespace(_config={"avisos_cuadro": False})):
                aviso_importante.avisar("Listo.")
        anunciar.assert_called_once_with("Listo.")
        cuadro.assert_called_once()

    def test_desde_otro_hilo_el_cuadro_se_pide_por_callafter(self):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=True), \
                mock.patch.object(aviso_importante, "anunciar") as anunciar, \
                mock.patch.object(aviso_importante.sound_player,
                                  "reproducir"), \
                mock.patch.object(aviso_importante.wx, "CallAfter") as diferir:
            hilo = threading.Thread(
                target=aviso_importante.avisar, args=("Desde el hilo.",))
            hilo.start()
            hilo.join()
        anunciar.assert_not_called()
        self.assertEqual(diferir.call_count, 1)
        self.assertTrue(aviso_importante._cuadro_abierto)


class TestCasillaDePreferencias(unittest.TestCase):

    def test_viene_desactivada_de_fabrica(self):
        self.assertEqual(
            config_predeterminada.obtener("ui", "avisos_cuadro"), "false")

    def test_se_guarda_y_se_relee(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "config.ini"
            ruta.write_text("[ui]\navisos_cuadro = true\n", encoding="utf-8")
            with redirigir_rutas(Path(temporal)):
                cargada = config.cargar_configuracion()
        self.assertTrue(cargada["avisos_cuadro"])

    def test_sin_la_clave_queda_desactivada(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "config.ini"
            ruta.write_text(config._CONFIG_FALLBACK, encoding="utf-8")
            with redirigir_rutas(Path(temporal)):
                cargada = config.cargar_configuracion()
        self.assertFalse(cargada["avisos_cuadro"])


class TestCableado(unittest.TestCase):
    """Cada grupo pide el cuadro con el texto que ya decía."""

    def setUp(self):
        _limpiar_cuadro()
        self.addCleanup(_limpiar_cuadro)

    def _pedir(self, funcion):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=True), \
                mock.patch.object(aviso_importante, "anunciar") as anunciar, \
                mock.patch.object(aviso_importante.sound_player,
                                  "reproducir") as sonar, \
                mock.patch.object(confirmar, "avisar") as cuadro, \
                mock.patch.object(aviso_importante.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            funcion()
        return cuadro, anunciar, sonar

    def _texto(self, cuadro):
        return cuadro.call_args.args[1]

    def test_a_falta_la_cuenta_de_restream(self):
        frame = SimpleNamespace(_alive=True)
        cuenta = mock.Mock()
        with mock.patch.object(ganchos, "cuenta_conectada",
                               return_value=False):
            cuadro, _anunciar, sonar = self._pedir(
                lambda: ganchos.supervisar_restream(
                    frame, "restream", cuenta_mod=cuenta))
        self.assertEqual(self._texto(cuadro), _(ganchos.MENSAJE_SIN_CUENTA))
        sonar.assert_any_call("transmision_problema")

    def test_b_detener_la_transmision(self):
        instancia = object.__new__(boton_directo.BotonDirecto)
        instancia._marco = SimpleNamespace(
            _alive=True, _obs_transmitiendo=True,
            _actualizar_boton_directo=lambda: None)
        cuadro, _anunciar, sonar = self._pedir(instancia._finalizada)
        self.assertEqual(self._texto(cuadro), _("Transmisión detenida."))
        sonar.assert_any_call("desconectado")

    def test_c_resultado_de_grabacion(self):
        instancia = object.__new__(control_grabacion.ControlGrabacion)
        instancia._al_cambiar = lambda: None
        cuadro, _anunciar, sonar = self._pedir(
            lambda: instancia._resultado("grabacion_iniciada"))
        self.assertEqual(self._texto(cuadro), "Grabación iniciada")
        sonar.assert_any_call("grabacion_iniciada")

    def test_d_comentario_publicado(self):
        cuadro, _anunciar, sonar = self._pedir(
            lambda: gui_comentarios.ComentariosPanel._escritura_ok(
                None, "Comentario publicado"))
        self.assertEqual(
            self._texto(cuadro),
            "Comentario publicado. Recuerda que YouTube puede tardar o "
            "retenerlo.")
        sonar.assert_any_call("comentario")

    def test_e_sesion_cerrada(self):
        instancia = SimpleNamespace(_api_refrescar_estado=lambda: None)
        with mock.patch.object(preferencias_api.credenciales,
                               "cerrar_sesion"):
            cuadro, _anunciar, sonar = self._pedir(
                lambda: preferencias_api.PaginaApi._api_logout(instancia, None))
        self.assertEqual(self._texto(cuadro), _("Sesión cerrada."))
        sonar.assert_any_call("desconectado")

    def test_f_directo_huerfano_finalizado(self):
        frame = SimpleNamespace(_alive=True)
        cuadro, _anunciar, sonar = self._pedir(
            lambda: gui_directo_huerfano._anunciar_fin(frame, 1))
        self.assertEqual(self._texto(cuadro), _("Directo finalizado en YouTube."))
        sonar.assert_any_call("desconectado")

    def test_g_descargas_agregadas(self):
        cuadro, _anunciar, sonar = self._pedir(
            lambda: buscador_acciones.anunciar_agregados(
                1, "Mi vídeo", True))
        self.assertEqual(self._texto(cuadro), "Descargando: Mi vídeo")
        sonar.assert_any_call("descarga_encolada")

    def test_h_lista_creada(self):
        instancia = object.__new__(gui_musica.ControlMusica)
        cuadro, _anunciar, sonar = self._pedir(
            lambda: instancia._avisar(
                anuncios_musica.aviso_lista_creada("Mi lista")))
        self.assertEqual(self._texto(cuadro), "Lista creada: Mi lista")
        sonar.assert_not_called()

    def test_i_fallo_de_una_operacion_de_obs(self):
        instancia = SimpleNamespace(
            cerrando=False, en_vuelo=False,
            _temporizador_consulta=mock.Mock(),
            _activar=lambda activo: None,
            _escribir_fallo=lambda mensaje: None,
            _enfocar_tras_fallo=lambda: None)
        cuadro, _anunciar, sonar = self._pedir(
            lambda: operaciones_obs.OperacionesObs.fallo(instancia, "Falló."))
        self.assertEqual(self._texto(cuadro), "Falló.")
        self.assertEqual(cuadro.call_args.kwargs["icono"],
                         confirmar.ICON_ERROR)
        sonar.assert_any_call("error")

    def test_no_revisando_obs_no_pide_cuadro(self):
        instancia = object.__new__(boton_directo.BotonDirecto)
        instancia._marco = SimpleNamespace(
            _alive=True,
            _config={},
            _guardar_destino_transmision=lambda destino: None)
        instancia.boton = mock.Mock()
        instancia._deteniendo = False
        instancia._transmitiendo = False
        with mock.patch("guyrapu.ui.gui_elegir_destino.pedir_destino",
                        return_value=("YouTube", "")), \
                mock.patch.object(boton_directo.diagnostico, "crear_hilo",
                                  return_value=mock.Mock()), \
                mock.patch.object(boton_directo, "anunciar") as anunciar, \
                mock.patch.object(aviso_importante, "_casilla_activa",
                                  return_value=True), \
                mock.patch.object(aviso_importante.wx, "CallAfter"), \
                mock.patch.object(confirmar, "avisar") as cuadro:
            instancia._transmitir()
        anunciar.assert_any_call(_("Revisando OBS antes de transmitir."))
        cuadro.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "solo Windows")
class TestCuadroReal(unittest.TestCase):
    """El cuadro de verdad: botón Aceptar y salida por Escape."""

    def setUp(self):
        self.app = app_de_prueba()
        _limpiar_cuadro()
        self.addCleanup(_limpiar_cuadro)
        self.enterContext(cuadros_reales_permitidos())

    def _abrir_y_leer(self, accion):
        capturado = {}

        def leer(intentos=20):
            hwnd = _hwnd_del_cuadro("Guyrapu")
            if not hwnd and intentos:
                wx.CallLater(100, leer, intentos - 1)
                return
            if hwnd:
                textos, botones = _botones(hwnd)
                capturado["textos"] = textos
                _cerrar_con_escape(hwnd, botones, capturado)

        wx.CallLater(300, leer)
        resultado = accion()
        wx.SafeYield()
        return resultado, capturado

    def test_abre_lee_aceptar_y_cierra_con_escape(self):
        with mock.patch.object(aviso_importante, "_casilla_activa",
                               return_value=True):
            _resultado, capturado = self._abrir_y_leer(
                lambda: aviso_importante.avisar("Listo."))
        self.assertEqual(capturado.get("textos"), ["Aceptar"])
        self.assertFalse(capturado.get("escape_fallo", False))
        self.assertFalse(aviso_importante._cuadro_abierto)


if __name__ == "__main__":
    unittest.main()
