"""Pruebas de la ventana de listas de música con un control falso.

No se corren en el encargo (abren ventanas): quedan escritas para correrlas
después. Las listas se arman dentro de un `tempfile.TemporaryDirectory`, que
se limpia solo. Toda ventana de primer nivel se libera con
`tests/ventanas_prueba.destruir`.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.music import listas
from ytchat.music.modelo import Tema
from ytchat.ui import gui_musica_listas
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class Evento:
    """Doble mínimo de un evento de teclado de wx."""

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

    def __init__(self, carpeta=None):
        self.carpeta = carpeta
        self.cola = ()
        self.artista = False
        self.combos = {}
        self.llamadas = []
        self.ventanas = []

    def carpeta_listas(self):
        return self.carpeta

    def registrar_ventana(self, ventana, tipo="musica"):
        self.ventanas.append(("registrar", tipo, ventana))

    def olvidar_ventana(self, tipo="musica"):
        self.ventanas.append(("olvidar", tipo))

    def incluir_artista(self):
        return self.artista

    def combos_atajo(self):
        return self.combos

    def reproducir_lista_guardada(self, nombre):
        self.llamadas.append(("reproducir_lista_guardada", nombre))

    def cola_actual(self):
        return self.cola

    def ejecutar_atajo(self, accion):
        self.llamadas.append(("ejecutar_atajo", accion))


def _dialogo(valor="", resultado=None):
    """Doble de diálogo que sirve como `with` y devuelve `valor`."""
    if resultado is None:
        resultado = wx.ID_OK
    dialogo = mock.MagicMock()
    dialogo.__enter__.return_value = dialogo
    dialogo.ShowModal.return_value = resultado
    dialogo.GetValue.return_value = valor
    dialogo.GetStringSelection.return_value = valor
    return dialogo


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaListas(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name) / "listas"
        self.anuncios = []
        self.sonidos = []
        self._parche_anunciar = mock.patch.object(
            gui_musica_listas, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche_anunciar.start()
        self._parche_snd = mock.patch.object(
            gui_musica_listas._snd, "reproducir",
            lambda evento: self.sonidos.append(evento))
        self._parche_snd.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            destruir(self.ventana)
        self._parche_snd.stop()
        self._parche_anunciar.stop()
        self.tmp.cleanup()

    def _abrir(self, control=None):
        control = control or ControlFalso(self.carpeta)
        self.ventana = gui_musica_listas.VentanaListas(None, control)
        return self.ventana

    def _panel(self):
        for hijo in self.ventana.GetChildren():
            if isinstance(hijo, wx.Panel):
                return hijo
        return None

    def _sembrar(self, nombre, titulos):
        """Crea una lista con temas reales y la selecciona."""
        archivos = []
        for i, titulo in enumerate(titulos):
            ruta = Path(self.tmp.name) / f"{nombre}{i}.mp3"
            ruta.write_bytes(b"x")
            archivos.append(Tema(str(ruta.resolve()), titulo))
        listas.guardar(self.carpeta, nombre, tuple(archivos))
        return archivos

    # ── Controles y orden de Tab ────────────────────────────────────────────

    def test_controles_y_nombres_en_orden_de_tab(self):
        self._abrir()
        panel = self._panel()
        interactivos = [c for c in panel.GetChildren()
                        if isinstance(c, (wx.ListBox, wx.Button))]
        self.assertEqual([c.GetName() for c in interactivos], [
            "Listas guardadas", "Reproducir la lista", "Nueva lista",
            "Renombrar", "Borrar", "Temas de la lista",
            "Guardar la cola como lista", "Cerrar"])

    def test_titulo_nombre_y_rotulos_con_mnemonicos_sin_repetir(self):
        self._abrir()
        self.assertEqual(self.ventana.GetTitle(), "Listas de música")
        self.assertEqual(self.ventana.GetName(), "VentanaListas")
        etiquetas = []
        for control in self._panel().GetChildren():
            if isinstance(control, (wx.StaticText, wx.Button)):
                etiquetas.append(control.GetLabel())
        for esperado in ("&Listas:", "&Temas de la lista:"):
            self.assertIn(esperado, etiquetas)
        mnemonicos = [e[e.index("&") + 1].lower() for e in etiquetas if "&" in e]
        self.assertEqual(len(mnemonicos), len(set(mnemonicos)))

    def test_sin_listas_muestra_el_placeholder(self):
        self._abrir()
        self.assertEqual(self.ventana.lb_listas.GetStrings(),
                         [gui_musica_listas.TEXTO_SIN_LISTAS])
        self.assertFalse(self.ventana.btn_reproducir.IsEnabled())

    def test_cada_boton_conserva_su_ancho_natural(self):
        self._abrir()
        panel = self._panel()
        panel.Layout()
        for boton in panel.GetChildren():
            if isinstance(boton, wx.Button):
                with self.subTest(boton=boton.GetName()):
                    self.assertGreaterEqual(
                        boton.GetSize().width, boton.GetBestSize().width)

    def test_enfocar_primer_control_va_a_las_listas(self):
        self._abrir()
        with mock.patch.object(self.ventana.lb_listas, "SetFocus") as foco:
            self.ventana.enfocar_primer_control()
        foco.assert_called_once_with()

    def test_con_listas_habilita_los_botones_y_carga_los_temas(self):
        self._sembrar("Rock", ["A", "B"])
        self._abrir()
        self.assertEqual(self.ventana.lb_listas.GetStrings(), ["Rock"])
        self.assertTrue(self.ventana.btn_reproducir.IsEnabled())
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["A", "B"])

    def test_enter_en_la_lista_reproduce(self):
        self._sembrar("Rock", ["A"])
        control = ControlFalso(self.carpeta)
        self._abrir(control)
        self.ventana._tecla_listas(Evento(wx.WXK_RETURN))
        self.assertIn(("reproducir_lista_guardada", "Rock"), control.llamadas)

    # ── Crear, renombrar y borrar ───────────────────────────────────────────

    def test_crear_con_el_dialogo_de_texto(self):
        self._abrir()
        with mock.patch.object(gui_musica_listas.wx, "TextEntryDialog",
                               return_value=_dialogo("Nueva")):
            self.ventana._nueva()
        self.assertEqual(self.ventana.lb_listas.GetStrings(), ["Nueva"])
        self.assertIn("Lista creada: Nueva", self.anuncios)

    def test_renombrar_con_el_dialogo_de_texto(self):
        self._sembrar("Vieja", ["A"])
        self._abrir()
        with mock.patch.object(gui_musica_listas.wx, "TextEntryDialog",
                               return_value=_dialogo("Nueva")):
            self.ventana._renombrar()
        self.assertEqual(self.ventana.lb_listas.GetStrings(), ["Nueva"])
        self.assertIn("Lista renombrada: Nueva", self.anuncios)

    def test_borrar_confirma_y_borra(self):
        self._sembrar("Rock", ["A"])
        self._abrir()
        with mock.patch.object(gui_musica_listas.wx, "MessageBox",
                               return_value=wx.YES):
            self.ventana._borrar()
        self.assertEqual(self.ventana.lb_listas.GetStrings(),
                         [gui_musica_listas.TEXTO_SIN_LISTAS])
        self.assertIn("Lista borrada: Rock", self.anuncios)

    def test_borrar_cancelado_no_borra(self):
        self._sembrar("Rock", ["A"])
        self._abrir()
        with mock.patch.object(gui_musica_listas.wx, "MessageBox",
                               return_value=wx.NO):
            self.ventana._borrar()
        self.assertEqual(self.ventana.lb_listas.GetStrings(), ["Rock"])

    def test_error_se_anuncia_con_su_sonido(self):
        self._sembrar("Rock", ["A"])
        self._abrir()
        with mock.patch.object(gui_musica_listas.wx, "TextEntryDialog",
                               return_value=_dialogo("rock")):
            self.ventana._nueva()
        self.assertEqual(self.sonidos, ["error"])
        self.assertIn("Ya hay una lista con ese nombre", self.anuncios)

    # ── Temas: mover y quitar ───────────────────────────────────────────────

    def test_alt_flecha_abajo_mueve_y_anuncia(self):
        self._sembrar("Rock", ["A", "B", "C"])
        self._abrir()
        self.ventana.lb_temas.SetSelection(0)
        self.ventana._tecla_temas(
            Evento(wx.WXK_DOWN, wx.MOD_ALT))
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["B", "A", "C"])
        self.assertIn("Tema movido a la posición 2 de 3", self.anuncios)

    def test_supr_quita_el_tema_e_anuncia(self):
        self._sembrar("Rock", ["A", "B"])
        self._abrir()
        self.ventana.lb_temas.SetSelection(0)
        self.ventana._tecla_temas(Evento(wx.WXK_DELETE))
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["B"])
        self.assertIn("Tema quitado de la lista", self.anuncios)

    # ── Guardar la cola ─────────────────────────────────────────────────────

    def test_guardar_la_cola_como_lista(self):
        control = ControlFalso(self.carpeta)
        control.cola = (Tema("C:/m/a.mp3", "A"),)
        self._abrir(control)
        with mock.patch.object(gui_musica_listas.wx, "TextEntryDialog",
                               return_value=_dialogo("Guardada")):
            self.ventana._guardar_cola()
        self.assertEqual(self.ventana.lb_listas.GetStrings(), ["Guardada"])
        self.assertIn("Lista guardada: Guardada", self.anuncios)

    def test_guardar_la_cola_sin_cola_avisa(self):
        control = ControlFalso(self.carpeta)
        control.cola = ()
        self._abrir(control)
        self.ventana._guardar_cola()
        self.assertIn("No hay temas en la cola", self.anuncios)

    # ── Atajos dentro de la ventana ─────────────────────────────────────────

    def test_atajo_de_musica_llama_al_control(self):
        control = ControlFalso(self.carpeta)
        control.combos = {(wx.MOD_CONTROL | wx.MOD_ALT, ord("T")):
                          "musica_que_suena"}
        self._abrir(control)
        evento = Evento(ord("T"), wx.MOD_CONTROL | wx.MOD_ALT)
        self.ventana._tecla_atajo(evento)
        self.assertIn(("ejecutar_atajo", "musica_que_suena"), control.llamadas)
        self.assertFalse(evento.skipped)

    def test_tecla_que_no_es_atajo_se_deja_pasar(self):
        control = ControlFalso(self.carpeta)
        self._abrir(control)
        for keycode in (wx.WXK_TAB, wx.WXK_RETURN, wx.WXK_ESCAPE):
            evento = Evento(keycode)
            self.ventana._tecla_atajo(evento)
            self.assertTrue(evento.skipped)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestAbrirListas(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def test_abre_modal_y_destruye_al_cerrar(self):
        control = ControlFalso()
        ventana = mock.Mock()
        with mock.patch.object(gui_musica_listas, "VentanaListas",
                               return_value=ventana) as clase:
            gui_musica_listas.abrir_ventana(control)
        clase.assert_called_once_with(None, control)
        ventana.ShowModal.assert_called_once_with()
        ventana.Destroy.assert_called_once_with()
        self.assertEqual([v[0] for v in control.ventanas],
                         ["registrar", "olvidar"])
        self.assertIs(control.ventanas[0][2], ventana)
        self.assertEqual([v[1] for v in control.ventanas], ["listas", "listas"])


if __name__ == "__main__":
    unittest.main()
