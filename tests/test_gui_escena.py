"""Pruebas de la ventana Escena sin conectar con OBS."""

import threading
import unittest
from unittest import mock

import wx

from bellbird.obs import (
    disenos_escena, disenos_guardados, obs_capas, obs_disposicion)
from bellbird.obs.obs_escena import FilaFuente
from bellbird.ui import escena_disenos
from bellbird.ui import escena_menu_fuente
from bellbird.ui import escena_captura_ventana
from bellbird.ui import escena_pagina_audio
from bellbird.ui import escena_pagina_escena
from bellbird.ui import escena_pagina_fuentes
from bellbird.ui import escena_tamano
from bellbird.ui import gui_grabaciones
from bellbird.ui import obs_ventana
from bellbird.ui import gui_microfono
from bellbird.ui import mover_con_flechas
from bellbird.ui import operaciones_obs
from tests.test_gui_transmision import (
    Evento, EventoTecla, GestorFalso, HiloInmediato)
from tests.ventanas_prueba import app_de_prueba, destruir


def _items_del_menu(menu):
    for item in menu.GetMenuItems():
        submenu = item.GetSubMenu()
        if submenu is not None:
            yield from _items_del_menu(submenu)
        elif item.GetItemLabelText():
            yield item


class PrincipalFalsa:

    def __init__(self, preferido="Mic/Aux"):
        self._config = {"obs_microfono": preferido}


class GestorConexion(GestorFalso):

    def __init__(self, conectado=False):
        super().__init__()
        self._conectado = conectado
        self.veces_conectar = 0

    @property
    def conectado(self):
        return self._conectado

    def conectar(self):
        self.veces_conectar += 1
        self._conectado = True

    def escenas(self):
        if not self._conectado:
            raise RuntimeError("not connected")
        return super().escenas()


class GestorConCapas(GestorFalso):

    def __init__(self):
        super().__init__()
        self.orden = ["Cámara", "Chat en el vídeo", "Juego"]

    def fuentes(self, escena):
        if escena == "Principal":
            return tuple(self.orden)
        return super().fuentes(escena)

    def mover_capa(self, escena, movimiento, parada=None, *, fuente=""):
        self._llamar("mover_capa", (escena, movimiento), {"fuente": fuente})
        total = len(self.orden)
        elementos = [
            {"sceneItemId": indice, "sourceName": nombre,
             "sceneItemIndex": total - 1 - indice}
            for indice, nombre in enumerate(self.orden)]
        movio = obs_capas.mover(
            lambda *args: None, elementos, escena, fuente, movimiento, parada)
        frase = obs_capas.frase_de_movimiento(
            elementos, fuente, movimiento, movio)
        if movio:
            indice = self.orden.index(fuente)
            destino = obs_capas.indice_destino(
                elementos, fuente, movimiento)
            self.orden.pop(indice)
            self.orden.insert(total - 1 - destino, fuente)
        return movio, frase


def _asegurar_obs(probar_conexion, al_anunciar=None, parada=None):
    return probar_conexion()


