"""Roles de autor de YouTube y sonido por rol."""

import queue
import sys
import threading
import types
import unittest
from unittest import mock

import main
from ytchat.core import sonidos_eventos
from ytchat.core.config import (
    TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA,
)


class AutorFalso:
    def __init__(self, **atributos):
        for clave, valor in atributos.items():
            setattr(self, clave, valor)


class TestRolDeAutor(unittest.TestCase):
    def test_cada_atributo_solo(self):
        self.assertEqual(
            sonidos_eventos.rol_de_autor(AutorFalso(isChatOwner=True)),
            sonidos_eventos.ROL_PROPIETARIO)
        self.assertEqual(
            sonidos_eventos.rol_de_autor(AutorFalso(isChatModerator=True)),
            sonidos_eventos.ROL_MODERADOR)
        self.assertEqual(
            sonidos_eventos.rol_de_autor(AutorFalso(isVerified=True)),
            sonidos_eventos.ROL_VERIFICADO)
        self.assertEqual(
            sonidos_eventos.rol_de_autor(AutorFalso(isChatSponsor=True)),
            sonidos_eventos.ROL_MIEMBRO)

    def test_precedencia(self):
        autor = AutorFalso(isChatModerator=True, isVerified=True,
                           isChatSponsor=True)
        self.assertEqual(sonidos_eventos.rol_de_autor(autor),
                         sonidos_eventos.ROL_MODERADOR)
        autor = AutorFalso(isChatOwner=True, isChatModerator=True,
                           isVerified=True, isChatSponsor=True)
        self.assertEqual(sonidos_eventos.rol_de_autor(autor),
                         sonidos_eventos.ROL_PROPIETARIO)
        autor = AutorFalso(isVerified=True, isChatSponsor=True)
        self.assertEqual(sonidos_eventos.rol_de_autor(autor),
                         sonidos_eventos.ROL_VERIFICADO)

    def test_none_y_sin_atributos(self):
        self.assertEqual(sonidos_eventos.rol_de_autor(None), "")
        self.assertEqual(sonidos_eventos.rol_de_autor(object()), "")
        self.assertEqual(sonidos_eventos.rol_de_autor(AutorFalso()), "")

    def test_nunca_lanza(self):
        class AutorRoto:
            @property
            def isChatOwner(self):
                raise RuntimeError("falla")
        self.assertEqual(sonidos_eventos.rol_de_autor(AutorRoto()), "")


class TestSonidoDeMensaje(unittest.TestCase):
    def test_comun_con_rol(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_TEXTO, sonidos_eventos.ROL_PROPIETARIO),
            "mensaje_propietario")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_TEXTO, sonidos_eventos.ROL_MODERADOR),
            "mensaje_moderador")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_TEXTO, sonidos_eventos.ROL_VERIFICADO),
            "mensaje_verificado")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_TEXTO, sonidos_eventos.ROL_MIEMBRO),
            "mensaje_miembro")

    def test_comun_sin_rol(self):
        self.assertEqual(sonidos_eventos.sonido_de_mensaje(TIPO_TEXTO, ""), "mensaje_nuevo")
        self.assertEqual(sonidos_eventos.sonido_de_mensaje(TIPO_TEXTO), "mensaje_nuevo")

    def test_entrada_suena_su_evento(self):
        self.assertEqual(sonidos_eventos.sonido_de_mensaje(TIPO_ENTRADA, ""), "entrada")

    def test_superchat_suena_una_sola_vez(self):
        for tipo in (TIPO_SUPERCHAT, TIPO_STICKER):
            self.assertEqual(
                sonidos_eventos.sonido_de_mensaje(
                    tipo, sonidos_eventos.ROL_MODERADOR), "superchat")

    def test_miembro_nuevo_no_usa_rol(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_MIEMBRO, sonidos_eventos.ROL_MODERADOR), "nuevo_miembro")

    def test_eventos_nuevos_de_tiktok_suenan_su_evento(self):
        for tipo in (TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA):
            self.assertEqual(sonidos_eventos.sonido_de_mensaje(tipo, ""), tipo)
            self.assertEqual(
                sonidos_eventos.sonido_de_mensaje(
                    tipo, sonidos_eventos.ROL_MODERADOR), tipo)


