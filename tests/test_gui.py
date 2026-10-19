"""Pruebas de la salida accesible de los registros."""

import logging
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.ui import gui
from ytchat.ui import gui_comentarios
from ytchat.ui import gui_preferencias
from ytchat.voice import motores
from ytchat.core import config
from ytchat.core import paths
from ytchat.player import reproductor
from ytchat.core import apagado
from ytchat.capture import alias
from ytchat.capture import programados
from ytchat.downloads import ytdlp_bin
from ytchat.ui.lista_chat import MensajeChat, ListaChat
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


class TestInicioGui(unittest.TestCase):

    def _menu_frame(self):
        frame = mock.Mock()
        frame._accel.return_value = ""
        elementos = []

        def crear_menu():
            menu = mock.MagicMock()

            def agregar(*args):
                elemento = mock.Mock()
                elementos.append((args[-1], elemento))
                return elemento

            menu.Append.side_effect = agregar
            menu.AppendRadioItem.side_effect = lambda *args: mock.Mock()
            menu.AppendCheckItem.side_effect = lambda *args: mock.Mock()
            return menu

        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
                mock.patch.object(gui.wx, "MenuBar"):
            gui.YTChatFrame._build_menubar(frame)
        frame._elementos_menu = elementos
        return frame

    def _handler_menu(self, frame, elemento):
        return next(llamada.args[1] for llamada in frame.Bind.call_args_list
                    if llamada.args[2] is elemento)

    def _elemento_menu(self, frame, texto):
        return next(elemento for etiqueta, elemento in frame._elementos_menu
                    if texto in etiqueta)

    def test_muestra_trae_al_frente_y_enfoca_la_url_en_ese_orden(self):
        orden = []
        aplicacion = mock.Mock()
        frame = mock.Mock()
        frame.txt_url.SetFocus.side_effect = lambda: orden.append("foco")
        frame.Show.side_effect = lambda: orden.append("muestra")
        frame.Raise.side_effect = lambda: orden.append("frente")
        configuracion = mock.Mock()
        configuracion.get.return_value = ""
        worker = mock.Mock()
        worker.voces.return_value = []

        with mock.patch.object(gui, "AplicacionYTChat", return_value=aplicacion), \
                mock.patch.object(gui, "YTChatFrame", return_value=frame), \
                redirigir_rutas("."), \
                mock.patch.object(gui, "_lector_init"), \
                mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui.wx, "CallAfter"):
            gui.iniciar_gui(configuracion, object(), object(), worker, object())

        self.assertEqual(orden, ["muestra", "frente", "foco"])

    def test_inicio_programa_el_precalentamiento(self):
        aplicacion = mock.Mock()
        frame = mock.Mock()
        configuracion = mock.Mock()
        configuracion.get.return_value = ""
        worker = mock.Mock()
        worker.voces.return_value = []

        with mock.patch.object(gui, "AplicacionYTChat", return_value=aplicacion), \
                mock.patch.object(gui, "YTChatFrame", return_value=frame), \
                redirigir_rutas("."), \
                mock.patch.object(gui, "_lector_init"), \
                mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui.wx, "CallAfter") as call_after:
            gui.iniciar_gui(configuracion, object(), object(), worker, object())

        call_after.assert_any_call(frame._arrancar_precalentamiento)

    def test_iniciar_gui_guarda_el_nombre_de_la_voz_numerica(self):
        aplicacion = mock.Mock()
        frame = mock.Mock()
        configuracion = {"voz": "1", "voz_eventos": ""}
        worker = mock.Mock()
        worker.voces.return_value = ["Voz A", "Voz B"]

        with mock.patch.object(gui, "AplicacionYTChat", return_value=aplicacion), \
                mock.patch.object(gui, "YTChatFrame", return_value=frame), \
                redirigir_rutas("."), \
                mock.patch.object(gui, "_lector_init"), \
                mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui.wx, "CallAfter"), \
                mock.patch.object(gui, "guardar_opcion") as guardar:
            gui.iniciar_gui(configuracion, object(), object(), worker, object())

        self.assertEqual(configuracion["voz"], "Voz B")
        guardar.assert_any_call(mock.ANY, "voz", "voz", "Voz B")

    def test_lector_init_deja_una_instancia_de_lector(self):
        import prism
        from ytchat.voice import lector as modulo_lector
        contexto = mock.Mock()
        contexto.create.side_effect = prism.PrismError("sin lector")
        anterior = gui._lector
        try:
            with mock.patch.object(prism, "Context", return_value=contexto):
                gui._lector_init()
            self.assertIsInstance(gui._lector, modulo_lector.Lector)
        finally:
            gui._lector = anterior

    def test_asercion_de_wx_se_registra_sin_anunciarse(self):
        aplicacion = mock.Mock()
        with mock.patch.object(gui.logger, "warning") as registrar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui.AplicacionYTChat.OnAssert(
                aplicacion, "ventana.cpp", 42, "indice < total", "índice inválido")

        registrar.assert_called_once_with(
            "wx aserción archivo=%s línea=%s condición=%s mensaje=%s",
            "ventana.cpp", 42, "indice < total", "índice inválido")
        anunciar.assert_not_called()

    def test_fin_de_sesion_usa_el_cierre_normal_de_la_ventana(self):
        aplicacion = mock.Mock()
        ventana = mock.Mock()
        evento = object()
        anterior = gui._gui_frame
        try:
            gui._gui_frame = ventana
            gui.AplicacionYTChat._on_fin_sesion(aplicacion, evento)
        finally:
            gui._gui_frame = anterior

        ventana._on_close.assert_called_once_with(evento)

    def test_menu_conectar_difiere_la_conexion(self):
        frame = self._menu_frame()
        conexion = self._handler_menu(frame, frame.mi_conectar)
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            conexion(mock.Mock())

        diferir.assert_called_once_with(frame._conectar_si_procede)
        frame._conectar_si_procede.assert_not_called()

    def test_menu_historial_difiere_la_apertura(self):
        frame = self._menu_frame()
        historial = self._handler_menu(
            frame, self._elemento_menu(frame, "Historial de directos"))
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            historial(mock.Mock())
        diferir.assert_called_once_with(frame._on_historial)
        frame._on_historial.assert_not_called()

    def test_menu_descargar_este_video_difiere_la_apertura(self):
        frame = self._menu_frame()
        url = "https://www.youtube.com/watch?v=prueba"
        frame._rep_panel.get_url_para_descarga.return_value = url
        descargar = self._handler_menu(frame, frame.mi_descargar_este)
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            descargar(mock.Mock())
        diferir.assert_called_once_with(frame._abrir_descargas, url=url)
        frame._abrir_descargas.assert_not_called()

    def test_menu_transmision_difiere_la_apertura(self):
        frame = self._menu_frame()
        transmision = self._handler_menu(frame, frame.mi_transmision)
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            transmision(mock.Mock())
        diferir.assert_called_once_with(frame._on_transmision, None)
        frame._on_transmision.assert_not_called()

    def test_menu_descargas_difiere_la_apertura(self):
        frame = self._menu_frame()
        descargas = self._handler_menu(frame, frame.mi_descargas)
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            descargas(mock.Mock())
        diferir.assert_called_once_with(frame._abrir_descargas)
        frame._abrir_descargas.assert_not_called()

    def test_menu_actualizar_ytdlp_difiere_la_apertura(self):
        frame = self._menu_frame()
        actualizar = self._handler_menu(frame, frame.mi_actualizar_ytdlp)
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            actualizar(mock.Mock())
        diferir.assert_called_once_with(frame._on_actualizar_ytdlp, None)
        frame._on_actualizar_ytdlp.assert_not_called()

    def test_menu_preferencias_difiere_la_apertura(self):
        frame = self._menu_frame()
        preferencias = self._handler_menu(
            frame, self._elemento_menu(frame, "Preferencias"))
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            preferencias(mock.Mock())
        diferir.assert_called_once_with(frame._on_preferencias, None)
        frame._on_preferencias.assert_not_called()

    def test_menu_acerca_de_difiere_la_apertura(self):
        frame = self._menu_frame()
        acerca_de = self._handler_menu(
            frame, self._elemento_menu(frame, "Acerca de"))
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            acerca_de(mock.Mock())
        diferir.assert_called_once_with(frame._on_about, None)
        frame._on_about.assert_not_called()

    def test_bind_menu_difiere_el_manejador(self):
        frame = mock.Mock()
        item = mock.Mock()
        manejador = mock.Mock()
        gui.YTChatFrame._bind_menu(frame, item, manejador)
        evento = frame.Bind.call_args.args[1]
        diferidos = []

        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda fn, *args: diferidos.append((fn, args))):
            evento(mock.Mock())

        manejador.assert_not_called()
        diferidos[0][0](*diferidos[0][1])
        manejador.assert_called_once_with()

    def test_bind_menu_pasa_los_argumentos_en_orden(self):
        frame = mock.Mock()
        item = mock.Mock()
        manejador = mock.Mock()
        gui.YTChatFrame._bind_menu(frame, item, manejador, "primero", 2, True)
        evento = frame.Bind.call_args.args[1]

        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            evento(mock.Mock())

        diferir.assert_called_once_with(manejador, "primero", 2, True)

    def test_reconstruir_el_menu_destruye_el_anterior_y_conserva_reanudar(self):
        # Preferencias reconstruye la barra: la vieja se destruye y el ítem de
        # pausa sale con el estado real de la lectura, no siempre «Pausar».
        frame = mock.Mock()
        frame._accel.return_value = ""
        frame._worker.esta_pausado.return_value = True
        with mock.patch.object(gui.wx, "Menu"), \
                mock.patch.object(gui.wx, "MenuBar"):
            gui.YTChatFrame._build_menubar(frame)

        frame.GetMenuBar.return_value.Destroy.assert_called_once_with()
        frame._sincronizar_pausa.assert_called_once_with()
        gui.YTChatFrame._sincronizar_pausa(frame)
        frame.mi_pausa.SetItemLabel.assert_called_once_with("&Reanudar lectura")

    def test_sincronizar_pausa_sin_worker_no_revienta(self):
        frame = mock.Mock()
        frame._worker.esta_pausado.side_effect = AttributeError
        gui.YTChatFrame._sincronizar_pausa(frame)
        frame.mi_pausa.SetItemLabel.assert_not_called()

    def test_contador_accesible_selecciona_todo_al_recibir_el_foco(self):
        contador = mock.Mock()
        contador.GetTextValue.return_value = "123"
        evento = mock.Mock()

        gui.ContadorAccesible._on_focus(contador, evento)

        contador.SetSelection.assert_called_once_with(0, 3)
        evento.Skip.assert_called_once_with()


class EventoTecladoFalso:
    def __init__(self, codigo, modificadores=0):
        self.codigo = codigo
        self.modificadores = modificadores
        self.omitido = False

    def GetKeyCode(self):
        return self.codigo

    def GetModifiers(self):
        return self.modificadores

    def Skip(self):
        self.omitido = True


