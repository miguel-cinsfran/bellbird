"""Prueba de equivalencia de la barra de menú.

Construye el menú con el mismo doble de frame que usan las pruebas de
`test_gui.py` (mocks de `wx.Menu` y `wx.MenuBar`, sin ventanas) y comprueba
la lista completa de (menú, etiqueta, id, tipo) en orden, con los submenús
atribuidos a su título. La lista se fijó contra el código anterior a mover
`_build_menubar` a `gui_menu.construir_menu`: entra por
`YTChatFrame._build_menubar`, que ahora delega, así que pasa igual antes y
después sin tocarla.
"""

import sys
import unittest
from unittest import mock

import wx

from tests.ventanas_prueba import destruir
from ytchat.ui import gui


def _construir_lista(accel=None):
    """Llama a `_build_menubar` con dobles y devuelve la lista ordenada."""
    barra = []

    def crear_menu(*args, **kwargs):
        menu = mock.MagicMock()
        menu._entradas = []

        def _item(tipo, args):
            if len(args) >= 2 and isinstance(args[1], str):
                etiqueta = args[1]
                identificador = args[0]
            else:
                etiqueta = args[0] if args and isinstance(args[0], str) else repr(args)
                identificador = args[0] if args else None
            menu._entradas.append((tipo, etiqueta, identificador))
            return mock.Mock()

        def _sub(sub, titulo, *args, **kwargs):
            menu._entradas.append(("submenu", titulo, sub))
            return mock.Mock()

        menu.Append.side_effect = lambda *args: _item("normal", args)
        menu.AppendRadioItem.side_effect = lambda *args: _item("radio", args)
        menu.AppendCheckItem.side_effect = lambda *args: _item("check", args)
        menu.AppendSubMenu.side_effect = _sub
        menu.AppendSeparator.side_effect = (
            lambda *args: menu._entradas.append(("sep", "---", None)))
        return menu

    def crear_barra(*args, **kwargs):
        barra_mock = mock.MagicMock()

        def anexar(menu, titulo):
            barra.append((titulo, menu))
            return True

        barra_mock.Append.side_effect = anexar
        return barra_mock

    frame = mock.Mock()
    frame._accel.return_value = ""
    if accel is not None:
        frame._accel.side_effect = accel
    frame._config = {"mostrar_botones_reproductor": True}
    with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu), \
            mock.patch.object(gui.wx, "MenuBar", side_effect=crear_barra):
        gui.YTChatFrame._build_menubar(frame)
    lista = []
    for titulo, menu in barra:
        for tipo, etiqueta, dato in menu._entradas:
            if tipo == "sep":
                lista.append((titulo, "---", None, "sep"))
            elif tipo == "submenu":
                lista.append((titulo, etiqueta, None, "submenu"))
                for stipo, setiqueta, sid in dato._entradas:
                    lista.append((etiqueta, setiqueta, sid, stipo))
            else:
                lista.append((titulo, etiqueta, dato, tipo))
    return [titulo for titulo, _ in barra], lista