class TestEsOrilla(unittest.TestCase):
    ARRIBA = sonidos_eventos.TECLA_FLECHA_ARRIBA
    ABAJO = sonidos_eventos.TECLA_FLECHA_ABAJO

    def test_arriba_en_primera_fila(self):
        self.assertTrue(sonidos_eventos.es_orilla(self.ARRIBA, 0, 5))

    def test_abajo_en_ultima_fila(self):
        self.assertTrue(sonidos_eventos.es_orilla(self.ABAJO, 4, 5))

    def test_adentro_no_es_orilla(self):
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA, 1, 5))
        self.assertFalse(sonidos_eventos.es_orilla(self.ABAJO, 0, 5))
        self.assertFalse(sonidos_eventos.es_orilla(self.ABAJO, 3, 5))

    def test_lista_vacia_ambas_flechas(self):
        self.assertTrue(sonidos_eventos.es_orilla(self.ARRIBA, -1, 0))
        self.assertTrue(sonidos_eventos.es_orilla(self.ABAJO, -1, 0))

    def test_sin_seleccion_y_lista_con_filas(self):
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA, -1, 5))
        self.assertFalse(sonidos_eventos.es_orilla(self.ABAJO, -1, 5))

    def test_una_sola_fila_es_ambas_orillas(self):
        self.assertTrue(sonidos_eventos.es_orilla(self.ARRIBA, 0, 1))
        self.assertTrue(sonidos_eventos.es_orilla(self.ABAJO, 0, 1))

    def test_otra_tecla_nunca_es_orilla(self):
        self.assertFalse(sonidos_eventos.es_orilla(ord("C"), 0, 5))
        self.assertFalse(sonidos_eventos.es_orilla(13, 0, 1))
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA + 1, 0, 0))

    def test_lo_no_numerico_no_lanza_y_es_falso(self):
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA, None, 5))
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA, 0, None))
        self.assertFalse(sonidos_eventos.es_orilla(self.ARRIBA, "x", "y"))

    def test_constantes_coinciden_con_wx(self):
        import wx
        self.assertEqual(sonidos_eventos.TECLA_FLECHA_ARRIBA, wx.WXK_UP)
        self.assertEqual(sonidos_eventos.TECLA_FLECHA_ABAJO, wx.WXK_DOWN)


class TestTramoRegalo(unittest.TestCase):
    def test_bordes(self):
        self.assertEqual(sonidos_eventos.tramo_regalo(1), "regalo_chico")
        self.assertEqual(sonidos_eventos.tramo_regalo(99), "regalo_chico")
        self.assertEqual(sonidos_eventos.tramo_regalo(100), "regalo_mediano")
        self.assertEqual(sonidos_eventos.tramo_regalo(999), "regalo_mediano")
        self.assertEqual(sonidos_eventos.tramo_regalo(1000), "regalo_grande")
        self.assertEqual(sonidos_eventos.tramo_regalo(5000), "regalo_grande")

    def test_sin_diamantes_es_chico(self):
        self.assertEqual(sonidos_eventos.tramo_regalo(0), "regalo_chico")


class TestSonidoRegaloTikTok(unittest.TestCase):
    def test_regalo_de_250_diamantes_es_mediano(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_SUPERCHAT, "", "250 diamantes", "tiktok"),
            "regalo_mediano")

    def test_regalo_grande(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_SUPERCHAT, "", "1500 diamantes", "tiktok"),
            "regalo_grande")

    def test_regalo_sin_numero_es_chico(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_SUPERCHAT, "", "", "tiktok"), "regalo_chico")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_SUPERCHAT, "", "regalo", "tiktok"), "regalo_chico")

    def test_superchat_de_youtube_sigue_igual(self):
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_SUPERCHAT, "", "5 €", "youtube"), "superchat")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(TIPO_SUPERCHAT, ""), "superchat")
        self.assertEqual(
            sonidos_eventos.sonido_de_mensaje(
                TIPO_STICKER, "", "250 diamantes", "tiktok"), "superchat")


