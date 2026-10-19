"""Pruebas de la ventana de música con un control falso.

No se corren en el encargo (abren ventanas): quedan escritas para correrlas
después. Toda ventana de primer nivel se libera con
`tests/ventanas_prueba.destruir`.
"""

import unittest
from unittest import mock

from ytchat.music.biblioteca import Biblioteca
from ytchat.music.modelo import EstadoMusica, Tema
from ytchat.ui import gui_musica_ventana
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class Evento:
    """Doble mínimo de un evento de wx."""

    def __init__(self, keycode=0, mods=0):
        self._keycode = keycode
        self._mods = mods
        self.skipped = False

    def GetKeyCode(self):
        return self._keycode

    def GetModifiers(self):
        return self._mods

    def Skip(self):
        self.skipped = True


class ControlFalso:

    def __init__(self, biblioteca=None, carpeta=r"C:\Musica"):
        self._biblio = biblioteca
        self.carpeta = carpeta
        self.llamadas = []
        self.ventanas = []
        self.estado_actual = None
        self.artista = False
        self.combos = {}

    def biblioteca(self, al_lista):
        self.llamadas.append(("biblioteca",))
        al_lista(self._biblio)

    def incluir_artista(self):
        return self.artista

    def combos_atajo(self):
        return self.combos

    def estado(self):
        return self.estado_actual

    def reproducir_temas(self, temas, en_orden=False):
        self.llamadas.append(("reproducir_temas", tuple(temas), en_orden))

    def reproducir_temas_desde(self, temas, indice):
        self.llamadas.append(("reproducir_temas_desde", tuple(temas), indice))

    def agregar_temas(self, temas):
        self.llamadas.append(("agregar_temas", tuple(temas)))

    def reproducir_a_continuacion(self, tema):
        self.llamadas.append(("reproducir_a_continuacion", tema))

    def agregar_enlace(self, url):
        self.llamadas.append(("agregar_enlace", url))

    def reproducir_desde(self, indice):
        self.llamadas.append(("reproducir_desde", indice))

    def cambiar_carpeta(self, ruta):
        self.llamadas.append(("cambiar_carpeta", ruta))
        self.carpeta = ruta

    def ejecutar_atajo(self, accion):
        self.llamadas.append(("ejecutar_atajo", accion))

    def registrar_ventana(self, ventana):
        self.ventanas.append(ventana)

    def olvidar_ventana(self):
        self.ventanas.append(None)

    def _carpeta(self):
        return self.carpeta


class ControlDiferido(ControlFalso):
    """No entrega la biblioteca hasta que la prueba lo pide."""

    def biblioteca(self, al_lista):
        self.llamadas.append(("biblioteca",))
        self.pendiente = al_lista