class TestEquivalenciaMenu(unittest.TestCase):

    def test_orden_de_menus(self):
        titulos, _ = _construir_lista()
        self.assertEqual(
            ["&Archivo", "&Ver", "&Chat", "Vo&z", "&Reproductor",
             "&Transmisión", "&Música", "&Herramientas", "A&yuda"], titulos)

    def test_contenido_completo_en_orden(self):
        _, lista = _construir_lista()
        ANY = gui.wx.ID_ANY
        self.assertEqual([
            ("&Archivo", "&Conectar", ANY, "normal"),
            ("&Archivo", "&Desconectar", ANY, "normal"),
            ("&Archivo", "Copiar &enlace del directo", ANY, "normal"),
            ("&Archivo", "---", None, "sep"),
            ("&Archivo", "&Historial de directos…", ANY, "normal"),
            ("&Archivo", "---", None, "sep"),
            ("&Archivo", "&Salir\tAlt+F4", gui.wx.ID_EXIT, "normal"),
            ("&Ver", "Región &siguiente\tF6", ANY, "normal"),
            ("&Ver", "Región &anterior\tShift+F6", ANY, "normal"),
            ("&Ver", "---", None, "sep"),
            ("&Ver", "Ir a co&nexión (URL)", ANY, "normal"),
            ("&Ver", "Ir a la &lista del panel actual", ANY, "normal"),
            ("&Ver", "Ir a &Chat en vivo", ANY, "normal"),
            ("&Ver", "Ir a Co&mentarios", ANY, "normal"),
            ("&Ver", "Ir al &Reproductor", ANY, "normal"),
            ("&Ver", "---", None, "sep"),
            ("&Ver", "Anunciar &estado", ANY, "normal"),
            ("&Ver", "Anunciar a&utor del último mensaje", ANY, "normal"),
            ("&Ver", "Mensajes recientes &del chat", None, "submenu"),
            ("Mensajes recientes &del chat", "Leer el último mensaje del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 2 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 3 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 4 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 5 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 6 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 7 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 8 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 9 desde el final del chat", ANY, "normal"),
            ("Mensajes recientes &del chat", "Leer el mensaje 10 desde el final del chat", ANY, "normal"),
            ("&Ver", "Describir la escena de &OBS", ANY, "normal"),
            ("&Ver", "Preguntar a la &IA sobre la imagen…", ANY, "normal"),
            ("&Ver", "Consul&ta rápida a la IA", ANY, "normal"),
            ("&Chat", "&Enviar mensaje al chat del directo (solo YouTube)…",
             ANY, "normal"),
            ("&Chat", "---", None, "sep"),
            ("&Chat", "&Filtro de mensajes", None, "submenu"),
            ("&Filtro de mensajes", "Todos", ANY, "radio"),
            ("&Filtro de mensajes", "Solo texto", ANY, "radio"),
            ("&Filtro de mensajes", "Super Chats", ANY, "radio"),
            ("&Filtro de mensajes", "Membresías", ANY, "radio"),
            ("Vo&z", "&Pausar lectura", ANY, "normal"),
            ("Vo&z", "&Detener voz", ANY, "normal"),
            ("Vo&z", "&Vaciar cola", ANY, "normal"),
            ("Vo&z", "---", None, "sep"),
            ("Vo&z", "Hablar más &lento", ANY, "normal"),
            ("Vo&z", "Hablar más &rápido", ANY, "normal"),
            ("Vo&z", "&Bajar volumen de la voz", ANY, "normal"),
            ("Vo&z", "&Subir volumen de la voz", ANY, "normal"),
            ("Vo&z", "---", None, "sep"),
            ("Vo&z", "S&ilenciar lectura TTS", ANY, "check"),
            ("Vo&z", "Silenciar s&onidos", ANY, "check"),
            ("Vo&z", "---", None, "sep"),
            ("Vo&z", "Seleccionar vo&z", None, "submenu"),
            ("&Reproductor", "&Reproducir o pausa", ANY, "normal"),
            ("&Reproductor", "R&etroceder 1 minuto", ANY, "normal"),
            ("&Reproductor", "&Avanzar 1 minuto", ANY, "normal"),
            ("&Reproductor", "&Ir al directo", ANY, "normal"),
            ("&Reproductor", "De&tener reproducción", ANY, "normal"),
            ("&Reproductor", "&Silenciar o activar audio", ANY, "normal"),
            ("&Reproductor", "Pantalla &completa", ANY, "normal"),
            ("&Reproductor", "Ca&lidad del vídeo", None, "submenu"),
            ("Ca&lidad del vídeo", "Automática", ANY, "radio"),
            ("Ca&lidad del vídeo", "1080p", ANY, "radio"),
            ("Ca&lidad del vídeo", "720p", ANY, "radio"),
            ("Ca&lidad del vídeo", "480p", ANY, "radio"),
            ("Ca&lidad del vídeo", "360p", ANY, "radio"),
            ("Ca&lidad del vídeo", "240p", ANY, "radio"),
            ("Ca&lidad del vídeo", "144p", ANY, "radio"),
            ("&Reproductor", "---", None, "sep"),
            ("&Reproductor", "Descargar este &vídeo", ANY, "normal"),
            ("&Reproductor", "---", None, "sep"),
            ("&Reproductor", "&Bajar volumen del reproductor", ANY, "normal"),
            ("&Reproductor", "S&ubir volumen del reproductor", ANY, "normal"),
            ("&Reproductor", "---", None, "sep"),
            ("&Reproductor", "Mostrar botones en &pantalla", ANY, "check"),
            ("&Transmisión", "&Panel de transmisión…", ANY, "normal"),
            ("&Transmisión", "Silenciar el &micrófono de OBS", ANY, "normal"),
            ("&Transmisión", "&Avisar cuando OBS no da abasto", ANY, "check"),
            ("&Música", "&Elegir música…", ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Reproducir o &pausar", ANY, "normal"),
            ("&Música", "&Siguiente canción", ANY, "normal"),
            ("&Música", "Canción &anterior", ANY, "normal"),
            ("&Música", "Subir el &volumen", ANY, "normal"),
            ("&Música", "&Bajar el volumen", ANY, "normal"),
            ("&Música", "&Qué suena", ANY, "normal"),
            ("&Música", "Adelantar 10 segu&ndos", ANY, "normal"),
            ("&Música", "Re&troceder 10 segundos", ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Silenciar la &música", ANY, "check"),
            ("&Música", "&Detener la música", ANY, "normal"),
            ("&Música", "&Orden aleatorio", ANY, "check"),
            ("&Música", "Cambiar la &repetición", ANY, "normal"),
            ("&Herramientas", "Gestor de &descargas…", ANY, "normal"),
            ("&Herramientas", "&Actualizar yt-dlp", ANY, "normal"),
            ("&Herramientas", "---", None, "sep"),
            ("&Herramientas", "&Preferencias…", ANY, "normal"),
            ("A&yuda", "&Guía de configuración de la API…", ANY, "normal"),
            ("A&yuda", "&Marcar incidencia", ANY, "normal"),
            ("A&yuda", "&Buscar actualizaciones…", ANY, "normal"),
            ("A&yuda", "&Acerca de", gui.wx.ID_ABOUT, "normal"),
        ], lista)


class TestMenuMusica(unittest.TestCase):
    """El menú Música con sus elementos y sus atajos a la vista."""

    def _entradas(self):
        from ytchat.core import config as cfg

        def accel(accion):
            valor = cfg.ATAJOS_DEFAULTS.get(accion, "")
            return ("\t" + gui._fmt_accel(valor)) if valor else ""

        _, lista = _construir_lista(accel)
        return [fila for fila in lista if fila[0] == "&Música"]

    def test_trece_elementos_en_orden_con_atajos(self):
        ANY = gui.wx.ID_ANY
        self.assertEqual([
            ("&Música", "&Elegir música…\tCtrl+Shift+M", ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Reproducir o &pausar\tCtrl+Alt+Space", ANY, "normal"),
            ("&Música", "&Siguiente canción\tCtrl+Alt+Right", ANY, "normal"),
            ("&Música", "Canción &anterior\tCtrl+Alt+Left", ANY, "normal"),
            ("&Música", "Subir el &volumen\tCtrl+Alt+Up", ANY, "normal"),
            ("&Música", "&Bajar el volumen\tCtrl+Alt+Down", ANY, "normal"),
            ("&Música", "&Qué suena\tCtrl+Alt+T", ANY, "normal"),
            ("&Música", "Adelantar 10 segu&ndos\tCtrl+Alt+Shift+Right",
             ANY, "normal"),
            ("&Música", "Re&troceder 10 segundos\tCtrl+Alt+Shift+Left",
             ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Silenciar la &música\tCtrl+Alt+M", ANY, "check"),
            ("&Música", "&Detener la música\tCtrl+Alt+D", ANY, "normal"),
            ("&Música", "&Orden aleatorio\tCtrl+Alt+A", ANY, "check"),
            ("&Música", "Cambiar la &repetición\tCtrl+Alt+R", ANY, "normal"),
        ], self._entradas())


class TestMenuRecientes(unittest.TestCase):
    """El submenú de mensajes recientes: diez ítems que leen 1 a 10."""

    def _ver(self):
        from ytchat.ui import gui_menu
        creados = []

        def crear_menu(*args, **kwargs):
            menu = mock.MagicMock()
            menu._entradas = []
            menu.Append.side_effect = (
                lambda *args: menu._entradas.append(args) or mock.Mock())
            creados.append(menu)
            return menu

        frame = mock.Mock()
        frame._accel.return_value = ""
        with mock.patch.object(gui.wx, "Menu", side_effect=crear_menu):
            gui_menu._construir_menu_ver(frame, mock.Mock())
        return frame, creados

    def test_items_en_orden_con_sus_etiquetas(self):
        from ytchat.ui.atajos_captura import ETIQUETAS
        _frame, creados = self._ver()
        sub = creados[1]
        self.assertEqual(
            [args[1] for args in sub._entradas],
            [ETIQUETAS[f"chat_reciente_{n}"] for n in range(1, 11)])

    def test_cada_item_llama_a_leer_reciente_con_su_numero(self):
        frame, _creados = self._ver()
        llamadas = [llamada.args[2] for llamada in
                    frame._bind_menu.call_args_list
                    if len(llamada.args) == 3
                    and llamada.args[1] is frame._leer_reciente]
        self.assertEqual(llamadas, list(range(1, 11)))

    def test_leer_reciente_delega_en_recientes(self):
        frame = mock.Mock()
        gui.YTChatFrame._leer_reciente(frame, 4)
        frame._recientes.leer.assert_called_once_with(4)


class TestRegistroDeComandos(unittest.TestCase):
    """El manejador genérico anota el comando y deja correr el del ítem."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def test_anota_la_etiqueta_y_no_impide_que_corra_el_manejador_propio(self):
        from ytchat.ui import gui_menu

        frame = wx.Frame(None)
        self.addCleanup(destruir, frame)
        barra = wx.MenuBar()
        menu = wx.Menu()
        item = menu.Append(wx.ID_ANY, "&Conectar\tCtrl+K")
        barra.Append(menu, "&Archivo")
        frame.SetMenuBar(barra)
        propias = []
        frame.Bind(wx.EVT_MENU, lambda _evento: propias.append("propio"), item)
        gui_menu._registrar_menus(frame)
        evento = wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId())
        with self.assertLogs(gui_menu.logger, level="DEBUG") as registro:
            frame.GetEventHandler().ProcessEvent(evento)

        self.assertEqual(propias, ["propio"])
        self.assertEqual(len(registro.output), 1)
        self.assertIn("MENU id=", registro.output[0])
        self.assertIn("etiqueta=Conectar", registro.output[0])

    def test_un_id_que_no_esta_en_la_barra_dice_interrogante(self):
        from ytchat.ui import gui_menu

        frame = wx.Frame(None)
        self.addCleanup(destruir, frame)
        frame.SetMenuBar(wx.MenuBar())
        gui_menu._registrar_menus(frame)
        evento = wx.CommandEvent(wx.EVT_MENU.typeId, 12345)
        with self.assertLogs(gui_menu.logger, level="DEBUG") as registro:
            frame.GetEventHandler().ProcessEvent(evento)

        self.assertIn("etiqueta=?", registro.output[0])


if __name__ == "__main__":
    unittest.main()