class TestEnterEnListas(unittest.TestCase):

    def test_chat_alt_enter_se_deja_pasar_al_acelerador(self):
        # Alt+Enter es el acelerador de «Enviar mensaje»: no debe copiar.
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._copiar_mensaje = mock.Mock()
        evento = EventoTecladoFalso(gui.wx.WXK_RETURN, gui.wx.MOD_ALT)
        frame._on_chat_char_hook(evento)
        frame._copiar_mensaje.assert_not_called()
        self.assertTrue(evento.omitido)

    def test_comentarios_alt_enter_se_deja_pasar_al_acelerador(self):
        panel = gui_comentarios.ComentariosPanel.__new__(
            gui_comentarios.ComentariosPanel)
        panel._leer = mock.Mock()
        evento = EventoTecladoFalso(gui_comentarios.wx.WXK_RETURN, gui_comentarios.wx.MOD_ALT)
        panel._on_char_hook(evento)
        panel._leer.assert_not_called()
        self.assertTrue(evento.omitido)

    def test_chat_enlaza_el_gancho_de_caracteres(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame.lb_chat = mock.Mock()
        frame._enlazar_eventos_chat()
        enlaces = [llamada.args[0] for llamada in frame.lb_chat.Bind.call_args_list]
        self.assertIn(gui.wx.EVT_CHAR_HOOK, enlaces)

    def test_chat_enter_copia_sin_omitirlo(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._copiar_mensaje = mock.Mock()
        evento = EventoTecladoFalso(gui.wx.WXK_RETURN)
        frame._on_chat_char_hook(evento)
        frame._copiar_mensaje.assert_called_once_with()
        self.assertFalse(evento.omitido)

    def test_chat_otra_tecla_se_deja_pasar(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._copiar_mensaje = mock.Mock()
        evento = EventoTecladoFalso(ord("a"))
        frame._on_chat_char_hook(evento)
        frame._copiar_mensaje.assert_not_called()
        self.assertTrue(evento.omitido)

    def test_comentarios_enlaza_el_gancho_de_caracteres(self):
        panel = gui_comentarios.ComentariosPanel.__new__(
            gui_comentarios.ComentariosPanel)
        panel.lb = mock.Mock()
        panel._enlazar_eventos_lista()
        enlaces = [llamada.args[0] for llamada in panel.lb.Bind.call_args_list]
        self.assertIn(gui_comentarios.wx.EVT_CHAR_HOOK, enlaces)

    def test_comentarios_enter_lee_sin_omitirlo(self):
        panel = gui_comentarios.ComentariosPanel.__new__(
            gui_comentarios.ComentariosPanel)
        panel._leer = mock.Mock()
        evento = EventoTecladoFalso(gui_comentarios.wx.WXK_RETURN)
        panel._on_char_hook(evento)
        panel._leer.assert_called_once_with()
        self.assertFalse(evento.omitido)

    def test_comentarios_otra_tecla_se_deja_pasar(self):
        panel = gui_comentarios.ComentariosPanel.__new__(
            gui_comentarios.ComentariosPanel)
        panel._leer = mock.Mock()
        evento = EventoTecladoFalso(ord("a"))
        panel._on_char_hook(evento)
        panel._leer.assert_not_called()
        self.assertTrue(evento.omitido)


class TestComentariosPanel(unittest.TestCase):

    def _panel_sin_api_key(self):
        app = gui_comentarios.wx.App(False)
        frame = gui_comentarios.wx.Frame(None)
        self.addCleanup(destruir, frame)
        self.addCleanup(destruir, app)
        hay_lectura = self.enterContext(mock.patch.object(gui_comentarios.credenciales, "hay_lectura", return_value=False))
        parches = ((gui_comentarios.youtube_api, "google_disponible", True),
                   (gui_comentarios.credenciales, "hay_sesion", False),
                   (gui_comentarios, "anunciar", None))
        for objeto, nombre, valor in parches:
            self.enterContext(mock.patch.object(objeto, nombre, return_value=valor))
        self.enterContext(mock.patch.object(gui_comentarios.wx, "MessageBox",
                                             side_effect=AssertionError("Se abrió un modal")))
        return gui_comentarios.ComentariosPanel(frame, queue.Queue(), {"tamanio_fuente_chat": 12}), hay_lectura

    def test_autocarga_sin_api_key_muestra_aviso_sin_modal(self):
        panel, _ = self._panel_sin_api_key()
        panel.set_video("unvideo", autocargar=True)
        self.assertEqual(panel.lb.GetCount(), 1)
        self.assertEqual(panel.lb.GetString(0),
                         "Falta la API key. Ponla en Preferencias, pestaña API, "
                         "para leer comentarios.")
        self.assertEqual(panel._video_id, "unvideo")
        self.assertNotIn("conectate a un video", panel.btn_comentar.GetLabel().lower())

    def test_recargar_tras_agregar_api_key_carga_el_video_recordado(self):
        panel, hay_lectura = self._panel_sin_api_key()
        panel.set_video("unvideo", autocargar=True)
        hay_lectura.return_value = True
        cliente = mock.Mock(leer_comentarios=mock.Mock(return_value=([], "")))
        def hilo_inmediato(objetivo, nombre):
            return mock.Mock(start=objetivo)

        with mock.patch.object(panel, "_cliente", return_value=cliente), \
                mock.patch.object(gui_comentarios.diagnostico, "crear_hilo",
                                  side_effect=hilo_inmediato):
            panel._recargar()
        cliente.leer_comentarios.assert_called_once_with("unvideo", page_token="", orden="relevance")

    def test_mostrar_no_disponible_olvida_el_video(self):
        panel, _ = self._panel_sin_api_key()
        panel.set_video("unvideo", autocargar=False)
        panel.mostrar_no_disponible("No hay comentarios aquí.")
        self.assertEqual(panel._video_id, "")


class GrabadorDeVoz:
    """Ocupa el lugar del lector de pantalla y anota lo que se le diría."""

    def __init__(self):
        self.hablado = []
        self.interrupciones = []
        self.brailleado = []

    def speak(self, texto, interrupt=None):
        self.hablado.append(texto)
        self.interrupciones.append(interrupt)

    def braille(self, texto):
        self.brailleado.append(texto)


class TestRegistroEsAnunciable(unittest.TestCase):

    def test_obs_vigilante_si_se_anuncia(self):
        self.assertTrue(gui.registro_es_anunciable("ytchat.obs_vigilante"))

    def test_diagnostico_no_se_anuncia(self):
        self.assertFalse(gui.registro_es_anunciable("ytchat.diagnostico"))

    def test_tecnicos_no_se_anuncian(self):
        for nombre in ("ytchat.descargas", "ytchat.main", "ytchat.tts_worker",
                       "ytchat.sound_player"):
            with self.subTest(nombre=nombre):
                self.assertFalse(gui.registro_es_anunciable(nombre))

    def test_nombres_vacios_no_se_anuncian(self):
        self.assertFalse(gui.registro_es_anunciable(""))
        self.assertFalse(gui.registro_es_anunciable(None))

    def test_manejador_consulta_el_nombre_del_registro(self):
        manejador = gui.WxAnnouncingHandler()
        registro = logging.LogRecord(
            "diagnostico.hilos", logging.INFO, __file__, 1, "oculto", (), None)
        with mock.patch.object(gui, "registro_es_anunciable", return_value=False) as decidir:
            with mock.patch.object(gui, "anunciar") as anunciar:
                manejador.emit(registro)
        decidir.assert_called_once_with("diagnostico.hilos")
        anunciar.assert_not_called()

    def test_anunciar_interrumpe_por_defecto(self):
        grabador = GrabadorDeVoz()
        with mock.patch.object(gui, "_lector", grabador):
            gui.anunciar("hola")

        self.assertEqual(grabador.hablado, ["hola"])
        self.assertEqual(grabador.interrupciones, [True])

    def test_anunciar_no_interrumpe_si_no_es_urgente(self):
        grabador = GrabadorDeVoz()
        with mock.patch.object(gui, "_lector", grabador):
            gui.anunciar("hola", urgente=False)

        self.assertEqual(grabador.interrupciones, [False])

    def test_anunciar_desde_otro_hilo_se_reenvia_al_hilo_principal(self):
        # La voz va por COM: desde un hilo ajeno no se habla, se difiere.
        grabador = GrabadorDeVoz()
        with mock.patch.object(gui, "_lector", grabador), \
                mock.patch.object(gui.wx, "IsMainThread", return_value=False), \
                mock.patch.object(gui.wx, "CallAfter") as diferir:
            gui.anunciar("hola", urgente=False)

        diferir.assert_called_once_with(gui.anunciar, "hola", False)
        self.assertEqual(grabador.hablado, [])
        self.assertEqual(grabador.brailleado, [])

    def test_anunciar_envia_braille_en_los_dos_casos(self):
        grabador = GrabadorDeVoz()
        with mock.patch.object(gui, "_lector", grabador):
            gui.anunciar("urgente")
            gui.anunciar("no urgente", urgente=False)

        self.assertEqual(grabador.brailleado, ["urgente", "no urgente"])

    def test_anunciar_registra_el_fallo_de_voz_sin_propagarse(self):
        salida = mock.Mock()
        salida.speak.side_effect = RuntimeError("COM no disponible")
        with mock.patch.object(gui, "_lector", salida), \
                mock.patch.object(gui.logger, "warning") as registrar:
            gui.anunciar("hola")

        registrar.assert_called_once_with(
            "No se pudo anunciar con voz: %s", mock.ANY)
        self.assertEqual(str(registrar.call_args.args[1]), "COM no disponible")

    def test_anunciar_no_registra_fallo_si_la_voz_responde(self):
        grabador = GrabadorDeVoz()
        with mock.patch.object(gui, "_lector", grabador), \
                mock.patch.object(gui.logger, "warning") as registrar:
            gui.anunciar("hola")

        registrar.assert_not_called()

    def test_aviso_de_espera_no_interrumpe(self):
        panel = mock.Mock()
        panel._cargando = True
        panel._inicio_progreso = 10
        panel._ultimo_aviso_progreso = None
        with mock.patch.object(reproductor.time, "monotonic", return_value=12), \
                mock.patch.object(reproductor.progreso, "aviso_de_espera",
                                  return_value="Buscando el vídeo, 2 segundos"), \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            reproductor.ReproductorPanel._on_timer_progreso(panel, None)

        anunciar.assert_called_once_with("Buscando el vídeo, 2 segundos", urgente=False)

    def test_manejador_omite_diagnostico_sin_parchear_anunciar(self):
        grabador = GrabadorDeVoz()
        registro = logging.LogRecord(
            "ytchat.diagnostico", logging.INFO, __file__, 1, "oculto", (), None)
        with mock.patch.object(gui, "_lector", grabador):
            gui.WxAnnouncingHandler().emit(registro)

        self.assertEqual(grabador.hablado, [])
        self.assertEqual(grabador.brailleado, [])

    def test_manejador_anuncia_mensaje_de_aplicacion(self):
        grabador = GrabadorDeVoz()
        registro = logging.LogRecord(
            "ytchat.obs_vigilante", logging.INFO, __file__, 1, "OBS volvio a responder", (), None)
        with mock.patch.object(gui, "_lector", grabador):
            gui.WxAnnouncingHandler().emit(registro)

        self.assertEqual(grabador.hablado, ["OBS volvio a responder"])

    def test_log_wx_redirige_segun_nivel(self):
        with mock.patch.object(gui.logger, "warning") as warn, \
                mock.patch.object(gui.logger, "debug") as dbg:
            redir = gui._LogWx()
            redir.DoLogRecord(gui.wx.LOG_Error, "fallo error", None)
            redir.DoLogRecord(gui.wx.LOG_Warning, "aviso", None)
            redir.DoLogRecord(gui.wx.LOG_Message, "mensaje", None)
            redir.DoLogRecord(gui.wx.LOG_Info, "info", None)
            redir.DoLogRecord(gui.wx.LOG_Debug, "debug", None)
        self.assertEqual(warn.call_count, 2)
        self.assertEqual(dbg.call_count, 3)
        warn.assert_any_call("wx: %s", "fallo error")
        warn.assert_any_call("wx: %s", "aviso")
        dbg.assert_any_call("wx: %s", "mensaje")


class TestAltoContraste(unittest.TestCase):
    """Con un tema de alto contraste de Windows la paleta propia no se aplica:
    esos colores los eligió el usuario precisamente para poder ver."""

    def test_sin_alto_contraste_se_pinta_la_paleta(self):
        control = mock.Mock()
        with mock.patch.object(gui, "ALTO_CONTRASTE", False):
            gui._tc(control)
        control.SetBackgroundColour.assert_called_once_with(gui._T.field)
        control.SetForegroundColour.assert_called_once_with(gui._T.text)

    def test_con_alto_contraste_no_se_toca_ningun_color(self):
        control = mock.Mock()
        with mock.patch.object(gui, "ALTO_CONTRASTE", True):
            gui._tc(control)
            gui._pintar(control, gui._T.bg, gui._T.text)
            gui._titulo(control)
        control.SetBackgroundColour.assert_not_called()
        control.SetForegroundColour.assert_not_called()
        control.SetFont.assert_called_once()   # la negrita de sección sí queda

    def test_pintar_solo_aplica_lo_que_se_le_pasa(self):
        control = mock.Mock()
        with mock.patch.object(gui, "ALTO_CONTRASTE", False):
            gui._pintar(control, fg=gui._T.dim)
        control.SetBackgroundColour.assert_not_called()
        control.SetForegroundColour.assert_called_once_with(gui._T.dim)

    def test_la_deteccion_nunca_revienta(self):
        self.assertIn(gui._detectar_alto_contraste(), (True, False))


class TestVentanaReal(unittest.TestCase):
    """Comprobaciones que necesitan la ventana de verdad (tamaños, Wrap)."""

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()

    def _ventana(self, **worker_extra):
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": False, "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False,
        }
        from types import SimpleNamespace
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100, **worker_extra)
        with mock.patch.object(gui.diagnostico, "crear_hilo"):
            frame = gui.YTChatFrame(None, configuracion, queue.Queue(), stats, worker,
                                    __import__("threading").Event())
        self.addCleanup(destruir, frame)
        frame.ShowWithoutActivating()
        gui.wx.Yield()
        return frame

    @staticmethod
    def _saltos(frame):
        return frame.lbl_tipo.GetLabel().count("\n")

    def test_el_texto_de_tipo_se_vuelve_a_ensanchar(self):
        # Wrap() solo parte; al agrandar la ventana el texto debe volver a
        # una línea y no quedarse troceado con los saltos de la ventana chica.
        frame = self._ventana()
        frame.SetSize((650, 700)); gui.wx.Yield()
        self.assertGreater(self._saltos(frame), 0)
        frame.SetSize((1500, 700)); gui.wx.Yield()
        self.assertEqual(self._saltos(frame), 0)
        self.assertEqual(frame.lbl_tipo.GetLabel(), gui.MENSAJE_INICIAL)

    def test_el_wrap_usa_el_ancho_actual_y_no_el_anterior(self):
        frame = self._ventana()
        frame.SetSize((1500, 700)); gui.wx.Yield()
        frame.SetSize((650, 700)); gui.wx.Yield()
        ancho_panel = frame._panel_principal.GetClientSize().width
        self.assertLessEqual(frame.lbl_tipo.GetBestSize().width, ancho_panel - 20)

    def test_fijar_tipo_conserva_el_texto_original(self):
        frame = self._ventana()
        frame.SetSize((650, 700)); gui.wx.Yield()
        frame._fijar_tipo("Directo programado: aún sin chat. Hay comentarios.")
        frame.SetSize((1500, 700)); gui.wx.Yield()
        self.assertEqual(frame.lbl_tipo.GetLabel(),
                         "Directo programado: aún sin chat. Hay comentarios.")

    def test_con_el_reproductor_a_la_vista_el_piso_sale_del_sizer(self):
        frame = self._ventana()
        self.assertLess(frame.GetMinClientSize().height, 500)
        frame._mostrar_zona(True)
        minimo = frame._panel_principal.GetSizer().GetMinSize()
        area = gui.wx.Display(frame).GetClientArea()
        esperado = max(480, min(minimo.height, area.height - 110))
        self.assertGreater(esperado, 500)
        self.assertAlmostEqual(frame.GetMinClientSize().height, esperado, delta=4)
        # La ventana se agrandó para que quepa todo (o ya cabía).
        self.assertGreaterEqual(frame.GetClientSize().height, esperado - 4)

    def test_el_piso_no_sigue_al_ancho_de_la_ventana(self):
        # La etiqueta sin partir no debe empujar el mínimo hasta el ancho actual.
        frame = self._ventana()
        frame.SetSize((1500, 700)); gui.wx.Yield()
        frame._mostrar_zona(True)
        self.assertLess(frame.GetMinClientSize().width, 1000)

    def test_reconstruir_el_menu_destruye_la_barra_anterior(self):
        frame = self._ventana(esta_pausado=lambda: True)
        anterior = frame.GetMenuBar()
        frame._build_menubar()
        self.assertIsNot(frame.GetMenuBar(), anterior)
        self.assertFalse(bool(anterior))
        self.assertEqual(frame.mi_pausa.GetItemLabelText(), "Reanudar lectura")


class TestFocoAlActivar(unittest.TestCase):
    """Al activarse la ventana no se roba el foco si ya está en un control
    suyo (p. ej. al cerrarse un aviso mientras se estaba en el reproductor)."""

    def _frame(self, conectado=True):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._conectado = conectado
        frame._foco_contenido = mock.Mock()
        frame.txt_url = mock.Mock()
        return frame

    def _control_dentro_de(self, frame):
        padre = mock.Mock()
        padre.GetParent.return_value = None
        # La cadena de padres llega al frame: el control es suyo.
        control = mock.Mock()
        control.GetParent.return_value = frame
        return control

    def test_no_mueve_el_foco_si_ya_esta_dentro_de_la_ventana(self):
        frame = self._frame()
        with mock.patch.object(gui.wx.Window, "FindFocus",
                               return_value=self._control_dentro_de(frame)):
            frame._foco_al_activar()
        frame._foco_contenido.assert_not_called()
        frame.txt_url.SetFocus.assert_not_called()

    def test_sin_foco_va_al_contenido_si_hay_conexion(self):
        frame = self._frame()
        with mock.patch.object(gui.wx.Window, "FindFocus", return_value=None):
            frame._foco_al_activar()
        frame._foco_contenido.assert_called_once_with()

    def test_foco_fuera_de_la_ventana_va_a_la_url_sin_conexion(self):
        frame = self._frame(conectado=False)
        ajeno = mock.Mock()
        ajeno.GetParent.return_value = None
        with mock.patch.object(gui.wx.Window, "FindFocus", return_value=ajeno):
            frame._foco_al_activar()
        frame.txt_url.SetFocus.assert_called_once_with()

    def test_on_activate_difiere_la_decision(self):
        frame = self._frame()
        frame._foco_al_activar = mock.Mock()
        evento = mock.Mock()
        evento.GetActive.return_value = True
        with mock.patch.object(gui.wx, "CallAfter") as diferir:
            frame._on_activate(evento)
        diferir.assert_called_once_with(frame._foco_al_activar)
        evento.Skip.assert_called_once_with()


class TestConexionCancelable(unittest.TestCase):

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._conectado = False
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame.txt_url.GetValue.return_value = "abcdefghijk"
        frame.btn_conectar = mock.Mock()
        frame.mi_conectar = mock.Mock()
        frame.mi_desconectar = mock.Mock()
        frame.on_conectar_cb = mock.Mock()
        frame.on_desconectar_cb = mock.Mock()
        frame.set_conectado = mock.Mock()
        return frame

    def test_mientras_conecta_desconectar_sigue_disponible(self):
        frame = self._frame()
        with mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui, "anunciar"):
            frame._on_conectar(None)
        self.assertTrue(frame._conectando)
        frame.mi_desconectar.Enable.assert_called_once_with(True)
        frame.btn_conectar.Enable.assert_called_once_with()
        frame.btn_conectar.Disable.assert_not_called()
        frame.on_conectar_cb.assert_called_once_with("abcdefghijk")

    def test_desconectar_durante_la_conexion_la_cancela(self):
        frame = self._frame()
        with mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._on_conectar(None)
            frame._desconectar_si_procede()
        frame.on_desconectar_cb.assert_called_once_with()
        frame.set_conectado.assert_called_once_with(False)
        anunciar.assert_called_with("Conexión cancelada")
        frame.txt_url.SetFocus.assert_called_once_with()

    def test_sin_conexion_ni_intento_desconectar_no_hace_nada(self):
        frame = self._frame()
        frame._desconectar_si_procede()
        frame.on_desconectar_cb.assert_not_called()

    def test_la_respuesta_de_conexion_apaga_el_estado_conectando(self):
        frame = self._frame()
        frame._conectando = True
        frame._actualizar_menus_por_conexion = mock.Mock()
        gui.YTChatFrame._set_conectado_ui(frame, True)
        self.assertFalse(frame._conectando)

    def test_alt_enter_sin_poder_escribir_anuncia_el_motivo(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._panel_redactar = mock.Mock()
        frame._panel_redactar.motivo.return_value = "Conéctate a un directo para escribir en el chat"
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._on_enviar_live(None)
        anunciar.assert_called_once_with("Conéctate a un directo para escribir en el chat")
        frame._panel_redactar.enfocar.assert_not_called()

    def test_alt_enter_con_chat_disponible_enfoca_el_compositor(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._panel_redactar = mock.Mock()
        frame._panel_redactar.motivo.return_value = ""
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._on_enviar_live(None)
        anunciar.assert_not_called()
        frame._panel_redactar.enfocar.assert_called_once_with()

    def test_respuesta_de_la_api_con_la_ventana_destruida_se_ignora(self):
        # Un frame sin construir se comporta como uno ya destruido (bool False).
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        with mock.patch.object(gui._snd, "reproducir") as sonar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._api_ok("Mensaje enviado al chat")
            frame._api_err(RuntimeError("x"))
        sonar.assert_not_called()
        anunciar.assert_not_called()


class _BarraDeMenu:

    def __init__(self):
        self.llamadas = []

    def EnableTop(self, *args):
        self.llamadas.append(args)


class _ControlMenu:

    def Enable(self, habilitado):
        pass


class TestMenusPorConexion(unittest.TestCase):

    def test_no_apaga_menu_reproductor_sin_conexion(self):
        frame = mock.Mock()
        frame._conectado = False
        frame._mi_ver_conexion = []
        frame._mi_voz_conexion = []
        frame._mi_filtro_sub = _ControlMenu()
        frame._es_tiktok = False
        frame._rep_panel = None
        frame.mi_descargar_este = _ControlMenu()
        barra = _BarraDeMenu()
        frame.GetMenuBar.return_value = barra

        gui.YTChatFrame._actualizar_menus_por_conexion(frame)

        self.assertEqual(barra.llamadas, [])


class TestAliasEnLaLista(unittest.TestCase):

    def test_lista_muestra_el_alias_del_autor(self):
        autor = "xX_gamer_29384756_Xx"
        alias.usar({autor.lower(): "Carlos"})
        self.addCleanup(alias.usar, {})
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"limpiar_emojis": True}

        texto = frame._format_display(autor, "hola", "12:00", 0, "")

        self.assertEqual(texto, "Carlos: hola, 12:00")


class TestFilasEventosTikTok(unittest.TestCase):

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"limpiar_emojis": True}
        return frame

    def test_seguir_dice_que_paso(self):
        texto = self._frame()._format_display("Ana", "", "12:00", config.TIPO_SEGUIR, "")

        self.assertEqual(texto, "Ana sigue el canal, 12:00")

    def test_compartir_dice_que_paso(self):
        texto = self._frame()._format_display("Ana", "", "12:00", config.TIPO_COMPARTIR, "")

        self.assertEqual(texto, "Ana compartió el directo, 12:00")

    def test_cofre_dice_que_paso(self):
        texto = self._frame()._format_display("Ana", "", "12:00", config.TIPO_COFRE, "")

        self.assertEqual(texto, "Ana envió un cofre, 12:00")

    def test_comentario_comun_no_cambia(self):
        texto = self._frame()._format_display("Ana", "hola", "12:00", config.TIPO_TEXTO, "")

        self.assertEqual(texto, "Ana: hola, 12:00")


class DialogoAliasFalso:

    def __init__(self, aceptar, valor):
        self.aceptar = aceptar
        self.valor = valor
        self.destruido = False

    def ShowModal(self):
        return gui.wx.ID_OK if self.aceptar else gui.wx.ID_CANCEL

    def GetValue(self):
        return self.valor

    def Destroy(self):
        self.destruido = True


class MenuChatFalso:

    def __init__(self):
        self.etiquetas = {}
        self.handlers = {}

    def Append(self, identificador, etiqueta):
        self.etiquetas[identificador] = etiqueta

    def AppendSeparator(self):
        pass

    def Bind(self, _evento, handler, id):
        self.handlers[id] = handler

    def Destroy(self):
        pass


class TestAliasDesdeElChat(unittest.TestCase):

    autor = "xX_gamer_29384756_Xx"

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame.lb_chat = mock.Mock()
        frame._rebuild_listbox = mock.Mock()
        return frame

    def test_aceptar_guarda_persiste_y_redibuja(self):
        frame = self._frame()
        dialogo = DialogoAliasFalso(True, "Carlos")
        alias.usar({})
        with mock.patch.object(gui.wx, "TextEntryDialog", return_value=dialogo), \
                mock.patch.object(gui.alias, "guardar") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._editar_alias_autor(self.autor)

        self.assertEqual(alias.visible(self.autor), "Carlos")
        guardar.assert_called_once_with(
            paths.alias(), {self.autor.lower(): "Carlos"})
        frame._rebuild_listbox.assert_called_once_with()
        frame.lb_chat.SetFocus.assert_called_once_with()
        self.assertTrue(dialogo.destruido)
        anunciar.assert_called_once_with("Alias guardado, Carlos")
        alias.usar({})

    def test_aceptar_vacio_quita_el_alias(self):
        frame = self._frame()
        dialogo = DialogoAliasFalso(True, "")
        alias.usar({self.autor.lower(): "Carlos"})
        with mock.patch.object(gui.wx, "TextEntryDialog", return_value=dialogo), \
                mock.patch.object(gui.alias, "guardar") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._editar_alias_autor(self.autor)

        self.assertEqual(alias.visible(self.autor), self.autor)
        guardar.assert_called_once_with(paths.alias(), {})
        frame._rebuild_listbox.assert_called_once_with()
        anunciar.assert_called_once_with("Alias quitado")
        alias.usar({})

    def test_cancelar_no_guarda_ni_redibuja(self):
        frame = self._frame()
        dialogo = DialogoAliasFalso(False, "Carlos")
        alias.usar({})
        with mock.patch.object(gui.wx, "TextEntryDialog", return_value=dialogo), \
                mock.patch.object(gui.alias, "guardar") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._editar_alias_autor(self.autor)

        guardar.assert_not_called()
        frame._rebuild_listbox.assert_not_called()
        anunciar.assert_not_called()
        frame.lb_chat.SetFocus.assert_called_once_with()

    def test_menu_muestra_alias_y_moderacion_recibe_autor_real(self):
        frame = self._frame()
        frame.lb_chat.GetSelection.return_value = 0
        registro = MensajeChat(plataforma="youtube", autor=self.autor,
                               identificador="canal-real", texto="hola",
                               hora="12:00:00", tipo="text", monto="")
        frame._get_selected_data = mock.Mock(return_value=registro)
        frame._autor_esta_silenciado = mock.Mock(return_value=False)
        frame._live_chat_id = "chat"
        frame._moderar = mock.Mock()
        frame._silenciar_autor = mock.Mock()
        menu = MenuChatFalso()
        alias.usar({self.autor.lower(): "Carlos"})
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 11)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()

        self.assertIn("Silenciar a Carlos (solo TTS)", menu.etiquetas.values())
        self.assertIn("Expulsar 5 min a Carlos (timeout)", menu.etiquetas.values())
        self.assertIn("Banear a Carlos del directo (permanente)", menu.etiquetas.values())
        self.assertIn("Cambiar el &alias de Carlos…", menu.etiquetas.values())
        identificador_ban = next(i for i, texto in menu.etiquetas.items()
                                 if texto.startswith("Banear"))
        identificador_silenciar = next(i for i, texto in menu.etiquetas.items()
                                       if texto.startswith("Silenciar"))
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion, *args: funcion(*args)):
            menu.handlers[identificador_ban](None)
            menu.handlers[identificador_silenciar](None)
        frame._moderar.assert_called_once_with(self.autor, "canal-real", None)
        frame._silenciar_autor.assert_called_once_with(self.autor, False)
        alias.usar({})