def _config_minima(**extras):
    base = {
        "usuarios_silenciados": [], "palabras_silenciadas": [],
        "silenciados_ocultar": set(), "silenciados_runtime": set(),
        "silenciar_lectura": False, "limpiar_emojis": False,
        "eliminar_urls": False, "max_longitud_mensaje": 200,
        "umbral_solo_nombre": 0, "formato_prefijo": "nombre_mensaje",
        "estrategia": "todas", "tamanio_maximo": 10,
    }
    base.update(extras)
    return base


class TestProcesarEntranteConRol(unittest.TestCase):
    def test_entrega_el_rol_a_on_message(self):
        recibidos = []

        def on_message(autor, mensaje, hora, tipo, monto, canal_id, rol=""):
            recibidos.append(rol)

        main.procesar_entrante("Ana", "hola", TIPO_TEXTO, "", "canal",
                               queue.Queue(), _config_minima(), main.Stats(),
                               on_message=on_message, rol="moderador")
        self.assertEqual(recibidos, ["moderador"])

    def test_sin_rol_queda_igual(self):
        recibidos = []

        def on_message(autor, mensaje, hora, tipo, monto, canal_id, rol=""):
            recibidos.append(rol)

        main.procesar_entrante("Ana", "hola", TIPO_TEXTO, "", "canal",
                               queue.Queue(), _config_minima(), main.Stats(),
                               on_message=on_message)
        self.assertEqual(recibidos, [""])


class TestCableadoCapturaYouTube(unittest.TestCase):
    def _item_pytchat(self, moderador=True):
        autor = types.SimpleNamespace(
            name="Ana", channelId="CANAL1", isChatOwner=False,
            isChatModerator=moderador, isVerified=False, isChatSponsor=False)
        return types.SimpleNamespace(
            author=autor, message="hola", type="textMessage",
            timestamp=None)

    def test_item_falso_con_moderador_llega_a_on_message_con_rol(self):
        item = self._item_pytchat(moderador=True)

        class ChatFalso:
            def __init__(self, items):
                self._items = items
                self._vivo = True

            def is_alive(self):
                return self._vivo

            def get(self):
                self._vivo = False
                chat = self

                class Lote:
                    def sync_items(self):
                        return chat._items
                return Lote()

            def raise_for_status(self):
                return None

        chat = ChatFalso([item])
        pytchat_falso = types.SimpleNamespace(create=lambda **k: chat)
        recibidos = []

        def on_message(autor, mensaje, hora, tipo, monto, canal_id, rol=""):
            recibidos.append((autor, rol))

        parada = threading.Event()
        with mock.patch.dict(sys.modules, {"pytchat": pytchat_falso}), \
                mock.patch.object(main, "_cliente_pytchat",
                                  return_value=mock.Mock(close=lambda: None)), \
                mock.patch.object(main._snd, "reproducir"):
            main._captura_en_loop("dQw4w9WgXcQ", queue.Queue(),
                                  _config_minima(reconectar=False),
                                  parada, main.Stats(),
                                  on_message=on_message,
                                  on_estado=None, sesion_activa=None)
        self.assertEqual(recibidos, [("Ana", "moderador")])


class VistaFalsa:
    """Vista falsa que registra las llamadas (actúa como marco vivo)."""

    def __init__(self):
        self.llamadas = []
        self.activa = True

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)

        def registrar(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))
            return True

        return registrar