def _biblioteca_de(*titulos):
    biblio = Biblioteca("C:/Musica")
    biblio._temas = tuple(
        Tema(f"C:/Musica/{titulo.lower()}.mp3", titulo) for titulo in titulos)
    return biblio


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaMusica(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self._parche = mock.patch.object(
            gui_musica_ventana, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            destruir(self.ventana)
        self._parche.stop()

    def _abrir(self, control):
        self.ventana = gui_musica_ventana.VentanaMusica(None, control)
        return self.ventana

    def _panel(self):
        for hijo in self.ventana.GetChildren():
            if isinstance(hijo, wx.Panel):
                return hijo
        return None

    # ── Controles y orden de Tab ────────────────────────────────────────────

    def test_controles_y_nombres_en_orden_de_tab(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        panel = self._panel()
        interactivos = [c for c in panel.GetChildren()
                        if isinstance(c, (wx.TextCtrl, wx.ListBox, wx.Button))]
        self.assertEqual([c.GetName() for c in interactivos], [
            "Buscar en la música", "Temas de la carpeta",
            "Reproducir este", "Reproducir todo", "Agregar a la cola",
            "Reproducir a continuación", "Agregar a una lista",
            "Agregar enlace", "Cola de reproducción",
            "Cambiar carpeta", "Cerrar"])

    def test_titulo_nombre_y_rotulos_con_mnemonicos_sin_repetir(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertEqual(self.ventana.GetTitle(), "Música")
        self.assertEqual(self.ventana.GetName(), "VentanaMusica")
        etiquetas = []
        for control in self._panel().GetChildren():
            if isinstance(control, (wx.StaticText, wx.Button)):
                etiquetas.append(control.GetLabel())
        for esperado in ("&Buscar:", "&Temas:", "C&ola:"):
            self.assertIn(esperado, etiquetas)
        mnemonicos = [e[e.index("&") + 1].lower() for e in etiquetas if "&" in e]
        self.assertEqual(len(mnemonicos), len(set(mnemonicos)))

    def test_el_resumen_tiene_nombre_y_no_se_anuncia_solo(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz")))
        self.assertEqual(self.ventana.lbl_resumen.GetName(),
                         "Resumen de la música")
        # Solo se anunció el resumen de la carga inicial, una vez.
        self.assertEqual(self.anuncios, ["2 temas en la carpeta"])

    # ── Estados ─────────────────────────────────────────────────────────────

    def test_estado_cargando_deshabilita_los_botones(self):
        control = ControlDiferido()
        self._abrir(control)
        self.assertEqual(self.ventana.lb_temas.GetStrings(), [
            gui_musica_ventana.TEXTO_CARGANDO])
        self.assertFalse(self.ventana.btn_reproducir.IsEnabled())
        self.assertFalse(self.ventana.btn_carpeta.IsEnabled())

    def test_estado_sin_carpeta_solo_deja_cambiar_carpeta(self):
        self._abrir(ControlFalso(biblioteca=None))
        self.assertEqual(self.ventana.lb_temas.GetStrings(), [
            gui_musica_ventana.TEXTO_SIN_CARPETA])
        self.assertFalse(self.ventana.btn_reproducir.IsEnabled())
        self.assertFalse(self.ventana.btn_agregar.IsEnabled())
        self.assertTrue(self.ventana.btn_carpeta.IsEnabled())

    def test_al_terminar_la_carga_habilita_los_botones(self):
        control = ControlDiferido()
        self._abrir(control)
        control.pendiente(_biblioteca_de("Rock"))
        self.assertTrue(self.ventana.btn_reproducir.IsEnabled())
        self.assertTrue(self.ventana.btn_todo.IsEnabled())
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Rock"])

    def test_agregar_enlace_habilitado_mientras_carga(self):
        self._abrir(ControlDiferido())
        self.assertTrue(self.ventana.btn_agregar_enlace.IsEnabled())
        self.assertFalse(self.ventana.btn_reproducir.IsEnabled())

    def test_agregar_enlace_habilitado_sin_carpeta(self):
        self._abrir(ControlFalso(biblioteca=None))
        self.assertTrue(self.ventana.btn_agregar_enlace.IsEnabled())
        self.assertFalse(self.ventana.btn_agregar.IsEnabled())
        self.assertTrue(self.ventana.btn_carpeta.IsEnabled())

    def test_cada_boton_conserva_su_ancho_natural(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        panel = self._panel()
        panel.SetSize(self.ventana.GetClientSize())
        panel.Layout()
        for boton in panel.GetChildren():
            if isinstance(boton, wx.Button):
                with self.subTest(boton=boton.GetName()):
                    self.assertEqual(
                        boton.GetSize().width, boton.GetBestSize().width)

    def test_enfocar_primer_control_va_al_buscador(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        with mock.patch.object(self.ventana.txt_buscar, "SetFocus") as foco:
            self.ventana.enfocar_primer_control()
        foco.assert_called_once_with()

    # ── Filtro ──────────────────────────────────────────────────────────────

    def test_filtrar_actualiza_la_lista_y_el_resumen(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz")))
        self.ventana.txt_buscar.SetValue("jaz")
        self.ventana._al_filtrar(Evento())
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Jazz"])
        self.assertEqual(self.ventana.lbl_resumen.GetLabel(), "1 de 2 temas")

    def test_filtrar_sin_resultados_deja_la_lista_vacia(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.ventana.txt_buscar.SetValue("zzz")
        self.ventana._al_filtrar(Evento())
        self.assertEqual(self.ventana.lb_temas.GetStrings(), [])
        self.assertEqual(self.ventana.lbl_resumen.GetLabel(), "0 de 1 tema")

    # ── Acciones ────────────────────────────────────────────────────────────

    def test_enter_en_la_lista_reproduce_desde_el_elegido(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN))
        self.assertIn(
            ("reproducir_temas_desde", control._biblio.temas(), 1),
            control.llamadas)

    def test_reproducir_este_usa_la_lista_filtrada(self):
        envio = None
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.txt_buscar.SetValue("jaz")
        self.ventana._al_filtrar(Evento())
        self.ventana.lb_temas.SetSelection(0)
        self.ventana._reproducir_este()
        for llamada in control.llamadas:
            if llamada[0] == "reproducir_temas_desde":
                envio = llamada
        self.assertIsNotNone(envio)
        self.assertEqual(envio[2], 0)
        self.assertEqual(len(envio[1]), 1)
        self.assertEqual(envio[1][0].titulo, "Jazz")

    def test_reproducir_todo_usa_la_lista_filtrada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana._reproducir_todo()
        self.assertIn(
            ("reproducir_temas", control._biblio.temas(), False),
            control.llamadas)

    def test_agregar_a_la_cola_suma_el_elegido(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._agregar()
        self.assertIn(
            ("agregar_temas", (control._biblio.temas()[1],)),
            control.llamadas)

    def test_a_continuacion_esta_entre_agregar_y_lista(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        panel = self._panel()
        nombres = [c.GetName() for c in panel.GetChildren()
                   if isinstance(c, wx.Button)]
        self.assertEqual(self.ventana.btn_a_continuacion.GetName(),
                         "Reproducir a continuación")
        self.assertEqual(self.ventana.btn_a_continuacion.GetLabel(),
                         "Reproducir a co&ntinuación")
        self.assertEqual(
            nombres[nombres.index("Agregar a la cola") + 1:
                    nombres.index("Agregar a la cola") + 3],
            ["Reproducir a continuación", "Agregar a una lista"])

    def test_a_continuacion_llama_al_control_con_el_elegido(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._a_continuacion()
        self.assertIn(
            ("reproducir_a_continuacion", control._biblio.temas()[1]),
            control.llamadas)

    def test_a_continuacion_sin_seleccion_no_llama(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(wx.NOT_FOUND)
        self.ventana._a_continuacion()
        self.assertNotIn("reproducir_a_continuacion",
                         [llamada[0] for llamada in control.llamadas])

    def _cuadro_enlace(self, valor, resultado=wx.ID_OK):
        cuadro = mock.MagicMock()
        cuadro.__enter__.return_value = cuadro
        cuadro.ShowModal.return_value = resultado
        cuadro.GetValue.return_value = valor
        return cuadro

    def test_agregar_enlace_valido_llama_al_control_sin_anunciar(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        antes = len(self.anuncios)
        cuadro = self._cuadro_enlace("https://youtu.be/abc123")
        with mock.patch.object(gui_musica_ventana.wx, "TextEntryDialog",
                               return_value=cuadro), \
                mock.patch.object(gui_musica_ventana, "_snd"):
            self.ventana._agregar_enlace()
        self.assertIn(("agregar_enlace", "https://youtu.be/abc123"),
                      control.llamadas)
        self.assertEqual(self.anuncios[antes:], [])

    def test_agregar_enlace_que_no_es_youtube_lo_delega_al_control(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        antes = len(self.anuncios)
        cuadro = self._cuadro_enlace("https://vimeo.com/12345")
        with mock.patch.object(gui_musica_ventana.wx, "TextEntryDialog",
                               return_value=cuadro), \
                mock.patch.object(gui_musica_ventana, "_snd"):
            self.ventana._agregar_enlace()
        self.assertIn(("agregar_enlace", "https://vimeo.com/12345"),
                      control.llamadas)
        self.assertEqual(self.anuncios[antes:], [])

    def test_agregar_enlace_vacio_no_hace_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        cuadro = self._cuadro_enlace("   ")
        with mock.patch.object(gui_musica_ventana.wx, "TextEntryDialog",
                               return_value=cuadro), \
                mock.patch.object(gui_musica_ventana, "_snd"):
            self.ventana._agregar_enlace()
        self.assertNotIn("agregar_enlace",
                         [llamada[0] for llamada in control.llamadas])

    def test_agregar_enlace_cancelado_no_hace_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        cuadro = self._cuadro_enlace("https://youtu.be/abc123", wx.ID_CANCEL)
        with mock.patch.object(gui_musica_ventana.wx, "TextEntryDialog",
                               return_value=cuadro), \
                mock.patch.object(gui_musica_ventana, "_snd"):
            self.ventana._agregar_enlace()
        self.assertNotIn("agregar_enlace",
                         [llamada[0] for llamada in control.llamadas])
        self.assertNotIn("Leyendo el enlace", self.anuncios)

    def test_enter_en_la_cola_reproduce_desde_esa_fila(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = EstadoMusica(
            (Tema("C:/Musica/rock.mp3", "Rock"),), 0, False, False, 50, False)
        self.ventana.refrescar_cola()
        self.assertEqual(self.ventana.lb_cola.GetStrings(),
                         ["Sonando: 1. Rock"])
        self.ventana.lb_cola.SetSelection(0)
        self.ventana._tecla_cola(Evento(wx.WXK_RETURN))
        self.assertIn(("reproducir_desde", 0), control.llamadas)

    def test_refrescar_cola_sin_motor_queda_vacia(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.ventana.refrescar_cola()
        self.assertEqual(self.ventana.lb_cola.GetStrings(), [])

    # ── Cambiar carpeta ─────────────────────────────────────────────────────

    def test_cambiar_carpeta_guarda_y_recarga(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control._biblio = _biblioteca_de("Nuevo")
        cuadro = mock.MagicMock()
        cuadro.__enter__.return_value = cuadro
        cuadro.ShowModal.return_value = wx.ID_OK
        cuadro.GetPath.return_value = r"C:\Otra"
        with mock.patch.object(gui_musica_ventana.wx, "DirDialog",
                               return_value=cuadro):
            self.ventana._cambiar_carpeta()
        self.assertIn(("cambiar_carpeta", r"C:\Otra"), control.llamadas)
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Nuevo"])

    def test_cambiar_carpeta_cancelado_no_hace_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        cuadro = mock.MagicMock()
        cuadro.__enter__.return_value = cuadro
        cuadro.ShowModal.return_value = wx.ID_CANCEL
        with mock.patch.object(gui_musica_ventana.wx, "DirDialog",
                               return_value=cuadro):
            self.ventana._cambiar_carpeta()
        self.assertNotIn("cambiar_carpeta",
                         [llamada[0] for llamada in control.llamadas])

    # ── Atajos dentro de la ventana ─────────────────────────────────────────

    def test_atajo_de_musica_llama_al_control(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        control.combos = {(wx.MOD_CONTROL | wx.MOD_ALT, ord("T")):
                          "musica_que_suena"}
        self._abrir(control)
        evento = Evento(ord("T"), wx.MOD_CONTROL | wx.MOD_ALT)
        self.ventana._tecla_atajo(evento)
        self.assertIn(("ejecutar_atajo", "musica_que_suena"), control.llamadas)
        self.assertFalse(evento.skipped)

    def test_tecla_que_no_es_atajo_se_deja_pasar(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        for keycode in (wx.WXK_TAB, wx.WXK_RETURN, wx.WXK_ESCAPE):
            evento = Evento(keycode)
            self.ventana._tecla_atajo(evento)
            self.assertTrue(evento.skipped)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestBotonesLlamanALoEsperado(unittest.TestCase):
    """Cada botón de acción dispara su llamada y ningún otro.

    Las pruebas de arriba llaman a los métodos directamente: un botón
    conectado al método equivocado pasaría igual. Acá va por el cableado
    de verdad, con un `wx.CommandEvent` de `wx.EVT_BUTTON` por el
    `GetEventHandler` del botón.
    """

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self._parche = mock.patch.object(
            gui_musica_ventana, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            destruir(self.ventana)
        self._parche.stop()

    def _abrir(self, control):
        self.ventana = gui_musica_ventana.VentanaMusica(None, control)
        return self.ventana

    def _pulsar(self, boton):
        boton.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, boton.GetId()))

    def test_botones_de_accion(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        temas = control._biblio.temas()
        self.ventana.lb_temas.SetSelection(1)
        with mock.patch.object(self.ventana, "_agregar_a_lista") as a_lista, \
                mock.patch.object(self.ventana, "_agregar_enlace") as enlace, \
                mock.patch.object(self.ventana,
                                  "_cambiar_carpeta") as carpeta:
            casos = [
                ("directo", self.ventana.btn_reproducir,
                 ("reproducir_temas_desde", tuple(temas), 1)),
                ("directo", self.ventana.btn_todo,
                 ("reproducir_temas", tuple(temas), False)),
                ("directo", self.ventana.btn_agregar,
                 ("agregar_temas", (temas[1],))),
                ("directo", self.ventana.btn_a_continuacion,
                 ("reproducir_a_continuacion", temas[1])),
                ("cuadro", self.ventana.btn_agregar_lista, None),
                ("cuadro", self.ventana.btn_agregar_enlace, None),
                ("cuadro", self.ventana.btn_carpeta, None),
            ]
            for modo, boton, esperado in casos:
                with self.subTest(boton=boton.GetName()):
                    control.llamadas.clear()
                    self.ventana.lb_temas.SetSelection(1)
                    self._pulsar(boton)
                    if modo == "directo":
                        self.assertIn(esperado, control.llamadas)
                    self.assertEqual(
                        sum(1 for llamada in control.llamadas
                            if llamada and llamada[0] in (
                                "reproducir_temas_desde", "reproducir_temas",
                                "agregar_temas", "reproducir_a_continuacion")),
                        1 if modo == "directo" else 0)
        a_lista.assert_called_once_with()
        enlace.assert_called_once_with()
        carpeta.assert_called_once_with()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestActualizarNombres(unittest.TestCase):
    """`actualizar_nombres`: cambia el texto sin mover selección ni foco."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self._parche = mock.patch.object(
            gui_musica_ventana, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            destruir(self.ventana)
        self._parche.stop()

    def _abrir(self, control):
        self.ventana = gui_musica_ventana.VentanaMusica(None, control)
        return self.ventana

    def test_cambia_el_texto_sin_mover_la_seleccion(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        mapa = {"C:/Musica/jazz.mp3": Tema(
            "C:/Musica/jazz.mp3", "Jazz Nuevo", artista="Ana")}
        # Sin parchear SetSelection: SetString la usa por dentro para
        # restaurar la selección y el parche la dejaría en -1.
        with mock.patch.object(
                self.ventana.lb_temas, "Set",
                side_effect=AssertionError("usa Set")):
            self.ventana.actualizar_nombres(mapa)
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Jazz Nuevo"])
        self.assertEqual(self.ventana.lb_temas.GetSelection(), 1)
        self.assertEqual(self.ventana._temas_filtrados[1].titulo, "Jazz Nuevo")
        self.assertEqual(self.ventana.lbl_resumen.GetLabel(),
                         "2 temas en la carpeta")

    def test_actualiza_la_cola_fila_por_fila(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        control.estado_actual = EstadoMusica(
            (Tema("C:/Musica/rock.mp3", "Rock"),
             Tema("C:/Musica/jazz.mp3", "Jazz")),
            0, False, False, 50, False)
        self.ventana.refrescar_cola()
        self.assertEqual(self.ventana.lb_cola.GetStrings(),
                         ["Sonando: 1. Rock", "2. Jazz"])
        self.ventana.lb_cola.SetSelection(1)
        control.estado_actual = EstadoMusica(
            (Tema("C:/Musica/rock.mp3", "Rock"),
             Tema("C:/Musica/jazz.mp3", "Jazz Nuevo")),
            0, False, False, 50, False)
        self.ventana.actualizar_nombres(
            {"C:/Musica/jazz.mp3": Tema("C:/Musica/jazz.mp3", "Jazz Nuevo")})
        self.assertEqual(self.ventana.lb_cola.GetStrings(),
                         ["Sonando: 1. Rock", "2. Jazz Nuevo"])
        self.assertEqual(self.ventana.lb_cola.GetSelection(), 1)

    def test_si_la_cola_cambio_de_cantidad_refresca_entera(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = EstadoMusica(
            (Tema("C:/Musica/rock.mp3", "Rock"),),
            0, False, False, 50, False)
        self.ventana.refrescar_cola()
        control.estado_actual = EstadoMusica(
            (Tema("C:/Musica/rock.mp3", "Rock Nuevo"),
             Tema("C:/Musica/jazz.mp3", "Jazz")),
            0, False, False, 50, False)
        self.ventana.actualizar_nombres(
            {"C:/Musica/rock.mp3": Tema("C:/Musica/rock.mp3", "Rock Nuevo")})
        self.assertEqual(self.ventana.lb_cola.GetStrings(),
                         ["Sonando: 1. Rock Nuevo", "2. Jazz"])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestAbrirVentana(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def test_abre_modal_y_destruye_al_cerrar(self):
        control = ControlFalso()
        ventana = mock.Mock()
        with mock.patch.object(gui_musica_ventana, "VentanaMusica",
                               return_value=ventana) as clase:
            gui_musica_ventana.abrir_ventana(control)
        clase.assert_called_once_with(None, control)
        ventana.ShowModal.assert_called_once_with()
        ventana.Destroy.assert_called_once_with()
        self.assertEqual(control.ventanas, [ventana, None])


if __name__ == "__main__":
    unittest.main()