class TestIdentidadModeracionChat(unittest.TestCase):
    """Moderación usa exclusivamente el registro seleccionado, nunca el último homónimo."""

    def _frame_con_chat(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._chat = ListaChat(max_items=500)
        frame._pendientes = []
        frame._pendientes_timer = None
        frame._filtro = None
        frame._config = {"limpiar_emojis": True, "silenciados_runtime": set(),
                         "silenciados_ocultar": set()}
        frame._sc_totales = {}
        frame._live_chat_id = "live123"
        frame._conectado = True
        frame._alive = True
        frame._autor_esta_oculto = lambda autor: False
        frame._autor_esta_silenciado = lambda autor: False
        frame._moderar = mock.Mock()
        frame._silenciar_autor = mock.Mock()
        frame._rehabilitar_autor = mock.Mock()
        frame.lb_chat = mock.Mock()
        frame.lb_chat.Freeze = mock.Mock()
        frame.lb_chat.Thaw = mock.Mock()
        frame.lb_chat.Delete = mock.Mock()
        frame.lb_chat.Append = mock.Mock()
        frame.lb_chat.Clear = mock.Mock()
        frame.lb_chat.GetSelection = mock.Mock(return_value=0)
        frame.lb_chat.GetCount = mock.Mock(return_value=0)
        return frame

    def _encolar_y_volcar(self, frame, plataforma, autor, identificador, texto="hola"):
        with mock.patch.object(gui.wx, "CallLater", return_value=mock.Mock()):
            frame.agregar_mensaje_chat(autor, texto, "12:00:00", "text", "", identificador,
                                       plataforma=plataforma)
        # Volcar sin depender del temporizador ni de wx.App.
        with mock.patch.object(gui.wx.Window, "FindFocus", return_value=None):
            frame._volcar_pendientes()

    def test_homonimos_banear_recibe_identificador_antiguo(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Igual", "AAA", "mensaje A")
        self._encolar_y_volcar(frame, "youtube", "Igual", "BBB", "mensaje B")
        # Seleccionar fila antigua (0 -> AAA).
        frame.lb_chat.GetSelection.return_value = 0
        menu = MenuChatFalso()
        alias.usar({})
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 20)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()
        identificador_ban = next(i for i, texto in menu.etiquetas.items() if texto.startswith("Banear"))
        with mock.patch.object(gui.wx, "CallAfter", side_effect=lambda fn, *a: fn(*a)):
            menu.handlers[identificador_ban](None)
        frame._moderar.assert_called_once_with("Igual", "AAA", None)
        self.assertNotEqual(frame._moderar.call_args.args[1], "BBB")
        alias.usar({})

    def test_homonimos_timeout_recibe_identificador_antiguo(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Igual", "AAA")
        self._encolar_y_volcar(frame, "youtube", "Igual", "BBB")
        frame.lb_chat.GetSelection.return_value = 0
        menu = MenuChatFalso()
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 20)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()
        identificador_timeout = next(i for i, texto in menu.etiquetas.items() if texto.startswith("Expulsar"))
        with mock.patch.object(gui.wx, "CallAfter", side_effect=lambda fn, *a: fn(*a)):
            menu.handlers[identificador_timeout](None)
        frame._moderar.assert_called_once_with("Igual", "AAA", 300)

    def test_tiktok_no_muestra_moderacion_aunque_tenga_identificador(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "tiktok", "Igual", "TIK123")
        frame.lb_chat.GetSelection.return_value = 0
        menu = MenuChatFalso()
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 20)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()
        self.assertNotIn("Banear a Igual del directo (permanente)", menu.etiquetas.values())
        self.assertNotIn("Expulsar 5 min a Igual (timeout)", menu.etiquetas.values())

    def test_youtube_sin_identificador_no_muestra_moderacion(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Igual", "")
        frame.lb_chat.GetSelection.return_value = 0
        menu = MenuChatFalso()
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 20)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()
        self.assertNotIn("Banear a Igual del directo (permanente)", menu.etiquetas.values())

    def test_copia_usa_texto_del_registro_seleccionado(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Igual", "AAA", "texto A")
        self._encolar_y_volcar(frame, "youtube", "Igual", "BBB", "texto B")
        frame.lb_chat.GetSelection.return_value = 0
        frame._clipboard_set = mock.Mock()
        with mock.patch.object(gui._snd, "reproducir"), mock.patch.object(gui, "anunciar"):
            frame._copiar_mensaje()
        frame._clipboard_set.assert_called_once_with("texto A")

    def test_copia_todo_usa_registro_seleccionado(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Igual", "AAA", "hola")
        frame.lb_chat.GetSelection.return_value = 0
        # Forzar monto y hora conocidas.
        frame._chat.todos[0] = MensajeChat(plataforma="youtube", autor="Igual",
                                          identificador="AAA", texto="hola",
                                          hora="12:34:56", tipo="text", monto="$5")
        frame._chat.visibles = [0]
        frame._clipboard_set = mock.Mock()
        with mock.patch.object(gui._snd, "reproducir"), mock.patch.object(gui, "anunciar"):
            frame._copiar_todo()
        frame._clipboard_set.assert_called_once_with("Igual: hola, 12:34:56 [$5]")

    def test_releer_usa_registro_seleccionado(self):
        frame = self._frame_con_chat()
        frame._cola = mock.Mock()
        frame._cola.put = mock.Mock()
        self._encolar_y_volcar(frame, "youtube", "Ana", "AAA", "hola mundo")
        frame.lb_chat.GetSelection.return_value = 0
        with mock.patch.object(gui, "anunciar"):
            frame._releer_mensaje()
        self.assertTrue(frame._cola.put.called)
        texto_tts = frame._cola.put.call_args.args[0]["texto_tts"]
        self.assertIn("hola mundo", texto_tts)

    def test_abrir_enlace_usa_texto_del_registro(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "Ana", "AAA", "mira https://example.com")
        frame.lb_chat.GetSelection.return_value = 0
        with mock.patch.object(gui.webbrowser, "open") as abrir, \
                mock.patch.object(gui, "anunciar"):
            frame._abrir_enlace()
        abrir.assert_called_once_with("https://example.com")

    def test_alias_solo_cambia_texto_visible_moderacion_recibe_real(self):
        frame = self._frame_con_chat()
        self._encolar_y_volcar(frame, "youtube", "xX_gamer_29384756_Xx", "CANAL1", "hola")
        frame.lb_chat.GetSelection.return_value = 0
        alias.usar({"xx_gamer_29384756_xx": "Carlos"})
        menu = MenuChatFalso()
        with mock.patch.object(gui.wx, "Menu", return_value=menu), \
                mock.patch.object(gui.wx, "NewIdRef", side_effect=range(1, 20)), \
                mock.patch.object(gui.youtube_api, "google_disponible", return_value=True), \
                mock.patch.object(gui.credenciales, "hay_sesion", return_value=True):
            frame._mostrar_menu_chat()
        self.assertIn("Silenciar a Carlos (solo TTS)", menu.etiquetas.values())
        identificador_ban = next(i for i, texto in menu.etiquetas.items() if texto.startswith("Banear"))
        with mock.patch.object(gui.wx, "CallAfter", side_effect=lambda fn, *a: fn(*a)):
            menu.handlers[identificador_ban](None)
        frame._moderar.assert_called_once_with("xX_gamer_29384756_Xx", "CANAL1", None)
        alias.usar({})


class TestMeGustaFueraDelModelo(unittest.TestCase):
    """El me gusta suena sin tocar ni el modelo ni la lista."""

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._chat = ListaChat(max_items=500)
        frame._filtro = None
        frame._config = {"limpiar_emojis": True}
        frame._autor_esta_oculto = lambda autor: False
        frame._sumar_superchat = mock.Mock()
        frame.lb_chat = mock.Mock()
        filas = []
        frame.lb_chat.Append.side_effect = lambda texto: filas.append(texto)
        frame.lb_chat.Delete.side_effect = lambda i: filas.pop(i)
        frame._filas = filas
        return frame

    def _registro(self, tipo, texto):
        return MensajeChat(plataforma="tiktok", autor="Ana",
                           identificador="C", texto=texto, hora="12:00",
                           tipo=tipo, monto="", rol="")

    def test_me_gusta_no_toca_modelo_ni_lista(self):
        from ytchat.core.config import TIPO_TEXTO, TIPO_ME_GUSTA
        frame = self._frame()
        primero = self._registro(TIPO_TEXTO, "primero")
        me_gusta = self._registro(TIPO_ME_GUSTA, "")
        segundo = self._registro(TIPO_TEXTO, "segundo")
        with mock.patch.object(gui._snd, "reproducir") as reproducir:
            self.assertTrue(frame._procesar_mensaje_chat(primero))
            self.assertFalse(frame._procesar_mensaje_chat(me_gusta))
            self.assertTrue(frame._procesar_mensaje_chat(segundo))
        self.assertEqual(len(frame._chat.todos), 2)
        self.assertEqual(len(frame._filas), 2)
        self.assertIs(frame._chat.dato_en_fila(1), segundo)
        self.assertEqual(frame._filas[1], frame._format_display(
            segundo.autor, segundo.texto, segundo.hora,
            segundo.tipo, segundo.monto))
        sonidos = [llamada.args[0] for llamada in reproducir.call_args_list]
        self.assertEqual(sonidos.count("me_gusta"), 1)


class TestProgramadosEnPreferencias(unittest.TestCase):

    def _dialogo(self, mensajes, seleccion):
        dialogo = gui_preferencias.PreferenciasDialog.__new__(
            gui_preferencias.PreferenciasDialog)
        dialogo._mensajes_programados = mensajes
        dialogo._ruta_programados = Path(tempfile.mktemp(suffix=".json"))
        dialogo.lista_programados = mock.Mock()
        dialogo.lista_programados.GetSelection.return_value = seleccion
        dialogo._refrescar_programados = mock.Mock()
        self.addCleanup(lambda: dialogo._ruta_programados.unlink(missing_ok=True))
        return dialogo

    def test_quitar_persiste_que_el_mensaje_desaparecio(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "mensajes_programados.json"
            mensajes = [
                {"texto": "Quitar", "minutos_min": 10, "minutos_max": 10,
                 "activo": True, "proximo": 100.0},
                {"texto": "Conservar", "minutos_min": 10, "minutos_max": 10,
                 "activo": True, "proximo": 200.0},
            ]
            dialogo = self._dialogo(mensajes, 0)
            dialogo._ruta_programados = ruta
            def guardar_doble(ruta_a_guardar, mensajes_a_guardar):
                Path(ruta_a_guardar).write_text(
                    json.dumps(mensajes_a_guardar, ensure_ascii=False), encoding="utf-8")

            with mock.patch.object(
                    gui_preferencias.programados, "guardar",
                    side_effect=guardar_doble), \
                    mock.patch.object(gui_preferencias, "anunciar"):
                dialogo._quitar_programado(None)

            guardados = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(guardados, [mensajes[0]])
            self.assertNotIn("Quitar", ruta.read_text(encoding="utf-8"))


    def test_guardar_edita_la_fila_elegida(self):
        mensajes = [
            {"texto": "Primero", "proximo": 100.0},
            {"texto": "Segundo", "proximo": 200.0},
            {"texto": "Tercero", "proximo": 300.0},
        ]
        dialogo = self._dialogo(mensajes, 2)
        dialogo._datos_programado = mock.Mock(return_value={"texto": "Editado"})
        dialogo._validar_programado = mock.Mock(return_value=True)
        with mock.patch.object(gui_preferencias.programados, "guardar"), \
                mock.patch.object(gui_preferencias, "anunciar"):
            dialogo._guardar_programado(None)

        self.assertEqual(mensajes[0]["texto"], "Primero")
        self.assertEqual(mensajes[2]["texto"], "Editado")

    def test_guardar_conserva_el_proximo_envio(self):
        mensajes = [
            {"texto": "Primero", "proximo": 100.0},
            {"texto": "Segundo", "proximo": 200.0},
        ]
        dialogo = self._dialogo(mensajes, 1)
        dialogo._datos_programado = mock.Mock(return_value={"texto": "Corregido"})
        dialogo._validar_programado = mock.Mock(return_value=True)
        with mock.patch.object(gui_preferencias.programados, "guardar"), \
                mock.patch.object(gui_preferencias, "anunciar"):
            dialogo._guardar_programado(None)

        self.assertEqual(mensajes[1]["proximo"], 200.0)

    def test_quitar_sin_seleccion_anuncia_y_no_revienta(self):
        dialogo = self._dialogo([], -1)
        with mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._quitar_programado(None)

        anunciar.assert_called_once_with("Elige primero un mensaje de la lista")


class TestCategoriasDePreferencias(unittest.TestCase):

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.ruta = Path.cwd()
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    @staticmethod
    def _buscar(raiz, nombre):
        pendientes = [raiz]
        while pendientes:
            control = pendientes.pop()
            if control.GetName() == nombre:
                return control
            pendientes.extend(control.GetChildren())
        return None

    def test_tiene_catorce_categorias_en_el_orden_acordado(self):
        dialogo = self._dialogo()
        self.assertEqual(
            [dialogo.nb.GetPageText(i) for i in range(dialogo.nb.GetPageCount())],
            ["General", "Voces", "Lectura", "Cola de lectura", "Interfaz y sonidos",
             "Reproductor", "Música", "Conexión", "Filtros",
             "Estado (F2)", "Atajos", "API y sesión", "Mensajes automáticos",
             "Transmisión"])

    def test_pagina_general_primera_con_las_cinco_casillas_en_orden(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.nb.GetPageText(0), "General")
        pagina = next(p for p in dialogo._paginas() if p.GetName() == "PagGeneral")
        casillas = [h.GetName() for h in pagina.GetChildren()
                    if isinstance(h, gui.wx.CheckBox)]
        self.assertEqual(
            casillas,
            ["Buscar actualizaciones al iniciar",
             "Preguntar antes de salir si hay un chat conectado "
             "o una transmisión en curso",
             "Recordar la última dirección",
             "Reproducir el sonido de inicio",
             "Guardar un registro detallado para diagnosticar fallos"])
        self.assertFalse(any(p.GetName() == "PagDiagnostico"
                             for p in dialogo._paginas()))

    def test_abre_con_el_foco_en_la_lista_de_categorias(self):
        dialogo = self._dialogo()
        self.assertIs(gui.wx.Window.FindFocus(), dialogo.lista_categorias)

    def test_controles_nuevos_tienen_su_nombre_accesible(self):
        dialogo = self._dialogo()
        for nombre, pagina in (
                ("Buscar actualizaciones al iniciar", "PagGeneral"),
                ("Preguntar antes de salir si hay un chat conectado "
                 "o una transmisión en curso", "PagGeneral"),
                ("Recordar la última dirección", "PagGeneral"),
                ("Reproducir el sonido de inicio", "PagGeneral"),
                ("Guardar un registro detallado para diagnosticar fallos",
                 "PagGeneral"),
                ("Estrategia de la cola", "PagCola"),
                ("Tamaño máximo de la cola", "PagCola"),
                ("Leer solo el nombre a partir de", "PagCola"),
                ("Reconectar automáticamente si se corta", "PagConexion"),
                ("Espera máxima entre intentos, en segundos", "PagConexion"),
                ("Número máximo de intentos", "PagConexion"),
                ("Puerto del panel de chat", "PagTransmision"),
                ("Micrófono de OBS", "PagTransmision")):
            control = self._buscar(dialogo, nombre)
            self.assertIsNotNone(control)
            self.assertEqual(control.GetParent().GetName(), pagina)

    def test_pagina_voces_tiene_los_controles_en_el_orden_de_tab(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas() if p.GetName() == "PagVoz")
        esperados = ["Motor de voz", "Voz de lectura", "Velocidad de la voz",
                     "Volumen de la voz", "Tono de la voz", "Probar voz",
                     "MultiVoz", "Voz para los eventos"]
        orden = [h.GetName() for h in pagina.GetChildren()
                 if h.GetName() in esperados]
        self.assertEqual(orden, esperados)
        self.assertEqual(dialogo.sp_velocidad.GetIncrement(), 5)
        self.assertEqual(dialogo.sp_volumen.GetIncrement(), 5)
        self.assertEqual(dialogo.sp_tono.GetIncrement(), 5)

    def test_mensaje_nuevo_nace_activo(self):
        dialogo = self._dialogo()
        self.assertTrue(dialogo.chk_mensaje_activo.GetValue())

    def test_lista_de_programados_tiene_nombre_accesible(self):
        dialogo = self._dialogo()
        control = self._buscar(dialogo, "Mensajes automáticos guardados")
        self.assertIsNotNone(control)
        self.assertIs(control, dialogo.lista_programados)

    def test_microfono_guardado_se_conserva_sin_consultar_obs(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"obs_microfono": "Mic/Aux"})
        self.addCleanup(destruir, dialogo)

        self.assertEqual(dialogo.cho_microfono_obs.GetStringSelection(), "Mic/Aux")
        self.assertEqual(dialogo.cho_microfono_obs.GetStrings(),
                         ["Elegir automáticamente", "Mic/Aux"])

    def test_pagina_musica_despues_de_reproductor_con_sus_controles_en_orden(self):
        dialogo = self._dialogo()
        textos = [dialogo.nb.GetPageText(i)
                  for i in range(dialogo.nb.GetPageCount())]
        self.assertEqual(textos.index("Música"), textos.index("Reproductor") + 1)
        pagina = next(p for p in dialogo._paginas() if p.GetName() == "PagMusica")
        esperados = ["Carpeta de música", "MusicaAleatorio", "Repetir la música",
                     "MusicaRetomar", "MusicaSonidoTema", "MusicaDecirTitulo",
                     "MusicaIncluirArtista", "Volumen de la música",
                     "Salida de audio de la música", "Buscar las salidas de audio",
                     "MusicaAtajosGlobales"]
        orden = [h.GetName() for h in pagina.GetChildren()
                 if h.GetName() in esperados]
        self.assertEqual(orden, esperados)

    def test_pagina_musica_etiquetas_con_su_mnemonico(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas() if p.GetName() == "PagMusica")
        etiquetas = [c.GetLabel() for c in pagina.GetChildren()
                     if isinstance(c, (gui.wx.StaticText, gui.wx.Button,
                                       gui.wx.CheckBox))
                     and "&" in c.GetLabel()]
        self.assertEqual(etiquetas, [
            "Carpeta de &música:",
            "Reproducir en orden &aleatorio",
            "&Repetir:",
            "Recordar la ú&ltima lista al abrir",
            "&Sonido al pasar de tema",
            "&Decir el título al pasar de tema",
            "Incluir el ar&tista en el título",
            "&Volumen de la música",
            "Salida de a&udio de la música",
            "&Buscar las salidas de audio",
            "Usar los atajos de música en cualquier &programa",
        ])

    def test_los_mnemonicos_de_musica_no_se_repiten_ni_chocan_con_guardar(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas() if p.GetName() == "PagMusica")
        letras = []
        for control in pagina.GetChildren():
            if not isinstance(control, (gui.wx.StaticText, gui.wx.Button,
                                        gui.wx.CheckBox, gui.wx.RadioButton)):
                continue
            etiqueta = control.GetLabel()
            if "&" in etiqueta:
                letras.append(etiqueta.split("&", 1)[1][:1].lower())
        self.assertEqual(len(letras), 11)
        self.assertEqual(len(letras), len(set(letras)), letras)
        self.assertNotIn("g", letras)
        self.assertNotIn("c", letras)

    def test_artista_solo_se_habilita_con_decir_titulo(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"musica_decir_titulo": True,
                       "musica_incluir_artista": True})
        self.addCleanup(destruir, dialogo)
        self.assertTrue(dialogo.chk_musica_incluir_artista.IsEnabled())
        dialogo.chk_musica_decir_titulo.SetValue(False)
        evento = gui.wx.CommandEvent(gui.wx.wxEVT_CHECKBOX,
                                     dialogo.chk_musica_decir_titulo.GetId())
        evento.SetEventObject(dialogo.chk_musica_decir_titulo)
        dialogo.chk_musica_decir_titulo.GetEventHandler().ProcessEvent(evento)
        self.assertFalse(dialogo.chk_musica_incluir_artista.IsEnabled())

    def test_salida_guardada_se_conserva_sin_consultar_vlc(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"musica_salida": "vieja",
                       "musica_salida_nombre": "Salida vieja"})
        self.addCleanup(destruir, dialogo)

        self.assertEqual(dialogo.cho_musica_salida.GetStrings(),
                         ["Salida predeterminada", "Salida vieja"])
        self.assertEqual(dialogo.cho_musica_salida.GetSelection(), 1)

    def test_buscar_salidas_lanza_hilo_sin_consultar_al_construir(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.cho_musica_salida.GetStrings(),
                         ["Salida predeterminada"])
        hilo = mock.Mock()
        consulta = {}

        def crear_hilo(target, nombre):
            consulta["target"] = target
            consulta["nombre"] = nombre
            return hilo

        with mock.patch.object(gui_preferencias.diagnostico, "crear_hilo",
                               side_effect=crear_hilo), \
                mock.patch("ytchat.music.adaptador_vlc.salidas_audio",
                           return_value=[("altavoces", "Altavoces")]), \
                mock.patch.object(gui_preferencias.wx, "CallAfter",
                                  side_effect=lambda funcion, *args: funcion(*args)), \
                mock.patch.object(gui_preferencias, "anunciar"):
            dialogo._buscar_salidas(None)
            consulta["target"]()

        self.assertEqual(consulta["nombre"], "SalidasAudioPrefs")
        hilo.start.assert_called_once_with()
        self.assertEqual(dialogo.cho_musica_salida.GetStrings(),
                         ["Salida predeterminada", "Altavoces"])

    def test_salidas_encontradas_anuncia_cuantas_hallo(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._salidas_encontradas(
                [("altavoces", "Altavoces"), ("auriculares", "Auriculares")])
        anunciar.assert_called_once_with("Se encontraron 2 salidas de audio")
        self.assertEqual(dialogo.cho_musica_salida.GetSelection(), 0)

    def test_sin_salidas_anuncia_que_no_hallo_ninguna(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._salidas_encontradas([])
        anunciar.assert_called_once_with("No se encontraron salidas de audio")
        self.assertEqual(dialogo.cho_musica_salida.GetStrings(),
                         ["Salida predeterminada"])

    def test_una_sola_salida_se_anuncia_en_singular(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._salidas_encontradas([("altavoces", "Altavoces")])
        anunciar.assert_called_once_with("Se encontró 1 salida de audio")

    def test_la_guardada_no_encontrada_no_suma(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"musica_salida": "vieja",
                       "musica_salida_nombre": "Salida vieja"})
        self.addCleanup(destruir, dialogo)

        with mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._salidas_encontradas([("altavoces", "Altavoces")])
        anunciar.assert_called_once_with("Se encontró 1 salida de audio")

    def test_la_elegida_se_conserva_al_rehacer_la_lista(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"musica_salida": "vieja",
                       "musica_salida_nombre": "Salida vieja"})
        self.addCleanup(destruir, dialogo)

        with mock.patch.object(gui_preferencias, "anunciar"):
            dialogo._salidas_encontradas([("altavoces", "Altavoces")])
        self.assertEqual(dialogo.cho_musica_salida.GetStrings(),
                         ["Salida predeterminada", "Altavoces", "Salida vieja"])
        self.assertEqual(dialogo.cho_musica_salida.GetStringSelection(),
                         "Salida vieja")

    def test_salidas_encontradas_ignora_el_dialogo_destruido(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias.PreferenciasDialog, "__bool__",
                               lambda self: False, create=True), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._salidas_encontradas([("altavoces", "Altavoces")])
        anunciar.assert_not_called()

    def test_buscar_microfonos_lanza_hilo_sin_conectar_al_construir(self):
        dialogo = self._dialogo()
        hilo = mock.Mock()
        consulta = {}

        def crear_hilo(target, nombre):
            consulta["target"] = target
            consulta["nombre"] = nombre
            return hilo

        gestor = mock.Mock()
        gestor.fuentes_audio.return_value = ("Mic/Aux",)
        with mock.patch.object(gui_preferencias.diagnostico, "crear_hilo",
                               side_effect=crear_hilo), \
                mock.patch.object(gui_preferencias, "GestorPanelObs",
                                  return_value=gestor) as gestor_clase, \
                mock.patch.object(gui_preferencias.obs_cliente, "leer_ajustes"), \
                mock.patch.object(gui_preferencias.wx, "CallAfter",
                                  side_effect=lambda funcion, *args: funcion(*args)):
            dialogo._buscar_microfonos(None)
            gestor_clase.assert_not_called()
            consulta["target"]()

        self.assertEqual(consulta["nombre"], "MicrofonosPrefs")
        hilo.start.assert_called_once_with()
        gestor.conectar.assert_called_once_with()

    def test_las_paginas_se_desplazan_en_vertical(self):
        # Atajos mide más de 1200 px: sin desplazamiento, sus botones de
        # abajo (y «Restablecer») quedaban fuera del alcance del ratón.
        dialogo = self._dialogo()
        for pagina in dialogo._paginas():
            with self.subTest(pagina=pagina.GetName()):
                self.assertIsInstance(pagina, gui.wx.ScrolledWindow)
                self.assertEqual(pagina.GetScrollPixelsPerUnit(), (0, 20))

    def test_cada_pagina_cabe_a_lo_ancho(self):
        # No hay desplazamiento horizontal: lo que no quepa a lo ancho se corta.
        dialogo = self._dialogo()
        barra = gui.wx.SystemSettings.GetMetric(gui.wx.SYS_VSCROLL_X)
        for pagina in dialogo._paginas():
            with self.subTest(pagina=pagina.GetName()):
                visible = pagina.GetClientSize().width
                self.assertGreater(visible, 100)
                self.assertLessEqual(pagina.GetSizer().GetMinSize().width, visible - barra)

    def test_el_dialogo_se_puede_agrandar_pero_no_por_debajo_de_las_paginas(self):
        dialogo = self._dialogo()
        self.assertTrue(dialogo.GetWindowStyleFlag() & gui.wx.RESIZE_BORDER)
        necesario = max(p.GetSizer().GetMinSize().width for p in dialogo._paginas())
        self.assertGreater(dialogo.GetMinSize().width, necesario)
        self.assertGreaterEqual(dialogo.GetSize().width, dialogo.GetMinSize().width)

    def test_respuestas_de_hilos_ignoran_el_dialogo_destruido(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias.PreferenciasDialog, "__bool__",
                               lambda self: False, create=True), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(gui_preferencias._snd, "reproducir") as sonar, \
                mock.patch.object(gui_preferencias.wx, "MessageBox") as aviso:
            dialogo._microfonos_encontrados(("Mic/Aux",))
            dialogo._api_login_ok()
            dialogo._api_login_err(RuntimeError("x"))
        anunciar.assert_not_called()
        sonar.assert_not_called()
        aviso.assert_not_called()

    def test_guardar_escribe_las_mismas_claves(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones") as guardar, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)

        guardar.assert_called_once()
        claves = [(seccion, clave)
                  for seccion, clave, _valor in guardar.call_args.args[1]]
        esperadas = [
            ("programados", "activo"),
            ("ui", "tamanio_fuente_chat"),
            ("ui", "mostrar_total_superchats"),
            ("ui", "autoplay_reproductor"),
            ("ui", "reproductor_solo_audio"),
            ("ui", "mostrar_metadatos"),
            ("ui", "mostrar_botones_reproductor"),
            ("ui", "cache_video_mb"),
            ("voz", "motor"), ("voz", "voz"), ("voz", "voz_eventos"),
            ("voz", "multivoz"), ("voz", "velocidad_voz"),
            ("voz", "volumen"), ("voz", "tono"),
            ("voz", "voz_respaldo"), ("voz", "elevenlabs_tope"),
            ("voz", "elevenlabs_solo_importantes"),
            ("lectura", "formato_prefijo"),
            ("texto", "limpiar_emojis"), ("texto", "eliminar_urls"),
            ("tiktok", "anunciar_entradas"), ("texto", "max_longitud_mensaje"),
            ("cola", "estrategia"), ("cola", "tamanio_maximo"),
            ("cola", "umbral_solo_nombre"),
            ("reconexion", "reconectar"),
            ("reconexion", "espera_entre_intentos"),
            ("reconexion", "max_intentos"),
            ("actualizaciones", "buscar_al_iniciar"),
            ("ui", "confirmar_salida"),
            ("ui", "recordar_direccion"),
            ("ui", "sonido_inicio"),
            ("diagnostico", "registro_detallado"),
            ("overlay", "puerto"), ("obs", "microfono"),
            ("transmision", "avisar_sobrecarga"),
            ("musica", "aleatorio"), ("musica", "repetir"),
            ("musica", "retomar"), ("musica", "sonido_tema"),
            ("musica", "decir_titulo"), ("musica", "incluir_artista"),
            ("musica", "volumen"), ("musica", "atajos_globales"), ("musica", "carpeta"),
            ("musica", "salida"), ("musica", "salida_nombre"),
        ]
        esperadas.extend(("estado", componente)
                          for componente in gui_preferencias.estado_sesion.COMPONENTES)
        esperadas.extend([
            ("filtros", "palabras_silenciadas"),
            ("filtros", "usuarios_silenciados"),
        ])
        esperadas.extend(("atajos", accion)
                          for accion in dialogo._valores_atajo
                          if accion not in gui_preferencias.cfg.ATAJOS_FIJOS)
        self.assertEqual(sorted(claves), sorted(esperadas))
        self.assertEqual(len(claves), len(set(claves)))


class TestPreferenciasElevenLabs(unittest.TestCase):
    """La página «Voces» configura ElevenLabs sin editar archivos."""

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    @staticmethod
    def _buscar(raiz, nombre):
        pendientes = [raiz]
        while pendientes:
            control = pendientes.pop()
            if control.GetName() == nombre:
                return control
            pendientes.extend(control.GetChildren())
        return None

    @staticmethod
    def _mnemonicos(pagina):
        tipos = (gui.wx.StaticText, gui.wx.Button, gui.wx.CheckBox,
                 gui.wx.RadioButton)
        letras = []
        for control in pagina.GetChildren():
            if not isinstance(control, tipos):
                continue
            etiqueta = control.GetLabel()
            if "&" in etiqueta:
                letras.append(etiqueta.split("&", 1)[1][:1].lower())
        return letras

    @staticmethod
    def _pagina_voz(dialogo):
        return next(p for p in dialogo._paginas() if p.GetName() == "PagVoz")

    def test_controles_elevenlabs_visibles_solo_con_ese_motor(self):
        dialogo = self._dialogo({"motor": "elevenlabs"})
        for ctrl in dialogo._eleven_ctrls:
            self.assertTrue(ctrl.IsShown())
        for nombre in ("Clave de ElevenLabs", "Comprobar clave",
                       "Tope de caracteres de ElevenLabs",
                       "Solo lo importante con ElevenLabs",
                       "Voz de Windows de respaldo"):
            self.assertIsNotNone(self._buscar(dialogo, nombre))
        self.assertFalse(dialogo.cho_voz.IsEnabled())
        self.assertEqual(dialogo.cho_voz.GetStringSelection(),
                         "(comprueba la clave)")

        otro = self._dialogo({})
        for ctrl in otro._eleven_ctrls:
            self.assertFalse(ctrl.IsShown())

    def test_los_mnemonicos_de_la_pagina_no_se_repiten(self):
        dialogo = self._dialogo()
        letras = self._mnemonicos(self._pagina_voz(dialogo))
        self.assertTrue(letras)
        self.assertEqual(len(letras), len(set(letras)), letras)
        self.assertNotIn("g", letras)
        self.assertNotIn("c", letras)

    def test_comprobar_clave_con_error_deja_la_voz_deshabilitada(self):
        from ytchat.voice import elevenlabs
        dialogo = self._dialogo({"motor": "elevenlabs"})
        dialogo.btn_comprobar_clave.Disable()
        cliente = mock.Mock()
        cliente.voces.side_effect = elevenlabs.ElevenLabsError(
            elevenlabs.MOTIVO_CLAVE, "La clave de ElevenLabs no es válida.")
        with mock.patch.object(elevenlabs, "ClienteElevenLabs",
                               return_value=cliente), \
                mock.patch.object(gui_preferencias.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._consultar_clave("mala", True)
        self.assertFalse(dialogo.cho_voz.IsEnabled())
        self.assertEqual(dialogo.cho_voz.GetStringSelection(),
                         "(comprueba la clave)")
        self.assertTrue(dialogo.btn_comprobar_clave.IsEnabled())
        anunciar.assert_called_once_with("La clave de ElevenLabs no es válida.")

    def test_comprobar_clave_con_exito_llena_voces_y_anuncia(self):
        from ytchat.voice import elevenlabs
        dialogo = self._dialogo({"motor": "elevenlabs"})
        dialogo.btn_comprobar_clave.Disable()
        cliente = mock.Mock()
        cliente.voces.return_value = [("id1", "Ana"), ("id2", "Beto")]
        cliente.saldo.return_value = (1234, 30000)
        with mock.patch.object(elevenlabs, "ClienteElevenLabs",
                               return_value=cliente), \
                mock.patch.object(gui_preferencias.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar:
            dialogo._consultar_clave("buena", True)
        self.assertEqual(dialogo.cho_voz.GetStrings(), ["Ana", "Beto"])
        self.assertTrue(dialogo.cho_voz.IsEnabled())
        anunciar.assert_called_once_with(
            "Clave válida. 2 voces. Usados 1.234 de 30.000 caracteres este mes.")

    def test_elegir_elevenlabs_muestra_los_controles(self):
        dialogo = self._dialogo({})
        for ctrl in dialogo._eleven_ctrls:
            self.assertFalse(ctrl.IsShown())
        dialogo.cho_motor.SetSelection(motores.MOTORES.index("elevenlabs"))
        dialogo._on_motor_cambiado(None)
        for ctrl in dialogo._eleven_ctrls:
            self.assertTrue(ctrl.IsShown())
        dialogo.cho_motor.SetSelection(0)
        dialogo._on_motor_cambiado(None)
        for ctrl in dialogo._eleven_ctrls:
            self.assertFalse(ctrl.IsShown())

    def test_guardar_con_elevenlabs_sin_voces_conserva_el_motor_anterior(self):
        dialogo = self._dialogo({"motor": "sapi", "voz": "Voz de prueba"})
        dialogo.cho_motor.SetSelection(motores.MOTORES.index("elevenlabs"))
        dialogo._on_motor_cambiado(None)
        self.assertEqual(dialogo._voces, [])
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=True) as guardar, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        claves = [(seccion, clave, valor)
                  for seccion, clave, valor in guardar.call_args.args[1]]
        self.assertNotIn(("voz", "motor", "elevenlabs"), claves)
        anunciar.assert_not_called()
        self.assertIn("El motor elegido no está disponible, se conserva el anterior.",
                      dialogo.avisos)

    def test_guardar_clave_nueva_usa_credenciales_y_no_el_ini(self):
        dialogo = self._dialogo({"motor": "elevenlabs"})
        dialogo.txt_clave_eleven.SetValue("clave-secreta")
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=True) as guardar, \
                mock.patch.object(gui_preferencias.credenciales,
                                  "guardar_campo") as guardar_campo, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        guardar_campo.assert_called_once_with("elevenlabs_clave", "clave-secreta")
        valores = [str(valor) for _seccion, _clave, valor in guardar.call_args.args[1]]
        self.assertNotIn("clave-secreta", valores)


class TestAplicarPreferenciasMotor(unittest.TestCase):
    """Aplicación en caliente del motor y la voz tras cerrar Preferencias."""

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()

    def _frame(self, configuracion):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = dict(configuracion)
        frame._conectado = False
        frame._voz_idx = 0
        frame.voz_submenu = mock.Mock()
        frame.voz_submenu.GetMenuItems.return_value = []
        frame.lb_chat = mock.Mock()
        frame._rep_panel = mock.Mock()
        for metodo in ("_build_menubar", "poblar_voces", "_aplicar_voz",
                       "_marcar_filtro", "_sincronizar_checks", "_rebuild_listbox",
                       "_set_conectado_ui", "_actualizar_estado_online",
                       "set_metadatos_visible", "_actualizar_vigilante_obs"):
            setattr(frame, metodo, mock.Mock())
        frame._worker = mock.Mock()
        return frame

    def test_motor_distinto_cambia_el_motor_y_anuncia(self):
        frame = self._frame({"motor": "onecore", "voz": "Voz B",
                             "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "sapi"
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz A", "Voz B"]), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._aplicar_preferencias_en_caliente()
        frame._worker.cambiar_motor.assert_called_once_with("onecore", "Voz B")
        anunciar.assert_any_call("Motor de voz: Windows OneCore")

    def test_mismo_motor_no_cambia_el_motor(self):
        frame = self._frame({"motor": "onecore", "voz": "Voz B",
                             "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "onecore"
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz A", "Voz B"]), \
                mock.patch.object(gui, "anunciar"):
            frame._aplicar_preferencias_en_caliente()
        frame._worker.cambiar_motor.assert_not_called()

    def test_solo_audio_activo_se_aplica_al_panel(self):
        frame = self._frame({"motor": "sapi", "atajos_raw": {},
                             "reproductor_solo_audio": True})
        frame._worker.motor_activo.return_value = "sapi"
        with mock.patch.object(gui, "anunciar"):
            frame._aplicar_preferencias_en_caliente()
        frame._rep_panel.set_solo_audio.assert_called_once_with(True)

    def test_solo_audio_ausente_se_aplica_en_falso(self):
        frame = self._frame({"motor": "sapi", "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "sapi"
        with mock.patch.object(gui, "anunciar"):
            frame._aplicar_preferencias_en_caliente()
        frame._rep_panel.set_solo_audio.assert_called_once_with(False)

    def test_aplica_los_ajustes_de_elevenlabs_al_worker(self):
        frame = self._frame({"motor": "elevenlabs", "atajos_raw": {},
                             "elevenlabs_tope": 40000,
                             "elevenlabs_solo_importantes": True,
                             "voz_respaldo": "Lucía"})
        frame._worker.motor_activo.return_value = "sapi"
        with mock.patch.object(motores, "listar_voces", return_value=["Ana"]), \
                mock.patch.object(gui, "anunciar"):
            frame._aplicar_preferencias_en_caliente()
        frame._worker.configurar_elevenlabs.assert_called_once_with(
            40000, True, "Lucía")


class TestGuardadoDeNuevasPreferencias(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                                encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _guardar(self, dialogo):
        with mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        # Los avisos ya no se dicen acá: los junta el diálogo y los dice la
        # ventana principal cuando recupera el foco.
        anunciar.assert_not_called()

    def _opciones_guardadas(self):
        parser = config._mk_parser()
        parser.read(self.ruta / "config.ini", encoding="utf-8")
        return parser

    def test_motor_sin_voces_no_escribe_motor_ni_voz_y_avisa(self):
        with mock.patch.object(motores, "listar_voces", return_value=[]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, {"motor": "onecore", "voz": "Voz vieja", "volumen": 0.5})
        self.addCleanup(destruir, dialogo)
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones") as guardar, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        claves = [(seccion, clave)
                  for seccion, clave, _valor in guardar.call_args.args[1]]
        self.assertNotIn(("voz", "motor"), claves)
        self.assertNotIn(("voz", "voz"), claves)
        self.assertIn(("voz", "velocidad_voz"), claves)
        self.assertIn(("voz", "volumen"), claves)
        self.assertIn(("voz", "tono"), claves)
        self.assertEqual(dialogo._config.get("motor"), "onecore")
        self.assertEqual(dialogo._config.get("voz"), "Voz vieja")
        anunciar.assert_not_called()
        self.assertIn("El motor elegido no está disponible, se conserva el anterior.",
                      dialogo.avisos)

    def test_cargar_configuracion_devuelve_registro_detallado_del_archivo(self):
        for valor, esperado in (("true", True), ("false", False)):
            with self.subTest(valor=valor):
                (self.ruta / "config.ini").write_text(
                    config._CONFIG_FALLBACK.replace("registro_detallado = false",
                                                    f"registro_detallado = {valor}"),
                    encoding="utf-8")
                self.assertEqual(config.cargar_configuracion()["registro_detallado"],
                                 esperado)

    def test_guardar_escribe_las_nueve_claves_nuevas(self):
        dialogo = self._dialogo()
        dialogo.rb_estrategia.SetSelection(0)
        dialogo.sp_cola_maxima.SetValue(42)
        dialogo.sp_umbral_nombre.SetValue(7)
        dialogo.chk_reconectar.SetValue(False)
        dialogo.sp_espera_reconexion.SetValue(12)
        dialogo.sp_max_intentos.SetValue(3)
        dialogo.chk_registro_detallado.SetValue(True)
        dialogo.sp_puerto_overlay.SetValue(9000)
        dialogo.cho_microfono_obs.Append("Mic/Aux")
        dialogo.cho_microfono_obs.SetSelection(1)

        self._guardar(dialogo)
        opciones = self._opciones_guardadas()

        self.assertEqual(opciones.get("cola", "estrategia"), "todas")
        self.assertEqual(opciones.get("cola", "tamanio_maximo"), "42")
        self.assertEqual(opciones.get("cola", "umbral_solo_nombre"), "7")
        self.assertEqual(opciones.get("reconexion", "reconectar"), "false")
        self.assertEqual(opciones.get("reconexion", "espera_entre_intentos"), "12")
        self.assertEqual(opciones.get("reconexion", "max_intentos"), "3")
        self.assertEqual(opciones.get("diagnostico", "registro_detallado"), "true")
        self.assertEqual(opciones.get("overlay", "puerto"), "9000")
        self.assertEqual(opciones.get("obs", "microfono"), "Mic/Aux")
        self.assertEqual(dialogo.avisos, [
            "Preferencias guardadas.",
            "El cambio del registro detallado se aplica al reiniciar la aplicación.",
        ])

    def test_estrategia_guarda_la_clave_y_no_la_etiqueta(self):
        for seleccion, clave, etiqueta in (
                (0, "todas", "Leer todos los mensajes"),
                (1, "limite", "Descartar los más viejos si se acumulan")):
            with self.subTest(clave=clave):
                dialogo = self._dialogo()
                dialogo.rb_estrategia.SetSelection(seleccion)
                self._guardar(dialogo)
                estrategia = self._opciones_guardadas().get("cola", "estrategia")
                self.assertEqual(estrategia, clave)
                self.assertNotEqual(estrategia, etiqueta)

    def test_cambiar_el_puerto_con_el_panel_encendido_avisa_donde_se_aplica(self):
        dialogo = self._dialogo({"overlay_activo": True, "overlay_puerto": 8730})
        dialogo.sp_puerto_overlay.SetValue(9000)

        self._guardar(dialogo)

        self.assertIn(
            "El puerto nuevo del panel de chat se aplica al apagarlo y "
            "volver a encenderlo desde el panel de transmisión.",
            dialogo.avisos)

    def test_el_puerto_sin_cambios_o_con_el_panel_apagado_no_avisa(self):
        for configuracion, puerto in (
                ({"overlay_activo": True, "overlay_puerto": 8730}, 8730),
                ({"overlay_activo": False, "overlay_puerto": 8730}, 9000)):
            with self.subTest(configuracion=configuracion, puerto=puerto):
                dialogo = self._dialogo(dict(configuracion))
                dialogo.sp_puerto_overlay.SetValue(puerto)
                self._guardar(dialogo)
                self.assertEqual(dialogo.avisos, ["Preferencias guardadas."])

    def test_microfono_automatico_se_guarda_vacio(self):
        dialogo = self._dialogo({"obs_microfono": "Mic/Aux"})
        dialogo.cho_microfono_obs.SetSelection(0)
        self.assertEqual(dialogo._ruta, self.ruta / "config.ini")

        self._guardar(dialogo)

        self.assertEqual(self._opciones_guardadas().get("obs", "microfono"), "")

    def test_musica_guarda_carpeta_salida_y_memoria(self):
        dialogo = self._dialogo()
        dialogo.dir_musica_carpeta.SetPath("C:\\Música\\Rock and Roll")
        dialogo.chk_musica_aleatorio.SetValue(True)
        dialogo.chk_musica_retomar.SetValue(False)
        dialogo.sp_musica_volumen.SetValue(80)
        dialogo._musica_salidas_ids = ["", "altavoces"]
        dialogo.cho_musica_salida.Set(["Salida predeterminada", "Altavoces"])
        dialogo.cho_musica_salida.SetSelection(1)

        self._guardar(dialogo)

        opciones = self._opciones_guardadas()
        self.assertEqual(opciones.get("musica", "carpeta"),
                         config.codificar_texto_ini("C:\\Música\\Rock and Roll"))
        self.assertEqual(opciones.get("musica", "aleatorio"), "true")
        self.assertEqual(opciones.get("musica", "repetir"), "no")
        self.assertEqual(opciones.get("musica", "retomar"), "false")
        self.assertEqual(opciones.get("musica", "sonido_tema"), "true")
        self.assertEqual(opciones.get("musica", "decir_titulo"), "true")
        self.assertEqual(opciones.get("musica", "incluir_artista"), "false")
        self.assertEqual(opciones.get("musica", "volumen"), "80")
        self.assertEqual(opciones.get("musica", "salida"), "altavoces")
        self.assertEqual(opciones.get("musica", "salida_nombre"), "Altavoces")
        self.assertEqual(dialogo._config["musica_carpeta"],
                         "C:\\Música\\Rock and Roll")
        self.assertEqual(dialogo._config["musica_salida"], "altavoces")
        self.assertEqual(dialogo._config["musica_salida_nombre"], "Altavoces")
        self.assertEqual(dialogo._config["musica_volumen"], 80)
        self.assertIs(dialogo._config["musica_aleatorio"], True)

    def test_musica_con_salida_predeterminada_guarda_vacio(self):
        dialogo = self._dialogo({"musica_salida": "vieja",
                                 "musica_salida_nombre": "Salida vieja"})
        dialogo.cho_musica_salida.SetSelection(0)

        self._guardar(dialogo)

        opciones = self._opciones_guardadas()
        self.assertEqual(opciones.get("musica", "salida"), "")
        self.assertEqual(opciones.get("musica", "salida_nombre"), "")
        self.assertEqual(dialogo._config["musica_salida"], "")
        self.assertEqual(dialogo._config["musica_salida_nombre"], "")

    def test_fallo_de_escritura_anuncia_que_se_perdera_y_no_el_exito(self):
        dialogo = self._dialogo()
        frase = ("Las preferencias se aplicaron, pero no se pudieron guardar "
                 "en el disco. Se perderán al cerrar la aplicación.")
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=False), \
                mock.patch.object(gui_preferencias._snd, "reproducir") as sonar, \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        self.assertEqual(dialogo.avisos, [frase])
        self.assertNotIn("Preferencias guardadas.", dialogo.avisos)
        anunciar.assert_not_called()
        sonar.assert_any_call("error")

    def test_escritura_ok_anuncia_preferencias_guardadas(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=True) as guardar, \
                mock.patch.object(gui_preferencias._snd, "reproducir") as sonar, \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        guardar.assert_called_once()
        self.assertEqual(dialogo.avisos, ["Preferencias guardadas."])
        anunciar.assert_not_called()
        sonar.assert_any_call("copiar")


class TestPreferenciasArchivoBotones(unittest.TestCase):
    """Los cuatro botones de General. Abre ventanas: NO correr en esta máquina."""

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text("[voz]\nmotor = sapi\n",
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pagina_general(self, dialogo):
        return next(p for p in dialogo._paginas() if p.GetName() == "PagGeneral")

    def test_general_tiene_los_cuatro_botones_despues_de_las_casillas(self):
        dialogo = self._dialogo()
        pagina = self._pagina_general(dialogo)
        hijos = pagina.GetChildren()
        self.assertEqual(
            [type(h).__name__ for h in hijos],
            ["CheckBox"] * 5 + ["Button"] * 4)
        self.assertEqual(
            [h.GetName() for h in hijos if isinstance(h, gui.wx.Button)],
            ["Abrir la carpeta de datos",
             "Exportar las preferencias",
             "Importar las preferencias",
             "Restablecer todas las preferencias"])

    def _cuadro_archivo(self, ruta):
        cuadro = mock.MagicMock()
        cuadro.ShowModal.return_value = gui.wx.ID_OK
        cuadro.GetPath.return_value = str(ruta)
        return cuadro

    def test_importar_valido_cierra_sin_guardar(self):
        dialogo = self._dialogo()
        origen = self.ruta / "nuevo.ini"
        origen.write_text("[voz]\nmotor = onecore\n", encoding="utf-8")
        cuadro = self._cuadro_archivo(origen)
        with mock.patch.object(gui_preferencias.wx, "FileDialog",
                               return_value=cuadro) as crear, \
                mock.patch.object(gui_preferencias.wx, "MessageBox"), \
                mock.patch.object(gui_preferencias.cfg,
                                  "guardar_opciones") as guardar, \
                mock.patch.object(dialogo, "EndModal") as cerrar:
            crear.return_value.__enter__.return_value = cuadro
            dialogo._importar_prefs(None)
        guardar.assert_not_called()
        self.assertEqual((self.ruta / "config.ini").read_text(encoding="utf-8"),
                         "[voz]\nmotor = onecore\n")
        self.assertEqual((self.ruta / "config.anterior.ini").read_text(
            encoding="utf-8"), "[voz]\nmotor = sapi\n")
        cerrar.assert_called_once_with(gui.wx.ID_CANCEL)

    def test_importar_invalido_no_cambia_nada_y_sigue_abierto(self):
        dialogo = self._dialogo()
        origen = self.ruta / "malo.txt"
        origen.write_text("esto no es un ini\n", encoding="utf-8")
        cuadro = self._cuadro_archivo(origen)
        with mock.patch.object(gui_preferencias.wx, "FileDialog",
                               return_value=cuadro) as crear, \
                mock.patch.object(gui_preferencias.wx,
                                  "MessageBox") as aviso, \
                mock.patch.object(dialogo, "EndModal") as cerrar:
            crear.return_value.__enter__.return_value = cuadro
            dialogo._importar_prefs(None)
        aviso.assert_called_once()
        self.assertEqual((self.ruta / "config.ini").read_text(encoding="utf-8"),
                         "[voz]\nmotor = sapi\n")
        self.assertFalse((self.ruta / "config.anterior.ini").exists())
        cerrar.assert_not_called()

    def test_importar_error_escritura_muestra_aviso_y_sigue_abierto(self):
        dialogo = self._dialogo()
        origen = self.ruta / "nuevo.ini"
        origen.write_text("[voz]\nmotor = onecore\n", encoding="utf-8")
        cuadro = self._cuadro_archivo(origen)
        with mock.patch.object(gui_preferencias.wx, "FileDialog",
                               return_value=cuadro) as crear, \
                mock.patch.object(gui_preferencias.wx,
                                  "MessageBox") as aviso, \
                mock.patch.object(gui_preferencias.preferencias_archivo,
                                  "importar",
                                  side_effect=OSError("disco lleno")), \
                mock.patch.object(dialogo, "EndModal") as cerrar:
            crear.return_value.__enter__.return_value = cuadro
            dialogo._importar_prefs(None)
        aviso.assert_called_once()
        texto = aviso.call_args.args[0]
        self.assertIn("No se pudieron importar las preferencias:", texto)
        self.assertIn("disco lleno", texto)
        cerrar.assert_not_called()

    def test_restablecer_con_no_no_cambia_nada(self):
        dialogo = self._dialogo()
        respuesta = mock.Mock()
        respuesta.ShowModal.return_value = gui.wx.ID_NO
        with mock.patch.object(gui_preferencias.wx, "MessageDialog",
                               return_value=respuesta) as crear, \
                mock.patch.object(gui_preferencias.wx, "MessageBox") as aviso, \
                mock.patch.object(dialogo, "EndModal") as cerrar:
            dialogo._restablecer_prefs(None)
        crear.assert_called_once()
        respuesta.Destroy.assert_called_once_with()
        aviso.assert_not_called()
        cerrar.assert_not_called()
        self.assertEqual((self.ruta / "config.ini").read_text(encoding="utf-8"),
                         "[voz]\nmotor = sapi\n")
        self.assertFalse((self.ruta / "config.anterior.ini").exists())


class TestProgramadorGui(unittest.TestCase):
    def _frame(self, **config):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"programados_activo": True, **config}
        frame._mensajes_programados = [{"texto": "Hola", "activo": True,
                                        "minutos_min": 5, "minutos_max": 5,
                                        "proximo": 0.0}]
        frame._programados_reloj_iniciado = True
        frame._programados_ultimo_envio = None
        frame._programado_en_curso = False
        frame._conectado = True
        frame._es_tiktok = False
        frame._live_chat_id = "chat"
        frame._chat_propio = True
        frame._conexion_propia = False
        return frame

    def test_envio_exitoso_avanza_el_reloj(self):
        frame = self._frame()
        with mock.patch.object(gui.programados, "calcular_proximo",
                               return_value=900.0) as calcular:
            frame._programado_enviado(frame._mensajes_programados[0])
        self.assertEqual(frame._mensajes_programados[0]["proximo"], 900.0)
        self.assertIsNotNone(frame._programados_ultimo_envio)
        calcular.assert_called_once()

    def test_envia_con_el_doble_de_la_api_sin_anunciar_exito(self):
        frame = self._frame()
        cliente = mock.Mock()
        cliente.token_actualizado.return_value = None

        class Hilo:
            def __init__(self, objetivo):
                self.objetivo = objetivo

            def start(self):
                self.objetivo()

        with mock.patch.object(gui.youtube_api, "ClienteYouTube",
                               return_value=cliente), \
                mock.patch.object(gui.credenciales, "cargar", return_value={}), \
                mock.patch.object(gui.diagnostico, "crear_hilo",
                                  side_effect=lambda objetivo, nombre: Hilo(objetivo)), \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=lambda fn, *args: fn(*args)), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._enviar_programado(frame._mensajes_programados[0], 1000.0)
        cliente.enviar_mensaje_live.assert_called_once_with("chat", "Hola")
        anunciar.assert_not_called()

    def test_no_duplica_un_envio_en_curso(self):
        frame = self._frame()
        frame._programado_en_curso = True
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_procesar_arma_la_bandera_antes_de_enviar(self):
        frame = self._frame()
        frame._mensajes_programados[0]["proximo"] = 0.0

        class Hilo:
            def start(self):
                pass

        with mock.patch.object(gui.time, "time", return_value=1000.0), \
                mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(gui.diagnostico, "crear_hilo",
                                  return_value=Hilo()):
            frame._procesar_programado()
        self.assertTrue(frame._programado_en_curso)

    def test_al_encender_da_cuerda_al_reloj(self):
        frame = self._frame()
        frame._programados_reloj_iniciado = False
        with mock.patch.object(gui.programados, "iniciar_reloj") as iniciar:
            frame._iniciar_programados_si_corresponde(1000.0)
        iniciar.assert_called_once()
        self.assertTrue(frame._programados_reloj_iniciado)

    def test_procesar_no_vuelve_a_dar_cuerda_al_reloj(self):
        frame = self._frame()
        frame._programados_reloj_iniciado = False
        frame._conectado = False
        mensaje = frame._mensajes_programados[0]
        with mock.patch.object(gui.time, "time", side_effect=(1000.0, 2000.0)):
            frame._procesar_programado()
            proximo = mensaje["proximo"]
            frame._procesar_programado()
        self.assertEqual(mensaje["proximo"], proximo)

    def test_no_envia_si_no_hay_conexion(self):
        frame = self._frame()
        frame._conectado = False
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_no_envia_sin_sesion_api(self):
        frame = self._frame()
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=False), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_no_envia_si_falta_live_chat_id(self):
        frame = self._frame()
        frame._live_chat_id = ""
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_no_envia_si_interruptor_apagado(self):
        frame = self._frame(programados_activo=False)
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_apagado_no_pide_sesion_api(self):
        frame = self._frame(programados_activo=False)
        with mock.patch.object(frame, "_sesion_api_disponible") as sesion, \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        sesion.assert_not_called()
        enviar.assert_not_called()

    def test_no_envia_en_tiktok(self):
        frame = self._frame()
        frame._es_tiktok = True
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_no_envia_en_directo_ajeno(self):
        frame = self._frame()
        frame._chat_propio = False
        frame._conexion_propia = False
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_envia_si_la_conexion_es_propia(self):
        frame = self._frame()
        frame._chat_propio = False
        frame._conexion_propia = True
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_called_once()

    def test_el_reloj_no_arranca_hasta_poder_mandar(self):
        frame = self._frame()
        frame._conectado = False
        frame._programados_reloj_iniciado = False
        mensaje = frame._mensajes_programados[0]
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(gui.time, "time", return_value=1000.0):
            frame._procesar_programado()
        self.assertFalse(frame._programados_reloj_iniciado)
        self.assertEqual(mensaje["proximo"], 0.0)
        frame._conectado = True
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(gui.time, "time", return_value=1000.0):
            frame._procesar_programado()
        self.assertTrue(frame._programados_reloj_iniciado)
        self.assertGreater(mensaje["proximo"], 0.0)

    def test_al_desconectar_el_reloj_vuelve_a_empezar(self):
        frame = self._frame()
        frame._conectado = False
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True):
            frame._procesar_programado()
        self.assertFalse(frame._programados_reloj_iniciado)

    def test_no_envia_si_elegir_devuelve_none(self):
        frame = self._frame()
        with mock.patch.object(frame, "_sesion_api_disponible", return_value=True), \
                mock.patch.object(gui.programados, "elegir_envio", return_value=None), \
                mock.patch.object(frame, "_enviar_programado") as enviar:
            frame._procesar_programado()
        enviar.assert_not_called()

    def test_error_apaga_programador_y_anuncia_una_vez(self):
        frame = self._frame()
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._programado_fallo(RuntimeError("rateLimitExceeded"))
        self.assertFalse(frame._config["programados_activo"])
        anunciar.assert_called_once_with(
            "Los mensajes automáticos se detuvieron por un error del servicio.")

    def test_error_baja_la_bandera_de_envio(self):
        frame = self._frame()
        frame._programado_en_curso = True
        with mock.patch.object(gui, "anunciar"):
            frame._programado_fallo(RuntimeError("rateLimitExceeded"))
        self.assertFalse(frame._programado_en_curso)

    def test_snapshot_omite_proximo_si_el_interruptor_esta_apagado(self):
        frame = self._frame(programados_activo=False)
        frame._tipo_video = "live_youtube"
        frame._titulo_stream = "Directo"
        frame._metadatos = {}
        frame._sc_totales = {}
        snapshot = frame._snapshot_sesion()
        self.assertEqual(snapshot.programados_proximo, "")


class TestPreferenciasRecargaProgramados(unittest.TestCase):

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._config = {}
        frame._mensajes_programados = [{"texto": "Viejo", "minutos_min": 10,
                                        "minutos_max": 10, "activo": True,
                                        "proximo": 900.0}]
        frame._programados_reloj_iniciado = True
        frame._aplicar_preferencias_en_caliente = mock.Mock()
        frame._actualizar_estado_online = mock.Mock()
        return frame

    def _correr(self, frame, acepto, nuevos, abrir=None):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "mensajes_programados.json"
            ruta.write_text(json.dumps(nuevos, ensure_ascii=False),
                            encoding="utf-8")
            with mock.patch.object(gui_preferencias, "abrir_preferencias",
                                   side_effect=abrir, return_value=acepto), \
                    mock.patch.object(gui.wx, "CallLater",
                                      side_effect=lambda ms, fn: fn()), \
                    mock.patch.object(gui.paths, "mensajes_programados",
                                      return_value=ruta):
                frame._on_preferencias(None)
        return frame

    def test_aceptar_recarga_la_lista_y_rearma_el_reloj(self):
        frame = self._correr(self._frame(), True, [{"texto": "Nuevo"}])
        self.assertEqual([m["texto"] for m in frame._mensajes_programados],
                         ["Nuevo"])
        self.assertFalse(frame._programados_reloj_iniciado)
        frame._aplicar_preferencias_en_caliente.assert_called_once()

    def test_cancelar_tambien_recarga_la_lista(self):
        frame = self._correr(self._frame(), False, [{"texto": "Nuevo"}])
        self.assertEqual([m["texto"] for m in frame._mensajes_programados],
                         ["Nuevo"])
        self.assertFalse(frame._programados_reloj_iniciado)
        frame._aplicar_preferencias_en_caliente.assert_not_called()

    def test_guardar_aplica_y_despues_anuncia_sin_urgencia(self):
        frame = self._frame()
        orden = []
        frame._aplicar_preferencias_en_caliente = mock.Mock(
            side_effect=lambda: orden.append("aplicar"))

        def abrir(parent, config, pagina=None, avisos=None):
            avisos.append("Preferencias guardadas.")
            return True

        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "mensajes_programados.json"
            ruta.write_text("[]", encoding="utf-8")
            with mock.patch.object(gui_preferencias, "abrir_preferencias",
                                   side_effect=abrir), \
                    mock.patch.object(gui.wx, "CallLater",
                                      side_effect=lambda ms, fn: fn()), \
                    mock.patch.object(gui.paths, "mensajes_programados",
                                      return_value=ruta), \
                    mock.patch.object(
                        gui, "anunciar",
                        side_effect=lambda texto, urgente=True:
                            orden.append(("anunciar", texto, urgente))):
                frame._on_preferencias(None)

        self.assertEqual(orden, [
            "aplicar",
            ("anunciar", "Preferencias guardadas.", False),
        ])

    def test_cancelar_no_aplica_ni_anuncia(self):
        frame = self._frame()
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "mensajes_programados.json"
            ruta.write_text("[]", encoding="utf-8")
            with mock.patch.object(gui_preferencias, "abrir_preferencias",
                                   return_value=False), \
                    mock.patch.object(gui.wx, "CallLater") as diferir, \
                    mock.patch.object(gui.paths, "mensajes_programados",
                                      return_value=ruta), \
                    mock.patch.object(gui, "anunciar") as anunciar:
                frame._on_preferencias(None)
        diferir.assert_not_called()
        frame._aplicar_preferencias_en_caliente.assert_not_called()
        anunciar.assert_not_called()


class TestDescartesGui(unittest.TestCase):
    def _frame(self, descartados=3):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._config = {"umbral_solo_nombre": 0}
        frame._stats = mock.Mock(descartados=descartados)
        frame._descartes_avisado = False
        frame._actualizar_sb = mock.Mock()
        frame._procesar_programado = mock.Mock()
        return frame

    def test_el_timer_anuncia_los_descartes_una_sola_vez(self):
        frame = self._frame()
        with mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui._snd, "reproducir") as sonido:
            frame._on_timer(None)
            frame._on_timer(None)
        anunciar.assert_called_once_with(gui.descartes.frase_aviso(0))
        sonido.assert_called_once_with("aviso")
        self.assertTrue(frame._descartes_avisado)

    def test_el_snapshot_lleva_los_descartes_al_estado(self):
        frame = self._frame(descartados=7)
        frame.__dict__.update(
            _conectado=False, _es_tiktok=False,
            _tipo_video=gui.deteccion.DESCONOCIDO, _titulo_stream="",
            _metadatos={}, _sc_totales={}, _mensajes_programados=[],
            _obs_vigilante=None, _cola=mock.Mock(), _worker=mock.Mock())
        snapshot = frame._snapshot_sesion()
        self.assertEqual(snapshot.descartados, "Mensajes descartados: 7")

    def test_al_reconectar_puede_avisar_otra_vez(self):
        frame = self._frame()
        frame._conectado = True
        frame._live_chat_id = ""
        frame._causa_sin_chat = ""
        frame._tipo_video = gui.deteccion.DESCONOCIDO
        frame._es_tiktok = False
        frame._descartar_pendientes = mock.Mock()
        frame._chat = mock.Mock()
        frame.lb_chat = mock.Mock()
        frame._sc_totales = {}
        frame._metadatos = {}
        frame.txt_info = mock.Mock()
        frame._rep_panel = mock.Mock()
        frame._com_panel = mock.Mock()
        frame._worker = mock.Mock()
        frame._mostrar_zona = mock.Mock()
        frame._anunciar_conectado = mock.Mock()
        frame.set_titulo_stream = mock.Mock()
        frame.lbl_tipo = mock.Mock()
        frame.txt_url = mock.Mock()
        frame._set_conectado_ui = mock.Mock()
        frame._actualizar_estado_online = mock.Mock()
        frame._stats.reset.side_effect = lambda: setattr(frame._stats, "descartados", 0)

        with mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.wx, "CallAfter"), \
                mock.patch.object(gui._snd, "reproducir"):
            frame._on_timer(None)
            frame.set_conectado(False)
            self.assertFalse(frame._descartes_avisado)
            frame._stats.descartados = 3
            frame.set_conectado(True)
            frame._on_timer(None)

        avisos = [llamada.args[0] for llamada in anunciar.call_args_list]
        self.assertEqual(avisos.count(gui.descartes.frase_aviso(0)), 2)


class TestLiveChatIdPorSesion(unittest.TestCase):
    """El id del chat en vivo llega de un hilo que puede terminar tarde: si
    es de una conexión anterior, aceptarlo mandaría los mensajes programados
    y el compositor al directo equivocado."""

    def _frame(self, video_actual):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame.__dict__.update(_alive=True, _video_id_sesion=video_actual,
                              _live_chat_id="", _causa_sin_chat="")
        frame._actualizar_estado_online = mock.Mock()
        return frame

    def test_acepta_el_id_del_video_vigente(self):
        frame = self._frame("abc")
        frame.set_live_chat_id("chat-abc", "", video_id="abc")
        self.assertEqual(frame._live_chat_id, "chat-abc")
        frame._actualizar_estado_online.assert_called_once()

    def test_ignora_el_id_de_un_video_anterior(self):
        frame = self._frame("nuevo")
        frame.set_live_chat_id("chat-viejo", "", video_id="viejo")
        self.assertEqual(frame._live_chat_id, "")
        frame._actualizar_estado_online.assert_not_called()

    def test_sin_video_id_conserva_el_comportamiento_anterior(self):
        frame = self._frame("abc")
        frame.set_live_chat_id("chat", "causa")
        self.assertEqual((frame._live_chat_id, frame._causa_sin_chat), ("chat", "causa"))

    def test_por_defecto_el_directo_es_ajeno(self):
        frame = self._frame("abc")
        frame.set_live_chat_id("chat", "causa")
        self.assertFalse(frame._chat_propio)

    def test_guarda_si_el_directo_es_propio(self):
        frame = self._frame("abc")
        frame.set_live_chat_id("chat", "causa", video_id="abc", propio=True)
        self.assertEqual(frame._live_chat_id, "chat")
        self.assertTrue(frame._chat_propio)

    def test_set_tipo_video_fija_el_video_de_la_sesion(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame.__dict__.update(_alive=True, _video_id_sesion="", _config={},
                              _sc_totales={}, _tipo_video=gui.deteccion.DESCONOCIDO,
                              _es_tiktok=False)
        for nombre in ("_descartar_pendientes", "_chat", "lb_chat", "_com_panel",
                       "_rep_panel", "_fijar_tipo", "_actualizar_estado_online",
                       "_actualizar_titulo"):
            setattr(frame, nombre, mock.Mock())
        try:
            frame.set_tipo_video(gui.deteccion.LIVE, "abc")
        except Exception:
            pass  # el resto del método toca controles que aquí no existen
        self.assertEqual(frame._video_id_sesion, "abc")


class TestEstadoObsEnF2(unittest.TestCase):
    def _frame(self, toggles, vigilante=None):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"estado_toggles": toggles, "programados_activo": False}
        frame._obs_vigilante = vigilante
        frame.__dict__.update(_conectado=False, _es_tiktok=False,
            _tipo_video=gui.deteccion.DESCONOCIDO, _titulo_stream="", _metadatos={},
            _sc_totales={}, _mensajes_programados=[])
        return frame
    def test_f2_dice_los_tres_datos_frescos_de_la_cache(self):
        vigilante = mock.Mock(estado=mock.Mock(return_value=gui.obs_vigilante.EstadoObs({"outputActive": True, "outputDuration": 60,
            "outputSkippedFrames": 2, "outputTotalFrames": 10},
            {"outputActive": True, "outputPaused": False, "outputTimecode": "00:01:00"}, "Principal")))
        frame = self._frame(set(gui._OBS_COMPONENTES), vigilante)
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._anunciar_estado()
        texto = anunciar.call_args.args[0]
        self.assertTrue(all(x in texto for x in ("Transmitiendo desde hace 1 min, 2 de 10 fotogramas perdidos",
                                                   "Grabando, 00:01:00", "Al aire: Principal")))
    def test_f2_omite_dato_pasado_y_sin_vigilante(self):
        for toggles, vigilante in (({"estado", *gui._OBS_COMPONENTES}, mock.Mock(estado=lambda: None)),
                                    ({"estado"}, None)):
            with mock.patch.object(gui, "anunciar") as anunciar:
                self._frame(toggles, vigilante)._anunciar_estado()
            self.assertEqual(anunciar.call_args.args[0], "Desconectado.")
    def test_marca_y_desmarca_los_componentes_de_obs(self):
        frame = self._frame({"obs_transmision"})
        with mock.patch.object(gui.obs_vigilante, "VigilanteObs") as clase:
            frame._actualizar_vigilante_obs()
            clase.return_value.iniciar.assert_called_once_with()
            frame._config["estado_toggles"] = set()
            frame._actualizar_vigilante_obs()
        clase.return_value.detener.assert_called_once_with()

class TestTransmisionSupervisadaEnF2(unittest.TestCase):
    def _frame(self, supervisor):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"estado_toggles": set(), "programados_activo": False}
        frame._obs_vigilante = None
        frame._supervisor = supervisor
        frame.__dict__.update(_conectado=False, _es_tiktok=False,
            _tipo_video=gui.deteccion.DESCONOCIDO, _titulo_stream="", _metadatos={},
            _sc_totales={}, _mensajes_programados=[])
        return frame

    def test_supervisor_activo_llega_al_snapshot(self):
        supervisor = mock.Mock()
        supervisor.activo = True
        supervisor.frase_estado.return_value = "Esperando a que TikTok muestre el directo"
        snapshot = self._frame(supervisor)._snapshot_sesion()
        self.assertEqual(snapshot.transmision_supervisada,
                         "Esperando a que TikTok muestre el directo")

    def test_supervisor_inactivo_deja_el_campo_vacio(self):
        supervisor = mock.Mock()
        supervisor.activo = False
        supervisor.frase_estado.return_value = "Esperando a que TikTok muestre el directo"
        snapshot = self._frame(supervisor)._snapshot_sesion()
        self.assertEqual(snapshot.transmision_supervisada, "")
        supervisor.frase_estado.assert_not_called()

class TestAnunciarAutor(unittest.TestCase):
    def _frame(self, autor):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._worker = mock.Mock()
        frame._worker.ultimo_autor.return_value = autor
        return frame

    def test_con_autor_anuncia_el_nombre(self):
        frame = self._frame("Ana")
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._anunciar_autor()
        anunciar.assert_called_once_with("Último mensaje leído de Ana")

    def test_sin_autor_avisa_que_todavia_no_se_leyo(self):
        frame = self._frame("")
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._anunciar_autor()
        anunciar.assert_called_once_with("Todavía no se leyó ningún mensaje.")

class TestActualizarYtdlp(unittest.TestCase):

    class _Evento:
        def __init__(self):
            self._marcado = False

        def is_set(self):
            return self._marcado

        def set(self):
            self._marcado = True

    class VentanaFalsa:
        """Doble de DialogoActualizacion: no abre nada en pantalla."""

        def __init__(self, padre, titulo):
            evento = TestActualizarYtdlp._Evento()
            self.padre = padre
            self.titulo = titulo
            self.mostrada = False
            self.elevada = False
            self._cerrado = False
            self._cancelado = evento
            self.estados = []
            self.anuncios = []
            self.progresos = []
            self.textos_sin_anunciar = []
            self.txt_estado = mock.Mock()
            self.txt_estado.SetValue.side_effect = self.textos_sin_anunciar.append
            self.btn_cerrar = mock.Mock()

        @property
        def cerrado(self):
            return self._cerrado

        @property
        def cancelado(self):
            return self._cancelado

        def Show(self):
            self.mostrada = True

        def Raise(self):
            self.elevada = True

        def estado(self, texto):
            self.estados.append(texto)
            self.anuncios.append(texto)

        def progreso(self, porcentaje):
            self.progresos.append(porcentaje)

        def en_hilo_principal(self, funcion, *args):
            if self._cerrado:
                return
            funcion(*args)

        def cerrar(self):
            self._cerrado = True
            self._cancelado.set()

    def _ejecutar(self, doble, frame=None):
        if frame is None:
            frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        ventanas = []
        hilo = mock.Mock()
        hilo.start.side_effect = lambda: hilo.target()

        def crear(target, nombre):
            hilo.target = target
            hilo.nombre = nombre
            return hilo

        def fabrica(padre, titulo):
            ventana = self.VentanaFalsa(padre, titulo)
            ventanas.append(ventana)
            return ventana

        with mock.patch("ytchat.ui.gui_actualizacion.DialogoActualizacion",
                        side_effect=fabrica), \
                mock.patch.object(gui.wx, "ProgressDialog") as dialogo, \
                mock.patch.object(gui.wx, "MessageBox") as mensaje, \
                mock.patch.object(gui.diagnostico, "crear_hilo", side_effect=crear), \
                mock.patch.object(ytdlp_bin, "actualizar_ytdlp", side_effect=doble):
            gui.YTChatFrame._on_actualizar_ytdlp(frame, None)
        return frame, ventanas, hilo, dialogo, mensaje

    def test_activar_anuncia_busqueda_antes_de_empezar(self):
        def doble(avisar, progreso, cancelar):
            return "ya_al_dia", "2026.08.20", "2026.08.20"

        frame, ventanas, hilo, _, _ = self._ejecutar(doble)
        ventana = ventanas[0]
        self.assertEqual("Actualizar yt-dlp", ventana.titulo)
        self.assertTrue(ventana.mostrada)
        self.assertIn("Buscando", ventana.anuncios[0])
        hilo.start.assert_called_once_with()
        self.assertEqual("ActualizarYtdlp", hilo.nombre)

    def test_con_version_nueva_anuncia_descarga(self):
        def doble(avisar, progreso, cancelar):
            avisar("2026.08.21")
            return "actualizado", "2026.08.20", "2026.08.21"

        _, ventanas, _, _, _ = self._ejecutar(doble)
        self.assertTrue(any(
            "Hay una versión nueva de yt-dlp, la 2026.08.21" in texto
            for texto in ventanas[0].anuncios))

    def test_cada_desenlace_anuncia_su_texto_y_deja_la_barra(self):
        casos = (
            ("actualizado", "2026.08.20", "2026.08.21"),
            ("ya_al_dia", "2026.08.20", "2026.08.20"),
            ("sin_conexion", "2026.08.20", ""),
            ("firma_incorrecta", "2026.08.20", "2026.08.21"),
            ("otro_fallo", "2026.08.20", "2026.08.21"),
        )
        for resultado in casos:
            with self.subTest(estado=resultado[0]):
                _, ventanas, _, _, _ = self._ejecutar(
                    lambda a, p, c, r=resultado: r)
                ventana = ventanas[0]
                self.assertIn("Buscando", ventana.anuncios[0])
                self.assertEqual(
                    ytdlp_bin.mensaje_de_actualizacion(*resultado),
                    ventana.anuncios[-1])
                if ytdlp_bin.resultado_actualizacion_es_fallo(resultado[0]):
                    self.assertEqual(0, ventana.progresos[-1])
                else:
                    self.assertEqual(100, ventana.progresos[-1])

    def test_pasa_las_versiones_al_mensaje_final(self):
        def doble(avisar, progreso, cancelar):
            return "firma_incorrecta", "", "2026.08.21"

        with mock.patch.object(ytdlp_bin, "mensaje_de_actualizacion",
                               return_value="hecho") as mensaje:
            _, ventanas, _, _, _ = self._ejecutar(doble)
        mensaje.assert_called_once_with("firma_incorrecta", "", "2026.08.21")
        self.assertEqual("hecho", ventanas[0].anuncios[-1])

    def test_ventana_cerrada_descarta_el_resultado(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)

        def doble(avisar, progreso, cancelar):
            frame._ventana_actualizar_ytdlp.cerrar()
            return "actualizado", "2026.08.20", "2026.08.21"

        _, ventanas, _, _, _ = self._ejecutar(doble, frame)
        self.assertEqual(1, len(ventanas[0].anuncios))

    def test_progreso_con_decenas_no_anuncia_y_no_usa_dialogos_viejos(self):
        def doble(avisar, progreso, cancelar):
            for porcentaje in (10, 20, 40, 100):
                progreso(porcentaje, 0, 100)
            return "actualizado", "2026.08.20", "2026.08.21"

        _, ventanas, _, dialogo, mensaje = self._ejecutar(doble)
        ventana = ventanas[0]
        self.assertEqual([10, 20, 40, 100, 100], ventana.progresos)
        self.assertIn("Descargando yt-dlp: 40 por ciento",
                      ventana.textos_sin_anunciar)
        self.assertFalse(any("por ciento" in texto
                             for texto in ventana.anuncios))
        dialogo.assert_not_called()
        mensaje.assert_not_called()

    def test_cancelacion_cableada_a_la_ventana(self):
        capturada = {}

        def doble(avisar, progreso, cancelar):
            capturada["cancelar"] = cancelar
            return "ya_al_dia", "2026.08.20", "2026.08.20"

        _, ventanas, _, _, _ = self._ejecutar(doble)
        ventana = ventanas[0]
        self.assertFalse(capturada["cancelar"]())
        ventana.cerrar()
        self.assertTrue(capturada["cancelar"]())

    def test_excepcion_termina_en_otro_fallo(self):
        def doble(avisar, progreso, cancelar):
            raise RuntimeError("boom")

        with mock.patch.object(gui, "logger"):
            _, ventanas, _, _, _ = self._ejecutar(doble)
        self.assertEqual(
            ytdlp_bin.mensaje_de_actualizacion("otro_fallo", motivo="boom"),
            ventanas[0].anuncios[-1])
        self.assertEqual(0, ventanas[0].progresos[-1])

    def test_segunda_pulsacion_reutiliza_la_ventana(self):
        def doble(avisar, progreso, cancelar):
            return "ya_al_dia", "2026.08.20", "2026.08.20"

        frame, ventanas, _, _, _ = self._ejecutar(doble)
        primera = ventanas[0]
        anuncios = len(primera.anuncios)
        _, ventanas2, hilo2, _, _ = self._ejecutar(doble, frame)
        self.assertEqual([], ventanas2)
        self.assertTrue(primera.elevada)
        primera.btn_cerrar.SetFocus.assert_called()
        hilo2.start.assert_not_called()
        self.assertEqual(anuncios, len(primera.anuncios))

    def test_ventana_cerrada_permite_abrir_otra(self):
        def doble(avisar, progreso, cancelar):
            return "ya_al_dia", "2026.08.20", "2026.08.20"

        frame, ventanas, _, _, _ = self._ejecutar(doble)
        ventanas[0].cerrar()
        _, ventanas2, hilo2, _, _ = self._ejecutar(doble, frame)
        self.assertEqual(1, len(ventanas2))
        hilo2.start.assert_called_once_with()


class TestCierreVentana(unittest.TestCase):

    def test_el_overlay_activo_se_enciende_al_construir_la_ventana(self):
        configuracion = {"overlay_activo": True, "overlay_puerto": 8730}

        def construir_menu(frame):
            frame.mi_overlay = mock.Mock()

        with mock.patch.object(gui.wx.Frame, "__init__", return_value=None), \
                mock.patch.object(gui.YTChatFrame, "_build_menubar", construir_menu), \
                mock.patch.object(gui.YTChatFrame, "_build_ui"), \
                mock.patch.object(gui.YTChatFrame, "_bind_events"), \
                mock.patch.object(gui.YTChatFrame, "_init_timer"), \
                mock.patch.object(gui.YTChatFrame, "SetBackgroundColour"), \
                mock.patch.object(gui.YTChatFrame, "Centre"), \
                mock.patch.object(gui, "anunciar_conflictos_atajos"), \
                mock.patch.object(gui.diagnostico, "crear_hilo") as crear, \
                mock.patch.object(gui.overlay_servidor, "encender") as encender, \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch.object(gui, "anunciar"):
            gui.YTChatFrame(None, configuracion, None, None, None, None)

        encender.assert_called_once_with(8730)

    def test_el_overlay_no_miente_si_el_puerto_esta_ocupado_al_arrancar(self):
        configuracion = {"overlay_activo": True, "overlay_puerto": 8730}

        with mock.patch.object(gui.wx.Frame, "__init__", return_value=None), \
                mock.patch.object(gui.YTChatFrame, "_build_menubar"), \
                mock.patch.object(gui.YTChatFrame, "_build_ui"), \
                mock.patch.object(gui.YTChatFrame, "_bind_events"), \
                mock.patch.object(gui.YTChatFrame, "_init_timer"), \
                mock.patch.object(gui.YTChatFrame, "SetBackgroundColour"), \
                mock.patch.object(gui.YTChatFrame, "Centre"), \
                mock.patch.object(gui, "anunciar_conflictos_atajos"), \
                mock.patch.object(gui.diagnostico, "crear_hilo"), \
                mock.patch.object(gui.overlay_servidor, "encender", side_effect=gui.overlay_servidor.OverlayPuertoOcupadoError), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame = gui.YTChatFrame(None, configuracion, None, None, None, None)

        self.assertFalse(frame._config["overlay_activo"])
        anunciar.assert_called_once_with(
            "No se pudo activar el panel, el puerto 8730 está ocupado")

    def test_el_precalentamiento_se_arranca_solo_con_la_ventana_viva(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._rep_panel = mock.Mock()
        frame._arrancar_precalentamiento()
        frame._rep_panel._precalentar.assert_called_once_with()

        frame._alive = False
        frame._rep_panel._precalentar.reset_mock()
        frame._arrancar_precalentamiento()
        frame._rep_panel._precalentar.assert_not_called()

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._apagando = False
        frame._alive = True
        frame._timer = mock.Mock()
        frame._diagnostico_timer = mock.Mock()
        frame._pendientes_timer = None
        frame.on_desconectar_cb = None
        frame._parada = mock.Mock()
        frame._rep_panel = mock.Mock()
        frame._worker = mock.Mock()
        frame._diagnostico_parada = mock.Mock()
        frame.Hide = mock.Mock()
        frame.Destroy = mock.Mock()
        return frame

    def test_con_captura_viva_programa_espera_y_anuncia_cerrando(self):
        frame = self._frame()
        hilo = mock.Mock()
        hilo.name = "Chat"
        hilo.is_alive.return_value = True
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=("Chat",)), \
                mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.wx, "CallLater") as call_later, \
                mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
            frame._on_close(None)

        anunciar.assert_called_once_with("Cerrando")
        call_later.assert_called_once_with(200, frame._comprobar_cierre)
        frame.Destroy.assert_not_called()
        registro.assert_not_called()
        logueo.assert_not_called()

    def test_sin_captura_no_anuncia_y_destruye(self):
        frame = self._frame()
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.wx, "CallLater") as call_later, \
                mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
            frame._on_close(None)

        anunciar.assert_not_called()
        call_later.assert_not_called()
        frame.Destroy.assert_called_once_with()
        logueo.assert_called_once_with(logging.INFO, "%s", "CIERRE captura limpia")
        registro.assert_called_once_with()

    def test_al_cerrar_detiene_el_vigilante_de_interfaz(self):
        frame = self._frame()
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.diagnostico.logger, "info"):
            frame._on_close(None)

        frame._diagnostico_parada.set.assert_called_once_with()

    def test_al_cerrar_para_los_dos_temporizadores(self):
        frame = self._frame()
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.diagnostico.logger, "info"):
            frame._on_close(None)

        frame._timer.Stop.assert_called_once_with()
        frame._diagnostico_timer.Stop.assert_called_once_with()

    def _frame_conectado(self):
        frame = self._frame()
        frame._config = {"confirmar_salida": True}
        frame._conectado = True
        frame._supervisor = None
        frame._obs_transmitiendo = False
        return frame

    @staticmethod
    def _evento_vetable():
        evento = mock.Mock()
        evento.CanVeto.return_value = True
        return evento

    def test_con_chat_conectado_y_no_veta_el_cierre(self):
        frame = self._frame_conectado()
        evento = self._evento_vetable()
        dialogo = mock.Mock()
        dialogo.ShowModal.return_value = gui.wx.ID_NO
        with mock.patch.object(gui.wx, "MessageDialog",
                               return_value=dialogo) as crear:
            frame._on_close(evento)

        crear.assert_called_once()
        args, _kwargs = crear.call_args
        self.assertEqual(args[1],
                         "¿Salir de la aplicación? Hay un chat conectado.")
        self.assertEqual(args[2], "Salir")
        dialogo.Destroy.assert_called_once_with()
        evento.Veto.assert_called_once_with()
        self.assertFalse(frame._apagando)
        frame.Destroy.assert_not_called()

    def test_con_chat_conectado_y_si_sigue_el_cierre(self):
        frame = self._frame_conectado()
        evento = self._evento_vetable()
        dialogo = mock.Mock()
        dialogo.ShowModal.return_value = gui.wx.ID_YES
        with mock.patch.object(gui.wx, "MessageDialog",
                               return_value=dialogo), \
                mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.diagnostico.logger, "info"):
            frame._on_close(evento)

        evento.Veto.assert_not_called()
        self.assertTrue(frame._apagando)
        frame.Destroy.assert_called_once_with()

    def test_con_marca_de_instalador_no_pregunta(self):
        frame = self._frame_conectado()
        frame._cerrar_sin_preguntar = True
        evento = self._evento_vetable()
        with mock.patch.object(gui.wx, "MessageDialog") as crear, \
                mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.diagnostico.logger, "info"):
            frame._on_close(evento)

        crear.assert_not_called()
        evento.Veto.assert_not_called()
        frame.Destroy.assert_called_once_with()

    def test_sin_actividad_no_pregunta(self):
        frame = self._frame()
        frame._config = {"confirmar_salida": True}
        frame._conectado = False
        frame._supervisor = None
        frame._obs_transmitiendo = False
        evento = self._evento_vetable()
        with mock.patch.object(gui.wx, "MessageDialog") as crear, \
                mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.diagnostico.logger, "info"):
            frame._on_close(evento)

        crear.assert_not_called()
        evento.Veto.assert_not_called()
        frame.Destroy.assert_called_once_with()

    def test_encender_el_overlay_con_el_puerto_ocupado_no_persiste_ni_miente(self):
        frame = self._frame()
        frame._config = {"overlay_puerto": 8730, "overlay_activo": False}
        with mock.patch.object(gui.overlay_servidor, "encender",
                               side_effect=gui.overlay_servidor.OverlayPuertoOcupadoError()), \
                mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui, "RUTA_CONFIG", None):
            resultado = frame._cambiar_overlay(True)
        self.assertFalse(resultado)
        self.assertFalse(frame._config["overlay_activo"])
        anunciar.assert_called_once_with(
            "No se pudo activar el panel, el puerto 8730 está ocupado")

    def test_el_puerto_ocupado_no_guarda_el_cambio_de_esta_sesion(self):
        frame = self._frame()
        frame._config = {"overlay_puerto": 8730, "overlay_activo": True}
        with mock.patch.object(gui.overlay_servidor, "encender",
                               side_effect=gui.overlay_servidor.OverlayPuertoOcupadoError()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui, "guardar_opcion") as guardar:
            frame._cambiar_overlay(True)

        self.assertFalse(frame._config["overlay_activo"])
        guardar.assert_not_called()

    def test_guardar_usuario_tiktok_quita_arroba_y_persiste(self):
        frame = self._frame()
        frame._config = {}
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = frame._guardar_usuario_tiktok("@szeiryugaming")
        self.assertEqual(resultado, "szeiryugaming")
        self.assertEqual(frame._config["tiktok_usuario"], "szeiryugaming")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "tiktok", "usuario", "szeiryugaming")

    def test_supervisar_iniciar_crea_el_supervisor_y_lo_arranca(self):
        frame = self._frame()
        creados = []

        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append((destino, usuario, al_anunciar,
                                al_conectar_chat))
                self.iniciado = False

            def iniciar(self):
                self.iniciado = True

        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        DobleSupervisor):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        self.assertEqual(len(creados), 1)
        destino, usuario, al_anunciar, al_conectar_chat = creados[0]
        self.assertEqual(destino, "TikTok")
        self.assertEqual(usuario, "u")
        self.assertTrue(callable(al_anunciar))
        self.assertTrue(callable(al_conectar_chat))
        self.assertTrue(frame._supervisor.iniciado)

    def test_supervisor_conectar_chat_sin_conexion_pone_url_y_conecta(self):
        frame = self._frame()
        frame._alive = True
        frame._conectado = False
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame._on_conectar = mock.Mock()
        creados = []

        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append((al_anunciar, al_conectar_chat))

            def iniciar(self):
                pass

        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        DobleSupervisor):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        _al_anunciar, al_conectar_chat = creados[0]
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()):
            al_conectar_chat("https://www.tiktok.com/@u/live")
        frame.txt_url.SetValue.assert_called_once_with(
            "https://www.tiktok.com/@u/live")
        frame._on_conectar.assert_called_once_with(None)

    def test_supervisor_conectar_chat_ya_conectado_no_cambia_y_avisa(self):
        frame = self._frame()
        frame._alive = True
        frame._conectado = True
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame._on_conectar = mock.Mock()
        creados = []

        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append((al_anunciar, al_conectar_chat))

            def iniciar(self):
                pass

        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        DobleSupervisor):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        _al_anunciar, al_conectar_chat = creados[0]
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_conectar_chat("https://www.tiktok.com/@u/live")
        frame._on_conectar.assert_not_called()
        frame.txt_url.SetValue.assert_not_called()
        anunciar.assert_called_once_with(
            "El chat ya estaba conectado, no lo cambié.")

    def test_supervisor_anunciar_reproduce_sonido_y_anuncia(self):
        frame = self._frame()
        frame._alive = True
        creados = []

        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append((al_anunciar, al_conectar_chat))

            def iniciar(self):
                pass

        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        DobleSupervisor):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        al_anunciar, _al_conectar_chat = creados[0]
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui._snd, "reproducir") as reproducir, \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_anunciar("x", "conectado")
        reproducir.assert_called_once_with("conectado")
        anunciar.assert_called_once_with("x")

    def test_supervisor_anunciar_con_ventana_muerta_no_hace_nada(self):
        frame = self._frame()
        frame._alive = True
        creados = []

        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append((al_anunciar, al_conectar_chat))

            def iniciar(self):
                pass

        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        DobleSupervisor):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        al_anunciar, _al_conectar_chat = creados[0]
        frame._alive = False
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui._snd, "reproducir") as reproducir, \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_anunciar("x", "conectado")
        reproducir.assert_not_called()
        anunciar.assert_not_called()

    def test_supervisar_iniciar_con_transmision_en_curso_no_crea_otro(self):
        frame = self._frame()
        previo = mock.Mock()
        previo.activo = True
        frame._supervisor = previo
        with mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision") as fabrica:
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        anunciar.assert_called_once_with("Ya hay una transmisión en curso.")
        fabrica.assert_not_called()
        self.assertIs(frame._supervisor, previo)

    def test_cerrar_con_supervisor_activo_abandona_sin_detener(self):
        frame = self._frame()
        supervisor = mock.Mock()
        supervisor.activo = True
        frame._supervisor = supervisor
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.overlay_servidor, "apagar"):
            frame._on_close(None)
        supervisor.abandonar.assert_called_once_with()
        supervisor.detener.assert_not_called()
        self.assertIsNone(frame._supervisor)

    def test_cerrar_apaga_el_overlay(self):
        frame = self._frame()
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.overlay_servidor, "apagar") as apagar:
            frame._on_close(None)
        apagar.assert_called_once_with()

    def test_el_timer_actualiza_la_marca_del_vigilante(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._diagnostico_marca = 10.0
        frame._diagnostico_censo = 10.0
        with mock.patch.object(gui.time, "monotonic", return_value=12.5), \
                mock.patch.object(gui.diagnostico, "debe_censar_hilos", return_value=None):
            frame._on_diagnostico_timer(None)

        self.assertEqual(frame._diagnostico_marca, 12.5)

    def test_el_vigilante_se_arranca_con_nombre_propio(self):
        hilos = []
        hilo = mock.Mock()

        def crear(target, nombre):
            hilos.append((target, nombre))
            return hilo

        configuracion = mock.Mock()
        configuracion.get.return_value = {}
        with mock.patch.object(gui.wx.Frame, "__init__", return_value=None), \
                mock.patch.object(gui.YTChatFrame, "_build_menubar"), \
                mock.patch.object(gui.YTChatFrame, "_build_ui"), \
                mock.patch.object(gui.YTChatFrame, "_bind_events"), \
                mock.patch.object(gui.YTChatFrame, "_init_timer"), \
                mock.patch.object(gui.YTChatFrame, "SetBackgroundColour"), \
                mock.patch.object(gui.YTChatFrame, "Centre"), \
                mock.patch.object(gui, "anunciar_conflictos_atajos"), \
                mock.patch.object(gui.diagnostico, "crear_hilo", side_effect=crear):
            gui.YTChatFrame(None, configuracion, None, None, None, None)

        self.assertEqual(len(hilos), 1)
        self.assertEqual(hilos[0][1], "VigilanteInterfaz")
        hilo.start.assert_called_once_with()

    def test_el_nombre_del_vigilante_no_es_de_captura(self):
        self.assertNotIn("VigilanteInterfaz", apagado.NOMBRES_HILOS_CAPTURA)

    def test_el_tope_del_cierre_sale_de_apagado(self):
        self.assertEqual(apagado.TOPE_ESPERA_CIERRE, 8.0)
        frame = self._frame()
        hilo = mock.Mock()
        hilo.name = "TikTok"
        hilo.is_alive.return_value = True
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=("TikTok",)), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.wx, "CallLater"):
            frame._on_close(None)

        self.assertEqual(frame._cierre_tope, apagado.TOPE_ESPERA_CIERRE)

    def test_comprobar_cierre_con_hilos_vivos_reprograma_y_no_destruye(self):
        frame = self._frame()
        frame._cierre_inicio = 100.0
        tope = apagado.TOPE_ESPERA_CIERRE
        frame._cierre_tope = tope
        hilo = mock.Mock(name="Chat")
        hilo.name = "Chat"
        hilo.is_alive.return_value = True
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=("Chat",)), \
                mock.patch.object(gui.time, "monotonic", return_value=100.0 + tope - 1.0), \
                mock.patch.object(gui.wx, "CallLater") as call_later, \
                mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
            frame._comprobar_cierre()

        call_later.assert_called_once_with(200, frame._comprobar_cierre)
        frame.Destroy.assert_not_called()
        registro.assert_not_called()
        logueo.assert_not_called()

    def test_comprobar_cierre_sin_hilos_destruye_y_registra_cierre_limpio(self):
        frame = self._frame()
        frame._cierre_inicio = 100.0
        frame._cierre_tope = apagado.TOPE_ESPERA_CIERRE
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=()), \
                mock.patch.object(gui.time, "monotonic", return_value=101.0), \
                mock.patch.object(gui.wx, "CallLater") as call_later, \
                mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
            frame._comprobar_cierre()

        call_later.assert_not_called()
        frame.Destroy.assert_called_once_with()
        logueo.assert_called_once_with(logging.INFO, "%s", "CIERRE captura limpia")
        registro.assert_called_once_with()

    def test_comprobar_cierre_con_tope_vencido_destruye_y_registra_hilos(self):
        frame = self._frame()
        frame._cierre_inicio = 100.0
        tope = apagado.TOPE_ESPERA_CIERRE
        frame._cierre_tope = tope
        hilo = mock.Mock(name="TikTok")
        hilo.name = "TikTok"
        hilo.is_alive.return_value = True
        with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", return_value=("TikTok",)), \
                mock.patch.object(gui.time, "monotonic", return_value=100.0 + tope + 1.0), \
                mock.patch.object(gui.wx, "CallLater") as call_later, \
                mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
            frame._comprobar_cierre()

        call_later.assert_not_called()
        frame.Destroy.assert_called_once_with()
        logueo.assert_called_once_with(
            logging.WARNING, "%s", f"CIERRE por tope={tope:.1f}s hilos vivos=TikTok")
        registro.assert_not_called()

    def test_nacimiento_tardio_detecta_reproductor_stop_nacido_en_detener_todo(self):
        import threading
        frame = self._frame()
        senal = threading.Event()
        hilo_real = None

        def detener_con_nacimiento():
            nonlocal hilo_real
            hilo_real = threading.Thread(target=lambda: senal.wait(timeout=5), name="ReproductorStop")
            hilo_real.start()

        frame._rep_panel.detener_todo.side_effect = detener_con_nacimiento
        llamadas = []

        def censo_aislado():
            if not llamadas:
                llamadas.append(1)
                return ()
            return tuple(sorted(h.name for h in threading.enumerate() if h.is_alive() and h.name == "ReproductorStop"))

        try:
            with mock.patch.object(gui.diagnostico, "hilos_vivos_de_la_aplicacion", side_effect=censo_aislado), \
                    mock.patch.object(gui, "anunciar") as anunciar, \
                    mock.patch.object(gui.wx, "CallLater") as call_later, \
                    mock.patch.object(gui.diagnostico.logger, "log") as logueo, \
                    mock.patch.object(gui.diagnostico, "registrar_cierre_fallos") as registro:
                frame._on_close(None)
                call_later.assert_called_once_with(200, frame._comprobar_cierre)
                frame.Destroy.assert_not_called()
                registro.assert_not_called()
                logueo.assert_not_called()
                anunciar.assert_not_called()
        finally:
            senal.set()
            if hilo_real is not None:
                hilo_real.join(timeout=2)
                self.assertFalse(hilo_real.is_alive())


