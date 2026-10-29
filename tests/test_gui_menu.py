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

from tests.letras_acceso import ingles
from tests.pseudo_prueba import con_pseudo
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
            ("&Ver", "Ir a co&nexión", ANY, "normal"),
            ("&Ver", "Ir a la &lista del panel actual", ANY, "normal"),
            ("&Ver", "Ir a &Chat del directo", ANY, "normal"),
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
            ("&Ver", "Describir escena de &OBS", ANY, "normal"),
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
            ("&Filtro de mensajes", "Avisos", ANY, "radio"),
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
            ("&Transmisión", "Silenciar el &micrófono de OBS", ANY, "check"),
            ("&Transmisión", "&Elegir micrófono…", ANY, "normal"),
            ("&Transmisión", "Mostrar &OBS", ANY, "normal"),
            ("&Transmisión", "&Avisar cuando OBS no da abasto", ANY, "check"),
            ("&Transmisión", "&Grabar también al transmitir", ANY, "check"),
            ("&Música", "&Elegir música…", ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Reproducir o &pausar", ANY, "normal"),
            ("&Música", "&Siguiente canción", ANY, "normal"),
            ("&Música", "Canción &anterior", ANY, "normal"),
            ("&Música", "Subir &volumen", ANY, "normal"),
            ("&Música", "&Bajar volumen", ANY, "normal"),
            ("&Música", "&Qué suena", ANY, "normal"),
            ("&Música", "Adelantar 10 segu&ndos", ANY, "normal"),
            ("&Música", "Re&troceder 10 segundos", ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Silenciar la &música", ANY, "check"),
            ("&Música", "&Detener música", ANY, "normal"),
            ("&Música", "&Orden aleatorio", ANY, "check"),
            ("&Música", "Cambiar &repetición", ANY, "normal"),
            ("&Herramientas", "Gestor de &descargas…", ANY, "normal"),
            ("&Herramientas", "&Actualizar yt-dlp", ANY, "normal"),
            ("&Herramientas", "---", None, "sep"),
            ("&Herramientas", "&Preferencias…", ANY, "normal"),
            ("A&yuda", "&Guía de configuración de la API…", ANY, "normal"),
            ("A&yuda", "&Marcar incidencia", ANY, "normal"),
            ("A&yuda", "Abrir carpeta de &registros", ANY, "normal"),
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
            ("&Música", "Subir &volumen\tCtrl+Alt+Up", ANY, "normal"),
            ("&Música", "&Bajar volumen\tCtrl+Alt+Down", ANY, "normal"),
            ("&Música", "&Qué suena\tCtrl+Alt+T", ANY, "normal"),
            ("&Música", "Adelantar 10 segu&ndos\tCtrl+Alt+Shift+Right",
             ANY, "normal"),
            ("&Música", "Re&troceder 10 segundos\tCtrl+Alt+Shift+Left",
             ANY, "normal"),
            ("&Música", "---", None, "sep"),
            ("&Música", "Silenciar la &música\tCtrl+Alt+M", ANY, "check"),
            ("&Música", "&Detener música\tCtrl+Alt+D", ANY, "normal"),
            ("&Música", "&Orden aleatorio\tCtrl+Alt+A", ANY, "check"),
            ("&Música", "Cambiar &repetición\tCtrl+Alt+R", ANY, "normal"),
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


class TestAbrirTransmision(unittest.TestCase):
    """Al abrir Transmisión se marca la casilla con el estado real."""

    def _frame(self, menu):
        frame = mock.Mock()
        frame._config = {"obs_microfono": "Mic/Aux"}
        frame.mi_obs_micro = mock.Mock()
        frame._consultando_micro = False
        return frame

    def _abrir(self, frame, menu, estado=None):
        from ytchat.ui import gui_menu
        evento = mock.Mock()
        evento.GetMenu.return_value = menu
        hilos = []
        def crear_hilo(funcion, nombre):
            hilo = mock.Mock()
            hilo.start.side_effect = lambda: hilos.append(funcion)
            return hilo
        with mock.patch.object(gui_menu.obs_entradas_audio, "estado_microfono",
                               return_value=estado), \
                mock.patch.object(gui_menu.diagnostico, "crear_hilo",
                                  side_effect=crear_hilo), \
                mock.patch.object(gui_menu.wx, "CallAfter",
                                  side_effect=lambda fn, *a: fn(*a)):
            gui_menu._al_abrir_transmision(frame, menu, evento)
            for funcion in hilos:
                funcion()
        return frame

    def test_otro_menu_no_consulta(self):
        from ytchat.ui import gui_menu
        frame = self._frame(object())
        evento = mock.Mock()
        evento.GetMenu.return_value = object()
        with mock.patch.object(gui_menu.diagnostico, "crear_hilo") as crear:
            gui_menu._al_abrir_transmision(frame, object(), evento)
        crear.assert_not_called()

    def test_con_estado_verdadero_marca_la_casilla(self):
        menu = object()
        frame = self._abrir(self._frame(menu), menu, estado=True)
        frame.mi_obs_micro.Check.assert_called_once_with(True)

    def test_con_estado_falso_la_desmarca(self):
        menu = object()
        frame = self._abrir(self._frame(menu), menu, estado=False)
        frame.mi_obs_micro.Check.assert_called_once_with(False)

    def test_sin_estado_deja_la_marca_como_estaba(self):
        menu = object()
        frame = self._abrir(self._frame(menu), menu, estado=None)
        frame.mi_obs_micro.Check.assert_not_called()

    def test_con_otra_consulta_en_curso_no_lanza_otra(self):
        from ytchat.ui import gui_menu
        menu = object()
        frame = self._frame(menu)
        frame._consultando_micro = True
        evento = mock.Mock()
        evento.GetMenu.return_value = menu
        with mock.patch.object(gui_menu.diagnostico, "crear_hilo") as crear:
            gui_menu._al_abrir_transmision(frame, menu, evento)
        crear.assert_not_called()

    def test_deja_correr_el_evento_en_los_dos_menus(self):
        from ytchat.ui import gui_menu
        menu = object()
        for abierto in (menu, object()):
            with self.subTest(abierto=abierto):
                frame = self._frame(menu)
                evento = mock.Mock()
                evento.GetMenu.return_value = abierto
                with mock.patch.object(gui_menu.diagnostico, "crear_hilo"):
                    gui_menu._al_abrir_transmision(frame, menu, evento)
                evento.Skip.assert_called_once_with()


class TestCableadoMostrarObs(unittest.TestCase):
    """Elegir Mostrar OBS llama a obs_ventana.mostrar y anuncia su texto."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def _frame_con_menu(self):
        from ytchat.ui import gui_menu

        frame = wx.Frame(None)
        self.addCleanup(destruir, frame)
        frame._accel = lambda _accion: ""
        frame._bind_menu = gui.YTChatFrame._bind_menu.__get__(frame)
        frame._config = {"avisar_sobrecarga": True}
        frame._on_transmision = mock.Mock()
        frame._on_obs_micro = mock.Mock()
        frame._alternar_aviso_sobrecarga = mock.Mock()
        barra = wx.MenuBar()
        gui_menu._construir_menu_transmision(frame, barra)
        frame.SetMenuBar(barra)
        return frame

    def test_elegir_mostrar_obs_anuncia_lo_que_devuelve_mostrar(self):
        from ytchat.ui import gui_menu

        frame = self._frame_con_menu()
        with mock.patch.object(gui_menu.obs_ventana, "mostrar",
                               return_value="OBS no está abierto.") as mostrar, \
                mock.patch.object(gui_menu, "anunciar") as anunciar, \
                mock.patch.object(gui_menu.wx, "CallAfter",
                                  side_effect=lambda fn, *a: fn(*a)):
            evento = wx.CommandEvent(
                wx.EVT_MENU.typeId, frame.mi_mostrar_obs.GetId())
            frame.GetEventHandler().ProcessEvent(evento)
        mostrar.assert_called_once_with()
        anunciar.assert_called_once_with("OBS no está abierto.")

    def test_microfono_de_obs_es_casilla(self):
        frame = self._frame_con_menu()
        self.assertTrue(frame.mi_obs_micro.IsCheckable())

    def test_elegir_microfono_sin_atajo_detras_del_silencio(self):
        frame = self._frame_con_menu()
        self.assertEqual(frame.mi_micro_obs.GetItemLabel(),
                         "&Elegir micrófono…")
        barra = frame.GetMenuBar()
        for indice in range(barra.GetMenuCount()):
            menu = barra.GetMenu(indice)
            ids = [item.GetId() for item in menu.GetMenuItems()]
            if frame.mi_obs_micro.GetId() in ids:
                self.assertEqual(
                    ids[ids.index(frame.mi_obs_micro.GetId()) + 1],
                    frame.mi_micro_obs.GetId())

    def test_elegir_microfono_abre_el_cuadro(self):
        from ytchat.ui import gui_menu

        with mock.patch("ytchat.ui.gui_microfono.abrir_microfono_obs") \
                as abrir, \
                mock.patch.object(gui_menu.wx, "CallAfter",
                                  side_effect=lambda fn, *a: fn(*a)):
            frame = self._frame_con_menu()
            evento = wx.CommandEvent(
                wx.EVT_MENU.typeId, frame.mi_micro_obs.GetId())
            frame.GetEventHandler().ProcessEvent(evento)
        abrir.assert_called_once_with(frame)


# Textos que arma otro módulo y la barra solo muestra: los nombres de
# filtro de `ytchat/core/config.py` (FILTROS). Las etiquetas de
# `ytchat/ui/atajos_captura.py` (ETIQUETAS) ya salen marcadas porque el
# menú las traduce con `etiqueta_de_accion`. La comparación es exacta en
# los dos sentidos: falla si aparece un texto nuevo sin envolver y si un
# pendiente ya no está en el recorrido, para vaciar la lista cuando esos
# módulos pasen por gettext.
PENDIENTES_OTROS_MODULOS = (
    "Todos",
    "Solo texto",
    "Super Chats",
    "Membresías",
    "Avisos",
)


class TestPseudoMenu(unittest.TestCase):
    """Pseudotraducción de la barra real: nada propio sin envolver.

    Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
    Construye la misma barra real que vuelca la prueba de convenciones y
    exige que cada etiqueta propia salga marcada.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        from scripts import convenciones_comandos as cc

        with con_pseudo():
            entradas = cc.construir_entradas_reales()
            sin_marcar = sorted(
                entrada.etiqueta for entrada in entradas
                if not entrada.etiqueta.startswith("[¡"))

        self.assertEqual(sin_marcar, sorted(PENDIENTES_OTROS_MODULOS))


class TestLetrasMenuEnIngles(unittest.TestCase):
    """La barra real en inglés: ninguna letra de acceso repetida.

    Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
    En este archivo no hay prueba en español de esa regla sobre el menú
    real, así que no es gemela de ninguna.
    """

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles

    def test_menu_real_en_ingles_sin_letras_repetidas(self):
        from scripts import convenciones_comandos as cc

        entradas = cc.construir_entradas_reales()
        self.assertEqual(cc.faltas_letras_repetidas(entradas), [])


if __name__ == "__main__":
    unittest.main()