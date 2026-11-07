"""El ayudante de confirmaciones y los textos de cada cuadro que lo usa.

Los dos últimos cuadros son reales y solo corren en Windows: abren el
diálogo nativo, leen el texto de sus botones y lo cierran con Escape.
"""

import ctypes
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from tests import cuadros_reales_permitidos
from tests.ventanas_prueba import app_de_prueba
from guyrapu.core.idioma import _
from guyrapu.ui import confirmar

if sys.platform == "win32":
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    EnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.FindWindowW.restype = wintypes.HWND
    user32.EnumChildWindows.argtypes = (
        wintypes.HWND, EnumProc, wintypes.LPARAM)
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = (
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetFocus.argtypes = ()
    user32.GetFocus.restype = wintypes.HWND
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.restype = wintypes.BOOL
else:
    user32 = None
    EnumProc = None


class DobleDialogo:
    """Cuadro falso: registra lo que recibe, sin abrir ninguna ventana."""

    ultimo = None
    respuesta = None

    def __init__(self, padre, mensaje, titulo, estilo):
        self.padre = padre
        self.mensaje = mensaje
        self.titulo = titulo
        self.estilo = estilo
        self.etiquetas_ok_cancel = None
        self.etiqueta_ok = None
        self.destruido = False
        DobleDialogo.ultimo = self

    def SetOKCancelLabels(self, etiqueta_ok, etiqueta_cancel):
        self.etiquetas_ok_cancel = (etiqueta_ok, etiqueta_cancel)

    def SetOKLabel(self, etiqueta):
        self.etiqueta_ok = etiqueta

    def ShowModal(self):
        return self.respuesta

    def Destroy(self):
        self.destruido = True


class TestPreguntar(unittest.TestCase):

    def _correr(self, respuesta, **opciones):
        DobleDialogo.respuesta = respuesta
        with mock.patch.object(confirmar, "MessageDialog", DobleDialogo):
            resultado = confirmar.preguntar(
                "padre", "¿Seguir?", "Título", "&Acción", "&Cancelar",
                **opciones)
        return resultado, DobleDialogo.ultimo

    def test_si_devuelve_verdadero_con_las_dos_etiquetas(self):
        resultado, dialogo = self._correr(confirmar.ID_OK)
        self.assertTrue(resultado)
        self.assertEqual(dialogo.etiquetas_ok_cancel,
                         ("&Acción", "&Cancelar"))
        self.assertTrue(dialogo.estilo & confirmar.OK)
        self.assertTrue(dialogo.estilo & confirmar.CANCEL)
        self.assertFalse(dialogo.estilo & confirmar.CANCEL_DEFAULT)
        self.assertTrue(dialogo.destruido)

    def test_no_devuelve_falso(self):
        resultado, _dialogo = self._correr(confirmar.ID_CANCEL)
        self.assertFalse(resultado)

    def test_predeterminado_no_y_centrado(self):
        _resultado, dialogo = self._correr(
            confirmar.ID_CANCEL, predeterminado_si=False, centrar=True)
        self.assertTrue(dialogo.estilo & confirmar.CANCEL_DEFAULT)
        self.assertTrue(dialogo.estilo & confirmar.CENTRE)

    def test_icono_elegido(self):
        _resultado, dialogo = self._correr(
            confirmar.ID_CANCEL, icono=confirmar.ICON_ERROR)
        self.assertTrue(dialogo.estilo & confirmar.ICON_ERROR)
        self.assertFalse(dialogo.estilo & confirmar.ICON_QUESTION)

    def test_avisar_usa_ok_y_la_etiqueta_dada(self):
        DobleDialogo.respuesta = confirmar.OK
        with mock.patch.object(confirmar, "MessageDialog", DobleDialogo):
            confirmar.avisar("padre", "Listo", "Título", "&Aceptar",
                             icono=confirmar.ICON_INFORMATION)
        dialogo = DobleDialogo.ultimo
        self.assertEqual(dialogo.etiqueta_ok, "&Aceptar")
        self.assertTrue(dialogo.estilo & confirmar.OK)
        self.assertTrue(dialogo.estilo & confirmar.ICON_INFORMATION)
        self.assertTrue(dialogo.destruido)


class TestCuadrosDeP1(unittest.TestCase):

    def test_salir_de_la_aplicacion(self):
        from guyrapu.ui import gui

        frame = mock.Mock()
        frame._apagando = False
        frame._cerrar_sin_preguntar = False
        frame._config = {"confirmar_salida": True}
        frame._conectado = True
        frame._supervisor = None
        frame._obs_transmitiendo = False
        evento = mock.Mock()
        evento.CanVeto.return_value = True
        gestor = mock.Mock()
        gestor.lista.return_value = []
        with mock.patch.object(gui, "gestor", return_value=gestor), \
                mock.patch.object(gui.confirmar, "preguntar",
                                  return_value=False) as preguntar:
            gui.VentanaPrincipal._on_close(frame, evento)
        preguntar.assert_called_once_with(
            frame, mock.ANY, _("Salir"), _("&Salir"), _("&Cancelar"),
            predeterminado_si=False, centrar=True)
        evento.Veto.assert_called_once_with()

    def test_abrir_la_carpeta_al_terminar_las_descargas(self):
        from guyrapu.ui import descargas_acciones

        with mock.patch.object(descargas_acciones.confirmar, "preguntar",
                               return_value=False) as preguntar:
            descargas_acciones._preguntar_carpeta("C:/Descargas", None)
        preguntar.assert_called_once_with(
            None, _("Descargas terminadas. ¿Abrir la carpeta?"),
            _("Administrador de descargas"), _("&Abrir carpeta"),
            _("Ahora &no"))

    def test_vaciar_la_lista_de_descargas(self):
        from guyrapu.ui import descargas_acciones

        acciones = descargas_acciones.AccionesDescarga(
            mock.Mock(), "C:/historial.json", lambda: None, lambda: None)
        with mock.patch.object(descargas_acciones.historial_descargas,
                               "cargar", return_value=[{"estado": "completado"}]), \
                mock.patch.object(descargas_acciones.confirmar, "preguntar",
                                  return_value=False) as preguntar:
            acciones.vaciar(None)
        preguntar.assert_called_once_with(
            None, mock.ANY, _("Vaciar lista"), _("&Vaciar lista"),
            _("&Cancelar"), icono=confirmar.ICON_WARNING,
            predeterminado_si=False)

    def test_un_video_ya_en_el_historial(self):
        from guyrapu.ui import gui_descargas

        with mock.patch.object(gui_descargas.historial_descargas, "cargar",
                               return_value=[]), \
                mock.patch.object(gui_descargas.filas_descargas,
                                  "ya_descargado", return_value=True), \
                mock.patch.object(gui_descargas.confirmar, "preguntar",
                                  return_value=False) as preguntar:
            gui_descargas._pedidos_nuevos(["uno"], None)
        preguntar.assert_called_once_with(
            None, _("Este vídeo ya está en el historial. "
                    "¿Agregar de todos modos?"),
            _("Administrador de descargas"), _("&Agregar"),
            _("&No agregar"), predeterminado_si=False)

    def test_varios_videos_ya_en_el_historial(self):
        from guyrapu.ui import gui_descargas

        with mock.patch.object(gui_descargas.historial_descargas, "cargar",
                               return_value=[]), \
                mock.patch.object(gui_descargas.filas_descargas,
                                  "ya_descargado", return_value=True), \
                mock.patch.object(gui_descargas.confirmar, "preguntar",
                                  return_value=False) as preguntar:
            gui_descargas._pedidos_nuevos(["uno", "dos"], None)
        preguntar.assert_called_once_with(
            None, _("2 ya están en el historial. ¿Agregar de todos modos?"),
            _("Administrador de descargas"), _("&Agregar todos"),
            _("Solo los &nuevos"), predeterminado_si=False)

    def test_moderar_con_suspension(self):
        from guyrapu.ui import gui_envio_chat

        frame = mock.Mock()
        with mock.patch.object(gui_envio_chat.confirmar, "preguntar",
                               return_value=False) as preguntar:
            gui_envio_chat.moderar(frame, "Ana", "CANAL", 300)
        preguntar.assert_called_once_with(
            frame, _("¿Suspender temporalmente a Ana durante 5 minutos?"),
            _("Confirmar moderación"), _("&Suspender"), _("&Cancelar"))

    def test_moderar_con_ocultacion(self):
        from guyrapu.ui import gui_envio_chat

        frame = mock.Mock()
        with mock.patch.object(gui_envio_chat.confirmar, "preguntar",
                               return_value=False) as preguntar:
            gui_envio_chat.moderar(frame, "Ana", "CANAL", None)
        preguntar.assert_called_once_with(
            frame, _("¿Ocultar a Ana en el canal de YouTube? "
                     "Se puede deshacer desde YouTube Studio."),
            _("Confirmar moderación"), _("&Ocultar"), _("&Cancelar"))

    def test_sesion_de_youtube_caducada(self):
        from guyrapu.ui import gui_preferencias

        with mock.patch.object(gui_preferencias.confirmar, "preguntar",
                               return_value=False) as preguntar:
            self.assertFalse(gui_preferencias.ofrecer_iniciar_sesion(None, {}))
        preguntar.assert_called_once_with(
            None, _("Tu sesión de YouTube caducó. ¿Abrir Preferencias para "
                    "volver a iniciar sesión?"),
            _("Sesión caducada"), _("&Abrir Preferencias"), _("Ahora &no"))

    def test_privacidad_de_la_ia(self):
        from guyrapu.ui import ia_privacidad

        ajustes = SimpleNamespace(privacidad_aceptada=False)
        with mock.patch.object(ia_privacidad.confirmaciones, "preguntar",
                               return_value=False) as preguntar:
            self.assertFalse(
                ia_privacidad.confirmar(None, ajustes, "OpenAI"))
        preguntar.assert_called_once_with(
            None, _("La captura de la escena y lo que escribas se envían "
                    "a OpenAI para que responda. Este aviso aparece una "
                    "sola vez. ¿Enviar?"),
            _("Privacidad"), _("&Enviar"), _("&Cancelar"),
            icono=confirmar.ICON_INFORMATION, predeterminado_si=False)

    def test_eliminar_una_lista_de_musica(self):
        from guyrapu.music import anuncios
        from guyrapu.ui import musica_ventana_acciones

        with mock.patch.object(musica_ventana_acciones.confirmar, "preguntar",
                               return_value=False) as preguntar:
            self.assertFalse(
                musica_ventana_acciones._confirmar_borrar(None, "Rock"))
        preguntar.assert_called_once_with(
            None, _(anuncios.TEXTO_CONFIRMAR_BORRAR_LISTA).format(
                nombre="Rock"),
            _("Música"), _("&Eliminar"), _("&Cancelar"),
            predeterminado_si=False)

    def test_restablecer_las_preferencias(self):
        from guyrapu.ui import preferencias_general

        pagina = SimpleNamespace(_ventana=mock.Mock())
        with mock.patch.object(preferencias_general.confirmar, "preguntar",
                               return_value=False) as preguntar:
            preferencias_general.PaginaGeneral._restablecer_prefs(pagina, None)
        preguntar.assert_called_once_with(
            pagina._ventana,
            _("¿Restablecer todas las preferencias a los valores "
              "de fábrica? Se guarda una copia de las actuales en "
              "la carpeta de datos."),
            _("Restablecer las preferencias"), _("&Restablecer"),
            _("&Cancelar"), predeterminado_si=False, centrar=True)

    def test_los_avisos_de_restablecer_dicen_aceptar(self):
        from guyrapu.ui import preferencias_general

        for fallo, icono in ((None, confirmar.ICON_INFORMATION),
                             (OSError("sin disco"), confirmar.ICON_ERROR)):
            with self.subTest(icono=icono):
                pagina = SimpleNamespace(_ventana=mock.Mock())
                restablecer = mock.patch.object(
                    preferencias_general.preferencias_archivo, "restablecer",
                    side_effect=fallo)
                with mock.patch.object(preferencias_general.confirmar,
                                       "preguntar", return_value=True), \
                        restablecer, \
                        mock.patch.object(preferencias_general.confirmar,
                                          "avisar") as avisar:
                    preferencias_general.PaginaGeneral._restablecer_prefs(
                        pagina, None)
                avisar.assert_called_once_with(
                    pagina._ventana, mock.ANY, mock.ANY, _("&Aceptar"),
                    icono=icono)

    def test_eliminar_la_clave_de_la_ia(self):
        from guyrapu.ai import opciones_ia
        from guyrapu.ui import preferencias_ia_clave

        proveedor = SimpleNamespace(id="gemini", nombre="Gemini")
        seccion = preferencias_ia_clave.SeccionClaveIA(
            lambda: proveedor, lambda: None)
        seccion._panel = "panel"
        seccion.btn_borrar = mock.Mock()
        with mock.patch.object(preferencias_ia_clave.confirmar, "preguntar",
                               return_value=False) as preguntar:
            seccion._on_borrar(None)
        preguntar.assert_called_once_with(
            "panel", opciones_ia.TEXTO_CONFIRMAR_BORRADO.format(
                proveedor="Gemini"),
            _("Eliminar clave"), _("&Eliminar clave"), _("&Cancelar"),
            icono=confirmar.ICON_WARNING, predeterminado_si=False)
        seccion.btn_borrar.SetFocus.assert_called_once_with()

    def test_eliminar_un_destino_de_restream(self):
        from guyrapu.ui import restream_pagina_destinos

        pagina = mock.Mock()
        pagina.pregunta.return_value = "¿Eliminar TikTok: uno?"
        with mock.patch.object(restream_pagina_destinos.confirmar, "preguntar",
                               return_value=False) as preguntar:
            self.assertFalse(
                restream_pagina_destinos.PaginaDestinos.confirmar(
                    pagina, "TikTok: uno"))
        preguntar.assert_called_once_with(
            pagina, "¿Eliminar TikTok: uno?", _("Eliminar destino"),
            _("&Eliminar"), _("&Cancelar"), predeterminado_si=False)

    def test_desconectar_la_cuenta_de_restream(self):
        from guyrapu.ui import restream_pagina_cuenta

        pagina = mock.Mock()
        with mock.patch.object(restream_pagina_cuenta.confirmar, "preguntar",
                               return_value=False) as preguntar:
            restream_pagina_cuenta.PaginaCuenta._desconectar(pagina)
        preguntar.assert_called_once_with(
            pagina,
            _("¿Desconectar la cuenta de Restream? Para volver a usarla hay "
              "que iniciar sesión otra vez en el navegador."),
            _("Desconectar cuenta"), _("&Desconectar"), _("&Cancelar"),
            predeterminado_si=False)
        pagina._al_desconectar.assert_not_called()

    def test_eliminar_un_perfil_de_restream(self):
        from guyrapu.ui import restream_pagina_perfiles

        pagina = mock.Mock()
        perfil = SimpleNamespace(nombre="Canal")
        with mock.patch.object(restream_pagina_perfiles.confirmar, "preguntar",
                               return_value=False) as preguntar:
            self.assertFalse(
                restream_pagina_perfiles.PaginaPerfiles.confirmar(
                    pagina, perfil))
        preguntar.assert_called_once_with(
            pagina, _("¿Eliminar el perfil {nombre}?").format(nombre="Canal"),
            _("Eliminar perfil"), _("&Eliminar"), _("&Cancelar"),
            predeterminado_si=False)

    def test_finalizar_el_directo(self):
        from guyrapu.ui import confirmar_transmision

        DobleDialogo.respuesta = confirmar.ID_CANCEL
        with mock.patch.object(confirmar, "MessageDialog", DobleDialogo):
            self.assertFalse(
                confirmar_transmision.confirmar_finalizar("padre"))
        dialogo = DobleDialogo.ultimo
        self.assertEqual(dialogo.mensaje,
                         _("¿Finalizar el directo? Quienes te están viendo "
                           "dejarán de verte."))
        self.assertEqual(dialogo.titulo, _("Finalizar directo"))
        self.assertEqual(dialogo.etiquetas_ok_cancel,
                         (_("&Finalizar directo"),
                          _("&Seguir transmitiendo")))
        self.assertTrue(dialogo.estilo & confirmar.CANCEL_DEFAULT)
        self.assertTrue(dialogo.estilo & confirmar.ICON_QUESTION)

    def test_directo_sin_imagen(self):
        from guyrapu.ui import gui_directo_huerfano

        frame = SimpleNamespace(
            _alive=True,
            _supervisar_transmision=mock.Mock(return_value=False))
        DobleDialogo.respuesta = confirmar.ID_CANCEL
        with mock.patch.object(confirmar, "MessageDialog", DobleDialogo), \
                mock.patch.object(gui_directo_huerfano, "anunciar") as anunciar, \
                mock.patch.object(gui_directo_huerfano.diagnostico,
                                  "crear_hilo") as crear_hilo:
            gui_directo_huerfano._preguntar(frame, [("vid1", "Charla")])
        crear_hilo.assert_not_called()
        anunciar.assert_called_once_with(_("El directo sigue en curso."))
        dialogo = DobleDialogo.ultimo
        self.assertEqual(dialogo.titulo, _("Directo sin imagen"))
        self.assertIn("Charla", dialogo.mensaje)
        self.assertEqual(dialogo.etiquetas_ok_cancel,
                         (_("&Finalizar directo"), _("&Dejarlo en curso")))
        self.assertTrue(dialogo.estilo & confirmar.CANCEL_DEFAULT)
        self.assertTrue(dialogo.estilo & confirmar.ICON_QUESTION)

    def test_reinicio_por_idioma(self):
        from guyrapu.ui import preferencias_general

        DobleDialogo.respuesta = confirmar.ID_CANCEL
        with mock.patch.object(confirmar, "MessageDialog", DobleDialogo), \
                mock.patch.object(preferencias_general.wx,
                                  "CallAfter") as llamar:
            self.assertFalse(preferencias_general.ofrecer_reinicio(None))
        llamar.assert_not_called()
        dialogo = DobleDialogo.ultimo
        self.assertEqual(dialogo.mensaje,
                         _("El idioma nuevo se aplica al reiniciar la "
                           "aplicación."))
        self.assertEqual(dialogo.titulo, _("Idioma"))
        self.assertEqual(dialogo.etiquetas_ok_cancel,
                         (_("&Reiniciar ahora"), _("&Más tarde")))
        self.assertFalse(dialogo.estilo & confirmar.CANCEL_DEFAULT)
        self.assertTrue(dialogo.estilo & confirmar.CENTRE)
        self.assertTrue(dialogo.estilo & confirmar.ICON_QUESTION)


def _hwnd_del_cuadro(titulo):
    hwnd = user32.FindWindowW(None, titulo)
    if hwnd:
        return hwnd
    for ventana in wx.GetTopLevelWindows():
        if ventana.GetTitle() == titulo:
            return int(ventana.GetHandle())
    return 0


def _botones(hwnd):
    textos, botones = [], []

    def cada(hijo, _parametro):
        clase = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hijo, clase, 64)
        if clase.value == "Button":
            texto = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hijo, texto, 256)
            textos.append(texto.value)
            botones.append(hijo)
        return True

    user32.EnumChildWindows(hwnd, EnumProc(cada), 0)
    return textos, botones