class TestUltimaDireccion(unittest.TestCase):
    """`set_conectado(True)` guarda la dirección solo en la transición de
    desconectado a conectado y con la opción activada."""

    def _frame(self, configuracion):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._conectado = False
        frame._config = dict(configuracion)
        frame.txt_url = mock.Mock()
        frame.txt_url.GetValue.return_value = "https://ejemplo.com/directo"
        frame._mostrar_zona = mock.Mock()
        frame._anunciar_conectado = mock.Mock()
        frame._set_conectado_ui = mock.Mock()
        frame._actualizar_estado_online = mock.Mock()
        return frame

    def test_con_opcion_activada_guarda_la_direccion(self):
        frame = self._frame({"recordar_direccion": True})
        with mock.patch.object(gui.wx, "CallAfter"), \
                mock.patch.object(gui, "guardar_opcion") as guardar:
            frame.set_conectado(True)

        self.assertEqual(frame._config["ultima_direccion"],
                         "https://ejemplo.com/directo")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "sesion", "ultima_direccion",
            "https://ejemplo.com/directo")

    def test_con_opcion_desactivada_no_guarda(self):
        frame = self._frame({"recordar_direccion": False})
        with mock.patch.object(gui.wx, "CallAfter"), \
                mock.patch.object(gui, "guardar_opcion") as guardar:
            frame.set_conectado(True)

        self.assertNotIn("ultima_direccion", frame._config)
        guardar.assert_not_called()

    def test_solo_guarda_en_la_transicion_a_conectado(self):
        frame = self._frame({"recordar_direccion": True})
        frame._conectado = True
        with mock.patch.object(gui.wx, "CallAfter"), \
                mock.patch.object(gui, "guardar_opcion") as guardar:
            frame.set_conectado(True)

        self.assertNotIn("ultima_direccion", frame._config)
        guardar.assert_not_called()


