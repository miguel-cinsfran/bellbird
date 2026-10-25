"""Pruebas de la ventana única de música y del cuadro de enlace.

No se corren en el encargo (abren ventanas): quedan escritas para correrlas
después. Toda ventana de primer nivel se libera con
`tests/ventanas_prueba.destruir`.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.music import anuncios, filtros, listas
from ytchat.music import pregunta_igualar
from ytchat.music import sonoridad
from ytchat.music.biblioteca import Biblioteca
from ytchat.music.modelo import EstadoMusica, Tema
from ytchat.music.sonoridad import ResultadoIgualacion
from ytchat.ui import (musica_dialogo_enlace, musica_editor_lista,
                       musica_menus, musica_ventana,
                       musica_ventana_acciones,
                       musica_ventana_igualando)
from ytchat.ui.gui import ALTO_CONTRASTE, _T
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

    def __init__(self, biblioteca=None, carpeta_listas=None,
                 temas_listas=None, estado=None, cola_visible=False,
                 midiendo=False, datos_pregunta=None,
                 resultado_igualacion=None, pendientes_calculadas=(),
                 total_calculado=0, responder_pedidos=True,
                 filtros_guardados=(False, "", "coleccion")):
        self._biblio = biblioteca
        self._carpeta_listas = carpeta_listas
        self._temas_listas = dict(temas_listas or {})
        self.estado_actual = estado
        self.cola = ()
        self.llamadas = []
        self.artista = False
        self.combos = {}
        self._cola_visible = bool(cola_visible)
        self._filtros_guardados = tuple(filtros_guardados)
        self._progreso_sonoridad = None
        self._midiendo = bool(midiendo)
        self.datos_pregunta = datos_pregunta
        self.resultado_igualacion = resultado_igualacion
        self.pendientes_calculadas = pendientes_calculadas
        self.total_calculado = total_calculado
        self.responder_pedidos = responder_pedidos
        self.preguntar = True
        self.datos_examen = None

    def biblioteca(self, al_lista):
        self.llamadas.append(("biblioteca",))
        al_lista(self._biblio)

    def carpeta_listas(self):
        return self._carpeta_listas

    def temas_de_lista(self, nombre):
        self.llamadas.append(("temas_de_lista", nombre))
        return self._temas_listas.get(nombre, ())

    def incluir_artista(self):
        return self.artista

    def combos_atajo(self):
        return self.combos

    def estado(self):
        return self.estado_actual

    def cola_actual(self):
        return self.cola

    def reproducir_ahora(self, temas):
        self.llamadas.append(("reproducir_ahora", tuple(temas)))

    def poner_a_continuacion(self, temas):
        self.llamadas.append(("poner_a_continuacion", tuple(temas)))

    def agregar_al_final(self, temas):
        self.llamadas.append(("agregar_al_final", tuple(temas)))

    def reproducir_desde_aqui(self, temas, indice):
        self.llamadas.append(("reproducir_desde_aqui", tuple(temas), indice))

    def reproducir_lista_guardada(self, nombre):
        self.llamadas.append(("reproducir_lista_guardada", nombre))

    def cola_visible(self):
        return self._cola_visible

    def recordar_cola_visible(self, visible):
        self.llamadas.append(("recordar_cola_visible", bool(visible)))
        self._cola_visible = bool(visible)

    def filtros_guardados(self):
        return self._filtros_guardados

    def recordar_filtros(self, visibles, artista, orden):
        self.llamadas.append(("recordar_filtros", bool(visibles), artista,
                              orden))
        self._filtros_guardados = (bool(visibles), artista, orden)

    def reproducir_desde(self, indice):
        self.llamadas.append(("reproducir_desde", indice))

    def quitar_de_cola(self, indice):
        self.llamadas.append(("quitar_de_cola", indice))

    def mover_en_cola(self, indice, paso):
        self.llamadas.append(("mover_en_cola", indice, paso))

    def vaciar_cola(self):
        self.llamadas.append(("vaciar_cola",))

    def mezclar_cola(self):
        self.llamadas.append(("mezclar_cola",))

    def abrir_enlace(self, url, modo):
        self.llamadas.append(("abrir_enlace", url, modo))

    def guardar_cola_como_lista(self, nombre):
        self.llamadas.append(("guardar_cola_como_lista", nombre))

    def agregar_a_lista(self, nombre, temas):
        self.llamadas.append(("agregar_a_lista", nombre, tuple(temas)))

    def guardar_lista(self, nombre, temas, viejo=None):
        self.llamadas.append(("guardar_lista", nombre, tuple(temas), viejo))

    def quitar_de_lista(self, nombre, indice):
        self.llamadas.append(("quitar_de_lista", nombre, indice))

    def crear_lista(self, nombre):
        self.llamadas.append(("crear_lista", nombre))

    def renombrar_lista(self, viejo, nuevo):
        self.llamadas.append(("renombrar_lista", viejo, nuevo))

    def borrar_lista(self, nombre):
        self.llamadas.append(("borrar_lista", nombre))

    def ejecutar_atajo(self, accion):
        self.llamadas.append(("ejecutar_atajo", accion))

    def _carpeta(self):
        return "C:/Musica"

    def biblioteca_actual(self):
        return self._biblio

    def reexaminar_carpeta(self, al_volver):
        self.llamadas.append(("reexaminar_carpeta",))
        if self.datos_examen is None:
            al_volver(None, 0, 0)
        else:
            nuevas, quitadas = self.datos_examen
            al_volver(self._biblio, nuevas, quitadas)

    def iniciar_igualacion(self, biblioteca):
        self.llamadas.append(("iniciar_igualacion", biblioteca))
        return self.resultado_igualacion

    def iniciar_medicion(self, pendientes):
        self.llamadas.append(("iniciar_medicion", tuple(pendientes)))
        return self.resultado_igualacion

    def pedir_pendientes(self, biblioteca, al_pendientes):
        self.llamadas.append(("pedir_pendientes", biblioteca))
        if self.responder_pedidos:
            al_pendientes(self.pendientes_calculadas, self.total_calculado)

    def confirmar_pregunta(self, pendientes, total):
        return self.datos_pregunta

    def detener_igualacion(self):
        self.llamadas.append(("detener_igualacion",))

    def midiendo_igualacion(self):
        return self._midiendo

    def datos_igualacion(self, biblioteca):
        return self.datos_pregunta

    def fijar_preguntar_igualar(self, valor):
        self.llamadas.append(("fijar_preguntar_igualar", valor))
        self.preguntar = valor

    def nombres(self):
        return [llamada[0] for llamada in self.llamadas]


def _biblioteca_de(*titulos, **campos):
    biblio = Biblioteca("C:/Musica")
    biblio._temas = tuple(
        Tema(f"C:/Musica/{titulo.lower()}.mp3", titulo, **campos)
        for titulo in titulos)
    return biblio


def _biblioteca_con(temas):
    biblio = Biblioteca("C:/Musica")
    biblio._temas = tuple(temas)
    return biblio


def _estado(*titulos, posicion=0):
    return EstadoMusica(
        tuple(Tema(f"C:/Musica/{t.lower()}.mp3", t) for t in titulos),
        posicion, False, False, 50, False)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaMusica(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta_listas = str(Path(self.tmp.name) / "listas")
        self.anuncios = []
        self._parche = mock.patch.object(
            musica_ventana, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            self.ventana._cancelar_temporizador()
            destruir(self.ventana)
        self._parche.stop()
        self.tmp.cleanup()

    def _abrir(self, control, abrir_listas=False):
        self.ventana = musica_ventana.VentanaMusica(
            None, control, abrir_listas=abrir_listas)
        return self.ventana

    def _panel(self):
        for hijo in self.ventana.GetChildren():
            if isinstance(hijo, wx.Panel):
                return hijo
        return None

    def _crear_lista(self, nombre, temas=()):
        listas.guardar(self.carpeta_listas, nombre, temas)

    # ── Controles, nombres y orden de Tab ──────────────────────────────────

    def test_controles_y_nombres_en_orden_de_tab(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertFalse(self.ventana.lb_cola.IsShown())
        interactivos = [
            control for control in self._panel().GetChildren()
            if isinstance(control, (wx.TextCtrl, wx.Choice, wx.ListBox,
                                    wx.Button))]
        self.assertEqual([control.GetName() for control in interactivos], [
            "Colecciones", "Buscar en la música", "Mostrar los filtros",
            "Mostrar", "Ordenar por", "Canciones",
            "Mostrar la cola", "Cola de reproducción",
            "Igualación del volumen", "Abrir enlace",
            "Nueva lista", "Cambiar carpeta", "Igualar el volumen",
            "Examinar la carpeta", "Cerrar"])

    def test_instala_busqueda_por_tecleo_en_las_tres_listas(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        with mock.patch.object(
                musica_ventana, "instalar_busqueda_tipo") as instalar:
            self._abrir(control)

        llamadas = {llamada.args[0]: llamada.args[1]
                    for llamada in instalar.call_args_list}
        self.assertEqual(
            set(llamadas),
            {self.ventana.lb_colecciones, self.ventana.lb_temas,
             self.ventana.lb_cola})
        for lista, obtener_textos in llamadas.items():
            with self.subTest(lista=lista.GetName()):
                self.assertEqual(obtener_textos(),
                                 list(lista.GetStrings()))

    def test_controles_y_nombres_con_la_cola_visible(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock"),
                                 cola_visible=True))
        self.assertTrue(self.ventana.lb_cola.IsShown())
        interactivos = [
            control for control in self._panel().GetChildren()
            if isinstance(control, (wx.TextCtrl, wx.ListBox, wx.Button))]
        self.assertEqual([control.GetName() for control in interactivos], [
            "Colecciones", "Buscar en la música", "Mostrar los filtros",
            "Canciones", "Ocultar la cola", "Cola de reproducción",
            "Igualación del volumen", "Abrir enlace",
            "Nueva lista", "Cambiar carpeta", "Igualar el volumen",
            "Examinar la carpeta", "Cerrar"])

    def test_mnemonicos_unicos_en_la_ventana(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        etiquetas = [
            control.GetLabel() for control in self._panel().GetChildren()
            if isinstance(control, (wx.StaticText, wx.Button))]
        mnemonicos = [etiqueta[etiqueta.index("&") + 1].lower()
                      for etiqueta in etiquetas if "&" in etiqueta]
        self.assertEqual(len(mnemonicos), len(set(mnemonicos)))

    def test_rotulos_de_la_ventana(self):
        self._abrir(ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            filtros_guardados=(True, "", "coleccion")))
        etiquetas = [
            control.GetLabel() for control in self._panel().GetChildren()
            if isinstance(control, wx.StaticText)]
        for esperado in ("Co&lecciones:", "&Buscar:", "C&anciones:",
                         "&Mostrar:", "Or&denar por:"):
            self.assertIn(esperado, etiquetas)
        self.assertNotIn("C&ola:", etiquetas)

    def test_colecciones_con_el_color_de_los_campos(self):
        if ALTO_CONTRASTE:
            self.skipTest("con alto contraste no se pinta nada")
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertEqual(self.ventana.lb_colecciones.GetBackgroundColour(),
                         _T.field)
        self.assertEqual(self.ventana.lb_colecciones.GetForegroundColour(),
                         _T.text)

    def test_igualando_sin_flechas_de_desplazamiento(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertTrue(self.ventana.txt_igualando.GetWindowStyle()
                        & wx.TE_NO_VSCROLL)

    # ── Teclas de la Biblioteca ────────────────────────────────────────────

    def test_intro_reproduce_ahora_el_elegido(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN))
        tema = control._biblio.temas()[1]
        self.assertIn(("reproducir_ahora", (tema,)), control.llamadas)

    def test_mayus_mas_intro_pone_a_continuacion(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN, wx.MOD_SHIFT))
        tema = control._biblio.temas()[1]
        self.assertIn(("poner_a_continuacion", (tema,)), control.llamadas)

    def test_control_mas_intro_agrega_al_final(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN, wx.MOD_CONTROL))
        tema = control._biblio.temas()[1]
        self.assertIn(("agregar_al_final", (tema,)), control.llamadas)

    def test_sin_seleccion_intro_no_llama_a_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(wx.NOT_FOUND)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN))
        self.assertNotIn("reproducir_ahora", control.nombres())

    def test_suprimir_con_la_carpeta_no_hace_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(0)
        self.ventana._tecla_temas(Evento(wx.WXK_DELETE))
        self.assertNotIn("quitar_de_lista", control.nombres())

    def test_suprimir_en_una_lista_propia_quita_ese_indice(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),
                 Tema("C:/Musica/jazz.mp3", "Jazz"))
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        self.ventana.lb_temas.SetSelection(1)
        self.ventana._tecla_temas(Evento(wx.WXK_DELETE))
        self.assertIn(("quitar_de_lista", "Mía", 1), control.llamadas)

    def test_tecla_de_aplicaciones_abre_el_menu_de_la_biblioteca(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(0)
        with mock.patch.object(self.ventana, "_menu_temas") as menu:
            self.ventana._tecla_temas(Evento(wx.WXK_WINDOWS_MENU))
        menu.assert_called_once_with()

    def test_mayus_f10_abre_el_menu_de_la_biblioteca(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(self.ventana, "_menu_temas") as menu:
            self.ventana._tecla_temas(Evento(wx.WXK_F10, wx.MOD_SHIFT))
        menu.assert_called_once_with()

    # ── Colecciones ────────────────────────────────────────────────────────

    def test_colecciones_trae_biblioteca_y_listas(self):
        real = Path(self.tmp.name) / "rock.mp3"
        real.write_bytes(b"audio")
        temas = (Tema(str(real.resolve()), "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(carpeta_listas=self.carpeta_listas,
                               temas_listas={"Mía": temas})
        self._abrir(control)
        self.assertEqual(self.ventana.lb_colecciones.GetStrings(),
                         ["Biblioteca", "Mía: 1"])
        self.assertEqual(self.ventana.lb_colecciones.GetSelection(), 0)

    def test_agregar_a_una_lista_conserva_la_cantidad_de_la_biblioteca(self):
        real = Path(self.tmp.name) / "rock.mp3"
        real.write_bytes(b"audio")
        temas = (Tema(str(real.resolve()), "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz"),
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control)
        self.assertEqual(
            self.ventana.lb_colecciones.GetString(0), "Biblioteca: 2")
        self.ventana.lb_colecciones.SetSelection(1)
        self.ventana._cambiar_coleccion(Evento())
        self.ventana.lb_temas.SetSelection(0)
        self.ventana._accion_biblioteca(
            (musica_menus.ACCION_AGREGAR_A_LISTA, "Mía"))
        self.assertEqual(
            self.ventana.lb_colecciones.GetString(0), "Biblioteca: 2")

    def test_elegir_una_lista_carga_sus_temas(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),
                 Tema("C:/Musica/jazz.mp3", "Jazz"))
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control)
        self.ventana.lb_colecciones.SetSelection(1)
        self.ventana._cambiar_coleccion(Evento())
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Jazz"])

    def test_elegir_biblioteca_vuelve_a_la_carpeta(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz"),
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control)
        self.ventana.lb_colecciones.SetSelection(1)
        self.ventana._cambiar_coleccion(Evento())
        self.ventana.lb_colecciones.SetSelection(0)
        self.ventana._cambiar_coleccion(Evento())
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Jazz"])

    def test_intro_en_biblioteca_reproduce_todo_aunque_filtre(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.txt_buscar.SetValue("jazz")
        self.ventana.lb_colecciones.SetSelection(0)
        self.ventana._tecla_colecciones(Evento(wx.WXK_RETURN))
        self.assertIn(
            ("reproducir_desde_aqui", tuple(control._biblio.temas()), 0),
            control.llamadas)

    def test_intro_en_biblioteca_cargando_no_llama_a_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana._cargando = True
        self.ventana._tecla_colecciones(Evento(wx.WXK_RETURN))
        self.assertNotIn("reproducir_desde_aqui", control.nombres())

    def test_intro_en_una_lista_reproduce_la_lista_guardada(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        self.ventana._tecla_colecciones(Evento(wx.WXK_RETURN))
        self.assertIn(("reproducir_lista_guardada", "Mía"),
                      control.llamadas)

    def test_suprimir_en_biblioteca_no_llama_a_nada(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana._tecla_colecciones(Evento(wx.WXK_DELETE))
        self.assertNotIn("borrar_lista", control.nombres())

    def test_suprimir_en_una_lista_confirmada_la_borra(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        with mock.patch.object(musica_ventana_acciones, "_confirmar_borrar",
                               return_value=True):
            self.ventana._tecla_colecciones(Evento(wx.WXK_DELETE))
        self.assertIn(("borrar_lista", "Mía"), control.llamadas)
        self.assertEqual(self.ventana.lb_colecciones.GetSelection(), 0)

    def test_suprimir_en_una_lista_cancelada_no_borra(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        with mock.patch.object(musica_ventana_acciones, "_confirmar_borrar",
                               return_value=False):
            self.ventana._tecla_colecciones(Evento(wx.WXK_DELETE))
        self.assertNotIn("borrar_lista", control.nombres())

    def test_tecla_de_aplicaciones_abre_el_menu_de_colecciones(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(self.ventana, "_menu_colecciones") as menu:
            self.ventana._tecla_colecciones(Evento(wx.WXK_WINDOWS_MENU))
        menu.assert_called_once_with()

    def test_mayus_f10_abre_el_menu_de_colecciones(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(self.ventana, "_menu_colecciones") as menu:
            self.ventana._tecla_colecciones(Evento(wx.WXK_F10, wx.MOD_SHIFT))
        menu.assert_called_once_with()

    def test_las_acciones_de_colecciones_se_despiden(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        with mock.patch.object(
                self.ventana, "_reproducir_coleccion") as reproducir, \
                mock.patch.object(
                    self.ventana,
                    "_agregar_coleccion_a_cola") as agregar, \
                mock.patch.object(
                    self.ventana, "_editar_lista") as editar, \
                mock.patch.object(
                    self.ventana, "_renombrar_lista") as renombrar, \
                mock.patch.object(
                    self.ventana, "_borrar_lista") as borrar, \
                mock.patch.object(
                    self.ventana, "_nueva_lista") as nueva:
            for accion in (musica_menus.ACCION_REPRODUCIR_COLECCION,
                           musica_menus.ACCION_AGREGAR_COLECCION,
                           musica_menus.ACCION_EDITAR_LISTA,
                           musica_menus.ACCION_RENOMBRAR_LISTA,
                           musica_menus.ACCION_BORRAR_LISTA,
                           musica_menus.ACCION_NUEVA_LISTA):
                self.ventana._accion_coleccion(accion)
        reproducir.assert_called_once_with()
        agregar.assert_called_once_with()
        editar.assert_called_once_with()
        renombrar.assert_called_once_with()
        borrar.assert_called_once_with()
        nueva.assert_called_once_with()

    def test_agregar_coleccion_suma_toda_la_lista_al_final(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),
                 Tema("C:/Musica/jazz.mp3", "Jazz"))
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        self.ventana._accion_coleccion(
            musica_menus.ACCION_AGREGAR_COLECCION)
        self.assertIn(("agregar_al_final", temas), control.llamadas)

    # ── Teclas de la Cola ──────────────────────────────────────────────────

    def test_intro_en_la_cola_reproduce_desde_esa_fila(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(1)
        self.ventana._tecla_cola(Evento(wx.WXK_RETURN))
        self.assertIn(("reproducir_desde", 1), control.llamadas)

    def test_suprimir_en_la_cola_quita(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(1)
        self.ventana._tecla_cola(Evento(wx.WXK_DELETE))
        self.assertIn(("quitar_de_cola", 1), control.llamadas)

    def test_alt_arriba_y_abajo_mueven(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(1)
        self.ventana._tecla_cola(Evento(wx.WXK_UP, wx.MOD_ALT))
        self.ventana._tecla_cola(Evento(wx.WXK_DOWN, wx.MOD_ALT))
        self.assertIn(("mover_en_cola", 1, -1), control.llamadas)
        self.assertIn(("mover_en_cola", 0, 1), control.llamadas)

    def test_tecla_de_aplicaciones_abre_el_menu_de_la_cola(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(self.ventana, "_menu_cola") as menu:
            self.ventana._tecla_cola(Evento(wx.WXK_WINDOWS_MENU))
        menu.assert_called_once_with()

    def test_mayus_f10_abre_el_menu_de_la_cola(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(self.ventana, "_menu_cola") as menu:
            self.ventana._tecla_cola(Evento(wx.WXK_F10, wx.MOD_SHIFT))
        menu.assert_called_once_with()

    def test_cada_lista_responde_solo_a_sus_teclas(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock")
        self.ventana.refrescar_cola()
        self.ventana.lb_temas.SetSelection(0)
        self.ventana.lb_cola.SetSelection(0)
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN))
        self.assertNotIn("reproducir_desde", control.nombres())
        control.llamadas.clear()
        self.ventana._tecla_cola(Evento(wx.WXK_RETURN))
        self.assertNotIn("reproducir_ahora", control.nombres())

    # ── Cola plegable ──────────────────────────────────────────────────────

    def test_la_cola_arranca_oculta_de_fabrica(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertFalse(self.ventana.lb_cola.IsShown())
        self.assertEqual(self.ventana.btn_cola.GetLabel(),
                         "Mostrar la c&ola")
        self.assertEqual(self.ventana.btn_cola.GetName(),
                         "Mostrar la cola")

    def test_lo_guardado_visible_se_respeta_al_abrir(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock"),
                                 cola_visible=True))
        self.assertTrue(self.ventana.lb_cola.IsShown())
        self.assertEqual(self.ventana.btn_cola.GetLabel(),
                         "Ocultar la c&ola")
        self.assertEqual(self.ventana.btn_cola.GetName(),
                         "Ocultar la cola")

    def test_el_boton_muestra_la_cola_con_foco_y_anuncio(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        control.cola = tuple(
            Tema(f"C:/Musica/t{i}.mp3", f"T{i}") for i in range(5))
        self._abrir(control)
        with mock.patch.object(self.ventana.lb_cola, "SetFocus") as foco:
            self.ventana._alternar_cola()
        self.assertTrue(self.ventana.lb_cola.IsShown())
        foco.assert_called_once_with()
        self.assertEqual(self.ventana.btn_cola.GetLabel(),
                         "Ocultar la c&ola")
        self.assertIn("Cola visible, 5 canciones", self.anuncios)
        self.assertIn(("recordar_cola_visible", True), control.llamadas)

    def test_el_boton_muestra_un_tema_en_singular(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        control.cola = (Tema("C:/Musica/t.mp3", "T"),)
        self._abrir(control)
        with mock.patch.object(self.ventana.lb_cola, "SetFocus"):
            self.ventana._alternar_cola()
        self.assertIn("Cola visible, 1 canción", self.anuncios)

    def test_el_boton_muestra_la_cola_vacia(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        with mock.patch.object(self.ventana.lb_cola, "SetFocus"):
            self.ventana._alternar_cola()
        self.assertIn("Cola visible, vacía", self.anuncios)

    def test_el_boton_oculta_la_cola_con_foco_y_anuncio(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"),
                               cola_visible=True)
        self._abrir(control)
        with mock.patch.object(self.ventana.btn_cola, "SetFocus") as foco:
            self.ventana._alternar_cola()
        self.assertFalse(self.ventana.lb_cola.IsShown())
        foco.assert_called_once_with()
        self.assertEqual(self.ventana.btn_cola.GetLabel(),
                         "Mostrar la c&ola")
        self.assertIn("Cola oculta", self.anuncios)
        self.assertIn(("recordar_cola_visible", False), control.llamadas)

    # ── Filtros por artista y orden ───────────────────────────────────────

    def _elegir(self, cuadro, indice):
        cuadro.SetSelection(indice)
        evento = wx.CommandEvent(wx.EVT_CHOICE.typeId, cuadro.GetId())
        cuadro.GetEventHandler().ProcessEvent(evento)

    def test_los_filtros_arrancan_ocultos_y_fuera_del_orden_de_tab(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertFalse(self.ventana.filtros.visibles)
        self.assertEqual(self.ventana.filtros.btn.GetLabel(),
                         "Mostrar los &filtros")
        self.assertEqual(self.ventana.filtros.btn.GetName(),
                         "Mostrar los filtros")
        self.assertFalse(self.ventana.filtros.cb_mostrar.IsShown())
        self.assertFalse(self.ventana.filtros.cb_ordenar.IsShown())
        self.assertFalse(self.ventana.filtros.lb_mostrar.IsShown())
        self.assertFalse(self.ventana.filtros.lb_ordenar.IsShown())

    def test_lo_guardado_visible_se_respeta_al_abrir_los_filtros(self):
        self._abrir(ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            filtros_guardados=(True, "", "coleccion")))
        self.assertTrue(self.ventana.filtros.visibles)
        self.assertEqual(self.ventana.filtros.btn.GetLabel(),
                         "Ocultar los &filtros")
        self.assertEqual(self.ventana.filtros.btn.GetName(),
                         "Ocultar los filtros")
        self.assertTrue(self.ventana.filtros.cb_mostrar.IsShown())
        self.assertTrue(self.ventana.filtros.cb_ordenar.IsShown())

    def test_el_boton_muestra_los_filtros_con_foco_y_anuncio(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(
                self.ventana.filtros.cb_mostrar, "SetFocus") as foco:
            self.ventana.filtros.alternar()
        self.assertTrue(self.ventana.filtros.cb_mostrar.IsShown())
        foco.assert_called_once_with()
        self.assertEqual(self.ventana.filtros.btn.GetLabel(),
                         "Ocultar los &filtros")
        self.assertIn("Filtros visibles", self.anuncios)
        self.assertIn(("recordar_filtros", True, "", "coleccion"),
                      control.llamadas)

    def test_el_boton_oculta_los_filtros_con_foco_y_anuncio(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            filtros_guardados=(True, "", "coleccion"))
        self._abrir(control)
        with mock.patch.object(self.ventana.filtros.btn, "SetFocus") as foco:
            self.ventana.filtros.alternar()
        self.assertFalse(self.ventana.filtros.cb_mostrar.IsShown())
        foco.assert_called_once_with()
        self.assertEqual(self.ventana.filtros.btn.GetLabel(),
                         "Mostrar los &filtros")
        self.assertIn("Filtros ocultos", self.anuncios)
        self.assertIn(("recordar_filtros", False, "", "coleccion"),
                      control.llamadas)

    def test_elegir_artista_y_orden_se_combina_con_buscar(self):
        biblioteca = _biblioteca_con((
            Tema("C:/Musica/zeta.mp3", "Zeta", artista="Ana",
                 duracion_ms=3000),
            Tema("C:/Musica/alfa.mp3", "Alfa", artista="Luis",
                 duracion_ms=1000),
            Tema("C:/Musica/beta.mp3", "Beta", artista="Ana & Luis",
                 duracion_ms=2000),
        ))
        self._abrir(ControlFalso(
            biblioteca=biblioteca,
            filtros_guardados=(True, "", "coleccion")))
        self.ventana.txt_buscar.SetValue("a")
        self.ventana._al_filtrar(Evento())
        self._elegir(
            self.ventana.filtros.cb_mostrar,
            self.ventana.filtros.cb_mostrar.GetStrings().index(
                "Ana, 2 canciones"))
        self._elegir(
            self.ventana.filtros.cb_ordenar,
            [clave for clave, _etiqueta
             in filtros.CRITERIOS].index(filtros.CRITERIO_TITULO))
        self.assertEqual(
            [tema.titulo for tema in self.ventana._temas_filtrados],
            ["Beta", "Zeta"])
        self.assertEqual(
            self.ventana.lb_temas.GetStrings(),
            ["Beta, Ana & Luis, 0:02", "Zeta, Ana, 0:03"])

    def test_ocultar_los_filtros_devuelve_todas_y_mostrarlos_filtra(self):
        biblioteca = _biblioteca_con((
            Tema("C:/Musica/uno.mp3", "Uno", artista="Ana"),
            Tema("C:/Musica/dos.mp3", "Dos", artista="Luis"),
            Tema("C:/Musica/tres.mp3", "Tres", artista="Ana"),
        ))
        self._abrir(ControlFalso(
            biblioteca=biblioteca,
            filtros_guardados=(True, "", "coleccion")))
        self._elegir(
            self.ventana.filtros.cb_mostrar,
            self.ventana.filtros.cb_mostrar.GetStrings().index(
                "Ana, 2 canciones"))
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Uno, Ana", "Tres, Ana"])
        with mock.patch.object(
                musica_ventana.wx, "CallLater") as aviso:
            self.ventana.filtros.alternar()
        aviso.assert_not_called()
        self.assertFalse(self.ventana.filtros.visibles)
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Uno, Ana", "Dos, Luis", "Tres, Ana"])
        self.assertIn("Filtros ocultos", self.anuncios)
        self.ventana.filtros.alternar()
        self.assertTrue(self.ventana.filtros.visibles)
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Uno, Ana", "Tres, Ana"])
        self.assertIn("Filtros visibles", self.anuncios)
        self.assertEqual(self.ventana.filtros.artista, "ana")

    def test_al_cambiar_un_cuadro_programa_y_anuncia_la_cantidad(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz")))
        with mock.patch.object(
                musica_ventana.wx, "CallLater") as programar:
            self._elegir(
                self.ventana.filtros.cb_ordenar,
                [clave for clave, _etiqueta
                 in filtros.CRITERIOS].index(filtros.CRITERIO_TITULO))
        programar.assert_called_once_with(
            700, self.ventana._avisar_coincidencias, True)
        self.ventana._avisar_coincidencias(True)
        self.assertIn("2 canciones coinciden", self.anuncios)

    def test_el_artista_recordado_que_no_esta_muestra_todas(self):
        self._abrir(ControlFalso(
            biblioteca=_biblioteca_de("Rock", artista="Ana"),
            filtros_guardados=(True, "luis", "coleccion")))
        self.assertEqual(self.ventana.filtros.artista, filtros.TODAS)
        self.assertEqual(
            self.ventana.filtros.cb_mostrar.GetStringSelection(),
            "Todas las canciones")
        self.assertEqual(
            [tema.titulo for tema in self.ventana._temas_filtrados],
            ["Rock"])

    def test_recordar_los_filtros_al_cerrar_y_abrir(self):
        biblioteca = _biblioteca_con((
            Tema("C:/Musica/vieja.mp3", "Vieja", artista="Ana",
                 fecha_ns=1),
            Tema("C:/Musica/nueva.mp3", "Nueva", artista="Ana",
                 fecha_ns=2),
            Tema("C:/Musica/otra.mp3", "Otra", artista="Luis", fecha_ns=3),
        ))
        control = ControlFalso(biblioteca=biblioteca)
        self._abrir(control)
        self.ventana.filtros.alternar()
        self._elegir(
            self.ventana.filtros.cb_mostrar,
            self.ventana.filtros.cb_mostrar.GetStrings().index(
                "Ana, 2 canciones"))
        self._elegir(
            self.ventana.filtros.cb_ordenar,
            [clave for clave, _etiqueta
             in filtros.CRITERIOS].index(filtros.CRITERIO_RECIENTES))
        guardados = control.filtros_guardados()
        self.ventana._cancelar_temporizador()
        destruir(self.ventana)
        self.ventana = None
        self._abrir(ControlFalso(
            biblioteca=biblioteca, filtros_guardados=guardados))
        self.assertTrue(self.ventana.filtros.visibles)
        self.assertEqual(
            self.ventana.filtros.cb_mostrar.GetStringSelection(),
            "Ana, 2 canciones")
        self.assertEqual(
            self.ventana.filtros.cb_ordenar.GetStringSelection(),
            "Más recientes primero")
        self.assertEqual(
            [tema.titulo for tema in self.ventana._temas_filtrados],
            ["Nueva", "Vieja"])

    # ── Intro por el gancho de la ventana ──────────────────────────────────

    def _char_hook(self, keycode=wx.WXK_RETURN, mods=0):
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.SetKeyCode(keycode)
        evento.SetControlDown(bool(mods & wx.MOD_CONTROL))
        evento.SetShiftDown(bool(mods & wx.MOD_SHIFT))
        evento.SetAltDown(bool(mods & wx.MOD_ALT))
        self.ventana.GetEventHandler().ProcessEvent(evento)

    def _doble_clic(self, lista):
        evento = wx.CommandEvent(wx.EVT_LISTBOX_DCLICK.typeId, lista.GetId())
        evento.SetEventObject(lista)
        lista.GetEventHandler().ProcessEvent(evento)

    def test_intro_por_la_ventana_reproduce_ahora_el_elegido(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetFocus()
        self.ventana.lb_temas.SetSelection(1)
        self._char_hook()
        tema = control._biblio.temas()[1]
        self.assertIn(("reproducir_ahora", (tema,)), control.llamadas)

    def test_mayus_intro_por_la_ventana_pone_a_continuacion(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetFocus()
        self.ventana.lb_temas.SetSelection(1)
        self._char_hook(mods=wx.MOD_SHIFT)
        tema = control._biblio.temas()[1]
        self.assertIn(("poner_a_continuacion", (tema,)), control.llamadas)

    def test_control_intro_por_la_ventana_agrega_al_final(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetFocus()
        self.ventana.lb_temas.SetSelection(1)
        self._char_hook(mods=wx.MOD_CONTROL)
        tema = control._biblio.temas()[1]
        self.assertIn(("agregar_al_final", (tema,)), control.llamadas)

    def test_intro_por_la_ventana_en_la_cola_reproduce_desde(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetFocus()
        self.ventana.lb_cola.SetSelection(1)
        self._char_hook()
        self.assertIn(("reproducir_desde", 1), control.llamadas)

    def test_intro_por_la_ventana_en_colecciones_reproduce_la_lista(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        self.ventana.lb_colecciones.SetFocus()
        self._char_hook()
        self.assertIn(("reproducir_lista_guardada", "Mía"),
                      control.llamadas)

    def test_intro_por_la_ventana_en_el_buscador_no_acciona(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.txt_buscar.SetFocus()
        self.ventana.lb_temas.SetSelection(1)
        self._char_hook()
        self.assertNotIn("reproducir_ahora", control.nombres())
        self.assertNotIn("agregar_al_final", control.nombres())

    def test_doble_clic_en_colecciones_reproduce_la_lista(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        self._doble_clic(self.ventana.lb_colecciones)
        self.assertIn(("reproducir_lista_guardada", "Mía"),
                      control.llamadas)

    def test_doble_clic_en_la_biblioteca_reproduce_ahora(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        self._doble_clic(self.ventana.lb_temas)
        tema = control._biblio.temas()[1]
        self.assertIn(("reproducir_ahora", (tema,)), control.llamadas)

    def test_doble_clic_en_la_cola_reproduce_desde(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(1)
        self._doble_clic(self.ventana.lb_cola)
        self.assertIn(("reproducir_desde", 1), control.llamadas)

    # ── Buscador ───────────────────────────────────────────────────────────

    def test_escape_con_texto_borra_y_anuncia(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz")))
        self.ventana.txt_buscar.SetValue("jaz")
        self.ventana._tecla_buscar(Evento(wx.WXK_ESCAPE))
        self.assertEqual(self.ventana.txt_buscar.GetValue(), "")
        self.assertIn(anuncios.TEXTO_BUSQUEDA_BORRADA, self.anuncios)
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Jazz"])

    def test_escape_sin_texto_cierra(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        with mock.patch.object(self.ventana, "EndModal") as cerrar:
            self.ventana._tecla_buscar(Evento(wx.WXK_ESCAPE))
        cerrar.assert_called_once_with(wx.ID_CANCEL)

    def test_flecha_abajo_va_a_la_biblioteca(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        with mock.patch.object(self.ventana.lb_temas, "SetFocus") as foco:
            self.ventana._tecla_buscar(Evento(wx.WXK_DOWN))
        foco.assert_called_once_with()

    def test_avisa_cuantos_coinciden(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz")))
        self.ventana.txt_buscar.SetValue("jaz")
        self.ventana._al_filtrar(Evento())
        self.ventana._avisar_coincidencias()
        self.assertIn("1 canción coincide", self.anuncios)

    # ── Menús ──────────────────────────────────────────────────────────────

    def test_entradas_exactas_de_la_biblioteca(self):
        entradas = musica_menus.entradas_biblioteca(False, ("Mía", "Otra"))
        self.assertEqual(
            [etiqueta for etiqueta, _accion in entradas],
            ["Reproducir &ahora", "Reproducir a &continuación",
             "A&gregar a la cola", "Reproducir &todo desde aquí",
             "Agregar a una &lista"])
        submenu = entradas[-1][1]
        self.assertEqual(
            [etiqueta for etiqueta, _accion in submenu],
            ["Mía", "Otra", "&Nueva lista…"])
        self.assertEqual(
            [etiqueta for etiqueta, _accion
             in musica_menus.entradas_biblioteca(True)][-1:],
            ["&Quitar de esta lista"])

    def test_entradas_exactas_de_colecciones(self):
        self.assertEqual(
            [etiqueta for etiqueta, _accion
             in musica_menus.entradas_colecciones(False)],
            ["&Reproducir", "A&gregar a la cola", "&Nueva lista…"])
        self.assertEqual(
            [etiqueta for etiqueta, _accion
             in musica_menus.entradas_colecciones(True)],
            ["&Reproducir", "A&gregar a la cola", "&Editar la lista…",
             "Re&nombrar la lista…", "&Borrar la lista…",
             "&Nueva lista…"])

    def test_entradas_exactas_de_la_cola(self):
        self.assertEqual(
            [etiqueta for etiqueta, _accion in musica_menus.entradas_cola()],
            ["&Reproducir", "&Quitar", "&Subir", "&Bajar",
             "&Ir al que suena", "&Mezclar la cola", "&Vaciar la cola",
             "&Guardar la cola como lista…"])

    def test_cada_accion_de_la_biblioteca_llama_a_lo_suyo(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        tema = control._biblio.temas()[1]
        self.ventana._accion_biblioteca(musica_menus.ACCION_AHORA)
        self.ventana._accion_biblioteca(musica_menus.ACCION_CONTINUACION)
        self.ventana._accion_biblioteca(musica_menus.ACCION_AGREGAR)
        self.ventana._accion_biblioteca(musica_menus.ACCION_TODO_DESDE_AQUI)
        self.ventana._accion_biblioteca(
            (musica_menus.ACCION_AGREGAR_A_LISTA, "Mía"))
        self.assertIn(("reproducir_ahora", (tema,)), control.llamadas)
        self.assertIn(("poner_a_continuacion", (tema,)), control.llamadas)
        self.assertIn(("agregar_al_final", (tema,)), control.llamadas)
        self.assertIn(("agregar_a_lista", "Mía", (tema,)), control.llamadas)
        self.assertIn(
            ("reproducir_desde_aqui", tuple(control._biblio.temas()), 1),
            control.llamadas)

    def test_las_acciones_de_lista_propia_se_despiden(self):
        self._crear_lista("Mía", (Tema("C:/Musica/rock.mp3", "Rock"),))
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": (Tema("C:/Musica/rock.mp3", "Rock"),)})
        self._abrir(control, abrir_listas=True)
        self.ventana.lb_temas.SetSelection(0)
        with mock.patch.object(self.ventana, "_quitar_lista") as quitar, \
                mock.patch.object(self.ventana, "_renombrar_lista") as renombrar, \
                mock.patch.object(self.ventana, "_borrar_lista") as borrar:
            for accion in (musica_menus.ACCION_QUITAR_DE_LISTA,
                           musica_menus.ACCION_RENOMBRAR_LISTA,
                           musica_menus.ACCION_BORRAR_LISTA):
                self.ventana._accion_biblioteca(accion)
        tema = self.ventana._temas_filtrados[0]
        quitar.assert_called_once_with(tema)
        renombrar.assert_called_once_with()
        borrar.assert_called_once_with()

    def test_cada_accion_de_la_cola_llama_a_lo_suyo(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz")
        control.cola = control.estado_actual.cola
        self.ventana.refrescar_cola()
        for accion in (musica_menus.ACCION_REPRODUCIR,
                       musica_menus.ACCION_QUITAR,
                       musica_menus.ACCION_SUBIR,
                       musica_menus.ACCION_BAJAR,
                       musica_menus.ACCION_MEZCLAR,
                       musica_menus.ACCION_VACIAR):
            self.ventana.lb_cola.SetSelection(1)
            self.ventana._accion_cola(accion)
        self.assertIn(("reproducir_desde", 1), control.llamadas)
        self.assertIn(("quitar_de_cola", 1), control.llamadas)
        self.assertIn(("mover_en_cola", 1, -1), control.llamadas)
        self.assertIn(("mover_en_cola", 1, 1), control.llamadas)
        self.assertIn(("mezclar_cola",), control.llamadas)
        self.assertIn(("vaciar_cola",), control.llamadas)

    def test_guardar_la_cola_como_lista_pide_el_nombre(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock")
        control.cola = control.estado_actual.cola
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(0)
        with mock.patch.object(
                musica_ventana_acciones, "_pedir_nombre",
                return_value="Copia"):
            self.ventana._accion_cola(musica_menus.ACCION_GUARDAR_COLA)
        self.assertIn(("guardar_cola_como_lista", "Copia"), control.llamadas)

    def test_nueva_lista_abre_el_editor_y_guarda(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        self._abrir(control)
        temas = (control._biblio.temas()[0],)
        with mock.patch.object(
                musica_editor_lista, "pedir_lista",
                return_value=("Mía", temas)) as pedir:
            self.ventana._nueva_lista()
        self.assertEqual(pedir.call_args[0][1], "")
        self.assertIn(("guardar_lista", "Mía", temas, None), control.llamadas)

    def test_editar_la_lista_pide_y_guarda_renombrando(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        nuevo = (Tema("C:/Musica/jazz.mp3", "Jazz"),)
        with mock.patch.object(
                musica_editor_lista, "pedir_lista",
                return_value=("Otra", nuevo)) as pedir:
            self.ventana._editar_lista()
        self.assertEqual(pedir.call_args[0][1], "Mía")
        self.assertIn(("guardar_lista", "Otra", nuevo, "Mía"),
                      control.llamadas)

    def test_editar_lista_usa_la_biblioteca_actual_del_control(self):
        temas_lista = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas_lista)
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz"),
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas_lista})
        self._abrir(control, abrir_listas=True)
        self.assertIsNone(self.ventana._biblioteca)
        with mock.patch.object(
                musica_editor_lista, "pedir_lista",
                return_value=("Mía", temas_lista)) as pedir:
            self.ventana._editar_lista()
        self.assertEqual([t.titulo for t in pedir.call_args[0][2]],
                         ["Rock", "Jazz"])
        self.assertNotIn(("biblioteca",), control.llamadas)

    def test_editar_lista_sin_biblioteca_actual_la_pide_al_control(self):
        temas_lista = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas_lista)
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz"),
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas_lista})
        self._abrir(control, abrir_listas=True)
        with mock.patch.object(control, "biblioteca_actual",
                               return_value=None), \
                mock.patch.object(
                    musica_editor_lista, "pedir_lista",
                    return_value=("Mía", temas_lista)) as pedir:
            self.ventana._editar_lista()
        self.assertIn(("biblioteca",), control.llamadas)
        self.assertEqual([t.titulo for t in pedir.call_args[0][2]],
                         ["Rock", "Jazz"])

    # ── Cola: refresco y «Ir al que suena» ─────────────────────────────────

    def test_refrescar_cola_conserva_la_seleccion(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz", "Blues")
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(1)
        control.estado_actual = _estado("Rock", "Jazz")
        self.ventana.refrescar_cola()
        self.assertEqual(self.ventana.lb_cola.GetSelection(), 1)
        control.estado_actual = _estado("Rock")
        self.ventana.refrescar_cola()
        self.assertEqual(self.ventana.lb_cola.GetSelection(), 0)

    def test_ir_al_que_suena_selecciona_su_fila(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        control.estado_actual = _estado("Rock", "Jazz", "Blues", posicion=2)
        self.ventana.refrescar_cola()
        self.ventana.lb_cola.SetSelection(0)
        self.ventana._ir_al_que_suena()
        self.assertEqual(self.ventana.lb_cola.GetSelection(), 2)

    # ── Apertura con abrir_listas ──────────────────────────────────────────

    def test_abrir_listas_deja_colecciones_en_la_primera_lista(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Alfa", temas)
        self._crear_lista("Beta", ())
        control = ControlFalso(
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Alfa": temas, "Beta": ()})
        self._abrir(control, abrir_listas=True)
        self.assertEqual(self.ventana.lb_colecciones.GetSelection(), 1)
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Rock"])
        with mock.patch.object(self.ventana.lb_colecciones,
                               "SetFocus") as foco:
            self.ventana.enfocar_primer_control()
        foco.assert_called_once_with()

    def test_abrir_listas_sin_listas_deja_el_foco_en_el_buscador(self):
        control = ControlFalso(carpeta_listas=self.carpeta_listas)
        self._abrir(control, abrir_listas=True)
        self.assertEqual(self.ventana.lb_colecciones.GetSelection(), 0)
        with mock.patch.object(self.ventana.txt_buscar,
                               "SetFocus") as foco:
            self.ventana.enfocar_primer_control()
        foco.assert_called_once_with()

    # ── Sin carpeta ────────────────────────────────────────────────────────

    def test_sin_carpeta_la_biblioteca_lo_dice_y_no_acciona(self):
        control = ControlFalso(biblioteca=None)
        self._abrir(control)
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         [musica_ventana.TEXTO_SIN_CARPETA])
        self.ventana._tecla_temas(Evento(wx.WXK_RETURN))
        self.assertNotIn("reproducir_ahora", control.nombres())

    # ── Enlaces ────────────────────────────────────────────────────────────

    def test_el_cuadro_de_enlace_llama_al_control(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(
                musica_dialogo_enlace, "pedir_enlace",
                return_value=("https://youtu.be/abc", "continuacion")):
            self.ventana._abrir_enlace()
        self.assertIn(
            ("abrir_enlace", "https://youtu.be/abc", "continuacion"),
            control.llamadas)

    def test_cuadro_de_enlace_cancelado_no_llama(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(
                musica_dialogo_enlace, "pedir_enlace", return_value=None):
            self.ventana._abrir_enlace()
        self.assertNotIn("abrir_enlace", control.nombres())


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaIgualando(unittest.TestCase):
    """Campo y barra del progreso de la igualación, sin correr nada."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self.ventana = musica_ventana.VentanaMusica(None, self.control)

    def tearDown(self):
        self.ventana._cancelar_temporizador()
        self.ventana._parar_igualando()
        destruir(self.ventana)

    def test_el_campo_nace_oculto(self):
        self.assertFalse(self.ventana.txt_igualando.IsShown())
        self.assertFalse(self.ventana.gauge_igualando.IsShown())

    def test_con_progreso_el_tic_muestra_el_campo_con_el_texto(self):
        self.control._progreso_sonoridad = (3, 10)
        self.ventana._tic_igualando()
        self.assertTrue(self.ventana.txt_igualando.IsShown())
        self.assertTrue(self.ventana.gauge_igualando.IsShown())
        self.assertEqual(self.ventana.txt_igualando.GetValue(),
                         "Igualando el volumen: 3 de 10")
        self.assertEqual(self.ventana.gauge_igualando.GetValue(), 30)

    def test_sin_progreso_oculta_y_devuelve_el_foco_a_temas(self):
        self.control._progreso_sonoridad = (3, 10)
        self.ventana._tic_igualando()
        self.ventana.txt_igualando.SetFocus()
        self.control._progreso_sonoridad = None
        self.ventana._tic_igualando()
        self.assertFalse(self.ventana.txt_igualando.IsShown())
        self.assertFalse(self.ventana.gauge_igualando.IsShown())
        self.assertIs(wx.Window.FindFocus(), self.ventana.lb_temas)

    def test_el_campo_entra_en_el_tab_con_la_igualacion_en_curso(self):
        self.control._progreso_sonoridad = (3, 10)
        self.ventana._tic_igualando()
        self.assertTrue(
            self.ventana.txt_igualando.AcceptsFocusFromKeyboard())
        self.ventana.btn_cola.SetFocus()
        self.ventana.btn_cola.Navigate()
        self.assertIs(wx.Window.FindFocus(), self.ventana.txt_igualando)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaBotonIgualar(unittest.TestCase):
    """El botón que pide o detiene la igualación, y su rotulado."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.control = None
        self.ventana = None
        self.anuncios = []
        self.sonidos = []
        self._parche = mock.patch.object(
            musica_ventana_igualando, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self._parche_sonido = mock.patch.object(
            musica_ventana_igualando._snd, "reproducir",
            lambda evento: self.sonidos.append(evento))
        self._parche_sonido.start()

    def tearDown(self):
        self._parche_sonido.stop()
        self._parche.stop()
        if self.ventana is not None:
            self.ventana._cancelar_temporizador()
            self.ventana._parar_igualando()
            destruir(self.ventana)

    def _abrir(self, control):
        self.control = control
        self.ventana = musica_ventana.VentanaMusica(None, control)
        return self.ventana

    def test_pulsar_sin_medir_pide_y_anuncia_el_inicio(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            pendientes_calculadas=("a.mp3", "b.mp3"), total_calculado=300,
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.INICIO, 2))
        self._abrir(control)
        self.ventana.alternar_igualacion()
        biblio = self.ventana._biblioteca
        self.assertIn(("pedir_pendientes", biblio), control.llamadas)
        self.assertIn(("iniciar_medicion", ("a.mp3", "b.mp3")),
                      control.llamadas)
        self.assertEqual(self.anuncios,
                         ["Igualando el volumen de 2 canciones"])
        self.assertEqual(self.sonidos, ["musica_igualando"])

    def test_pulsar_con_opcion_apagada_lo_dice(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            pendientes_calculadas=("a.mp3",), total_calculado=100,
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.OPCION_APAGADA))
        self._abrir(control)
        self.ventana.alternar_igualacion()
        self.assertEqual(
            self.anuncios,
            ["La igualación del volumen está desactivada. Actívala en "
             "Preferencias, página Música."])
        self.assertEqual(self.sonidos, [])

    def test_pulsar_sin_ffmpeg_lo_dice(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            pendientes_calculadas=("a.mp3",), total_calculado=100,
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.SIN_FFMPEG))
        self._abrir(control)
        self.ventana.alternar_igualacion()
        self.assertEqual(
            self.anuncios, ["No se puede igualar el volumen: falta ffmpeg."])
        self.assertEqual(self.sonidos, [])

    def test_pulsar_sin_pendientes_lo_dice(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.NADA_PENDIENTE))
        self._abrir(control)
        self.ventana.alternar_igualacion()
        self.assertEqual(
            self.anuncios,
            ["Todas las canciones tienen el volumen igualado."])
        self.assertEqual(self.sonidos, [])

    def test_pulsar_sin_carpeta_reusa_el_texto_de_sin_carpeta(self):
        self._abrir(ControlFalso(biblioteca=None))
        self.ventana.alternar_igualacion()
        self.assertEqual(self.anuncios, [anuncios.TEXTO_SIN_CARPETA])
        self.assertNotIn("pedir_pendientes", self.control.nombres())
        self.assertNotIn("iniciar_medicion", self.control.nombres())
        self.assertEqual(self.sonidos, [])

    def test_boton_con_carpeta_sin_indexar_pide_indexar_y_calcula(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            pendientes_calculadas=("a.mp3", "b.mp3"), total_calculado=200,
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.INICIO, 2))
        self._abrir(control)
        biblio = self.ventana._biblioteca
        self.ventana._al_biblioteca_para_igualar(biblio)
        self.assertIn(("pedir_pendientes", biblio), control.llamadas)
        self.assertIn(("iniciar_medicion", ("a.mp3", "b.mp3")),
                      control.llamadas)
        self.assertEqual(self.anuncios,
                         ["Igualando el volumen de 2 canciones"])

    def test_pulsar_midiendo_detiene_y_anuncia(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"),
                               midiendo=True)
        self._abrir(control)
        self.ventana.alternar_igualacion()
        self.assertIn(("detener_igualacion",), control.llamadas)
        self.assertEqual(self.anuncios,
                         ["Igualación del volumen detenida."])
        self.assertEqual(self.sonidos, [])

    def test_el_tic_rotula_el_boton_al_empezar_y_al_terminar(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.assertEqual(self.ventana.btn_igualar.GetLabel(),
                         "&Igualar el volumen")
        control._midiendo = True
        self.ventana._tic_igualando()
        self.assertEqual(self.ventana.btn_igualar.GetLabel(),
                         "Detener la &igualación")
        control._midiendo = False
        self.ventana._tic_igualando()
        self.assertEqual(self.ventana.btn_igualar.GetLabel(),
                         "&Igualar el volumen")

    def test_el_foco_en_el_boton_se_queda_en_el_boton(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana.btn_igualar.SetFocus()
        control._midiendo = True
        self.ventana._tic_igualando()
        self.assertIs(wx.Window.FindFocus(), self.ventana.btn_igualar)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaPreguntaIgualar(unittest.TestCase):
    """La pregunta que sale al recibir la biblioteca de la carpeta."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.control = None
        self.ventana = None
        self.anuncios = []
        self.sonidos = []
        self._parche = mock.patch.object(
            musica_ventana_igualando, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self._parche_sonido = mock.patch.object(
            musica_ventana_igualando._snd, "reproducir",
            lambda evento: self.sonidos.append(evento))
        self._parche_sonido.start()

    def tearDown(self):
        self._parche_sonido.stop()
        self._parche.stop()
        if self.ventana is not None:
            self.ventana._cancelar_temporizador()
            self.ventana._parar_igualando()
            destruir(self.ventana)

    def _abrir(self, control, responder_pedidos=False):
        self.control = control
        control.responder_pedidos = responder_pedidos
        self.ventana = musica_ventana.VentanaMusica(None, control)
        return self.ventana

    def _dialogo(self, respuesta, marcada):
        clase = mock.patch.object(
            musica_ventana_igualando.wx, "RichMessageDialog").start()
        self.addCleanup(clase.stop)
        dialogo = clase.return_value
        dialogo.ShowModal.return_value = respuesta
        dialogo.IsCheckBoxChecked.return_value = marcada
        return clase, dialogo

    def test_si_inicia_y_con_la_casilla_guarda_que_no_se_pregunte_mas(self):
        pendientes = ("a.mp3", "b.mp3", "c.mp3")
        total = 300 * 1024 * 1024
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            datos_pregunta=(3, total),
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.INICIO, 3))
        self._abrir(control)
        clase, dialogo = self._dialogo(wx.ID_YES, True)
        self.ventana._al_pendientes_pregunta(pendientes, total)
        texto, titulo = clase.call_args.args[1:3]
        self.assertEqual(texto, pregunta_igualar.texto_pregunta(3, total))
        self.assertEqual(titulo, pregunta_igualar.TITULO)
        dialogo.ShowCheckBox.assert_called_once_with(
            pregunta_igualar.CASILLA)
        self.assertIn(("iniciar_medicion", pendientes), control.llamadas)
        self.assertIn(("fijar_preguntar_igualar", False), control.llamadas)
        self.assertEqual(self.anuncios,
                         ["Igualando el volumen de 3 canciones"])
        self.assertEqual(self.sonidos, ["musica_igualando"])

    def test_no_cierra_sin_medir_y_sin_la_casilla_no_guarda_nada(self):
        pendientes = ("a.mp3", "b.mp3", "c.mp3")
        total = 300 * 1024 * 1024
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            datos_pregunta=(3, total),
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.INICIO, 3))
        self._abrir(control)
        self._dialogo(wx.ID_NO, False)
        self.ventana._al_pendientes_pregunta(pendientes, total)
        self.assertNotIn("iniciar_medicion", control.nombres())
        self.assertNotIn("fijar_preguntar_igualar", control.nombres())
        self.assertEqual(self.anuncios, [])

    def test_no_con_la_casilla_tambien_guarda_que_no_se_pregunte_mas(self):
        pendientes = ("a.mp3", "b.mp3", "c.mp3")
        total = 300 * 1024 * 1024
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock"),
            datos_pregunta=(3, total),
            resultado_igualacion=ResultadoIgualacion(
                sonoridad.INICIO, 3))
        self._abrir(control)
        self._dialogo(wx.ID_NO, True)
        self.ventana._al_pendientes_pregunta(pendientes, total)
        self.assertNotIn("iniciar_medicion", control.nombres())
        self.assertIn(("fijar_preguntar_igualar", False), control.llamadas)

    def test_sin_lo_que_preguntar_no_abre_el_dialogo(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        with mock.patch.object(
                musica_ventana_igualando.wx,
                "RichMessageDialog") as clase:
            self.ventana._al_pendientes_pregunta((), 0)
        clase.assert_not_called()
        self.assertEqual(self.anuncios, [])

    def test_preguntar_pide_las_pendientes_una_sola_vez_por_apertura(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        self._abrir(control)
        self.ventana._preguntado_igualar = False
        control.llamadas.clear()
        biblio = self.ventana._biblioteca
        self.ventana.preguntar_igualacion(biblio)
        self.ventana.preguntar_igualacion(biblio)
        pedidos = [llamada for llamada in control.llamadas
                   if llamada[0] == "pedir_pendientes"]
        self.assertEqual(pedidos, [("pedir_pendientes", biblio)])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoEnlace(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)

    def _abrir(self):
        self.dialogo = musica_dialogo_enlace.DialogoEnlace(None)
        return self.dialogo

    def _panel(self):
        for hijo in self.dialogo.GetChildren():
            if isinstance(hijo, wx.Panel):
                return hijo
        return None

    def test_nombres_y_orden_de_tab(self):
        dialogo = self._abrir()
        interactivos = [
            control for control in self._panel().GetChildren()
            if isinstance(control, (wx.TextCtrl, wx.Button))]
        self.assertEqual([control.GetName() for control in interactivos], [
            "Dirección de YouTube", "Reproducir ahora", "A continuación",
            "Agregar a la cola", "Cancelar"])

    def test_mnemonicos_unicos(self):
        dialogo = self._abrir()
        etiquetas = [
            control.GetLabel() for control in self._panel().GetChildren()
            if isinstance(control, (wx.StaticText, wx.Button))]
        mnemonicos = [etiqueta[etiqueta.index("&") + 1].lower()
                      for etiqueta in etiquetas if "&" in etiqueta]
        self.assertEqual(len(mnemonicos), len(set(mnemonicos)))

    def test_los_tres_botones_devuelven_su_modo(self):
        dialogo = self._abrir()
        dialogo.txt_enlace.SetValue("https://youtu.be/abc")
        for boton, modo in (
                (dialogo.btn_ahora, "ahora"),
                (dialogo.btn_continuacion, "continuacion"),
                (dialogo.btn_cola, "final")):
            with self.subTest(modo=modo):
                with mock.patch.object(dialogo, "EndModal"):
                    boton.GetEventHandler().ProcessEvent(
                        wx.CommandEvent(wx.EVT_BUTTON.typeId, boton.GetId()))
                self.assertEqual(dialogo.datos(), ("https://youtu.be/abc", modo))

    def test_direccion_vacia_no_devuelve_nada(self):
        dialogo = self._abrir()
        dialogo.txt_enlace.SetValue("   ")
        self.assertIsNone(dialogo.datos())

    def test_cancelar_no_devuelve_nada(self):
        with mock.patch.object(
                musica_dialogo_enlace.DialogoEnlace, "ShowModal",
                return_value=wx.ID_CANCEL):
            self.assertIsNone(musica_dialogo_enlace.pedir_enlace(None))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoEditorLista(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)

    def _abrir(self):
        self.dialogo = musica_editor_lista.DialogoEditorLista(None)
        return self.dialogo

    def _panel(self):
        for hijo in self.dialogo.GetChildren():
            if isinstance(hijo, wx.Panel):
                return hijo
        return None

    def test_cada_etiqueta_va_justo_antes_de_su_control(self):
        self._abrir()
        hijos = self._panel().GetChildren()
        for etiqueta, control in (
                ("&Nombre:", self.dialogo.txt_nombre),
                ("&Buscar:", self.dialogo.txt_buscar),
                ("C&anciones:", self.dialogo.lb_temas)):
            with self.subTest(etiqueta=etiqueta):
                posicion = hijos.index(control)
                self.assertGreater(posicion, 0)
                self.assertIsInstance(hijos[posicion - 1], wx.StaticText)
                self.assertEqual(hijos[posicion - 1].GetLabel(), etiqueta)

    def test_la_lista_y_los_botones_entran_en_el_cuadro(self):
        self._abrir()
        pedido = self.dialogo.GetSizer().GetMinSize()
        cliente = self.dialogo.GetClientSize()
        self.assertGreaterEqual(cliente.width, pedido.width)
        self.assertGreaterEqual(cliente.height, pedido.height)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaVigiaYExaminar(unittest.TestCase):
    """El aviso del vigía y el botón Examinar la carpeta."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta_listas = str(Path(self.tmp.name) / "listas")
        self.anuncios = []
        self._parche = mock.patch.object(
            musica_ventana, "anunciar",
            lambda texto, urgente=True: self.anuncios.append(texto))
        self._parche.start()
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            self.ventana._cancelar_temporizador()
            destruir(self.ventana)
        self._parche.stop()
        self.tmp.cleanup()

    def _abrir(self, control, abrir_listas=False):
        self.ventana = musica_ventana.VentanaMusica(
            None, control, abrir_listas=abrir_listas)
        return self.ventana

    def _crear_lista(self, nombre, temas=()):
        listas.guardar(self.carpeta_listas, nombre, temas)

    def test_el_boton_examinar_tiene_rotulo_nombre_y_tab(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.assertEqual(self.ventana.btn_examinar.GetLabel(),
                         "E&xaminar la carpeta")
        self.assertEqual(self.ventana.btn_examinar.GetName(),
                         "Examinar la carpeta")
        self.ventana.btn_examinar.SetFocus()
        self.ventana.btn_examinar.Navigate()
        self.assertIs(wx.Window.FindFocus(), self.ventana.btn_cerrar)

    def test_el_vigia_pone_al_dia_sin_perder_filtro_ni_seleccion(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz", "Blues"))
        self._abrir(control)
        self.ventana.txt_buscar.SetValue("blu")
        self.ventana.lb_temas.SetSelection(0)
        biblio = control._biblio
        biblio._temas = tuple(
            t for t in biblio._temas if t.titulo != "Jazz")
        self.ventana.refrescar_por_vigia()
        self.assertEqual(self.ventana.txt_buscar.GetValue(), "blu")
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Blues"])
        self.assertEqual(self.ventana.lb_colecciones.GetString(0),
                         "Biblioteca: 2")

    def test_el_vigia_conserva_el_tema_elegido_si_sigue_estando(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz", "Blues"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        biblio = control._biblio
        biblio._temas = biblio._temas + (
            Tema("C:/Musica/tango.mp3", "Tango"),)
        self.ventana.refrescar_por_vigia()
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Jazz", "Blues", "Tango"])
        self.assertEqual(self.ventana.lb_temas.GetSelection(), 1)

    def test_el_vigia_acerca_al_indice_si_el_tema_ya_no_esta(self):
        control = ControlFalso(
            biblioteca=_biblioteca_de("Rock", "Jazz", "Blues"))
        self._abrir(control)
        self.ventana.lb_temas.SetSelection(1)
        biblio = control._biblio
        biblio._temas = tuple(
            t for t in biblio._temas if t.titulo != "Jazz")
        self.ventana.refrescar_por_vigia()
        self.assertEqual(self.ventana.lb_temas.GetStrings(),
                         ["Rock", "Blues"])
        self.assertEqual(self.ventana.lb_temas.GetSelection(), 1)

    def test_el_vigia_con_una_lista_propia_no_toca_nada(self):
        temas = (Tema("C:/Musica/rock.mp3", "Rock"),)
        self._crear_lista("Mía", temas)
        control = ControlFalso(
            biblioteca=_biblioteca_de("Otra"),
            carpeta_listas=self.carpeta_listas,
            temas_listas={"Mía": temas})
        self._abrir(control, abrir_listas=True)
        biblio = control._biblio
        biblio._temas = biblio._temas + (
            Tema("C:/Musica/nueva.mp3", "Nueva"),)
        self.ventana.refrescar_por_vigia()
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Rock"])

    def test_el_vigia_no_mueve_el_foco_de_canciones(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        self.ventana.lb_temas.SetFocus()
        self.ventana.refrescar_por_vigia()
        self.assertIs(wx.Window.FindFocus(), self.ventana.lb_temas)

    def test_examinar_sin_carpeta_usa_el_aviso_de_hoy(self):
        control = ControlFalso(biblioteca=None)
        self._abrir(control)
        del self.anuncios[:]
        with mock.patch.object(control, "_carpeta", return_value=""):
            self.ventana.examinar_carpeta()
        self.assertEqual(self.anuncios, [anuncios.TEXTO_SIN_CARPETA])
        self.assertNotIn("reexaminar_carpeta", control.nombres())

    def test_examinar_anuncia_y_refresca_la_lista(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock", "Jazz"))
        control.datos_examen = (1, 2)
        self._abrir(control)
        del self.anuncios[:]
        biblio = control._biblio
        biblio._temas = (biblio._temas[0],)
        self.ventana.examinar_carpeta()
        self.assertIn(("reexaminar_carpeta",), control.llamadas)
        self.assertFalse(self.ventana._examinando)
        self.assertEqual(
            self.anuncios,
            ["Carpeta examinada: 1 canción nueva y 2 quitadas."])
        self.assertEqual(self.ventana.lb_temas.GetStrings(), ["Rock"])

    def test_examinar_sin_cambios_lo_dice(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        control.datos_examen = (0, 0)
        self._abrir(control)
        del self.anuncios[:]
        self.ventana.examinar_carpeta()
        self.assertEqual(self.anuncios,
                         ["Carpeta examinada: sin cambios."])

    def test_mientras_examina_otra_pulsacion_no_lanza_otro_hilo(self):
        control = ControlFalso(biblioteca=_biblioteca_de("Rock"))
        control.datos_examen = (0, 0)
        self._abrir(control)
        self.ventana._examinando = True
        self.ventana.examinar_carpeta()
        self.assertNotIn("reexaminar_carpeta", control.nombres())

    def test_con_la_ventana_destruida_refrescar_no_lanza(self):
        self._abrir(ControlFalso(biblioteca=_biblioteca_de("Rock")))
        ventana = self.ventana
        destruir(ventana)
        self.ventana = None
        ventana.refrescar_por_vigia()  # no debe lanzar


if __name__ == "__main__":
    unittest.main()
