"""Pruebas de la ventana Organizar escena sin conectar con OBS."""

import threading
import unittest
from unittest import mock

from bellbird.obs import obs_disposicion
from bellbird.obs import obs_estado
from bellbird.ui import gui_organizar_escena
from bellbird.ui import mover_con_flechas
from bellbird.ui import operaciones_obs
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.test_gui_transmision import (
    Evento, EventoTecla, GestorFalso, HiloInmediato)
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


ROTULOS = [
    "&Escena:", "Guardar &imagen…", "&Descripción de la escena:",
    "&Ventana:", "&Capturar ventana", "&Fuente:", "&Posición:",
    "&Mover fuente", "&Ancho:", "A&lto:", "Cambiar &tamaño",
    "Mostrar en la esce&na", "&Bloquear posición", "Traer al f&rente",
    "Mover con flec&has", "Deshacer cambi&os", "A&yuda", "Cerrar",
]

NOMBRES = [
    "Escena", "Guardar imagen…", "Descripción de la escena", "Ventana",
    "Capturar ventana", "Fuente", "Posición", "Mover fuente",
    "Ancho en píxeles", "Alto en píxeles", "Cambiar tamaño",
    "Mostrar en la escena", "Bloquear posición", "Traer al frente",
    "Mover con flechas", "Deshacer cambios", "Ayuda", "Cerrar",
]


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestOrganizarEscenaDialog(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self.categorias = []
        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_organizar_escena.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_organizar_escena, "anunciar", anunciar),
            mock.patch.object(mover_con_flechas, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
        self.gestor = GestorFalso()
        self.dialogo = gui_organizar_escena.OrganizarEscenaDialog(
            None, self.gestor, "Principal")
        self.anuncios.clear()
        self.categorias.clear()

    def tearDown(self):
        destruir(self.dialogo)
        for parche in reversed(self.parches):
            parche.stop()

    def _nombres_en_orden(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.Button,
                                 wx.CheckBox, wx.SpinCtrl)):
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres_en_orden(hijo))
        return nombres

    def _rotulos_en_orden(self, ventana):
        rotulos = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.StaticText, wx.Button, wx.CheckBox)):
                if hijo.GetLabel():
                    rotulos.append(hijo.GetLabel())
            rotulos.extend(self._rotulos_en_orden(hijo))
        return rotulos

    def test_orden_de_tab_exacto(self):
        self.assertEqual(self._nombres_en_orden(self.dialogo), NOMBRES)

    def test_rotulos_y_letras_en_el_orden_de_la_ventana(self):
        self.assertEqual(self._rotulos_en_orden(self.dialogo), ROTULOS)

    def test_foco_inicial_en_escena(self):
        self.assertIs(self.dialogo.FindFocus(), self.dialogo.cho_escena)

    def test_cambiar_escena_no_pone_la_escena_al_aire(self):
        self.gestor.poner_escena_al_aire = mock.Mock()
        self.dialogo.cho_escena.SetStringSelection("Juego")
        self.dialogo._cambiar_escena(Evento())
        self.gestor.poner_escena_al_aire.assert_not_called()

    def test_cambiar_escena_actualiza_fuentes_y_descripcion(self):
        self.dialogo.cho_escena.SetStringSelection("Juego")
        self.dialogo._cambiar_escena(Evento())
        self.assertEqual(self.dialogo.cho_fuente.GetStrings(), ["Captura"])
        self.assertTrue(self.dialogo.txt_descripcion.GetValue().startswith(
            "Escena: Juego."))
        self.assertIn("Fuente:", self.dialogo.txt_descripcion.GetValue())

    def test_cerrar_no_cierra_el_gestor(self):
        self.gestor.cerrar = mock.Mock()
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        self.gestor.cerrar.assert_not_called()
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_cerrar_detiene_el_aviso_pendiente(self):
        temporizador = mock.Mock()
        self.dialogo._operaciones._temporizador_consulta = temporizador
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        temporizador.Stop.assert_called_once_with()

    def test_descripcion_es_lectura_multilinea(self):
        estilo = self.dialogo.txt_descripcion.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_READONLY)
        self.assertTrue(estilo & wx.TE_MULTILINE)

    def test_descripcion_tiene_la_escena_y_el_detalle_de_la_fuente(self):
        texto = self.dialogo.txt_descripcion.GetValue()
        lineas = texto.splitlines()
        self.assertTrue(lineas[0].startswith("Escena: Principal."))
        self.assertIn("1: Juego,", lineas[1])
        self.assertIn("", lineas)
        self.assertIn("Fuente: Chat en el vídeo", texto)

    def test_tras_operacion_actualiza_descripcion_y_controles(self):
        snap = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=800, alto=500,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=32, arriba=18,
            visible=False, bloqueada=True)
        self.dialogo._tras_operacion(snap)
        self.assertIn("Fuente: Chat en el vídeo",
                      self.dialogo.txt_descripcion.GetValue())
        self.assertIn("800 por 500", self.dialogo.txt_descripcion.GetValue())
        self.assertEqual(self.dialogo.sp_ancho.GetValue(), 800)
        self.assertEqual(self.dialogo.sp_alto.GetValue(), 500)
        self.assertFalse(self.dialogo.chk_mostrar.GetValue())
        self.assertTrue(self.dialogo.chk_fijar.GetValue())

    def test_un_fallo_escribe_en_la_descripcion_y_enfoca_cerrar(self):
        with mock.patch.object(self.dialogo.btn_cerrar, "SetFocus") as foco:
            self.dialogo._escribir_fallo("OBS no contesta")
            self.dialogo._enfocar_tras_fallo()
        self.assertEqual(self.dialogo.txt_descripcion.GetValue(),
                         "OBS no contesta")
        foco.assert_called_once_with()

    def test_la_escena_sin_fuentes_avisa_en_la_descripcion(self):
        self.dialogo._cargar_fuentes((), "")
        self.assertEqual(self.dialogo.txt_descripcion.GetValue(),
                         "La escena no tiene fuentes.")

    def test_entrar_en_mover_cambia_el_rotulo_y_anuncia_las_teclas(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.assertTrue(self.dialogo._mover.en_curso)
        self.assertEqual(self.dialogo.btn_ajuste.GetLabel(),
                         "Moviendo con flechas")
        self.assertIn("Flechas para mover, Control para pasos grandes, "
                      "Mayúsculas para pasos de un píxel. Intro confirma, "
                      "Esc deshace, Tab sale.", self.anuncios)

    def test_flecha_mueve_y_anuncia_el_conjunto_corto(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.anuncios.clear()
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_RIGHT))
        self.assertIn(("mover", "Principal", 10, 0), self.gestor.llamadas)
        self.assertEqual(self.anuncios[-1], "Arriba a la izquierda.")

    def test_flecha_se_descarta_si_hay_movimiento_en_vuelo(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._ajuste.en_vuelo = True
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_RIGHT))
        self.assertNotIn(("mover", "Principal", 10, 0), self.gestor.llamadas)

    def test_escape_deshace_y_anuncia_movimiento_deshecho(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_ESCAPE))
        self.assertIn(("posicionar", "Principal", 32, 18, 5),
                      self.gestor.llamadas)
        self.assertIn("Movimiento deshecho", self.anuncios)

    def test_escape_con_movimiento_en_vuelo_espera_a_que_aterrice(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._ajuste.en_vuelo = True
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_ESCAPE))
        self.assertFalse(self.dialogo._mover.en_curso)
        self.assertNotIn(("posicionar", "Principal", 32, 18, 5),
                         self.gestor.llamadas)
        self.dialogo._mover._terminado(self.gestor.snap)
        self.assertIn(("posicionar", "Principal", 32, 18, 5),
                      self.gestor.llamadas)
        self.assertEqual(self.anuncios[-1], "Movimiento deshecho")
        self.assertFalse(self.dialogo._mover._ajuste.deshacer_pendiente)

    def test_escape_con_movimiento_fallido_tambien_deshace(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._ajuste.en_vuelo = True
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_ESCAPE))
        self.dialogo._mover._fallo("OBS no contesta")
        self.assertIn(("posicionar", "Principal", 32, 18, 5),
                      self.gestor.llamadas)
        self.assertNotIn("OBS no contesta", self.anuncios)

    def test_escape_sin_transformacion_avisa(self):
        self.gestor.transformacion_inicial = {}
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._tecla(EventoTecla(wx.WXK_ESCAPE))
        self.assertFalse(self.dialogo._mover.en_curso)
        self.assertNotIn("posicionar",
                         [llamada[0] for llamada in self.gestor.llamadas])
        self.assertEqual(self.anuncios[-1],
                         "No se pudo deshacer el movimiento")

    def test_tab_confirma_y_deja_navegar(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        evento = EventoTecla(wx.WXK_TAB)
        self.dialogo._mover._tecla(evento)
        self.assertFalse(self.dialogo._mover.en_curso)
        self.assertTrue(evento.se_omitio)
        self.assertIn("Posición confirmada", self.anuncios)

    def test_perder_el_foco_confirma(self):
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._perdio_foco(Evento())
        self.assertFalse(self.dialogo._mover.en_curso)
        self.assertIn("Posición confirmada", self.anuncios)

    def test_mover_declara_su_categoria(self):
        self.dialogo._mover._anunciar(self.gestor.snap)
        self.assertEqual(self.categorias[-1], "ajuste")

    def test_guardar_imagen_titulo_y_anuncio(self):
        cuadro = mock.MagicMock()
        cuadro.ShowModal.return_value = wx.ID_OK
        cuadro.GetPath.return_value = "C:/captura.png"
        with mock.patch.object(gui_organizar_escena.wx, "FileDialog",
                               return_value=cuadro) as crear:
            crear.return_value.__enter__.return_value = cuadro
            self.dialogo.btn_captura.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                self.dialogo.btn_captura.GetId()))
        self.assertEqual(crear.call_args.args[1],
                         "Guardar imagen de la escena")
        self.assertIn(("captura_de_escena", "Principal", "C:/captura.png"),
                      self.gestor.llamadas)
        self.assertIn("Imagen guardada", self.anuncios)

    def test_usar_ventana_sin_seleccion_avisa(self):
        self.dialogo.cho_ventana.SetSelection(wx.NOT_FOUND)
        self.anuncios.clear()
        self.dialogo._usar_ventana(Evento())
        self.assertEqual(self.anuncios,
                         ["Elige primero una ventana en Ventana."])
        self.assertNotIn("usar_ventana",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_usar_ventana_llama_con_escena_y_valor(self):
        self.dialogo.cho_escena.SetStringSelection("Principal")
        self.dialogo.cho_ventana.SetSelection(0)
        self.gestor.llamadas.clear()
        self.anuncios.clear()
        self.dialogo._usar_ventana(Evento())
        self.assertIn(("usar_ventana", "Principal",
                       "Champions:Ventana:juego.exe"), self.gestor.llamadas)
        self.assertEqual(self.anuncios,
                         ["Ahora se captura Champions, de juego.exe."])
        self.assertIn(("ventanas", "Principal"), self.gestor.llamadas)

    def test_elegir_en_el_desplegable_de_ventanas_no_cambia_nada(self):
        self.gestor.usar_ventana = mock.Mock()
        self.dialogo.cho_ventana.SetSelection(1)
        self.dialogo.cho_ventana.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            self.dialogo.cho_ventana.GetId()))
        self.gestor.usar_ventana.assert_not_called()

    def test_restaurar_anuncia_cambios_deshechos(self):
        self.dialogo.btn_restaurar.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_restaurar.GetId()))
        self.assertIn("Cambios deshechos", self.anuncios)

    def test_ayuda_titulo_y_texto(self):
        with mock.patch.object(gui_organizar_escena.wx, "MessageBox") as aviso:
            self.dialogo.btn_ayuda.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                self.dialogo.btn_ayuda.GetId()))
        self.assertEqual(aviso.call_args.args[0],
                         obs_estado.TEXTO_AYUDA_ESCENA)
        self.assertEqual(aviso.call_args.args[1],
                         "Ayuda de Organizar escena")

    def test_sin_barra_de_desplazamiento(self):
        self.dialogo.SetSize((600, 1080))
        self.dialogo.Layout()
        zona = self.dialogo._zona_desplazable
        zona.Layout()
        self.assertLessEqual(zona.GetVirtualSize().GetHeight(),
                             zona.GetClientSize().GetHeight())

    def test_ancho_minimo_600(self):
        self.assertGreaterEqual(self.dialogo.GetMinSize().GetWidth(), 600)

    def test_elegir_una_posicion_no_coloca_la_fuente(self):
        self.gestor.colocar = mock.Mock()
        self.dialogo.cho_posicion.SetSelection(8)
        self.dialogo.cho_posicion.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            self.dialogo.cho_posicion.GetId()))
        self.gestor.colocar.assert_not_called()

    def test_boton_colocar_usa_la_clave_del_anclaje_elegido(self):
        self.dialogo.cho_posicion.SetSelection(8)
        self.dialogo.btn_colocar.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_colocar.GetId()))
        self.assertIn(("colocar", "Principal", "inferior-derecha"),
                      self.gestor.llamadas)

    def test_mostrar_snap_refleja_el_anclaje_real(self):
        self.dialogo._mostrar_snap(self.gestor.snap)
        self.assertEqual(self.dialogo.cho_posicion.GetStringSelection(),
                         "Arriba a la izquierda")

    def test_mostrar_snap_fuera_de_anclajes_deja_sin_posicion(self):
        snap = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=460, alto=620,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=100, arriba=100,
            visible=True, bloqueada=False)
        self.dialogo.cho_posicion.SetSelection(0)
        self.dialogo._mostrar_snap(snap)
        self.assertEqual(self.dialogo.cho_posicion.GetSelection(),
                         wx.NOT_FOUND)

    def test_carga_las_fuentes_y_prefiere_el_panel_de_chat(self):
        self.assertEqual(self.dialogo.cho_fuente.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])
        self.assertEqual(self.dialogo.cho_fuente.GetStringSelection(),
                         "Chat en el vídeo")

    def test_cargar_ventanas_vacias_deja_el_desplegable_vacio(self):
        self.dialogo._cargar_ventanas((), "")
        self.assertEqual(self.dialogo.cho_ventana.GetStrings(), [])
        self.assertEqual(self.dialogo._valor_ventana(), "")

    def test_cada_boton_de_campo_comparte_la_grilla_con_su_campo(self):
        for campo, boton in (
                (self.dialogo.cho_escena, self.dialogo.btn_captura),
                (self.dialogo.cho_ventana, self.dialogo.btn_usar_ventana),
                (self.dialogo.cho_posicion, self.dialogo.btn_colocar)):
            with self.subTest(boton=boton.GetName()):
                grilla = campo.GetContainingSizer()
                self.assertIsNotNone(grilla)
                self.assertIs(boton.GetContainingSizer(), grilla)
                hijos = [hijo.GetWindow() for hijo in grilla.GetChildren()
                         if hijo.GetWindow() is not None]
                self.assertLess(hijos.index(campo), hijos.index(boton))

    def test_leer_y_ajuste_piden_la_instantanea_de_la_fuente(self):
        self.dialogo.cho_fuente.SetSelection(0)
        self.gestor.instantaneas.clear()
        self.dialogo._cambiar_fuente(Evento())
        self.assertEqual(self.gestor.instantaneas[-1],
                         (("Principal",), "Cámara"))
        self.dialogo.btn_ajuste.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_ajuste.GetId()))
        self.dialogo._mover._mover(10, 0)
        self.assertEqual(self.gestor.instantaneas[-1],
                         (("Principal",), "Cámara"))

    def test_aplicar_tamano_usa_los_dos_numeros(self):
        self.dialogo.sp_ancho.SetValue(800)
        self.dialogo.sp_alto.SetValue(500)
        self.dialogo._tamano(Evento())
        self.assertIn(("redimensionar", "Principal", 800, 500),
                      self.gestor.llamadas)

    def test_acciones_operan_sobre_la_fuente_elegida(self):
        self.dialogo.cho_fuente.SetStringSelection("Cámara")
        self.dialogo.cho_posicion.SetSelection(0)
        self.dialogo._colocar(Evento())
        self.dialogo._mostrar(Evento())
        self.dialogo._fijar(Evento())
        self.dialogo._frente(Evento())
        self.assertEqual(self.gestor.fuentes_enviadas[-4:], [
            ("colocar", "Cámara"), ("mostrar", "Cámara"),
            ("fijar", "Cámara"), ("al_frente", "Cámara"),
        ])

    def test_tamano_redimensiona_el_panel_y_escala_otra_fuente(self):
        self.dialogo._tamano(Evento())
        self.dialogo.cho_fuente.SetStringSelection("Cámara")
        self.dialogo._tamano(Evento())
        self.assertIn(("redimensionar", "Principal", 460, 620),
                      self.gestor.llamadas)
        self.assertIn(("escalar", "Principal", 460, 620),
                      self.gestor.llamadas)
        self.assertIn(("redimensionar", None), self.gestor.fuentes_enviadas)
        self.assertIn(("escalar", "Cámara"), self.gestor.fuentes_enviadas)

    def test_tamano_sin_imagen_no_anuncia_exito(self):
        self.dialogo.cho_fuente.SetStringSelection("Cámara")
        self.gestor.escalable = False
        self.dialogo._tamano(Evento())
        self.assertEqual(self.anuncios[-1],
                         "Cámara todavía no informa su tamaño.")

    def test_mostrar_usa_el_valor_de_la_casilla(self):
        self.dialogo.chk_mostrar.SetValue(False)
        self.dialogo._mostrar(Evento())
        self.assertIn(("mostrar", "Principal", False), self.gestor.llamadas)

    def test_fijar_usa_el_valor_de_la_casilla(self):
        self.dialogo.chk_fijar.SetValue(True)
        self.dialogo._fijar(Evento())
        self.assertIn(("fijar", "Principal", True), self.gestor.llamadas)

    def test_traer_al_frente_llama_al_gestor(self):
        self.dialogo._frente(Evento())
        self.assertIn(("al_frente", "Principal"), self.gestor.llamadas)

    def test_deshacer_devuelve_los_valores_de_las_dos_fuentes_tocadas(self):
        self.dialogo._tamano(Evento())
        self.dialogo.cho_fuente.SetStringSelection("Cámara")
        self.dialogo._tamano(Evento())
        self.dialogo._restaurar(Evento())
        self.assertEqual(self.gestor.llamadas[-8:-4], [
            ("posicionar", "Principal", 32, 18, 5),
            ("redimensionar", "Principal", 460, 620),
            ("mostrar", "Principal", True),
            ("fijar", "Principal", False),
        ])
        self.assertEqual(self.gestor.llamadas[-4:], [
            ("posicionar", "Principal", 32, 18, 5),
            ("escalar", "Principal", 460, 620),
            ("mostrar", "Principal", True),
            ("fijar", "Principal", False),
        ])
        self.assertEqual(self.gestor.fuentes_enviadas[-8:], [
            ("posicionar", "Chat en el vídeo"), ("redimensionar", None),
            ("mostrar", "Chat en el vídeo"), ("fijar", "Chat en el vídeo"),
            ("posicionar", "Cámara"), ("escalar", "Cámara"),
            ("mostrar", "Cámara"), ("fijar", "Cámara"),
        ])

    def test_destruir_marca_el_cierre_y_los_movimientos_tardios_no_tocan_controles(self):
        self.dialogo._mover._ajuste.entrar(self.gestor.transformacion_inicial)
        self.dialogo._mover._ajuste.en_vuelo = True
        self.dialogo._operaciones._al_destruir(Evento())
        self.assertTrue(self.dialogo._operaciones.cerrando)
        with mock.patch.object(self.dialogo._mover, "_al_mover") as mostrar,                 mock.patch.object(self.dialogo._operaciones, "fallo") as fallo:
            self.dialogo._mover._terminado(self.gestor.snap)
            self.dialogo._mover._ajuste.en_vuelo = True
            self.dialogo._mover._fallo("tarde")
        mostrar.assert_not_called()
        fallo.assert_not_called()
        self.assertFalse(self.dialogo._mover._ajuste.en_vuelo)

    def test_anuncia_la_instantanea_nueva_despues_del_cambio(self):
        self.gestor.snap_nuevo = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=800, alto=500,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=32, arriba=18,
            visible=False, bloqueada=True)
        self.dialogo._frente(Evento())
        self.assertIn("800 por 500", self.anuncios[-1])
        self.assertIn("Oculta", self.anuncios[-1])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoOrganizarEscena(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_organizar_escena.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_organizar_escena, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(mover_con_flechas, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = gui_organizar_escena.OrganizarEscenaDialog(
                None, GestorFalso(), "Principal")
            sin_marcar = textos_sin_marcar(dialogo, propios=(
                "Principal", "Juego", "Cámara", "Chat en el vídeo",
                "Captura", "Champions, de juego.exe", "Charla, de otro.exe",
                "Arriba a la izquierda"))
        self.addCleanup(destruir, dialogo)
        self.assertEqual(sorted(" ".join(texto.split()) for texto in sin_marcar),
                         [])


if __name__ == "__main__":
    unittest.main()