class TestCopiarEnlaceDirecto(unittest.TestCase):

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._enlace_directo = ""
        frame._clipboard_set = mock.Mock()
        frame._ruta_historial = mock.Mock(return_value="historial.json")
        return frame

    def _registrar(self, frame, plataforma, url, directo):
        with mock.patch.object(gui.historial, "cargar", return_value=[]), \
                mock.patch.object(gui.historial, "upsert", return_value=[]), \
                mock.patch.object(gui.historial, "guardar"):
            frame.registrar_historial(plataforma, "clave", url, "título",
                                      "canal", directo)

    def test_registrar_directo_youtube_y_copiar_copia_suena_y_anuncia(self):
        frame = self._frame()
        url = "https://www.youtube.com/watch?v=abcdefghijk"
        self._registrar(frame, "youtube", url, True)
        self.assertEqual(frame._enlace_directo, url)
        with mock.patch.object(gui._snd, "reproducir") as sonar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._copiar_enlace_directo()
        frame._clipboard_set.assert_called_once_with(url)
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Enlace del directo copiado.")

    def test_registrar_video_no_directo_y_copiar_avisa_sin_copiar(self):
        frame = self._frame()
        self._registrar(frame, "youtube",
                        "https://www.youtube.com/watch?v=abcdefghijk", False)
        self.assertEqual(frame._enlace_directo, "")
        with mock.patch.object(gui._snd, "reproducir") as sonar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._copiar_enlace_directo()
        frame._clipboard_set.assert_not_called()
        sonar.assert_not_called()
        anunciar.assert_called_once_with("No hay ningún directo conectado.")

    def test_registrar_directo_tiktok_y_copiar_copia(self):
        frame = self._frame()
        url = "https://www.tiktok.com/@usuario/live"
        self._registrar(frame, "tiktok", url, True)
        self.assertEqual(frame._enlace_directo, url)
        with mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._copiar_enlace_directo()
        frame._clipboard_set.assert_called_once_with(url)
        anunciar.assert_called_once_with("Enlace del directo copiado.")

    def test_tras_desconectar_no_hay_enlace(self):
        frame = self._frame()
        frame._enlace_directo = "https://www.youtube.com/watch?v=abcdefghijk"
        frame._live_chat_id = ""
        frame._video_id_sesion = ""
        frame._causa_sin_chat = ""
        frame._tipo_video = gui.deteccion.DESCONOCIDO
        frame._es_tiktok = False
        frame._descartes_avisado = False
        frame._descartar_pendientes = mock.Mock()
        frame._chat = mock.Mock()
        frame.lb_chat = mock.Mock()
        frame._sc_totales = {}
        frame._metadatos = {}
        frame.txt_info = mock.Mock()
        frame._rep_panel = mock.Mock()
        frame._com_panel = mock.Mock()
        frame._worker = mock.Mock()
        frame._stats = mock.Mock()
        frame._actualizar_sb = mock.Mock()
        frame._reiniciar_datos_sesion()
        self.assertEqual(frame._enlace_directo, "")
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._copiar_enlace_directo()
        frame._clipboard_set.assert_not_called()
        anunciar.assert_called_once_with("No hay ningún directo conectado.")

    def test_item_de_menu_existe_con_su_atajo(self):
        frame = mock.Mock()
        frame._accel.side_effect = (
            lambda accion: "\tCtrl+Shift+E" if accion == "copiar_enlace" else "")
        elementos = []

        def crear_menu():
            menu = mock.MagicMock()

            def agregar(*args):
                elemento = mock.Mock()
                elementos.append((args[-1], elemento))
                return elemento

            menu.Append.side_effect = agregar
            menu.AppendRadioItem.side_effect = lambda *args: mock.Mock()
            menu.AppendCheckItem.side_effect = lambda *args: mock.Mock()
            return menu

        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
                mock.patch.object(gui.wx, "MenuBar"):
            gui.YTChatFrame._build_menubar(frame)
        etiquetas = [etiqueta for etiqueta, _ in elementos]
        candidata = next(e for e in etiquetas if "enlace del directo" in e)
        self.assertIn("Copiar &enlace del directo", candidata)
        self.assertIn("\tCtrl+Shift+E", candidata)

    def test_item_de_menu_anunciar_autor_enlazado(self):
        frame = mock.Mock()
        frame._accel.side_effect = (
            lambda accion: "\tF3" if accion == "anunciar_autor" else "")
        elementos = []

        def crear_menu():
            menu = mock.MagicMock()

            def agregar(*args):
                elemento = mock.Mock()
                elementos.append((args[-1], elemento))
                return elemento

            menu.Append.side_effect = agregar
            menu.AppendRadioItem.side_effect = lambda *args: mock.Mock()
            menu.AppendCheckItem.side_effect = lambda *args: mock.Mock()
            return menu

        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
                mock.patch.object(gui.wx, "MenuBar"):
            gui.YTChatFrame._build_menubar(frame)
        esperado = frame._accel("anunciar_autor")
        etiqueta, elemento = next(
            (etiqueta, elemento) for etiqueta, elemento in elementos
            if "a&utor del último mensaje" in etiqueta)
        self.assertIn(esperado, etiqueta)
        frame._bind_menu.assert_any_call(elemento, frame._anunciar_autor)

    def test_item_de_menu_describir_escena_enlazado(self):
        frame = mock.Mock()
        frame._accel.side_effect = (
            lambda accion: "\tCtrl+F2" if accion == "describir_escena" else "")
        elementos = []

        def crear_menu():
            menu = mock.MagicMock()

            def agregar(*args):
                elemento = mock.Mock()
                elementos.append((args[-1], elemento))
                return elemento

            menu.Append.side_effect = agregar
            menu.AppendRadioItem.side_effect = lambda *args: mock.Mock()
            menu.AppendCheckItem.side_effect = lambda *args: mock.Mock()
            return menu

        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
                mock.patch.object(gui.wx, "MenuBar"):
            gui.YTChatFrame._build_menubar(frame)
        esperado = frame._accel("describir_escena")
        etiqueta, elemento = next(
            (etiqueta, elemento) for etiqueta, elemento in elementos
            if "Describir la escena" in etiqueta)
        self.assertIn("Describir la escena de &OBS", etiqueta)
        self.assertIn(esperado, etiqueta)
        frame._bind_menu.assert_any_call(elemento, frame._describir_escena)

    def test_letras_de_acceso_unicas_en_cada_menu(self):
        # Dos entradas del mismo menú con la misma letra no ejecutan nada:
        # pulsar la letra salta entre las dos. Se recorre la barra y se
        # nombra el menú y las entradas repetidas.
        menus = []

        def crear_menu():
            menu = mock.MagicMock()
            menu._etiquetas = []

            def agregar(*args):
                if args and isinstance(args[-1], str):
                    menu._etiquetas.append(args[-1])
                return mock.Mock()

            def agregar_submenu(*args):
                if len(args) >= 2 and isinstance(args[1], str):
                    menu._etiquetas.append(args[1])
                if args and hasattr(args[0], "_etiquetas"):
                    args[0]._titulo_submenu = (
                        args[1] if len(args) >= 2 else "")
                return mock.Mock()

            menu.Append.side_effect = agregar
            menu.AppendRadioItem.side_effect = agregar
            menu.AppendCheckItem.side_effect = agregar
            menu.AppendSubMenu.side_effect = agregar_submenu
            menus.append(menu)
            return menu

        anexados = []

        def crear_barra():
            barra = mock.MagicMock()

            def anexar(menu, titulo):
                anexados.append((titulo, menu))
                return True

            barra.Append.side_effect = anexar
            return barra

        frame = mock.Mock()
        frame._accel.return_value = ""
        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
                mock.patch.object(gui.wx, "MenuBar", side_effect=crear_barra):
            gui.YTChatFrame._build_menubar(frame)

        def letra_de_acceso(etiqueta):
            texto = etiqueta.split("\t")[0]
            posicion = texto.find("&")
            while posicion != -1:
                if posicion + 1 < len(texto):
                    if texto[posicion + 1] == "&":
                        posicion = texto.find("&", posicion + 2)
                        continue
                    return texto[posicion + 1].upper()
                break
            return ""

        for titulo, menu in anexados:
            vistas = {}
            for etiqueta in menu._etiquetas:
                letra = letra_de_acceso(etiqueta)
                if not letra:
                    continue
                vistas.setdefault(letra, []).append(etiqueta)
            for letra, repetidas in vistas.items():
                self.assertEqual(
                    len(repetidas), 1,
                    f"Menú {titulo}: la letra {letra} se repite en "
                    f"{repetidas}")
        for menu in menus:
            titulo = getattr(menu, "_titulo_submenu", "")
            if not titulo:
                continue
            vistas = {}
            for etiqueta in menu._etiquetas:
                letra = letra_de_acceso(etiqueta)
                if not letra:
                    continue
                vistas.setdefault(letra, []).append(etiqueta)
            for letra, repetidas in vistas.items():
                self.assertEqual(
                    len(repetidas), 1,
                    f"Menú {titulo}: la letra {letra} se repite en "
                    f"{repetidas}")

    def test_describir_escena_sin_obs_anuncia_y_no_crea_el_gestor(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._descripcion_escena_en_curso = False
        with mock.patch.object(gui.obs_activacion, "obs_esta_en_ejecucion",
                               return_value=False) as en_ejecucion, \
                mock.patch.object(gui, "GestorPanelObs") as gestor, \
                mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.diagnostico, "crear_hilo") as crear_hilo:
            gui.YTChatFrame._describir_escena(frame)
        en_ejecucion.assert_called_once_with()
        anunciar.assert_called_once_with("OBS no está abierto.")
        gestor.assert_not_called()
        crear_hilo.assert_not_called()

    def test_describir_escena_en_curso_no_lanza_otro_hilo(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._descripcion_escena_en_curso = True
        with mock.patch.object(gui.obs_activacion, "obs_esta_en_ejecucion") as en_ejecucion, \
                mock.patch.object(gui.diagnostico, "crear_hilo") as crear_hilo, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui.YTChatFrame._describir_escena(frame)
        en_ejecucion.assert_not_called()
        crear_hilo.assert_not_called()
        anunciar.assert_not_called()


class TestSupervisarDirectoYoutube(unittest.TestCase):
    # Cableado de _supervisar_transmision para destino YouTube, sin ventanas:
    # pedir_datos_directo y el supervisor son dobles.

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._supervisor = None
        frame._config = {
            "transmision_youtube_titulo": "",
            "transmision_youtube_descripcion": "",
            "transmision_youtube_privacidad": "unlisted",
            "transmision_youtube_latencia": "normal",
            "transmision_youtube_ninos": False,
            "transmision_youtube_dvr": True,
            "transmision_youtube_categoria": "",
            "transmision_youtube_etiquetas": "",
            "transmision_youtube_miniatura": "",
            "transmision_youtube_lista": "",
            "transmision_youtube_lista_titulo": "",
        }
        frame._actualizar_boton_directo = mock.Mock()
        return frame

    def _doble_supervisor(self, creados):
        class DobleSupervisor:
            def __init__(self, destino, usuario, al_anunciar=None,
                         al_conectar_chat=None, al_terminar=None,
                         preparar_emision=None, esperar_emision=None,
                         finalizar_emision=None, ruta_fin_pendiente=None,
                         avisar_sobrecarga=None):
                creados.append({
                    "destino": destino, "usuario": usuario,
                    "al_conectar_chat": al_conectar_chat,
                    "preparar_emision": preparar_emision,
                    "esperar_emision": esperar_emision,
                    "finalizar_emision": finalizar_emision,
                    "ruta_fin_pendiente": ruta_fin_pendiente})
                self.iniciado = False

            def iniciar(self):
                self.iniciado = True

        return DobleSupervisor

    def test_sin_sesion_anuncia_y_no_arranca_ni_pide_datos(self):
        frame = self._frame()
        with mock.patch.object(gui.credenciales, "cargar", return_value={}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                  return_value=False), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo") as pedir, \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision") as fabrica, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._supervisar_transmision("iniciar", "YouTube", "")
        anunciar.assert_called_once_with(
            "Para transmitir a YouTube hace falta iniciar sesión con "
            "Google, en Preferencias, pestaña API y sesión.")
        pedir.assert_not_called()
        fabrica.assert_not_called()
        self.assertIsNone(frame._supervisor)

    def test_cancelado_anuncia_y_no_arranca(self):
        frame = self._frame()
        with mock.patch.object(gui.credenciales, "cargar", return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                  return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=None), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision") as fabrica, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._supervisar_transmision("iniciar", "YouTube", "")
        anunciar.assert_called_once_with("No se transmitió.")
        fabrica.assert_not_called()
        self.assertIsNone(frame._supervisor)

    def test_con_datos_guarda_y_arranca_con_ganchos(self):
        frame = self._frame()
        creados = []
        pedido = {"titulo": "Hola", "descripcion": "algo",
                  "privacidad": "public"}
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "efectivas",
                                   return_value={"token": "t",
                                                 "api_key": "k-prueba"}) as efectivas, \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido) as pedir, \
                mock.patch.object(gui.youtube_api, "ClienteYouTube") as cliente, \
                mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._supervisar_transmision("iniciar", "YouTube", "")
        pedir.assert_called_once_with(frame, "", "", "unlisted", None,
                                      "normal", False, True, "", "", "",
                                      "", "", mock.ANY)
        self.assertEqual(frame._config["transmision_youtube_titulo"], "Hola")
        self.assertEqual(frame._config["transmision_youtube_descripcion"], "algo")
        self.assertEqual(frame._config["transmision_youtube_privacidad"], "public")
        self.assertEqual(frame._config["transmision_youtube_latencia"], "normal")
        self.assertFalse(frame._config["transmision_youtube_ninos"])
        self.assertTrue(frame._config["transmision_youtube_dvr"])
        self.assertEqual(guardar.call_count, 11)
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_titulo", "Hola")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_descripcion", "algo")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_privacidad", "public")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_latencia", "normal")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_ninos", "false")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_dvr", "true")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_lista", "")
        guardar.assert_any_call(
            gui.RUTA_CONFIG, "transmision", "youtube_lista_titulo", "")
        cliente.assert_called_once_with({"token": "t",
                                           "api_key": "k-prueba"})
        efectivas.assert_called_once_with({"token": "t"})
        self.assertEqual(len(creados), 1)
        self.assertTrue(callable(creados[0]["preparar_emision"]))
        self.assertTrue(callable(creados[0]["esperar_emision"]))
        self.assertTrue(callable(creados[0]["finalizar_emision"]))
        self.assertTrue(frame._supervisor.iniciado)
        anunciar.assert_not_called()

    def test_ganchos_reciben_extras_y_avisar(self):
        frame = self._frame()
        creados = []
        pedido = {"titulo": "Hola", "descripcion": "algo",
                  "privacidad": "public", "categoria": "27",
                  "etiquetas": ["uno", "dos"],
                  "miniatura": "C:/tmp/mini.png", "lista": "PL123"}
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "efectivas",
                                   return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido), \
                mock.patch.object(gui.youtube_api, "ClienteYouTube"), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch("ytchat.youtube.emision.ganchos_youtube",
                           return_value=(mock.Mock(), mock.Mock(),
                                         mock.Mock())) as ganchos, \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)), \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._supervisar_transmision("iniciar", "YouTube", "")
        ganchos.assert_called_once()
        extras = ganchos.call_args.kwargs["extras"]
        self.assertEqual(extras["categoria"], "27")
        self.assertEqual(extras["etiquetas"], ["uno", "dos"])
        self.assertEqual(extras["miniatura"], "C:/tmp/mini.png")
        self.assertEqual(extras["lista"], "PL123")
        self.assertEqual(ganchos.call_args.kwargs["avisar"], anunciar)
        self.assertEqual(len(creados), 1)

    def test_pedir_datos_recibe_un_cargador_de_listas(self):
        frame = self._frame()
        creados = []
        pedido = {"titulo": "Hola", "descripcion": "algo",
                  "privacidad": "public"}
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "efectivas",
                                   return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido) as pedir, \
                mock.patch.object(gui.youtube_api, "ClienteYouTube"), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)):
            frame._supervisar_transmision("iniciar", "YouTube", "")
        self.assertTrue(callable(pedir.call_args.args[-1]))

    def test_titulo_vacio_anuncia_y_no_arranca(self):
        frame = self._frame()
        pedido = {"titulo": "   ", "descripcion": "", "privacidad": "unlisted"}
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                  return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision") as fabrica, \
                mock.patch.object(gui, "anunciar") as anunciar:
            frame._supervisar_transmision("iniciar", "YouTube", "")
        anunciar.assert_called_once_with("Falta el título del directo.")
        fabrica.assert_not_called()
        self.assertIsNone(frame._supervisor)

    def test_revision_llega_a_la_ventana_del_directo(self):
        frame = self._frame()
        creados = []
        pedido = {"titulo": "Hola", "descripcion": "algo",
                  "privacidad": "public"}
        revision = mock.sentinel.revision
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido) as pedir, \
                mock.patch.object(gui.youtube_api, "ClienteYouTube"), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)):
            frame._supervisar_transmision(
                "iniciar", "YouTube", "", revision=revision)
        pedir.assert_called_once_with(frame, "", "", "unlisted", revision,
                                      "normal", False, True, "", "", "",
                                      "", "", mock.ANY)
        self.assertEqual(len(creados), 1)

    def test_tiktok_arranca_sin_ganchos_y_sin_pedir_datos(self):
        frame = self._frame()
        creados = []
        with mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo") as pedir, \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)):
            frame._supervisar_transmision("iniciar", "TikTok", "u")
        pedir.assert_not_called()
        self.assertEqual(len(creados), 1)
        self.assertEqual(creados[0]["destino"], "TikTok")
        self.assertIsNone(creados[0]["preparar_emision"])
        self.assertIsNone(creados[0]["esperar_emision"])
        self.assertIsNone(creados[0]["finalizar_emision"])
        self.assertTrue(frame._supervisor.iniciado)

    def _conectar_chat_youtube(self, frame, privacidad, **extra):
        creados = []
        pedido = {"titulo": "Hola", "descripcion": "algo",
                  "privacidad": privacidad}
        pedido.update(extra)
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={"token": "t"}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=True), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido), \
                mock.patch.object(gui.youtube_api, "ClienteYouTube"), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           self._doble_supervisor(creados)):
            frame._supervisar_transmision("iniciar", "YouTube", "")
        return creados[0]["al_conectar_chat"]

    def test_privado_no_conecta_el_chat_y_avisa(self):
        frame = self._frame()
        frame._alive = True
        frame._conectado = False
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame._on_conectar = mock.Mock()
        al_conectar_chat = self._conectar_chat_youtube(frame, "private")
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_conectar_chat("https://www.youtube.com/watch?v=abc123")
        frame._on_conectar.assert_not_called()
        frame.txt_url.SetValue.assert_not_called()
        anunciar.assert_called_once_with(
            "El directo es privado y YouTube no deja leer su chat. Para "
            "leerlo, transmite como público o no listado.")

    def test_no_listado_si_conecta_el_chat(self):
        frame = self._frame()
        frame._alive = True
        frame._conectado = False
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame._on_conectar = mock.Mock()
        al_conectar_chat = self._conectar_chat_youtube(frame, "unlisted")
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_conectar_chat("https://www.youtube.com/watch?v=abc123")
        frame._on_conectar.assert_called_once_with(None)
        anunciar.assert_not_called()

    def test_ninos_no_conecta_el_chat_y_avisa(self):
        frame = self._frame()
        frame._alive = True
        frame._conectado = False
        frame._conectando = False
        frame.txt_url = mock.Mock()
        frame._on_conectar = mock.Mock()
        al_conectar_chat = self._conectar_chat_youtube(frame, "unlisted",
                                                       ninos=True)
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=lambda funcion: funcion()), \
                mock.patch.object(gui, "anunciar") as anunciar:
            al_conectar_chat("https://www.youtube.com/watch?v=abc123")
        frame._on_conectar.assert_not_called()
        frame.txt_url.SetValue.assert_not_called()
        anunciar.assert_called_once_with(
            "El directo está marcado como hecho para niños y YouTube no "
            "tiene chat.")