class TestVentanaObs(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.anuncios = []
        self.categorias = []

        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)

        self.asegurar = mock.Mock(side_effect=_asegurar_obs)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(obs_ventana.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                              self.asegurar),
            mock.patch.object(obs_ventana, "anunciar", anunciar),
            mock.patch.object(escena_pagina_escena, "anunciar", anunciar),
            mock.patch.object(escena_pagina_fuentes, "anunciar", anunciar),
            mock.patch.object(escena_captura_ventana, "anunciar", anunciar),
            mock.patch.object(gui_microfono, "anunciar", anunciar),
            mock.patch.object(mover_con_flechas, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                              return_value=[]),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
            mock.patch.object(gui_microfono, "abrir_microfono_obs"),
        ]
        for parche in self.parches:
            parche.start()
        self.principal = PrincipalFalsa()
        self.gestor = GestorConCapas()
        self.dialogo = self._crear()
        self.anuncios.clear()
        self.categorias.clear()
        self.asegurar.reset_mock()

    def tearDown(self):
        for parche in reversed(self.parches):
            parche.stop()

    def _crear(self, gestor=None):
        dialogo = obs_ventana.VentanaObs(
            None, self.principal, gestor=self.gestor if gestor is None else gestor)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pulsar(self, boton):
        boton.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, boton.GetId()))

    def _elegir(self, lista):
        lista.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId, lista.GetId()))

    def _marcar(self, casilla, valor):
        casilla.SetValue(valor)
        casilla.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHECKBOX.typeId, casilla.GetId()))

    def _elegir_fuente(self, pagina, nombre):
        indice = next(i for i, fila in enumerate(pagina._filas)
                      if fila.nombre == nombre)
        pagina.lst_fuentes.SetSelection(indice)

    def _abrir_menu_de_fuente(self, pagina, al_elegir=None, marcada=None):
        etiquetas = []

        def falso_popup(menu):
            for item in _items_del_menu(menu):
                etiqueta = item.GetItemLabelText()
                etiquetas.append(etiqueta)
                if etiqueta == al_elegir:
                    evento = wx.CommandEvent(
                        wx.EVT_MENU.typeId, item.GetId())
                    if marcada is not None:
                        evento.SetInt(1 if marcada else 0)
                    item.GetMenu().ProcessEvent(evento)

        with mock.patch.object(pagina.lst_fuentes, "PopupMenu", falso_popup):
            pagina._mostrar_menu_fuente(pagina.lst_fuentes)
        return etiquetas

    def _abrir_menu_agregar(self, pagina, al_elegir=None):
        etiquetas = []

        def falso_popup(menu):
            for item in _items_del_menu(menu):
                etiqueta = item.GetItemLabelText()
                etiquetas.append(etiqueta)
                if etiqueta == al_elegir:
                    item.GetMenu().ProcessEvent(
                        wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId()))

        with mock.patch.object(pagina.btn_agregar, "PopupMenu", falso_popup):
            self._pulsar(pagina.btn_agregar)
        return etiquetas

    @staticmethod
    def _modal_con_seleccion(indice):
        def mostrar(dialogo):
            dialogo.cho_ventana.SetSelection(indice)
            return wx.ID_OK
        return mostrar

    def _cuadro_tamano(self, porcentaje_ancho=29, porcentaje_alto=69):
        dialogo = escena_tamano.TamanoFuenteDialog(
            self.dialogo, porcentaje_ancho, porcentaje_alto)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _nombres(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.Button,
                                 wx.CheckBox, wx.SpinCtrl, wx.ListBox)):
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres(hijo))
        return nombres

    def test_titulo_y_pestanas(self):
        self.assertEqual(self.dialogo.GetTitle(), "Panel de OBS")
        self.assertEqual(
            [self.dialogo.nb.GetPageText(i)
             for i in range(self.dialogo.nb.GetPageCount())],
            ["General", "Escena", "Transmisión", "Audio", "Grabación"])

    def test_al_abrir_la_escena_al_aire_la_lista_de_fuentes(self):
        self.anuncios.clear()
        dialogo = self._crear()
        pagina = dialogo._pagina_escena
        self.assertEqual(pagina.cho_escena.GetStringSelection(), "Principal")
        self.assertFalse(hasattr(pagina, "txt_descripcion"))
        self.assertEqual(dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])
        self.assertTrue(any(a.startswith("Escena: Principal.")
                            for a in self.anuncios))
        self.assertIs(dialogo.FindFocus(), pagina.cho_escena)

    def test_la_escena_al_aire_es_la_elegida(self):
        self.gestor.escena_resultante = "Juego"
        dialogo = self._crear()
        self.assertEqual(dialogo._pagina_escena.cho_escena.GetStringSelection(),
                         "Juego")
        self.assertEqual(dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
                         ["Captura"])
        self.assertEqual(dialogo._pagina_fuentes.fuente(), "Captura")

    def test_al_abrir_llama_al_asegurador_de_obs(self):
        self._crear()
        self.asegurar.assert_called_once()
        self.assertTrue(callable(self.asegurar.call_args.args[0]))
        self.assertTrue(callable(self.asegurar.call_args.kwargs["al_anunciar"]))

    def test_sin_conexion_conecta_antes_de_leer_aunque_obs_ya_corra(self):
        gestor = GestorConexion(conectado=False)
        with mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                               return_value=False) as asegurar:
            dialogo = self._crear(gestor=gestor)
        asegurar.assert_called_once()
        self.assertEqual(gestor.veces_conectar, 1)
        self.assertTrue(gestor.conectado)
        self.assertEqual(dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])

    def test_con_la_conexion_abierta_no_reconecta(self):
        gestor = GestorConexion(conectado=True)
        with mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                               return_value=False) as asegurar:
            dialogo = self._crear(gestor=gestor)
        asegurar.assert_called_once()
        self.assertEqual(gestor.veces_conectar, 0)
        self.assertEqual(dialogo._pagina_escena.cho_escena.GetStringSelection(),
                         "Principal")

    def test_elegir_otra_escena_recarga_sin_cambiarla_al_aire(self):
        self.gestor.poner_escena_al_aire = mock.Mock()
        self.anuncios.clear()
        pagina = self.dialogo._pagina_escena
        pagina.cho_escena.SetStringSelection("Juego")
        self._elegir(pagina.cho_escena)
        self.gestor.poner_escena_al_aire.assert_not_called()
        self.assertEqual(
            self.dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
            ["Captura"])
        self.assertEqual(
            self.anuncios,
            ["Escena: Juego. 1 fuente, de adelante hacia atrás."])

    def test_cambiar_escena_la_cambia_al_aire_y_anuncia(self):
        self.gestor.escena_resultante = "Juego"
        pagina = self.dialogo._pagina_escena
        pagina.cho_escena.SetStringSelection("Juego")
        self._pulsar(pagina.btn_cambiar)
        self.assertIn(("poner_escena_al_aire", "Juego"),
                      self.gestor.llamadas)
        self.assertIn("Escena actual: Juego", self.anuncios)

    def test_cada_accion_de_fuentes_llama_al_gestor(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_tamano, "pedir_tamano",
                               return_value=(50, None, "inferior-derecha")):
            pagina._posicion_tamano()
        self._abrir_menu_de_fuente(
            pagina, "Mostrar en la escena", marcada=False)
        self._abrir_menu_de_fuente(
            pagina, "Bloquear posición", marcada=True)
        self._abrir_menu_de_fuente(pagina, "Mover a la cima")
        self._pulsar(pagina.btn_restaurar)
        self.assertIn(("colocar", "Principal", "inferior-derecha"),
                      self.gestor.llamadas)
        self.assertIn(("redimensionar", "Principal", 800, 1078),
                      self.gestor.llamadas)
        self.assertIn(("mostrar", "Principal", False), self.gestor.llamadas)
        self.assertIn(("fijar", "Principal", True), self.gestor.llamadas)
        self.assertIn(("al_frente", "Principal"), self.gestor.llamadas)
        self.assertIn("Cambios deshechos", self.anuncios)

    def test_el_menu_de_la_fuente_tiene_sus_acciones_en_orden(self):
        pagina = self.dialogo._pagina_fuentes
        etiquetas = self._abrir_menu_de_fuente(pagina)
        self.assertEqual(
            etiquetas,
            ["Mostrar en la escena", "Bloquear posición",
             "Posición y tamaño…", "Mover a la cima", "Subir", "Bajar",
             "Mover al fondo"])

    def test_el_menu_marca_las_casillas_segun_la_fila(self):
        pagina = self.dialogo._pagina_fuentes
        fila = FilaFuente("Juego", "Juego", False, True)
        pagina._filas = (fila,)
        menu = escena_menu_fuente.menu_de_fuente(
            fila, mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        self.addCleanup(menu.Destroy)
        items = [item for item in menu.GetMenuItems()
                 if item.GetItemLabelText()]
        self.assertFalse(items[0].IsChecked())
        self.assertTrue(items[1].IsChecked())

    def test_el_submenu_ordenar_no_repite_letras_de_acceso(self):
        fila = FilaFuente("Juego", "Juego", True, False)
        menu = escena_menu_fuente.menu_de_fuente(
            fila, mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        self.addCleanup(menu.Destroy)
        ordenar = next(item.GetSubMenu() for item in menu.GetMenuItems()
                       if item.GetSubMenu() is not None)
        letras = [etiqueta[etiqueta.index("&") + 1].lower()
                  for etiqueta in (item.GetItemLabel()
                                   for item in ordenar.GetMenuItems())]
        self.assertEqual(len(set(letras)), len(letras))

    def test_cada_entrada_del_menu_llama_a_su_accion(self):
        pagina = self.dialogo._pagina_fuentes
        for etiqueta, movimiento in (
                ("Subir", "adelante"),
                ("Bajar", "atras"),
                ("Mover al fondo", "fondo")):
            self._abrir_menu_de_fuente(pagina, etiqueta)
            self.assertIn(("mover_capa", "Principal", movimiento),
                          self.gestor.llamadas)
        self._abrir_menu_de_fuente(pagina, "Mover a la cima")
        self.assertIn(("al_frente", "Principal"), self.gestor.llamadas)

    def test_la_tecla_aplicaciones_abre_el_menu_de_la_fila(self):
        pagina = self.dialogo._pagina_fuentes
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_WINDOWS_MENU
        with mock.patch.object(pagina, "_mostrar_menu_fuente") as mostrar:
            pagina.lst_fuentes.ProcessEvent(evento)
        mostrar.assert_called_once_with(pagina.lst_fuentes)

    def test_mayus_f10_abre_el_mismo_menu_de_la_fila(self):
        pagina = self.dialogo._pagina_fuentes
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_F10
        evento.SetShiftDown(True)
        with mock.patch.object(pagina, "_mostrar_menu_fuente") as mostrar:
            pagina.lst_fuentes.ProcessEvent(evento)
        mostrar.assert_called_once_with(pagina.lst_fuentes)

    def test_sin_seleccion_anuncia_y_no_abre_el_menu(self):
        pagina = self.dialogo._pagina_fuentes
        pagina.lst_fuentes.SetSelection(wx.NOT_FOUND)
        with mock.patch.object(pagina.lst_fuentes, "PopupMenu") as popup:
            pagina._mostrar_menu_fuente(pagina.lst_fuentes)
        popup.assert_not_called()
        self.assertIn("Sin selección", self.anuncios)

    def test_tamano_sin_seleccion_anuncia_y_no_abre_el_cuadro(self):
        pagina = self.dialogo._pagina_fuentes
        pagina.lst_fuentes.SetSelection(wx.NOT_FOUND)
        with mock.patch.object(escena_tamano, "pedir_tamano") as pedir:
            pagina._posicion_tamano()
        pedir.assert_not_called()
        self.assertIn("Sin selección", self.anuncios)

    def test_tamano_sin_lienzo_anuncia_y_no_abre_el_cuadro(self):
        pagina = self.dialogo._pagina_fuentes
        self.gestor.snap = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=460, alto=620)
        with mock.patch.object(escena_tamano, "pedir_tamano") as pedir:
            pagina._posicion_tamano()
        pedir.assert_not_called()
        self.assertIn(
            f"{pagina.fuente()} todavía no informa su tamaño.",
            self.anuncios)

    def test_tamano_abre_con_el_ultimo_tamano_de_la_fuente(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_tamano, "pedir_tamano",
                               return_value=None) as pedir:
            pagina._posicion_tamano()
        pedir.assert_called_once_with(pagina, 29, 69)

    def test_elegir_la_mitad_aplica_la_mitad_del_ancho_del_lienzo(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(pagina.lst_fuentes, "SetFocus") as foco, \
                mock.patch.object(escena_tamano, "pedir_tamano",
                                  return_value=(50, None, "")):
            pagina._posicion_tamano()
        self.assertIn(("redimensionar", "Principal", 800, 1078),
                      self.gestor.llamadas)
        foco.assert_called_once_with()

    def test_posicion_y_tamano_con_un_lugar_tambien_coloca(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_tamano, "pedir_tamano",
                               return_value=(50, None, "inferior-derecha")):
            pagina._posicion_tamano()
        self.assertIn(("redimensionar", "Principal", 800, 1078),
                      self.gestor.llamadas)
        self.assertIn(("colocar", "Principal", "inferior-derecha"),
                      self.gestor.llamadas)

    def test_cancelar_el_tamano_no_aplica_nada(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(pagina.lst_fuentes, "SetFocus"), \
                mock.patch.object(escena_tamano, "pedir_tamano",
                                  return_value=None):
            pagina._posicion_tamano()
        self.assertNotIn("redimensionar",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_mostrar_relee_la_lista_y_conserva_la_fila(self):
        pagina = self.dialogo._pagina_fuentes
        filas = tuple(
            FilaFuente(nombre, f"{nombre}, se ve", True, False)
            for nombre in self.gestor.fuentes("Principal"))
        with mock.patch.object(self.gestor, "filas_escena",
                               return_value=filas) as releer:
            self._abrir_menu_de_fuente(
                pagina, "Mostrar en la escena", marcada=False)
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        releer.assert_called_once_with("Principal")

    def test_mover_con_flechas_relee_la_lista(self):
        pagina = self.dialogo._pagina_fuentes
        filas = tuple(
            FilaFuente(nombre, f"{nombre}, movida", True, False)
            for nombre in self.gestor.fuentes("Principal"))
        self._pulsar(pagina.btn_ajuste)
        with mock.patch.object(self.gestor, "filas_escena",
                               return_value=filas) as releer:
            pagina._mover._mover(10, 0)
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        releer.assert_called_once_with("Principal")

    def test_aplicar_diseno_relee_la_lista(self):
        pagina = self.dialogo._pagina_fuentes
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Juego")
        filas = tuple(
            FilaFuente(nombre, f"{nombre}, con diseño", True, False)
            for nombre in self.gestor.fuentes("Principal"))
        with mock.patch.object(escena_disenos, "pedir_diseno",
                               return_value=("Diseño", diseno)), \
                mock.patch.object(disenos_guardados, "cargar",
                                  return_value=[]), \
                mock.patch.object(pagina.btn_diseno, "SetFocus"), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas) as releer:
            self._pulsar(pagina.btn_diseno)
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        releer.assert_called_once_with("Principal")

    def test_deshacer_relee_la_lista(self):
        pagina = self.dialogo._pagina_fuentes
        filas = tuple(
            FilaFuente(nombre, f"{nombre}, deshecha", True, False)
            for nombre in self.gestor.fuentes("Principal"))
        with mock.patch.object(self.gestor, "filas_escena",
                               return_value=filas) as releer:
            self._pulsar(pagina.btn_restaurar)
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        releer.assert_called_once_with("Principal")

    def test_el_boton_de_diseno_abre_con_las_fuentes_de_la_escena(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_disenos, "pedir_diseno",
                               return_value=None) as pedir, \
                mock.patch.object(disenos_guardados, "cargar",
                                  return_value=[]) as cargar, \
                mock.patch.object(pagina.btn_diseno, "SetFocus") as foco:
            self._pulsar(pagina.btn_diseno)
        cargar.assert_called_once_with()
        foco.assert_called_once_with()
        args = pedir.call_args.args
        self.assertIs(args[0], pagina)
        self.assertEqual([fuente.nombre for fuente in args[1]],
                         ["Cámara", "Juego", "Chat en el vídeo"])
        self.assertEqual([fuente.tipo for fuente in args[1]],
                         ["otra", "otra", "chat"])
        self.assertEqual(args[2], [])

    def test_cancelar_el_diseno_no_aplica_nada(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_disenos, "pedir_diseno",
                               return_value=None), \
                mock.patch.object(disenos_guardados, "cargar",
                                  return_value=[]), \
                mock.patch.object(escena_pagina_fuentes.aplicar_diseno,
                                  "aplicar_diseno") as aplicar, \
                mock.patch.object(pagina.btn_diseno, "SetFocus"):
            self._pulsar(pagina.btn_diseno)
        aplicar.assert_not_called()
        self.assertNotIn(("transformar", "Juego"),
                         self.gestor.fuentes_enviadas)

    def test_aceptar_el_diseno_lo_aplica_y_anuncia_el_resumen(self):
        pagina = self.dialogo._pagina_fuentes
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Juego")
        with mock.patch.object(escena_disenos, "pedir_diseno",
                               return_value=("Diseño", diseno)), \
                mock.patch.object(disenos_guardados, "cargar",
                                  return_value=[]), \
                mock.patch.object(pagina.btn_diseno, "SetFocus") as foco:
            self._pulsar(pagina.btn_diseno)
        self.assertIn(("transformar", "Juego"), self.gestor.fuentes_enviadas)
        self.assertIn(
            "Diseño aplicado: Diseño. Juego se ajusta a su lugar. "
            "No se movieron: Cámara, Chat en el vídeo.", self.anuncios)
        foco.assert_called_once_with()

    def test_sin_fuentes_para_un_diseno_anuncia_y_no_abre_el_cuadro(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(
                escena_pagina_fuentes.aplicar_diseno, "fuentes_de_escena",
                return_value=[disenos_escena.Fuente(
                    "Chat en el vídeo", "chat", 460, 620)]), \
                mock.patch.object(escena_disenos, "pedir_diseno") as pedir:
            self._pulsar(pagina.btn_diseno)
        pedir.assert_not_called()
        self.assertIn("La escena no tiene fuentes para un diseño.",
                      self.anuncios)

    def test_sin_escena_el_boton_de_diseno_anuncia_sin_seleccion(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(pagina, "_escena", return_value=""):
            self._pulsar(pagina.btn_diseno)
        self.assertIn("Sin selección", self.anuncios)

    def test_mover_anuncia_el_lugar_y_despues_la_descripcion(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Chat en el vídeo")
        self._abrir_menu_de_fuente(pagina, "Subir")
        aviso = next(anuncio for anuncio in self.anuncios
                     if anuncio.startswith("Chat en el vídeo: 1 de 3 en el orden."))
        self.assertIn("Chat en el vídeo.", aviso)

    def test_mover_en_el_extremo_anuncia_que_ya_esta_en_el_borde(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        self._abrir_menu_de_fuente(pagina, "Subir")
        self.assertIn("Cámara ya está en la cima.", self.anuncios)
        self._elegir_fuente(pagina, "Juego")
        self._abrir_menu_de_fuente(pagina, "Mover al fondo")
        self.assertIn("Juego ya está al fondo.", self.anuncios)

    def test_la_lista_fuente_queda_ordenada_y_con_la_misma_fuente(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Chat en el vídeo")
        self._abrir_menu_de_fuente(pagina, "Subir")
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         ["Chat en el vídeo", "Cámara", "Juego"])
        self.assertEqual(pagina.fuente(),
                         "Chat en el vídeo")

    def test_los_tres_movimientos_entran_en_deshacer(self):
        pagina = self.dialogo._pagina_fuentes
        for fuente, etiqueta in (("Cámara", "Subir"),
                                 ("Chat en el vídeo", "Bajar"),
                                 ("Juego", "Mover al fondo")):
            self._elegir_fuente(pagina, fuente)
            self._abrir_menu_de_fuente(pagina, etiqueta)
        self.gestor.llamadas.clear()
        self._pulsar(pagina.btn_restaurar)
        self.assertEqual(
            len([llamada for llamada in self.gestor.llamadas
                 if llamada[0] == "transformar"]), 3)

    def test_agregar_fuente_abre_un_menu_con_captura_y_camara(self):
        pagina = self.dialogo._pagina_fuentes
        self.assertEqual(
            self._abrir_menu_agregar(pagina),
            ["Captura de ventana…", "Cámara…"])

    def test_capturar_ventana_pide_las_ventanas_y_aplica_la_elegida(self):
        pagina = self.dialogo._pagina_fuentes
        filas = (
            FilaFuente("Captura de ventana", "Captura de ventana", True, False),
            FilaFuente("Chat en el vídeo", "Chat en el vídeo", True, False))
        elegida = self.gestor.opciones_ventana[1][1]
        with mock.patch.object(
                escena_captura_ventana.DialogoCapturarVentana, "ShowModal",
                self._modal_con_seleccion(1)), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas) as releer, \
                mock.patch.object(pagina.lst_fuentes, "SetFocus") as foco:
            self._abrir_menu_agregar(pagina, "Captura de ventana…")
        self.assertIn(("ventanas", "Principal"), self.gestor.llamadas)
        self.assertIn(
            ("usar_ventana", "Principal", elegida), self.gestor.llamadas)
        self.assertIn("Ahora se captura Champions, de juego.exe.",
                      self.anuncios)
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        releer.assert_called_once_with("Principal")
        foco.assert_called()

    def test_capturar_ventana_si_la_fuente_no_esta_elige_la_primera(self):
        pagina = self.dialogo._pagina_fuentes
        filas = (FilaFuente("Nueva", "Nueva", True, False),)
        with mock.patch.object(
                escena_captura_ventana.DialogoCapturarVentana, "ShowModal",
                self._modal_con_seleccion(0)), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas), \
                mock.patch.object(pagina.lst_fuentes, "SetFocus"):
            self._abrir_menu_agregar(pagina, "Captura de ventana…")
        self.assertEqual(pagina.fuente(), "Nueva")

    def test_capturar_ventana_sin_ventana_elegida_dice_lo_de_siempre(self):
        dialogo = escena_captura_ventana.DialogoCapturarVentana(
            self.dialogo, (("Charla, de otro.exe", "charla"),), "")
        self.addCleanup(destruir, dialogo)
        dialogo.EndModal = mock.Mock()
        dialogo._al_aceptar(None)
        dialogo.EndModal.assert_not_called()
        self.assertIn("Elige primero una ventana en Ventana.", self.anuncios)

    def test_el_cuadro_capturar_ventana_abre_con_la_capturada_elegida(self):
        dialogo = escena_captura_ventana.DialogoCapturarVentana(
            self.dialogo, self.gestor.opciones_ventana,
            self.gestor.actual_ventana)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetTitle(), "Capturar ventana")
        self.assertEqual(dialogo.cho_ventana.GetName(), "Ventana")
        self.assertEqual(dialogo.rotulo_ventana.GetLabel(), "&Ventana:")
        self.assertEqual(
            dialogo.cho_ventana.GetStrings(),
            ["Champions, de juego.exe", "Charla, de otro.exe"])
        self.assertEqual(dialogo.cho_ventana.GetStringSelection(),
                         "Champions, de juego.exe")
        self.assertIs(dialogo.FindFocus(), dialogo.cho_ventana)
        self.assertEqual(dialogo.btn_aceptar.GetLabel(), "&Aceptar")
        self.assertEqual(dialogo.btn_cancelar.GetLabel(), "&Cancelar")

    def test_escape_cancela_el_cuadro_de_ventana(self):
        dialogo = escena_captura_ventana.DialogoCapturarVentana(
            self.dialogo, self.gestor.opciones_ventana,
            self.gestor.actual_ventana)
        self.addCleanup(destruir, dialogo)
        dialogo.EndModal = mock.Mock()
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.KeyCode = wx.WXK_ESCAPE
        dialogo.ProcessEvent(evento)
        dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_al_cerrar_el_cuadro_el_foco_vuelve_a_fuentes(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(
                escena_captura_ventana.DialogoCapturarVentana, "ShowModal",
                return_value=wx.ID_CANCEL), \
                mock.patch.object(pagina.lst_fuentes, "SetFocus") as foco:
            self._abrir_menu_agregar(pagina, "Captura de ventana…")
        foco.assert_called_once_with()

    def test_camara_llama_a_agregar_camara_y_relee_elegiendo_la_primera(self):
        pagina = self.dialogo._pagina_fuentes
        filas = (FilaFuente("Cámara", "Cámara", True, False),
                 FilaFuente("Chat en el vídeo", "Chat en el vídeo", True,
                            False))

        def agregar(ventana, al_agregar):
            al_agregar(("Cámara",))

        with mock.patch.object(escena_pagina_fuentes.agregar_camara,
                               "agregar", side_effect=agregar) as llamada, \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas) as releer:
            self._abrir_menu_agregar(pagina, "Cámara…")
        self.assertIs(llamada.call_args.args[0], self.dialogo)
        self.assertTrue(callable(llamada.call_args.args[1]))
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         [fila.texto for fila in filas])
        self.assertEqual(pagina.fuente(), "Cámara")
        releer.assert_called_once_with("Principal")

    def test_silenciar_usa_el_preferido_del_principal(self):
        with mock.patch.object(
                gui_microfono.obs_entradas_audio, "alternar_microfono",
                return_value=("Micrófono silenciado", "Mic/Aux", True)) as alternar:
            self._marcar(self.dialogo._pagina_audio.chk_silenciar, True)
        alternar.assert_called_once_with(self.gestor, "Mic/Aux")
        self.assertIn("Micrófono silenciado", self.anuncios)
        self.assertTrue(self.dialogo._pagina_audio.chk_silenciar.GetValue())

    def test_elegir_microfono_abre_con_el_principal(self):
        with mock.patch.object(escena_pagina_audio.gui_microfono,
                               "abrir_microfono_obs") as abrir:
            self._pulsar(self.dialogo._pagina_audio.btn_microfono)
        self.assertIs(abrir.call_args.args[0], self.principal)
        self.assertTrue(callable(abrir.call_args.kwargs["al_cerrar"]))

    def test_cerrar_con_gestor_propio_lo_cierra(self):
        with mock.patch.object(obs_ventana, "GestorPanelObs",
                               return_value=self.gestor):
            dialogo = obs_ventana.VentanaObs(None, self.principal)
        self.addCleanup(destruir, dialogo)
        dialogo.EndModal = mock.Mock()
        dialogo._cerrar(Evento())
        self.assertIn(("cerrar",), self.gestor.llamadas)
        dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_cerrar_con_gestor_dado_no_lo_cierra(self):
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        self.assertNotIn(("cerrar",), self.gestor.llamadas)
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_si_obs_no_responde_lo_dice_en_general(self):
        self.anuncios.clear()
        dialogo = self._crear(gestor=GestorFalso(fallo=True))
        self.assertEqual(dialogo._pagina_general.texto(),
                         "OBS no está disponible")
        self.assertIn("OBS no está disponible", self.anuncios)

    def test_nombres_accesibles(self):
        escena = self.dialogo._pagina_escena
        self.assertEqual(escena.cho_escena.GetName(), "Escena")
        self.assertEqual(escena.btn_cambiar.GetName(), "Cambiar escena")
        self.assertEqual(escena.btn_imagen.GetName(), "Guardar imagen…")
        fuentes = self.dialogo._pagina_fuentes
        self.assertEqual(fuentes.lst_fuentes.GetName(), "Fuentes")
        self.assertEqual(fuentes.btn_ajuste.GetName(), "Mover con flechas")
        self.assertEqual(fuentes.btn_diseno.GetName(), "Aplicar diseño…")
        self.assertEqual(fuentes.btn_agregar.GetName(), "Agregar fuente…")
        self.assertEqual(fuentes.btn_restaurar.GetName(), "Deshacer cambios")
        audio = self.dialogo._pagina_audio
        self.assertEqual(audio.chk_silenciar.GetName(), "Silenciar micrófono")
        self.assertEqual(audio.chk_escuchar.GetName(), "Escuchar micrófono")
        self.assertEqual(audio.btn_microfono.GetName(), "Elegir micrófono…")
        self.assertEqual(audio.btn_probar.GetName(), "Probar micrófono")
        self.assertEqual(self.dialogo.btn_cerrar.GetName(), "Cerrar")

    def test_orden_de_tab_de_cada_pestana(self):
        self.assertEqual(self._nombres(self.dialogo._pagina_escena), [
            "Escena", "Cambiar escena", "Fuentes", "Mover con flechas",
            "Aplicar diseño…", "Agregar fuente…", "Deshacer cambios",
            "Guardar imagen…"])
        self.assertEqual(self._nombres(self.dialogo._pagina_audio), [
            "Silenciar micrófono", "Elegir micrófono…", "Probar micrófono",
            "Filtros del micrófono…", "Escuchar micrófono"])
        self.assertEqual(self._nombres(self.dialogo)[-1:], ["Cerrar"])

    def test_cuadro_tamano_abre_con_el_comun_actual(self):
        dialogo = self._cuadro_tamano(25, 33)
        self.assertEqual(dialogo.GetTitle(),
                         "Posición y tamaño de la fuente")
        self.assertEqual(dialogo.cho_posicion.GetStringSelection(),
                         "Donde está ahora")
        self.assertEqual(dialogo.cho_tamano.GetStringSelection(),
                         "Un cuarto del vídeo")
        self.assertEqual(dialogo.sp_ancho.GetName(),
                         "Ancho en porcentaje del vídeo")
        self.assertEqual(dialogo.sp_alto.GetName(),
                         "Alto en porcentaje del vídeo")
        self.assertTrue(dialogo.chk_proporcion.GetValue())
        self.assertFalse(dialogo.sp_ancho.IsShown())
        self.assertFalse(dialogo.sp_alto.IsShown())
        self.assertIs(dialogo.GetDefaultItem(), dialogo.btn_aceptar)

    def test_cuadro_tamano_personalizado_abre_con_el_porcentaje_actual(self):
        dialogo = self._cuadro_tamano(29, 69)
        self.assertEqual(dialogo.cho_tamano.GetStringSelection(),
                         "Personalizado")
        self.assertEqual(dialogo.sp_ancho.GetValue(), 29)
        self.assertEqual(dialogo.sp_alto.GetValue(), 69)
        self.assertTrue(dialogo.sp_ancho.IsShown())

    def test_elegir_personalizado_muestra_ancho(self):
        dialogo = self._cuadro_tamano(25, 33)
        dialogo.cho_tamano.SetStringSelection("Personalizado")
        self._elegir(dialogo.cho_tamano)
        self.assertTrue(dialogo.rotulo_ancho.IsShown())
        self.assertTrue(dialogo.sp_ancho.IsShown())

    def test_desmarcar_mantener_proporcion_muestra_alto(self):
        dialogo = self._cuadro_tamano(29, 69)
        self.assertFalse(dialogo.sp_alto.IsShown())
        self._marcar(dialogo.chk_proporcion, False)
        self.assertTrue(dialogo.rotulo_alto.IsShown())
        self.assertTrue(dialogo.sp_alto.IsShown())

    def test_elegir_la_mitad_del_video_devuelve_su_porcentaje(self):
        dialogo = self._cuadro_tamano(25, 33)
        dialogo.cho_tamano.SetStringSelection("La mitad del vídeo")
        self._elegir(dialogo.cho_tamano)
        self.assertFalse(dialogo.sp_ancho.IsShown())
        dialogo.EndModal = mock.Mock()
        dialogo._al_aceptar(None)
        dialogo.EndModal.assert_called_once_with(wx.ID_OK)
        self.assertEqual(dialogo.tamano_elegido(), (50, None))

    def test_aceptar_en_el_cuadro_devuelve_los_porcentajes(self):
        dialogo = self._cuadro_tamano(29, 69)
        dialogo.sp_ancho.SetValue(80)
        self._marcar(dialogo.chk_proporcion, False)
        dialogo.sp_alto.SetValue(50)
        dialogo.EndModal = mock.Mock()
        dialogo._al_aceptar(None)
        dialogo.EndModal.assert_called_once_with(wx.ID_OK)
        self.assertEqual(dialogo.tamano_elegido(), (80, 50))

    def test_aceptar_con_un_lugar_devuelve_el_anclaje(self):
        dialogo = self._cuadro_tamano(29, 69)
        dialogo.cho_posicion.SetStringSelection("Abajo a la derecha")
        dialogo.EndModal = mock.Mock()
        dialogo._al_aceptar(None)
        self.assertEqual(dialogo.anclaje_elegido(), "inferior-derecha")

    def test_cancelar_en_el_cuadro_no_devuelve_tamano(self):
        dialogo = self._cuadro_tamano()
        dialogo.EndModal = mock.Mock()
        dialogo._al_cancelar(None)
        dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)
        self.assertIsNone(dialogo.tamano_elegido())

    def test_escape_cierra_el_cuadro_sin_tamano(self):
        dialogo = self._cuadro_tamano()
        dialogo.EndModal = mock.Mock()
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.KeyCode = wx.WXK_ESCAPE
        dialogo.ProcessEvent(evento)
        dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)
        self.assertIsNone(dialogo.tamano_elegido())

    def test_escape_durante_el_ajuste_lo_deshace_sin_cerrar(self):
        self.dialogo.EndModal = mock.Mock()
        pagina = self.dialogo._pagina_fuentes
        self._pulsar(pagina.btn_ajuste)
        self.assertTrue(pagina._mover.en_curso)
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.KeyCode = wx.WXK_ESCAPE
        self.dialogo.GetEventHandler().ProcessEvent(evento)
        self.dialogo.EndModal.assert_not_called()
        self.assertFalse(pagina._mover.en_curso)
        self.assertIn(("posicionar", "Principal", 32, 18, 5),
                      self.gestor.llamadas)
        self.assertIn("Movimiento deshecho", self.anuncios)

    def test_escape_cierra(self):
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._al_tecla(EventoTecla(wx.WXK_ESCAPE))
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_el_pie_solo_tiene_cerrar(self):
        self.assertFalse(hasattr(self.dialogo, "btn_ayuda"))
        self.assertTrue(hasattr(self.dialogo, "btn_cerrar"))


if __name__ == "__main__":
    unittest.main()
