"""Pruebas sin ventana de `ytchat/ui/gui_transmitir.py`.

Sin ventanas reales: el frame es un doble (`types.SimpleNamespace` con
los atributos que usa cada función) y `wx.CallAfter` se reemplaza por
un doble que llama en el acto, igual que en `test_boton_directo.py`.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from ytchat.ui import gui, gui_transmitir
from ytchat.ui.sesion_conectada import SesionConectada


def _llamada_inmediata(funcion, *args, **kwargs):
    return funcion(*args, **kwargs)


class HiloInmediato:
    """Doble de `diagnostico.crear_hilo` que ejecuta el objetivo al arrancar."""

    def __init__(self, target, nombre, **kwargs):
        self.target = target
        self.nombre = nombre
        self.daemon = kwargs.get("daemon", True)
        self.iniciado = False

    def start(self):
        self.iniciado = True
        self.target()


class TestCambiarOverlay(unittest.TestCase):

    def setUp(self):
        self._hilos = []

        def crear_hilo(target, nombre, **kwargs):
            hilo = HiloInmediato(target, nombre, **kwargs)
            self._hilos.append(hilo)
            return hilo

        patcher_hilo = mock.patch.object(
            gui.diagnostico, "crear_hilo", side_effect=crear_hilo)
        patcher_hilo.start()
        self.addCleanup(patcher_hilo.stop)
        patcher_recarga = mock.patch(
            "ytchat.obs.obs_panel_recarga.recargar_fuente_panel")
        self._recarga = patcher_recarga.start()
        self.addCleanup(patcher_recarga.stop)

    def _frame(self):
        return SimpleNamespace(_config={"overlay_puerto": 8730})

    def test_encender_activa_y_anuncia(self):
        frame = self._frame()
        with mock.patch.object(gui.overlay_servidor, "encender") as encender, \
                mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            resultado = gui_transmitir.cambiar_overlay(frame, True)
        self.assertTrue(resultado)
        encender.assert_called_once_with(8730)
        self.assertTrue(frame._config["overlay_activo"])
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "overlay", "activo", "true")
        anunciar.assert_called_once_with(
            "Panel de chat activo en el puerto 8730")
        self._recarga.assert_called_once_with()
        self.assertEqual(len(self._hilos), 1)
        self.assertEqual(self._hilos[0].nombre, "RecargarPanelObs")
        self.assertTrue(self._hilos[0].daemon)
        self.assertTrue(self._hilos[0].iniciado)

    def test_encender_con_puerto_ocupado_apaga_y_no_guarda(self):
        frame = self._frame()
        error = gui.overlay_servidor.OverlayPuertoOcupadoError("ocupado")
        with mock.patch.object(gui.overlay_servidor, "encender",
                               side_effect=error), \
                mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            resultado = gui_transmitir.cambiar_overlay(frame, True)
        self.assertFalse(resultado)
        self.assertFalse(frame._config["overlay_activo"])
        guardar.assert_not_called()
        anunciar.assert_called_once_with(
            "No se pudo activar el panel, el puerto 8730 está ocupado")
        self._recarga.assert_not_called()
        self.assertEqual(self._hilos, [])

    def test_apagar_guarda_y_anuncia(self):
        frame = SimpleNamespace(_config={"overlay_activo": True})
        with mock.patch.object(gui.overlay_servidor, "apagar") as apagar, \
                mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            resultado = gui_transmitir.cambiar_overlay(frame, False)
        self.assertFalse(resultado)
        apagar.assert_called_once_with()
        self.assertFalse(frame._config["overlay_activo"])
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "overlay", "activo", "false")
        anunciar.assert_called_once_with("Panel de chat apagado")
        self._recarga.assert_not_called()
        self.assertEqual(self._hilos, [])


class TestGuardarUsuarioTiktok(unittest.TestCase):

    def test_normaliza_arroba_y_guarda(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = gui_transmitir.guardar_usuario_tiktok(
                frame, "  @micanal  ")
        self.assertEqual(resultado, "micanal")
        self.assertEqual(frame._config["tiktok_usuario"], "micanal")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "tiktok", "usuario", "micanal")

    def test_invalido_queda_vacio(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = gui_transmitir.guardar_usuario_tiktok(frame, "!!!")
        self.assertEqual(resultado, "")
        self.assertEqual(frame._config["tiktok_usuario"], "")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "tiktok", "usuario", "")


class TestGuardarDestinoTransmision(unittest.TestCase):

    def test_destino_valido_se_guarda(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = gui_transmitir.guardar_destino_transmision(
                frame, "TikTok")
        self.assertEqual(resultado, "TikTok")
        self.assertEqual(frame._config["transmision_destino"], "TikTok")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "TikTok")

    def test_destino_invalido_se_guarda_vacio(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = gui_transmitir.guardar_destino_transmision(
                frame, "Twitch")
        self.assertEqual(resultado, "")
        self.assertEqual(frame._config["transmision_destino"], "")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "")


class TestGuardarDatosDirectoYoutube(unittest.TestCase):

    def test_guarda_y_normaliza(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = gui_transmitir.guardar_datos_directo_youtube(
                frame, "  Hola  ", "una descripción", "invalida",
                latencia="rara", ninos=True, dvr=False, categoria="99",
                etiquetas=["juegos", "directo"], miniatura="  foto.png ",
                lista="", lista_titulo="Se ignora")
        self.assertEqual(resultado["titulo"], "Hola")
        self.assertEqual(resultado["privacidad"], "unlisted")
        self.assertEqual(resultado["latencia"], "normal")
        self.assertEqual(resultado["categoria"], "")
        self.assertTrue(resultado["ninos"])
        self.assertFalse(resultado["dvr"])
        self.assertEqual(resultado["lista_titulo"], "")
        self.assertEqual(frame._config["transmision_youtube_titulo"], "Hola")
        self.assertEqual(
            frame._config["transmision_youtube_etiquetas"],
            "juegos, directo")
        self.assertEqual(
            frame._config["transmision_youtube_miniatura"], "foto.png")
        self.assertEqual(guardar.call_count, 11)

    def test_lista_con_titulo_se_conserva(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion"):
            resultado = gui_transmitir.guardar_datos_directo_youtube(
                frame, "Título", "", "public", lista="  PL123  ",
                lista_titulo="  Mi lista  ")
        self.assertEqual(resultado["lista"], "PL123")
        self.assertEqual(resultado["lista_titulo"], "Mi lista")
        self.assertEqual(
            frame._config["transmision_youtube_lista_titulo"], "Mi lista")


class TestActualizarBotonDirecto(unittest.TestCase):

    def _frame(self, **extras):
        frame = SimpleNamespace(
            sesion=SesionConectada(
                es_tiktok=False, usuario_tiktok="", conexion_propia=True),
            _config={"tiktok_usuario": ""},
            _conectado=False, _conectando=False,
            _obs_transmitiendo=False,
            _supervisar_transmision=mock.Mock(return_value=False),
            _boton_directo=mock.Mock())
        for clave, valor in extras.items():
            if clave == "_es_tiktok":
                frame.sesion.es_tiktok = valor
            elif clave == "_usuario_tiktok_sesion":
                frame.sesion.usuario_tiktok = valor
            elif clave == "_conexion_propia":
                frame.sesion.conexion_propia = valor
            elif clave == "_enlace_directo":
                frame.sesion.enlace_directo = valor
            else:
                setattr(frame, clave, valor)
        return frame

    def test_sin_boton_no_falla(self):
        frame = SimpleNamespace()
        gui_transmitir.actualizar_boton_directo(frame)

    def test_pasa_estado_al_boton(self):
        frame = self._frame()
        frame._supervisar_transmision.side_effect = (
            lambda accion: accion == "activo")
        gui_transmitir.actualizar_boton_directo(frame)
        frame._boton_directo.actualizar.assert_called_once_with(
            False, False, True, True, False)

    def test_pasa_deteniendo_al_boton(self):
        frame = self._frame()
        frame._supervisar_transmision.side_effect = (
            lambda accion: accion in ("activo", "deteniendo"))
        gui_transmitir.actualizar_boton_directo(frame)
        frame._boton_directo.actualizar.assert_called_once_with(
            False, False, True, True, True)

    def test_error_del_supervisor_usa_el_flag(self):
        frame = self._frame(_conectado=True, _conexion_propia=False,
                            _obs_transmitiendo=True)
        frame._supervisar_transmision.side_effect = RuntimeError("roto")
        gui_transmitir.actualizar_boton_directo(frame)
        frame._boton_directo.actualizar.assert_called_once_with(
            True, False, False, True, False)


class TestAlTerminarSupervisor(unittest.TestCase):

    def test_vivo_apaga_y_actualiza(self):
        frame = SimpleNamespace(_alive=True, _obs_transmitiendo=True,
                                _actualizar_boton_directo=mock.Mock())
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=_llamada_inmediata):
            gui_transmitir.al_terminar_supervisor(frame)
        self.assertFalse(frame._obs_transmitiendo)
        frame._actualizar_boton_directo.assert_called_once_with()

    def test_muerto_no_toca_nada(self):
        frame = SimpleNamespace(_alive=False, _obs_transmitiendo=True,
                                _actualizar_boton_directo=mock.Mock())
        with mock.patch.object(gui.wx, "CallAfter",
                               side_effect=_llamada_inmediata):
            gui_transmitir.al_terminar_supervisor(frame)
        self.assertTrue(frame._obs_transmitiendo)
        frame._actualizar_boton_directo.assert_not_called()


class TestSupervisarTransmision(unittest.TestCase):

    def test_activo_sin_supervisor_es_falso(self):
        frame = SimpleNamespace(_supervisor=None)
        self.assertFalse(
            gui_transmitir.supervisar_transmision(frame, "activo"))

    def test_activo_refleja_supervisor(self):
        frame = SimpleNamespace(
            _supervisor=SimpleNamespace(activo=True))
        self.assertTrue(
            gui_transmitir.supervisar_transmision(frame, "activo"))
        frame._supervisor.activo = False
        self.assertFalse(
            gui_transmitir.supervisar_transmision(frame, "activo"))

    def test_activo_da_true_con_supervisor_deteniendo(self):
        frame = SimpleNamespace(
            _supervisor=SimpleNamespace(activo=False, deteniendo=True))
        self.assertTrue(
            gui_transmitir.supervisar_transmision(frame, "activo"))

    def test_deteniendo_devuelve_el_estado(self):
        frame = SimpleNamespace(
            _supervisor=SimpleNamespace(activo=True, deteniendo=True))
        self.assertTrue(
            gui_transmitir.supervisar_transmision(frame, "deteniendo"))
        frame._supervisor.deteniendo = False
        self.assertFalse(
            gui_transmitir.supervisar_transmision(frame, "deteniendo"))
        self.assertFalse(gui_transmitir.supervisar_transmision(
            SimpleNamespace(_supervisor=None), "deteniendo"))

    def test_iniciar_con_supervisor_activo_anuncia(self):
        supervisor = SimpleNamespace(activo=True)
        frame = SimpleNamespace(_supervisor=supervisor)
        with mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        anunciar.assert_called_once_with(
            "Ya hay una transmisión en curso.")
        self.assertIs(frame._supervisor, supervisor)

    def test_iniciar_con_supervisor_deteniendo_anuncia_y_no_crea(self):
        supervisor = SimpleNamespace(activo=False, deteniendo=True)
        frame = SimpleNamespace(_supervisor=supervisor)
        with mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        anunciar.assert_called_once_with(
            "Deteniendo la transmisión. Esperando a que OBS confirme.")
        self.assertIs(frame._supervisor, supervisor)

    def test_iniciar_youtube_sin_sesion_anuncia(self):
        frame = SimpleNamespace(_supervisor=None)
        with mock.patch.object(gui.credenciales, "cargar",
                               return_value={}), \
                mock.patch.object(gui.credenciales, "hay_sesion",
                                   return_value=False), \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "YouTube", "")
        anunciar.assert_called_once_with(
            "Para transmitir a YouTube hace falta iniciar "
            "sesión con Google, en Preferencias, pestaña API y sesión.")
        self.assertIsNone(frame._supervisor)

    def test_iniciar_tiktok_crea_e_inicia_supervisor(self):
        frame = SimpleNamespace(
            _supervisor=None, _config={}, _alive=True,
            _conectado=False, _conectando=False,
            _actualizar_boton_directo=mock.Mock(),
            _al_terminar_supervisor=mock.Mock())
        supervisor = mock.Mock()
        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        self.assertIs(frame._supervisor, supervisor)
        supervisor.iniciar.assert_called_once_with()
        frame._actualizar_boton_directo.assert_called_once_with()
        args, kwargs = fabrica.call_args
        self.assertEqual(args[0], "TikTok")
        self.assertEqual(args[1], "alguien")
        self.assertEqual(kwargs["al_terminar"],
                         frame._al_terminar_supervisor)

    def test_iniciar_youtube_pasa_la_ruta_de_fin_pendiente(self):
        frame = SimpleNamespace(
            _supervisor=None, _config={}, _alive=True,
            _actualizar_boton_directo=mock.Mock(),
            _al_terminar_supervisor=mock.Mock(),
            _guardar_datos_directo_youtube=mock.Mock(return_value={
                "titulo": "T", "descripcion": "", "privacidad": "unlisted"}))
        supervisor = mock.Mock()
        credenciales = SimpleNamespace(
            cargar=lambda: {"token": "t"},
            hay_sesion=lambda datos: True,
            efectivas=lambda datos: {"efectivas": True},
            guardar_campo=mock.Mock())
        pedido = {"titulo": "T", "descripcion": "", "privacidad": "unlisted"}
        sentinela = object()
        with mock.patch.object(gui, "credenciales", credenciales), \
                mock.patch.object(gui, "youtube_api") as youtube_api, \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido), \
                mock.patch("ytchat.youtube.emision.cuerpo_emision",
                           return_value={"cuerpo": True}), \
                mock.patch("ytchat.youtube.emision.ganchos_youtube",
                           return_value=("p", "e", "f")), \
                mock.patch("ytchat.core.paths.fin_pendiente",
                           return_value=sentinela), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "YouTube", "")
        youtube_api.ClienteYouTube.assert_called_once()
        self.assertIs(frame._supervisor, supervisor)
        supervisor.iniciar.assert_called_once_with()
        args, kwargs = fabrica.call_args
        self.assertEqual(args[0], "YouTube")
        self.assertIs(kwargs["ruta_fin_pendiente"], sentinela)

    def test_detener_sin_supervisor_no_hace_nada(self):
        frame = SimpleNamespace(_supervisor=None,
                                _actualizar_boton_directo=mock.Mock())
        with mock.patch.object(gui.diagnostico,
                               "crear_hilo") as crear_hilo:
            gui_transmitir.supervisar_transmision(frame, "detener")
        crear_hilo.assert_not_called()
        frame._actualizar_boton_directo.assert_not_called()

    def test_detener_lanza_hilo_y_actualiza(self):
        supervisor = mock.Mock()
        hilo = mock.Mock()
        frame = SimpleNamespace(
            _supervisor=supervisor,
            _actualizar_boton_directo=mock.Mock())
        with mock.patch.object(gui.diagnostico, "crear_hilo",
                               return_value=hilo) as crear_hilo:
            gui_transmitir.supervisar_transmision(frame, "detener")
        crear_hilo.assert_called_once_with(
            supervisor.detener, "DetenerSupervisor")
        hilo.start.assert_called_once_with()
        frame._actualizar_boton_directo.assert_called_once_with()

    def _frame_inicia(self, config):
        return SimpleNamespace(
            _supervisor=None, _config=config, _alive=True,
            _actualizar_boton_directo=mock.Mock(),
            _al_terminar_supervisor=mock.Mock())

    def test_iniciar_pasa_el_aviso_de_sobrecarga_de_la_config(self):
        supervisor = mock.Mock()
        frame = self._frame_inicia({"avisar_sobrecarga": False})
        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        consulta = fabrica.call_args.kwargs["avisar_sobrecarga"]
        self.assertFalse(consulta())

    def test_el_aviso_de_sobrecarga_lee_la_config_en_cada_llamada(self):
        supervisor = mock.Mock()
        frame = self._frame_inicia({})
        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        consulta = fabrica.call_args.kwargs["avisar_sobrecarga"]
        self.assertTrue(consulta())
        frame._config["avisar_sobrecarga"] = False
        self.assertFalse(consulta())

    def test_iniciar_pasa_los_enganches_de_grabacion_envueltos(self):
        from ytchat.obs import obs_salida
        from ytchat.obs.obs_panel import GestorPanelObs
        supervisor = mock.Mock()
        frame = self._frame_inicia({})
        with mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                        return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        kwargs = fabrica.call_args.kwargs
        self.assertTrue(callable(kwargs["esperar_salida"]))
        self.assertTrue(callable(kwargs["crear_gestor"]))
        self.assertIsNot(kwargs["esperar_salida"], obs_salida.esperar_salida)
        self.assertIsNot(kwargs["crear_gestor"], GestorPanelObs)

    def test_la_casilla_de_grabacion_se_lee_en_cada_llamada(self):
        supervisor = mock.Mock()
        frame = self._frame_inicia({"grabar_al_transmitir": False})
        capturado = {}

        class GrabacionFalsa:
            def __init__(self, activa=None, al_anunciar=None,
                         crear_gestor=None):
                capturado["activa"] = activa

            def envolver_crear_gestor(self, original):
                return original

            def envolver_esperar_salida(self, original):
                return original

        with mock.patch("ytchat.obs.obs_grabacion.GrabacionAlTransmitir",
                        GrabacionFalsa), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           return_value=supervisor):
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "TikTok", "alguien")
        self.assertFalse(capturado["activa"]())
        frame._config["grabar_al_transmitir"] = True
        self.assertTrue(capturado["activa"]())


class TestAlternarAvisoSobrecarga(unittest.TestCase):

    def test_desactivar_guarda_marca_y_anuncia(self):
        item = mock.Mock()
        frame = SimpleNamespace(_config={"avisar_sobrecarga": True},
                                mi_avisos_sobrecarga=item)
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_aviso_sobrecarga(frame)
        self.assertFalse(frame._config["avisar_sobrecarga"])
        item.Check.assert_called_once_with(False)
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "avisar_sobrecarga", "false")
        anunciar.assert_called_once_with("Avisos de sobrecarga desactivados")

    def test_activar_guarda_marca_y_anuncia(self):
        item = mock.Mock()
        frame = SimpleNamespace(_config={"avisar_sobrecarga": False},
                                mi_avisos_sobrecarga=item)
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_aviso_sobrecarga(frame)
        self.assertTrue(frame._config["avisar_sobrecarga"])
        item.Check.assert_called_once_with(True)
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "avisar_sobrecarga", "true")
        anunciar.assert_called_once_with("Avisos de sobrecarga activados")

    def test_sin_item_no_falla_y_usa_el_por_defecto(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_aviso_sobrecarga(frame)
        self.assertFalse(frame._config["avisar_sobrecarga"])
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "avisar_sobrecarga", "false")
        anunciar.assert_called_once_with("Avisos de sobrecarga desactivados")


class TestAlternarGrabarAlTransmitir(unittest.TestCase):

    def test_desactivar_guarda_marca_y_anuncia(self):
        item = mock.Mock()
        frame = SimpleNamespace(_config={"grabar_al_transmitir": True},
                                mi_grabar_al_transmitir=item)
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_grabar_al_transmitir(frame)
        self.assertFalse(frame._config["grabar_al_transmitir"])
        item.Check.assert_called_once_with(False)
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "grabar_al_transmitir", "false")
        anunciar.assert_called_once_with(
            "Grabación al transmitir desactivada")

    def test_activar_guarda_marca_y_anuncia(self):
        item = mock.Mock()
        frame = SimpleNamespace(_config={"grabar_al_transmitir": False},
                                mi_grabar_al_transmitir=item)
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_grabar_al_transmitir(frame)
        self.assertTrue(frame._config["grabar_al_transmitir"])
        item.Check.assert_called_once_with(True)
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "grabar_al_transmitir", "true")
        anunciar.assert_called_once_with(
            "Grabación al transmitir activada")

    def test_sin_item_no_falla_y_usa_el_por_defecto(self):
        frame = SimpleNamespace(_config={})
        with mock.patch.object(gui, "guardar_opcion") as guardar, \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui_transmitir.alternar_grabar_al_transmitir(frame)
        self.assertTrue(frame._config["grabar_al_transmitir"])
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "grabar_al_transmitir", "true")
        anunciar.assert_called_once_with(
            "Grabación al transmitir activada")


class TestAlConectarChatEnlaceDirecto(unittest.TestCase):
    """Al conectar el chat de un directo propio, el enlace queda copiable
    aunque YouTube no tenga chat (para niños o privado)."""

    URL = "https://www.youtube.com/watch?v=abcdefghijk"

    def _conector(self, frame):
        supervisor = mock.Mock()
        credenciales = SimpleNamespace(
            cargar=lambda: {"token": "t"},
            hay_sesion=lambda datos: True,
            efectivas=lambda datos: {"efectivas": True},
            guardar_campo=mock.Mock())
        pedido = {"titulo": "T", "descripcion": "", "privacidad": "private"}
        with mock.patch.object(gui, "credenciales", credenciales), \
                mock.patch.object(gui, "youtube_api"), \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=pedido), \
                mock.patch("ytchat.youtube.emision.cuerpo_emision",
                           return_value={"cuerpo": True}), \
                mock.patch("ytchat.youtube.emision.ganchos_youtube",
                           return_value=("p", "e", "f")), \
                mock.patch("ytchat.core.paths.fin_pendiente",
                           return_value=None), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision",
                           return_value=supervisor) as fabrica:
            gui_transmitir.supervisar_transmision(
                frame, "iniciar", "YouTube", "")
        return fabrica.call_args.kwargs["al_conectar_chat"]

    def _frame(self, guardados):
        return SimpleNamespace(
            _supervisor=None, _config={}, _alive=True,
            _conectado=False, _conectando=False,
            sesion=SesionConectada(enlace_directo=""),
            txt_url=mock.Mock(), _on_conectar=mock.Mock(),
            _actualizar_boton_directo=mock.Mock(),
            _al_terminar_supervisor=mock.Mock(),
            _guardar_datos_directo_youtube=mock.Mock(
                return_value=guardados))

    def _conectar(self, guardados):
        frame = self._frame(guardados)
        conector = self._conector(frame)
        with mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=_llamada_inmediata):
            conector(self.URL)
        return frame, anunciar

    def test_privado_guarda_el_enlace_antes_de_avisar(self):
        frame, anunciar = self._conectar(
            {"titulo": "T", "descripcion": "", "privacidad": "private",
             "ninos": False})
        self.assertEqual(frame.sesion.enlace_directo, self.URL)
        anunciar.assert_called_once_with(
            "El directo es privado y YouTube no deja leer su chat. "
            "Para leerlo, transmite como público o no listado.")

    def test_ninos_guarda_el_enlace_antes_de_avisar(self):
        frame, anunciar = self._conectar(
            {"titulo": "T", "descripcion": "", "privacidad": "public",
             "ninos": True})
        self.assertEqual(frame.sesion.enlace_directo, self.URL)
        anunciar.assert_called_once_with(
            "El directo está marcado como hecho para niños y YouTube no "
            "tiene chat.")


if __name__ == "__main__":
    unittest.main()