class TestOrillaChat(unittest.TestCase):
    def _frame(self, seleccion, total):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame.lb_chat = mock.Mock()
        frame.lb_chat.GetSelection.return_value = seleccion
        frame.lb_chat.GetCount.return_value = total
        frame._copiar_mensaje = mock.Mock()
        frame._mostrar_menu_chat = mock.Mock()
        return frame

    def _tecla(self, codigo):
        evento = mock.Mock()
        evento.GetKeyCode.return_value = codigo
        evento.ControlDown.return_value = False
        return evento

    def test_arriba_en_primera_fila_suena_y_se_omite(self):
        from ytchat.core import sonidos_eventos
        frame = self._frame(0, 5)
        evento = self._tecla(sonidos_eventos.TECLA_FLECHA_ARRIBA)
        with mock.patch.object(gui._snd, "reproducir") as reproducir:
            frame._on_chat_key(evento)
        reproducir.assert_called_once_with("orilla")
        evento.Skip.assert_called_once_with()

    def test_abajo_en_ultima_fila_suena_y_se_omite(self):
        from ytchat.core import sonidos_eventos
        frame = self._frame(4, 5)
        evento = self._tecla(sonidos_eventos.TECLA_FLECHA_ABAJO)
        with mock.patch.object(gui._snd, "reproducir") as reproducir:
            frame._on_chat_key(evento)
        reproducir.assert_called_once_with("orilla")
        evento.Skip.assert_called_once_with()

    def test_arriba_en_segunda_fila_no_suena(self):
        from ytchat.core import sonidos_eventos
        frame = self._frame(1, 5)
        evento = self._tecla(sonidos_eventos.TECLA_FLECHA_ARRIBA)
        with mock.patch.object(gui._snd, "reproducir") as reproducir:
            frame._on_chat_key(evento)
        reproducir.assert_not_called()
        evento.Skip.assert_called_once_with()


