"""El ayudante de confirmaciones y los textos de cada cuadro que lo usa."""

import unittest
from types import SimpleNamespace
from unittest import mock

from guyrapu.core.idioma import _
from guyrapu.ui import confirmar


class DobleDialogo:
    """Cuadro falso: registra lo que recibe, sin abrir ninguna ventana."""

    ultimo = None
    respuesta = None

    def __init__(self, padre, mensaje, titulo, estilo):
        self.padre = padre
        self.mensaje = mensaje
        self.titulo = titulo
        self.estilo = estilo
        self.etiquetas_si_no = None
        self.etiqueta_ok = None
        self.escape = None
        self.destruido = False
        DobleDialogo.ultimo = self

    def SetYesNoLabels(self, etiqueta_si, etiqueta_no):
        self.etiquetas_si_no = (etiqueta_si, etiqueta_no)

    def SetOKLabel(self, etiqueta):
        self.etiqueta_ok = etiqueta

    def SetEscapeId(self, identificador):
        self.escape = identificador

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
        resultado, dialogo = self._correr(confirmar.ID_YES)
        self.assertTrue(resultado)
        self.assertEqual(dialogo.etiquetas_si_no, ("&Acción", "&Cancelar"))
        self.assertEqual(dialogo.escape, confirmar.ID_NO)
        self.assertTrue(dialogo.estilo & confirmar.YES_NO)
        self.assertFalse(dialogo.estilo & confirmar.NO_DEFAULT)
        self.assertTrue(dialogo.destruido)

    def test_no_devuelve_falso(self):
        resultado, _dialogo = self._correr(confirmar.ID_NO)
        self.assertFalse(resultado)

    def test_predeterminado_no_y_centrado(self):
        _resultado, dialogo = self._correr(
            confirmar.ID_NO, predeterminado_si=False, centrar=True)
        self.assertTrue(dialogo.estilo & confirmar.NO_DEFAULT)
        self.assertTrue(dialogo.estilo & confirmar.CENTRE)

    def test_icono_elegido(self):
        _resultado, dialogo = self._correr(
            confirmar.ID_NO, icono=confirmar.ICON_ERROR)
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


if __name__ == "__main__":
    unittest.main()
