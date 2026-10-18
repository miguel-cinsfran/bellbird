"""Prueba de equivalencia de la barra de menú.

Construye el menú con el mismo doble de frame que usan las pruebas de
`test_gui.py` (mocks de `wx.Menu` y `wx.MenuBar`, sin ventanas) y comprueba
la lista completa de (menú, etiqueta, id, tipo) en orden, con los submenús
atribuidos a su título. La lista se fijó contra el código anterior a mover
`_build_menubar` a `gui_menu.construir_menu`: entra por
`YTChatFrame._build_menubar`, que ahora delega, así que pasa igual antes y
después sin tocarla.
"""

import unittest
from unittest import mock

from ytchat.ui import gui


def _construir_lista():
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
             "&Transmisión", "&Herramientas", "A&yuda"], titulos)

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
            ("&Ver", "Describir la escena de &OBS", ANY, "normal"),
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
            ("&Herramientas", "Gestor de &descargas…", ANY, "normal"),
            ("&Herramientas", "&Actualizar yt-dlp", ANY, "normal"),
            ("&Herramientas", "---", None, "sep"),
            ("&Herramientas", "&Preferencias…", ANY, "normal"),
            ("A&yuda", "&Guía de configuración de la API…", ANY, "normal"),
            ("A&yuda", "&Marcar incidencia", ANY, "normal"),
            ("A&yuda", "&Buscar actualizaciones…", ANY, "normal"),
            ("A&yuda", "&Acerca de", gui.wx.ID_ABOUT, "normal"),
        ], lista)


if __name__ == "__main__":
    unittest.main()