class TestFinDirectoGui(unittest.TestCase):
    """«fin_directo» cierra igual que «desconectado»: solo cambia el sonido."""

    def _frame_conectado(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._alive = True
        frame._conectado = True
        frame._pendientes_timer = None
        frame._pendientes = []
        frame._chat = mock.Mock()
        frame.lb_chat = mock.Mock()
        frame._sc_totales = {}
        frame._mostrar_zona = mock.Mock()
        frame.set_titulo_stream = mock.Mock()
        frame._fijar_tipo = mock.Mock()
        frame._set_conectado_ui = mock.Mock()
        frame._actualizar_estado_online = mock.Mock()
        frame._actualizar_sb = mock.Mock()
        frame.txt_url = mock.Mock()
        frame.txt_info = mock.Mock()
        frame._rep_panel = mock.Mock()
        frame._com_panel = mock.Mock()
        frame._worker = mock.Mock()
        frame._stats = mock.Mock()
        return frame

    def _desconectar(self, frame, *args):
        with mock.patch.object(gui._snd, "reproducir") as reproducir, \
                mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=lambda fn, *a, **k: fn(*a, **k)):
            frame.set_conectado(*args)
        return reproducir, anunciar

    def test_fin_directo_suena_distinto_y_cierra_igual(self):
        normal = self._frame_conectado()
        rep_normal, _an_normal = self._desconectar(normal, False)
        fin = self._frame_conectado()
        rep_fin, _an_fin = self._desconectar(fin, False, "fin_directo")
        rep_normal.assert_called_once_with("desconectado")
        rep_fin.assert_called_once_with("fin_directo")
        self.assertEqual(normal._mostrar_zona.call_args,
                         fin._mostrar_zona.call_args)
        self.assertEqual(normal.set_titulo_stream.call_args,
                         fin.set_titulo_stream.call_args)
        self.assertEqual(normal._fijar_tipo.call_args,
                         fin._fijar_tipo.call_args)
        self.assertEqual(normal._set_conectado_ui.call_args,
                         fin._set_conectado_ui.call_args)

    def test_por_defecto_sigue_sonando_desconectado(self):
        frame = self._frame_conectado()
        reproducir, _anunciar = self._desconectar(frame, False)
        reproducir.assert_called_once_with("desconectado")


class TestCableadoAnuncioAjuste(unittest.TestCase):
    def test_ajustar_volume_repetido_acorta_y_otro_control_completa(self):
        from ytchat.core import anuncio_ajuste
        from ytchat.core.anuncio_ajuste import AnuncioAjuste
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        volumen = [40]
        velocidad = [0]
        frame._worker = mock.Mock()
        frame._worker.cambiar_volumen.side_effect = lambda delta: volumen.__setitem__(0, volumen[0] + delta)
        frame._worker.get_volume.side_effect = lambda: volumen[0]
        frame._worker.cambiar_rate.side_effect = lambda delta: velocidad.__setitem__(0, velocidad[0] + delta)
        frame._worker.get_rate.side_effect = lambda: velocidad[0]
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()), \
                mock.patch.object(gui, "guardar_opcion"), \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui.YTChatFrame._ajustar_volume(frame, +5)
            gui.YTChatFrame._ajustar_volume(frame, +5)
            gui.YTChatFrame._ajustar_rate(frame, +1)
        dichos = [llamada.args[0] for llamada in anunciar.call_args_list]
        self.assertEqual(dichos, ["Volumen de la voz: 45%", "50%", "Velocidad de la voz: 1"])


if __name__ == "__main__":
    unittest.main()