def _cerrar_si_sigue(hwnd, botones, capturado):
    if user32.IsWindow(hwnd):
        capturado["escape_fallo"] = True
        if botones:
            user32.PostMessageW(botones[-1], 0x00F5, 0, 0)


def _cerrar_con_escape(hwnd, botones, capturado):
    foco = user32.GetFocus() or (botones[0] if botones else hwnd)
    user32.PostMessageW(foco, 0x0100, 0x1B, 0)
    user32.PostMessageW(foco, 0x0101, 0x1B, 0)
    wx.CallLater(2000, _cerrar_si_sigue, hwnd, botones, capturado)


@unittest.skipUnless(sys.platform == "win32", "solo Windows")
class TestCuadrosReales(unittest.TestCase):
    """Los cuadros nativos de verdad, con sus botones y la salida por Escape."""

    def setUp(self):
        self.app = app_de_prueba()
        self.enterContext(cuadros_reales_permitidos())

    def _abrir_y_leer(self, titulo, accion):
        capturado = {}

        def leer(intentos=20):
            hwnd = _hwnd_del_cuadro(titulo)
            if not hwnd and intentos:
                wx.CallLater(100, leer, intentos - 1)
                return
            if hwnd:
                textos, botones = _botones(hwnd)
                capturado["textos"] = textos
                _cerrar_con_escape(hwnd, botones, capturado)

        wx.CallLater(300, leer)
        return accion(), capturado

    def _exigir_escape(self, capturado):
        self.assertFalse(capturado.get("escape_fallo", False),
                         "Escape no cerró el cuadro")

    def test_preguntar_muestra_sus_etiquetas_y_escape_devuelve_falso(self):
        titulo = "Prueba de botones de confirmar"
        resultado, capturado = self._abrir_y_leer(
            titulo,
            lambda: confirmar.preguntar(
                None, "¿Eliminar la lista?", titulo, "&Eliminar",
                "&Cancelar", predeterminado_si=False))
        self.assertFalse(resultado)
        self.assertCountEqual(capturado["textos"], ["&Eliminar", "&Cancelar"])
        self._exigir_escape(capturado)

    def test_avisar_muestra_aceptar(self):
        titulo = "Prueba de botones de avisar"
        resultado, capturado = self._abrir_y_leer(
            titulo,
            lambda: confirmar.avisar(None, "Listo.", titulo, "&Aceptar"))
        self.assertIsNone(resultado)
        self.assertEqual(capturado["textos"], ["&Aceptar"])
        self._exigir_escape(capturado)


@unittest.skipUnless(sys.platform == "win32", "solo Windows")
class TestGuardaDeCuadros(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def test_sin_permiso_preguntar_lanza_con_el_titulo(self):
        titulo = "Prueba de guarda de cuadros"
        with mock.patch.dict(os.environ):
            os.environ.pop("GUYRAPU_PRUEBAS_CON_CUADROS", None)
            with self.assertRaisesRegex(
                    AssertionError,
                    "Una prueba abrió un cuadro de Windows real: "
                    + titulo):
                confirmar.preguntar(None, "¿Seguir?", titulo,
                                    "&Sí", "&No")


if __name__ == "__main__":
    unittest.main()