class TestReenvioRolConexion(unittest.TestCase):
    def _conexiones(self):
        from ytchat.capture.conexion import Conexiones
        from ytchat.capture.sesiones import RegistroSesiones
        vista = VistaFalsa()
        conexiones = Conexiones(
            queue.Queue(), {}, mock.Mock(), threading.Event(),
            crear_hilo=lambda *a, **k: _HiloInerte(),
            registro=RegistroSesiones(), vista=vista)
        return conexiones, vista

    def _agregados(self, vista):
        return [(a, kw) for n, a, kw in vista.llamadas
                if n == "agregar_mensaje"]

    def test_youtube_reenvia_el_rol(self):
        conexiones, vista = self._conexiones()
        callbacks = {}
        def captura(*args, **kwargs):
            callbacks.update(kwargs)

        def hilo(objetivo, nombre, **kwargs):
            return _HiloEjecuta(objetivo) if nombre == "Chat" else _HiloInerte()

        conexiones._crear_hilo = hilo
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("T", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo",
                                  return_value=True), \
                mock.patch.object(main, "captura_con_reconexion",
                                  side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir"):
            conexiones.conectar("dQw4w9WgXcQ")
            callbacks["on_message"]("Ana", "hola", "12:00", main.TIPO_TEXTO,
                                    "", "CANAL1", rol="moderador")
        agregados = self._agregados(vista)
        self.assertEqual(len(agregados), 1)
        args, kwargs = agregados[0]
        self.assertEqual(kwargs.get("rol"), "moderador")
        self.assertEqual(kwargs.get("plataforma"), "youtube")

    def test_tiktok_reenvia_el_rol_por_defecto(self):
        conexiones, vista = self._conexiones()
        callbacks = {}
        def captura(*args, **kwargs):
            callbacks.update(kwargs)

        def hilo(objetivo, nombre, **kwargs):
            return _HiloEjecuta(objetivo) if nombre == "TikTok" else _HiloInerte()

        conexiones._crear_hilo = hilo
        from ytchat.capture import tiktok_captura
        with mock.patch.object(main, "procesar_entrante",
                               side_effect=lambda *a, **k: k["on_message"](
                                   "Ana", "hola", "12:00", main.TIPO_TEXTO,
                                   "", "TIKID", rol="")), \
                mock.patch.object(tiktok_captura, "capturar_con_reconexion",
                                  side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir"):
            conexiones._conectar_tiktok("pepe")
            callbacks["on_evento"]("Ana", "hola", main.TIPO_TEXTO, "", "TIKID")
        agregados = self._agregados(vista)
        self.assertEqual(len(agregados), 1)
        args, kwargs = agregados[0]
        self.assertEqual(kwargs.get("rol"), "")
        self.assertEqual(kwargs.get("plataforma"), "tiktok")


class _HiloInerte:
    def start(self):
        return None


class _HiloEjecuta:
    def __init__(self, objetivo):
        self.objetivo = objetivo

    def start(self):
        self.objetivo()


class TestSonidoGuiPorRol(unittest.TestCase):
    def _frame(self):
        from ytchat.ui import gui
        from ytchat.ui.chat_vivo import ControladorChat
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"limpiar_emojis": True}
        frame._autor_esta_oculto = lambda autor: False
        frame._sumar_superchat = mock.Mock()
        frame.lb_chat = mock.Mock()
        frame.chat_vivo = ControladorChat(
            frame.lb_chat, 500,
            activo=lambda: True,
            autor_oculto=frame._autor_esta_oculto,
            formatear=frame._format_display,
            al_superchat=frame._sumar_superchat)
        return frame

    def _procesar(self, frame, tipo, rol):
        from ytchat.ui import chat_vivo
        from ytchat.ui.lista_chat import MensajeChat
        registro = MensajeChat(plataforma="youtube", autor="Ana",
                               identificador="C", texto="hola", hora="12:00",
                               tipo=tipo, monto="", rol=rol)
        with mock.patch.object(chat_vivo._snd, "reproducir") as reproducir:
            frame.chat_vivo._procesar(registro)
        return reproducir.call_args.args[0]

    def test_verificado_reproduce_su_evento(self):
        self.assertEqual(self._procesar(self._frame(), TIPO_TEXTO, "verificado"),
                         "mensaje_verificado")

    def test_sin_rol_reproduce_comun(self):
        self.assertEqual(self._procesar(self._frame(), TIPO_TEXTO, ""), "mensaje_nuevo")


if __name__ == "__main__":
    unittest.main()
