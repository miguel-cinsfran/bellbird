"""Pruebas de la ventana Escena sin conectar con OBS."""

import threading
import unittest
from unittest import mock

import wx

from guyrapu.obs import (
    disenos_escena, disenos_guardados, fuentes_obs, obs_capas, obs_cliente,
    obs_disposicion)
from guyrapu.obs.obs_escena import FilaFuente
from guyrapu.ui import escena_acciones_fuente
from guyrapu.ui import escena_agregar_fuente
from guyrapu.ui import escena_disenos
from guyrapu.ui import escena_edicion_fuente
from guyrapu.ui import escena_menu_fuente
from guyrapu.ui import escena_captura_ventana
from guyrapu.ui import escena_pagina_audio
from guyrapu.ui import escena_pagina_escena
from guyrapu.ui import escena_pagina_fuentes
from guyrapu.ui import escena_propiedades
from guyrapu.ui import escena_tamano
from guyrapu.ui import gui_grabaciones
from guyrapu.ui import obs_ventana
from guyrapu.ui import gui_microfono
from guyrapu.ui import mover_con_flechas
from guyrapu.ui import operaciones_obs
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
        self.escenas_por_nombre = {
            "Principal": self.orden,
            "Juego": ["Captura"],
        }
        self.peticiones = []
        self.fallo_peticion = None

    def escenas(self):
        return tuple(self.escenas_por_nombre)

    def escena_al_aire(self):
        return self.escena_resultante

    def poner_escena_al_aire(self, escena, parada=None):
        self.llamadas.append(("poner_escena_al_aire", escena))
        self.escena_resultante = escena
        return escena

    def fuentes(self, escena):
        return tuple(self.escenas_por_nombre.get(escena, ()))

    def usar_ventana(self, escena, valor, parada=None, nombre=""):
        self.llamadas.append(("usar_ventana", escena, valor))
        return "Ahora se captura Champions, de juego.exe."

    def elementos(self, escena, parada=None):
        return [{"sceneItemId": indice + 1, "sourceName": nombre,
                 "sceneItemIndex": indice, "sceneItemEnabled": True,
                 "sceneItemTransform": {
                     "positionX": 32, "positionY": 18, "alignment": 5,
                     "scaleX": 1, "scaleY": 1}}
                for indice, nombre in enumerate(self.fuentes(escena))]

    def _pedir(self, tipo, datos=None, parada=None):
        if self.fallo_peticion is not None:
            raise self.fallo_peticion
        datos = datos or {}
        self.peticiones.append((tipo, dict(datos)))
        if tipo == "CreateScene":
            self.escenas_por_nombre.setdefault(datos["sceneName"], [])
            return {}
        if tipo == "SetSceneName":
            return self._pedir_set_scene_name(datos)
        if tipo == "RemoveScene":
            return self._pedir_remove_scene(datos)
        if tipo == "GetSceneItemList":
            return {"sceneItems": self.elementos(datos["sceneName"], parada)}
        if tipo == "DuplicateSceneItem":
            return self._pedir_duplicate(datos)
        return {}

    def _pedir_set_scene_name(self, datos):
        antes = datos["sceneName"]
        nombre = datos["newSceneName"]
        self.escenas_por_nombre[nombre] = self.escenas_por_nombre.pop(antes)
        if self.escena_resultante == antes:
            self.escena_resultante = nombre
        return {}

    def _pedir_remove_scene(self, datos):
        nombre = datos["sceneName"]
        self.escenas_por_nombre.pop(nombre, None)
        if self.escena_resultante == nombre and self.escenas_por_nombre:
            self.escena_resultante = next(iter(self.escenas_por_nombre))
        return {}

    def _pedir_duplicate(self, datos):
        origen = self.escenas_por_nombre.get(datos["sceneName"], [])
        destino = self.escenas_por_nombre.setdefault(
            datos["destinationSceneName"], [])
        indice = datos["sceneItemId"] - 1
        if not 0 <= indice < len(origen):
            return {}
        destino.append(origen[indice])
        return {"sceneItemId": len(destino)}

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

        self.sonar = mock.Mock()

        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)

        def avisar(texto, sonido=None, *, error=False):
            anunciar(texto)
            if sonido:
                self.sonar.reproducir(sonido)

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
            mock.patch.object(escena_agregar_fuente, "anunciar", anunciar),
            mock.patch.object(escena_acciones_fuente, "anunciar", anunciar),
            mock.patch.object(escena_edicion_fuente, "anunciar", anunciar),
            mock.patch.object(escena_captura_ventana, "anunciar", anunciar),
            mock.patch.object(gui_microfono, "anunciar", anunciar),
            mock.patch.object(mover_con_flechas, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "avisar", avisar),
            mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                              return_value=[]),
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

    def _elegir_escena(self, pagina, nombre):
        indice = next(i for i, (escena, _cantidad)
                      in enumerate(pagina._escenas) if escena == nombre)
        pagina.lst_escenas.SetSelection(indice)
        pagina.lst_escenas.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_LISTBOX.typeId,
                            pagina.lst_escenas.GetId()))

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

    def _menu_de_escena(self, pagina, al_elegir=None):
        etiquetas = []
        textos = []

        def falso_popup(menu):
            for item in _items_del_menu(menu):
                etiquetas.append(item.GetItemLabelText())
                textos.append(item.GetItemLabel())
                if item.GetItemLabelText() == al_elegir:
                    item.GetMenu().ProcessEvent(
                        wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId()))

        with mock.patch.object(pagina.lst_escenas, "PopupMenu", falso_popup):
            pagina._mostrar_menu(pagina.lst_escenas)
        return etiquetas, textos

    def _dialogo_de_nombre(self, valores):
        creados = []

        class Dialogo:

            def __init__(self, padre, mensaje, titulo, value=""):
                self.mensaje = mensaje
                self.titulo = titulo
                self.value = value
                creados.append(self)

            def ShowModal(self):
                return wx.ID_OK

            def GetValue(self):
                return valores.pop(0)

            def Destroy(self):
                pass

        return mock.patch.object(
            escena_pagina_escena.wx, "TextEntryDialog", Dialogo), creados

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
        self.assertEqual(pagina.escena(), "Principal")
        self.assertFalse(hasattr(pagina, "txt_descripcion"))
        self.assertEqual(
            pagina.lst_escenas.GetStrings(),
            ["Principal, escena actual, 3 fuentes", "Juego, 1 fuente"])
        self.assertEqual(dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])
        self.assertTrue(any(a.startswith("Escena: Principal.")
                            for a in self.anuncios))
        self.assertIs(dialogo.FindFocus(), pagina.lst_escenas)

    def test_la_escena_al_aire_es_la_elegida(self):
        self.gestor.escena_resultante = "Juego"
        dialogo = self._crear()
        self.assertEqual(dialogo._pagina_escena.escena(), "Juego")
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
        self.assertEqual(dialogo._pagina_escena.escena(), "Principal")

    def test_elegir_otra_escena_recarga_sin_cambiarla_al_aire(self):
        self.gestor.poner_escena_al_aire = mock.Mock()
        self.anuncios.clear()
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Juego")
        self.gestor.poner_escena_al_aire.assert_not_called()
        self.assertEqual(
            self.dialogo._pagina_fuentes.lst_fuentes.GetStrings(),
            ["Captura"])
        self.assertEqual(
            self.anuncios,
            ["Escena: Juego. 1 fuente, de adelante hacia atrás."])

    def test_cambiar_escena_la_cambia_al_aire_y_anuncia(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Juego")
        self._pulsar(pagina.btn_cambiar)
        self.assertIn(("poner_escena_al_aire", "Juego"),
                      self.gestor.llamadas)
        self.assertIn("Escena actual: Juego", self.anuncios)
        self.assertEqual(
            pagina.lst_escenas.GetStrings(),
            ["Principal, 3 fuentes", "Juego, escena actual, 1 fuente"])

    def test_cambiar_escena_a_la_actual_avisa_y_no_hace_nada(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Principal")
        self._pulsar(pagina.btn_cambiar)
        self.assertNotIn(
            ("poner_escena_al_aire", "Principal"), self.gestor.llamadas)
        self.assertIn(
            "Principal ya es la escena actual.", self.anuncios)

    def test_agregar_escena_pide_el_nombre_y_la_deja_elegida(self):
        pagina = self.dialogo._pagina_escena
        with mock.patch.object(pagina, "_pedir_nombre",
                               return_value="Charla"):
            self._pulsar(pagina.btn_agregar)
        self.assertIn(("CreateScene", {"sceneName": "Charla"}),
                      self.gestor.peticiones)
        self.assertIn("Escena Charla agregada.", self.anuncios)
        self.assertEqual(pagina.escena(), "Charla")
        self.assertIn("Charla, sin fuentes", pagina.lst_escenas.GetStrings())
        self.assertEqual(self.gestor.escena_resultante, "Principal")
        self.assertIs(self.dialogo.FindFocus(), pagina.lst_escenas)

    def test_agregar_escena_propone_el_primer_numero_libre(self):
        pagina = self.dialogo._pagina_escena
        parche, creados = self._dialogo_de_nombre(["Escena 1"])
        with parche:
            self._pulsar(pagina.btn_agregar)
        self.assertEqual(creados[0].mensaje, "Nombre de la escena:")
        self.assertEqual(creados[0].titulo, "Agregar escena")
        self.assertEqual(creados[0].value, "Escena 1")

    def test_cambiar_nombre_relee_con_la_escena_elegida(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Juego")
        with mock.patch.object(pagina, "_pedir_nombre",
                               return_value="Charla"):
            pagina._cambiar_nombre()
        self.assertIn(("SetSceneName", {"sceneName": "Juego",
                                        "newSceneName": "Charla"}),
                      self.gestor.peticiones)
        self.assertIn("Escena Juego cambiada a Charla.", self.anuncios)
        self.assertEqual(pagina.escena(), "Charla")
        self.assertIn("Charla, 1 fuente", pagina.lst_escenas.GetStrings())
        self.assertIs(self.dialogo.FindFocus(), pagina.lst_escenas)

    def test_cambiar_nombre_abre_con_el_nombre_actual(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Juego")
        parche, creados = self._dialogo_de_nombre(["Juego"])
        with parche:
            pagina._cambiar_nombre()
        self.assertEqual(creados[0].mensaje, "Nombre de la escena:")
        self.assertEqual(creados[0].titulo, "Cambiar nombre")
        self.assertEqual(creados[0].value, "Juego")

    def test_duplicar_crea_la_copia_con_las_mismas_fuentes(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Principal")
        pagina._duplicar()
        self.assertEqual(
            self.gestor.escenas_por_nombre["Principal - copia"],
            ["Cámara", "Chat en el vídeo", "Juego"])
        self.assertEqual(pagina.escena(), "Principal - copia")
        self.assertIn("Escena Principal - copia agregada.", self.anuncios)
        self.assertIn("Principal - copia, 3 fuentes",
                      pagina.lst_escenas.GetStrings())

    def test_eliminar_pregunta_y_deja_la_siguiente_elegida(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Juego")
        with mock.patch.object(pagina, "_confirmar_eliminar",
                               return_value=True):
            pagina._eliminar()
        self.assertIn(("RemoveScene", {"sceneName": "Juego"}),
                      self.gestor.peticiones)
        self.assertNotIn("Juego", self.gestor.escenas_por_nombre)
        self.assertEqual(pagina.escena(), "Principal")
        self.assertIn("Escena Juego eliminada.", self.anuncios)

    def test_eliminar_la_unica_escena_avisa_sin_preguntar(self):
        self.gestor.escenas_por_nombre = {"Principal": self.gestor.orden}
        self.gestor.escena_resultante = "Principal"
        dialogo = self._crear()
        pagina = dialogo._pagina_escena
        self.anuncios.clear()
        with mock.patch.object(pagina, "_confirmar_eliminar") as confirmar:
            pagina._eliminar()
        confirmar.assert_not_called()
        self.assertIn("No se puede eliminar la única escena.", self.anuncios)

    def test_eliminar_pregunta_con_eliminar_y_cancelar(self):
        pagina = self.dialogo._pagina_escena
        with mock.patch.object(
                escena_pagina_escena.confirmar, "preguntar",
                return_value=True) as preguntar:
            self.assertTrue(pagina._confirmar_eliminar("Juego"))
        preguntar.assert_called_once_with(
            pagina, "¿Eliminar la escena Juego?", "Eliminar escena",
            "&Eliminar", "&Cancelar", predeterminado_si=False)

    def test_un_nombre_vacio_no_crea_nada(self):
        pagina = self.dialogo._pagina_escena
        parche, _creados = self._dialogo_de_nombre([""])
        with parche:
            pagina._agregar()
        self.assertNotIn("CreateScene",
                         [tipo for tipo, _datos in self.gestor.peticiones])
        self.assertEqual(len(self.gestor.escenas_por_nombre), 2)

    def test_un_nombre_repetido_avisa_y_vuelve_a_pedirlo(self):
        pagina = self.dialogo._pagina_escena
        parche, creados = self._dialogo_de_nombre(["Juego", "Charla"])
        with parche:
            self.assertEqual(
                pagina._pedir_nombre("Agregar escena", "Escena 3"),
                "Charla")
        self.assertEqual(len(creados), 2)
        self.assertIn("Ya hay una escena con ese nombre.", self.anuncios)

    def test_el_menu_de_la_escena_tiene_sus_acciones_en_orden(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Principal")
        etiquetas, textos = self._menu_de_escena(pagina)
        self.assertEqual(
            etiquetas,
            ["Cambiar escena", "Cambiar nombre…", "Duplicar", "Eliminar",
             "Guardar imagen…"])
        self.assertEqual(
            [texto.split("\t")[-1] for texto in textos[:4]],
            ["Enter", "F2", "Ctrl+D", "Del"])
        self.assertEqual(textos[4], "&Guardar imagen…")

    def test_cada_entrada_del_menu_de_la_escena_llama_a_su_accion(self):
        pagina = self.dialogo._pagina_escena
        self._elegir_escena(pagina, "Principal")
        for etiqueta, accion in (
                ("Cambiar escena", "_cambiar_al_aire"),
                ("Cambiar nombre…", "_cambiar_nombre"),
                ("Duplicar", "_duplicar"),
                ("Eliminar", "_eliminar"),
                ("Guardar imagen…", "_guardar_imagen")):
            with mock.patch.object(pagina, accion) as llamada:
                self._menu_de_escena(pagina, etiqueta)
            llamada.assert_called_once_with()

    def test_las_teclas_de_la_lista_ejecutan_las_acciones(self):
        pagina = self.dialogo._pagina_escena
        for tecla, accion, control in (
                (wx.WXK_RETURN, "cambiar", False),
                (wx.WXK_F2, "renombrar", False),
                (ord("D"), "duplicar", True),
                (wx.WXK_DELETE, "eliminar", False)):
            llamada = mock.Mock()
            with mock.patch.dict(pagina._acciones, {accion: llamada}):
                evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
                evento.KeyCode = tecla
                evento.SetControlDown(control)
                pagina.lst_escenas.ProcessEvent(evento)
            llamada.assert_called_once_with()

    def test_la_tecla_aplicaciones_abre_el_menu_de_la_escena(self):
        pagina = self.dialogo._pagina_escena
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_WINDOWS_MENU
        with mock.patch.object(pagina, "_mostrar_menu") as mostrar:
            pagina.lst_escenas.ProcessEvent(evento)
        mostrar.assert_called_once_with(pagina.lst_escenas)

    def test_mayus_f10_abre_el_mismo_menu_de_la_escena(self):
        pagina = self.dialogo._pagina_escena
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_F10
        evento.SetShiftDown(True)
        with mock.patch.object(pagina, "_mostrar_menu") as mostrar:
            pagina.lst_escenas.ProcessEvent(evento)
        mostrar.assert_called_once_with(pagina.lst_escenas)

    def test_guardar_imagen_sale_de_la_pestana_y_usa_la_escena_elegida(self):
        pagina = self.dialogo._pagina_escena
        self.assertFalse(hasattr(pagina, "btn_imagen"))
        self._elegir_escena(pagina, "Juego")

        class Dialogo:

            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def ShowModal(self):
                return wx.ID_OK

            def GetPath(self):
                return "C:/temporal/escena.png"

        with mock.patch.object(
                escena_pagina_escena.wx, "FileDialog", Dialogo), \
                mock.patch.object(
                    escena_pagina_escena.consultas_transmision,
                    "capturar") as capturar:
            pagina._guardar_imagen()
        capturar.assert_called_once_with(
            self.gestor, "Juego", "", "C:/temporal/escena.png")
        self.assertIn("Imagen guardada", self.anuncios)

    def test_un_fallo_de_obs_avisa_con_su_sonido_y_no_cambia_la_lista(self):
        pagina = self.dialogo._pagina_escena
        antes = pagina.lst_escenas.GetStrings()
        self.gestor.fallo_peticion = obs_cliente.ObsError("OBS no respondió")
        with mock.patch.object(pagina, "_pedir_nombre",
                               return_value="Charla"):
            self._pulsar(pagina.btn_agregar)
        self.assertEqual(pagina.lst_escenas.GetStrings(), antes)
        self.assertIn("OBS no respondió", self.anuncios)
        self.sonar.reproducir.assert_any_call("error")

    def test_cada_accion_de_fuentes_llama_al_gestor(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(escena_tamano, "pedir_tamano",
                               return_value=(50, None, "inferior-derecha")):
            pagina._posicion_tamano()
        self._abrir_menu_de_fuente(
            pagina, "Mostrar en la escena", marcada=False)
        self._abrir_menu_de_fuente(
            pagina, "Bloquear posición", marcada=True)
        self._abrir_menu_de_fuente(pagina, "Traer al frente")
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
             "Propiedades…", "Cambiar nombre…", "Duplicar", "Eliminar",
             "Tamaño y posición…", "Mover con flechas",
             "Centrar en el vídeo", "Ajustar al vídeo", "Llenar el vídeo",
             "Voltear horizontalmente", "Voltear verticalmente",
             "Girar a la derecha", "Girar a la izquierda",
             "Restablecer tamaño y posición",
             "Traer al frente", "Traer adelante", "Enviar atrás",
             "Enviar al fondo"])

    def test_el_menu_marca_las_casillas_segun_la_fila(self):
        pagina = self.dialogo._pagina_fuentes
        fila = FilaFuente("Juego", "Juego", False, True)
        pagina._filas = (fila,)
        menu = escena_menu_fuente.menu_de_fuente(fila, mock.Mock())
        self.addCleanup(menu.Destroy)
        items = [item for item in menu.GetMenuItems()
                 if item.GetItemLabelText()]
        self.assertFalse(items[0].IsChecked())
        self.assertTrue(items[1].IsChecked())

    def test_el_submenu_ordenar_no_repite_letras_de_acceso(self):
        fila = FilaFuente("Juego", "Juego", True, False)
        menu = escena_menu_fuente.menu_de_fuente(fila, mock.Mock())
        self.addCleanup(menu.Destroy)
        ordenar = next(item.GetSubMenu() for item in menu.GetMenuItems()
                       if item.GetItemLabelText() == "Ordenar")
        letras = [etiqueta[etiqueta.index("&") + 1].lower()
                  for etiqueta in (item.GetItemLabel()
                                   for item in ordenar.GetMenuItems())]
        self.assertEqual(len(set(letras)), len(letras))

    def test_cada_entrada_del_menu_llama_a_su_accion(self):
        pagina = self.dialogo._pagina_fuentes
        for etiqueta, movimiento in (
                ("Traer adelante", "adelante"),
                ("Enviar atrás", "atras"),
                ("Enviar al fondo", "fondo")):
            self._abrir_menu_de_fuente(pagina, etiqueta)
            self.assertIn(("mover_capa", "Principal", movimiento),
                          self.gestor.llamadas)
        self._abrir_menu_de_fuente(pagina, "Traer al frente")
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
        self._elegir_fuente(pagina, "Chat en el vídeo")
        pagina._mover.iniciar()
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
        self._abrir_menu_de_fuente(pagina, "Traer adelante")
        aviso = next(anuncio for anuncio in self.anuncios
                     if anuncio.startswith("Chat en el vídeo: 1 de 3 en el orden."))
        self.assertIn("Chat en el vídeo.", aviso)

    def test_mover_en_el_extremo_anuncia_que_ya_esta_en_el_borde(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        self._abrir_menu_de_fuente(pagina, "Traer adelante")
        self.assertIn("Cámara ya está en la cima.", self.anuncios)
        self._elegir_fuente(pagina, "Juego")
        self._abrir_menu_de_fuente(pagina, "Enviar al fondo")
        self.assertIn("Juego ya está al fondo.", self.anuncios)

    def test_la_lista_fuente_queda_ordenada_y_con_la_misma_fuente(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Chat en el vídeo")
        self._abrir_menu_de_fuente(pagina, "Traer adelante")
        self.assertEqual(pagina.lst_fuentes.GetStrings(),
                         ["Chat en el vídeo", "Cámara", "Juego"])
        self.assertEqual(pagina.fuente(),
                         "Chat en el vídeo")

    def test_los_tres_movimientos_entran_en_deshacer(self):
        pagina = self.dialogo._pagina_fuentes
        for fuente, etiqueta in (("Cámara", "Traer adelante"),
                                 ("Chat en el vídeo", "Enviar atrás"),
                                 ("Juego", "Enviar al fondo")):
            self._elegir_fuente(pagina, fuente)
            self._abrir_menu_de_fuente(pagina, etiqueta)
        self.gestor.llamadas.clear()
        self._pulsar(pagina.btn_restaurar)
        self.assertEqual(
            len([llamada for llamada in self.gestor.llamadas
                 if llamada[0] == "transformar"]), 3)

    def test_agregar_fuente_abre_el_menu_con_los_ocho_tipos(self):
        pagina = self.dialogo._pagina_fuentes
        self.assertEqual(
            self._abrir_menu_agregar(pagina),
            ["Cámara…", "Captura de pantalla…", "Captura de ventana…",
             "Captura de juego…", "Imagen…", "Archivo multimedia…",
             "Texto…", "Fuente de otra escena…"])

    def test_capturar_ventana_pide_las_ventanas_y_aplica_la_elegida(self):
        pagina = self.dialogo._pagina_fuentes
        filas = (
            FilaFuente("Captura de ventana", "Captura de ventana", True, False),
            FilaFuente("Chat en el vídeo", "Chat en el vídeo", True, False))
        elegida = self.gestor.opciones_ventana[1][1]
        with mock.patch.object(
                escena_agregar_fuente, "_pedir_nombre",
                return_value="Captura de ventana"), \
                mock.patch.object(
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
                escena_agregar_fuente, "_pedir_nombre",
                return_value="Captura de ventana"), \
                mock.patch.object(
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
                escena_agregar_fuente, "_pedir_nombre",
                return_value="Captura de ventana"), \
                mock.patch.object(
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

        def agregar(ventana, al_agregar, al_pedir_nombre=None):
            al_agregar(("Cámara",))

        with mock.patch.object(escena_agregar_fuente.agregar_camara,
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

    def test_el_cuadro_de_pantalla_vacio_avisa_y_deshabilita_aceptar(self):
        dialogo = escena_propiedades.DialogoEleccion(
            self.dialogo, "Captura de pantalla", "DialogoPantalla",
            "&Pantalla:", (), "", "No hay pantallas para capturar.")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.aviso_vacio.GetLabel(),
                         "No hay pantallas para capturar.")
        self.assertFalse(dialogo.btn_aceptar.IsEnabled())
        self.assertIs(dialogo.FindFocus(), dialogo.btn_cancelar)

    def test_el_cuadro_de_juego_oculta_la_ventana_y_enfoca_el_modo(self):
        dialogo = escena_propiedades.DialogoJuego(
            self.dialogo, (("Champions", "champions"),),
            {"modo": "window", "ventana": "champions"})
        self.addCleanup(destruir, dialogo)
        self.assertTrue(dialogo.cho_ventana.IsShown())
        dialogo.cho_modo.SetSelection(0)
        dialogo.cho_modo.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId, dialogo.cho_modo.GetId()))
        self.assertFalse(dialogo.cho_ventana.IsShown())
        self.assertTrue(dialogo.btn_aceptar.IsEnabled())

    def test_el_cuadro_de_juego_sin_ventanas_deshabilita_solo_una_ventana(
            self):
        dialogo = escena_propiedades.DialogoJuego(
            self.dialogo, (), {"modo": "window"})
        self.addCleanup(destruir, dialogo)
        self.assertTrue(dialogo.aviso_vacio.IsShown())
        self.assertFalse(dialogo.btn_aceptar.IsEnabled())
        dialogo.cho_modo.SetSelection(0)
        dialogo.cho_modo.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId, dialogo.cho_modo.GetId()))
        self.assertFalse(dialogo.aviso_vacio.IsShown())
        self.assertTrue(dialogo.btn_aceptar.IsEnabled())

    def test_el_cuadro_de_texto_abre_con_72_y_su_rango(self):
        dialogo = escena_propiedades.DialogoTexto(self.dialogo, {})
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.spin_tamano.GetValue(), 72)
        self.assertEqual(dialogo.spin_tamano.GetMin(), 8)
        self.assertEqual(dialogo.spin_tamano.GetMax(), 300)
        self.assertIs(dialogo.FindFocus(), dialogo.txt_texto)

    def test_el_cuadro_de_archivo_avisa_si_no_existe_y_no_cierra(self):
        dialogo = escena_propiedades.DialogoArchivo(
            self.dialogo, "imagen", {"archivo": "C:/no-existe.png"})
        self.addCleanup(destruir, dialogo)
        dialogo.EndModal = mock.Mock()
        with mock.patch.object(escena_propiedades, "anunciar") as anunciar:
            dialogo._al_aceptar(None)
        dialogo.EndModal.assert_not_called()
        anunciar.assert_called_once_with("Elige un archivo que exista.")

    def test_silenciar_usa_la_fuente_de_la_fila(self):
        pagina = self.dialogo._pagina_audio
        pagina._poner_filas((("Mic/Aux", False, ()),), "Mic/Aux")
        with mock.patch.object(
                escena_pagina_audio.filtros_microfono, "leer_filtros_de",
                return_value={"Mic/Aux": ()}), \
                mock.patch.object(
                    escena_pagina_audio.filtros_microfono, "leer_filtros",
                    return_value=()):
            self._marcar(pagina.chk_silenciar, True)
        self.assertIn(("alternar_silencio", "Mic/Aux"), self.gestor.llamadas)
        self.assertIn("Mic/Aux: silenciada.", self.anuncios)
        self.assertTrue(pagina.chk_silenciar.GetValue())

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
        self.assertEqual(escena.lst_escenas.GetName(), "Escenas")
        self.assertEqual(escena.btn_cambiar.GetName(), "Cambiar escena")
        self.assertEqual(escena.btn_agregar.GetName(), "Agregar escena…")
        fuentes = self.dialogo._pagina_fuentes
        self.assertEqual(fuentes.lst_fuentes.GetName(), "Fuentes")
        self.assertEqual(fuentes.btn_diseno.GetName(), "Aplicar diseño…")
        self.assertEqual(fuentes.btn_agregar.GetName(), "Agregar fuente…")
        self.assertEqual(fuentes.btn_restaurar.GetName(),
                         "Deshacer todos los cambios")
        audio = self.dialogo._pagina_audio
        self.assertEqual(audio.lst_audio.GetName(), "Fuentes de audio")
        self.assertEqual(audio.chk_silenciar.GetName(), "Silenciar")
        self.assertEqual(audio.chk_escuchar.GetName(), "Escuchar")
        self.assertEqual(audio.btn_microfono.GetName(), "Elegir micrófono…")
        self.assertEqual(audio.btn_probar.GetName(), "Probar nivel")
        self.assertEqual(audio.btn_filtros.GetName(), "Filtros…")
        self.assertEqual(self.dialogo.btn_cerrar.GetName(), "Cerrar")

    def test_orden_de_tab_de_cada_pestana(self):
        self.assertEqual(self._nombres(self.dialogo._pagina_escena), [
            "Escenas", "Cambiar escena", "Agregar escena…", "Fuentes",
            "Aplicar diseño…", "Agregar fuente…",
            "Deshacer todos los cambios"])
        self.assertEqual(self._nombres(self.dialogo._pagina_audio), [
            "Fuentes de audio", "Silenciar", "Elegir micrófono…",
            "Probar nivel", "Filtros…", "Escuchar"])
        self.assertEqual(self._nombres(self.dialogo)[-1:], ["Cerrar"])

    def test_cuadro_tamano_abre_con_el_comun_actual(self):
        dialogo = self._cuadro_tamano(25, 33)
        self.assertEqual(dialogo.GetTitle(),
                         "Tamaño y posición de la fuente")
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
        self._elegir_fuente(pagina, "Chat en el vídeo")
        pagina._mover.iniciar()
        self.assertTrue(pagina._mover.en_curso)
        pagina._mover._mover(10, 0)
        self.assertFalse(pagina.acciones_fuente._pila.vacia)
        pagina._tecla_fuente(EventoTecla(wx.WXK_ESCAPE))
        self.dialogo.EndModal.assert_not_called()
        self.assertFalse(pagina._mover.en_curso)
        self.assertTrue(pagina.acciones_fuente._pila.vacia)
        self.assertIn(("posicionar", "Principal", 32, 18, 5),
                      self.gestor.llamadas)
        self.assertIn("Movimiento deshecho", self.anuncios)

    def test_los_atajos_de_la_lista_hacen_su_accion(self):
        pagina = self.dialogo._pagina_fuentes
        acciones = pagina.acciones_fuente
        self._elegir_fuente(pagina, "Juego")
        with mock.patch.object(acciones, "mostrar") as mostrar:
            pagina._tecla_fuente(EventoTecla(wx.WXK_SPACE))
        mostrar.assert_called_once_with(False)
        with mock.patch.object(acciones, "renombrar") as renombrar:
            pagina._tecla_fuente(EventoTecla(wx.WXK_F2))
        renombrar.assert_called_once_with()
        with mock.patch.object(acciones, "duplicar") as duplicar:
            pagina._tecla_fuente(EventoTecla(ord("D"), ctrl=True))
        duplicar.assert_called_once_with()
        with mock.patch.object(acciones, "eliminar") as eliminar:
            pagina._tecla_fuente(EventoTecla(wx.WXK_DELETE))
        eliminar.assert_called_once_with()
        with mock.patch.object(acciones, "deshacer") as deshacer:
            pagina._tecla_fuente(EventoTecla(ord("Z"), ctrl=True))
        deshacer.assert_called_once_with()
        with mock.patch.object(acciones, "ordenar") as ordenar:
            for codigo, movimiento in (
                    (wx.WXK_HOME, "frente"),
                    (wx.WXK_UP, "adelante"),
                    (wx.WXK_DOWN, "atras"),
                    (wx.WXK_END, "fondo")):
                pagina._tecla_fuente(EventoTecla(codigo, ctrl=True))
        self.assertEqual(
            [llamada.args[0] for llamada in ordenar.call_args_list],
            ["frente", "adelante", "atras", "fondo"])

    def test_deshacer_reaplica_el_ultimo_cambio_y_lo_anuncia(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Juego")
        self._abrir_menu_de_fuente(
            pagina, "Bloquear posición", marcada=True)
        self.gestor.llamadas.clear()
        pagina.acciones_fuente.deshacer()
        self.assertIn(("fijar", "Principal", False), self.gestor.llamadas)
        self.assertIn("Deshecho: bloqueo de Juego.", self.anuncios)

    def test_deshacer_sin_cambios_lo_dice(self):
        pagina = self.dialogo._pagina_fuentes
        pagina._tecla_fuente(EventoTecla(ord("Z"), ctrl=True))
        self.assertIn("No hay nada que deshacer.", self.anuncios)

    def test_renombrar_pide_el_nombre_y_actualiza_la_lista(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        filas = (FilaFuente("Cámara nueva", "Cámara nueva", True, False),)
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_pedir_nombre",
                return_value="Cámara nueva") as pedir, \
                mock.patch.object(fuentes_obs, "renombrar") as renombrar, \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.renombrar()
        pedir.assert_called_once_with("Cámara")
        renombrar.assert_called_once_with(
            self.gestor, "Principal", "Cámara", "Cámara nueva")
        self.assertEqual(pagina.fuente(), "Cámara nueva")
        self.assertIn(
            "Cámara cambiada a Cámara nueva. El nombre cambia en todas las "
            "escenas que la usan.", self.anuncios)

    def test_renombrar_con_un_nombre_ocupado_vuelve_a_pedir(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        filas = (FilaFuente("Cámara nueva", "Cámara nueva", True, False),)
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_pedir_nombre",
                side_effect=["Juego", "Cámara nueva"]) as pedir, \
                mock.patch.object(fuentes_obs, "renombrar"), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.renombrar()
        self.assertEqual(pedir.call_count, 2)
        self.assertIn("Ya hay una fuente con ese nombre.", self.anuncios)

    def test_renombrar_actualiza_la_camara_guardada(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        filas = (FilaFuente("Cámara nueva", "Cámara nueva", True, False),)
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_pedir_nombre",
                return_value="Cámara nueva"), \
                mock.patch.object(fuentes_obs, "renombrar"), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas), \
                mock.patch.object(
                    escena_edicion_fuente.preferencias_camara,
                    "recordar_cambio_de_nombre") as recordar:
            pagina.acciones_fuente.renombrar()
        recordar.assert_called_once_with(
            self.principal, "Cámara", "Cámara nueva")

    def test_eliminar_confirma_y_selecciona_la_siguiente(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Cámara")
        filas = (FilaFuente("Chat en el vídeo", "Chat en el vídeo", True,
                            False),)
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_confirmar_eliminar",
                return_value=True), \
                mock.patch.object(fuentes_obs, "eliminar") as eliminar, \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.eliminar()
        eliminar.assert_called_once_with(self.gestor, "Principal", "Cámara")
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")
        self.assertIn("Cámara eliminada de la escena.", self.anuncios)

    def test_eliminar_la_ultima_selecciona_la_anterior(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Juego")
        filas = (FilaFuente("Cámara", "Cámara", True, False),
                 FilaFuente("Chat en el vídeo", "Chat en el vídeo", True,
                            False))
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_confirmar_eliminar",
                return_value=True), \
                mock.patch.object(fuentes_obs, "eliminar"), \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.eliminar()
        self.assertEqual(pagina.fuente(), "Chat en el vídeo")

    def test_eliminar_cancelado_no_toca_obs(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Juego")
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_confirmar_eliminar",
                return_value=False), \
                mock.patch.object(fuentes_obs, "eliminar") as eliminar:
            pagina.acciones_fuente.eliminar()
        eliminar.assert_not_called()
        self.assertEqual(pagina.fuente(), "Juego")

    def test_eliminar_pregunta_con_cancelar_por_defecto(self):
        pagina = self.dialogo._pagina_fuentes
        with mock.patch.object(
                escena_edicion_fuente.confirmar, "preguntar",
                return_value=True) as preguntar:
            self.assertTrue(
                pagina.acciones_fuente._edicion._confirmar_eliminar("Cámara"))
        preguntar.assert_called_once_with(
            pagina, "¿Eliminar Cámara de esta escena?", "Eliminar fuente",
            "&Eliminar", "&Cancelar", predeterminado_si=False)

    def test_duplicar_copia_y_selecciona_la_copia(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Juego")
        filas = (FilaFuente("Juego - copia", "Juego - copia", True, False),)
        with mock.patch.object(
                fuentes_obs, "duplicar", return_value="Juego - copia") \
                as duplicar, \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.duplicar()
        duplicar.assert_called_once_with(
            self.gestor, "Principal", "Juego", tipo="")
        self.assertEqual(pagina.fuente(), "Juego - copia")
        self.assertIn("Juego duplicada como Juego - copia.", self.anuncios)

    def test_duplicar_el_chat_avisa_sin_llamar_a_obs(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Chat en el vídeo")
        with mock.patch.object(fuentes_obs, "duplicar") as duplicar:
            pagina.acciones_fuente.duplicar()
        duplicar.assert_not_called()
        self.assertIn("Solo puede haber un chat en el vídeo.", self.anuncios)

    def test_cada_accion_del_menu_de_transformar_llama_a_la_suya(self):
        pagina = self.dialogo._pagina_fuentes
        for etiqueta, metodo in (
                ("Tamaño y posición…", "posicion_tamano"),
                ("Mover con flechas", "mover_con_flechas"),
                ("Centrar en el vídeo", "centrar"),
                ("Ajustar al vídeo", "ajustar"),
                ("Llenar el vídeo", "llenar"),
                ("Voltear horizontalmente", "voltear_horizontal"),
                ("Voltear verticalmente", "voltear_vertical"),
                ("Girar a la derecha", "girar_derecha"),
                ("Girar a la izquierda", "girar_izquierda"),
                ("Restablecer tamaño y posición", "restablecer")):
            with mock.patch.object(
                    pagina.acciones_fuente, metodo) as accion:
                self._abrir_menu_de_fuente(pagina, etiqueta)
            accion.assert_called_once()

    def test_centrar_anuncia_la_accion_y_el_estado_nuevo(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Juego")
        filas = (FilaFuente(
            "Juego", "Juego", True, False, "", "en el centro",
            "la mitad del vídeo"),)
        with mock.patch.object(
                fuentes_obs, "aplicar_transformacion") as aplicar, \
                mock.patch.object(self.gestor, "filas_escena",
                                  return_value=filas):
            pagina.acciones_fuente.centrar()
        aplicar.assert_called_once()
        self.assertIn(
            "Juego centrada. En el centro. La mitad del vídeo.",
            self.anuncios)

    def test_el_menu_muestra_los_atajos_de_cada_accion(self):
        fila = FilaFuente("Juego", "Juego", True, False)
        menu = escena_menu_fuente.menu_de_fuente(fila, mock.Mock())
        self.addCleanup(menu.Destroy)
        etiquetas = {
            item.GetItemLabelText(): item.GetItemLabel()
            for item in _items_del_menu(menu)}
        self.assertIn("\tSpace", etiquetas["Mostrar en la escena"])
        self.assertIn("\tAlt+Enter", etiquetas["Propiedades…"])
        self.assertIn("\tF2", etiquetas["Cambiar nombre…"])
        self.assertIn("\tCtrl+D", etiquetas["Duplicar"])
        self.assertIn("\tDel", etiquetas["Eliminar"])
        self.assertIn("\tCtrl+Home", etiquetas["Traer al frente"])
        self.assertIn("\tCtrl+Up", etiquetas["Traer adelante"])
        self.assertIn("\tCtrl+Down", etiquetas["Enviar atrás"])
        self.assertIn("\tCtrl+End", etiquetas["Enviar al fondo"])
        self.assertEqual(etiquetas["Eliminar"], "E&liminar\tDel")
        self.assertEqual(etiquetas["Traer adelante"],
                         "Traer a&delante\tCtrl+Up")

    def test_el_submenu_transformar_tiene_tres_separadores(self):
        fila = FilaFuente("Juego", "Juego", True, False)
        menu = escena_menu_fuente.menu_de_fuente(fila, mock.Mock())
        self.addCleanup(menu.Destroy)
        transformar = next(
            item.GetSubMenu() for item in menu.GetMenuItems()
            if item.GetItemLabelText() == "Transformar")
        separadores = sum(
            1 for item in transformar.GetMenuItems() if item.IsSeparator())
        self.assertEqual(separadores, 3)

    def test_renombrar_el_chat_avisa_y_no_pide_nombre_ni_toca_obs(self):
        pagina = self.dialogo._pagina_fuentes
        self._elegir_fuente(pagina, "Chat en el vídeo")
        with mock.patch.object(
                pagina.acciones_fuente._edicion, "_pedir_nombre") as pedir, \
                mock.patch.object(fuentes_obs, "renombrar") as renombrar:
            pagina._tecla_fuente(EventoTecla(wx.WXK_F2))
        pedir.assert_not_called()
        renombrar.assert_not_called()
        self.assertIn(
            "Chat en el vídeo no se puede cambiar de nombre: Guyrapu lo "
            "reconoce por él.", self.anuncios)

    def test_escape_cierra(self):
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._al_tecla(EventoTecla(wx.WXK_ESCAPE))
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_el_pie_solo_tiene_cerrar(self):
        self.assertFalse(hasattr(self.dialogo, "btn_ayuda"))
        self.assertTrue(hasattr(self.dialogo, "btn_cerrar"))


if __name__ == "__main__":
    unittest.main()
