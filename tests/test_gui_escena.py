"""Pruebas de la ventana Escena sin conectar con OBS."""

import threading
import unittest
from unittest import mock

import wx

from bellbird.obs import obs_capas, obs_disposicion
from bellbird.ui import escena_pagina_agregar
from bellbird.ui import escena_pagina_audio
from bellbird.ui import escena_pagina_escena
from bellbird.ui import escena_pagina_fuentes
from bellbird.ui import escena_ventana
from bellbird.ui import gui_microfono
from bellbird.ui import mover_con_flechas
from bellbird.ui import operaciones_obs
from tests.test_gui_transmision import (
    Evento, EventoTecla, GestorFalso, HiloInmediato)
from tests.ventanas_prueba import destruir


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


class TestVentanaEscena(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self.categorias = []

        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)

        self.asegurar = mock.Mock(side_effect=_asegurar_obs)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(escena_ventana.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(escena_ventana.obs_lanzador, "asegurar_obs",
                              self.asegurar),
            mock.patch.object(escena_ventana, "anunciar", anunciar),
            mock.patch.object(escena_pagina_escena, "anunciar", anunciar),
            mock.patch.object(escena_pagina_fuentes, "anunciar", anunciar),
            mock.patch.object(escena_pagina_agregar, "anunciar", anunciar),
            mock.patch.object(gui_microfono, "anunciar", anunciar),
            mock.patch.object(mover_con_flechas, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
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
        dialogo = escena_ventana.VentanaEscena(
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

    def _nombres(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.Button,
                                 wx.CheckBox, wx.SpinCtrl)):
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres(hijo))
        return nombres

    def test_titulo_y_pestanas(self):
        self.assertEqual(self.dialogo.GetTitle(), "Escena")
        self.assertEqual(
            [self.dialogo.nb.GetPageText(i)
             for i in range(self.dialogo.nb.GetPageCount())],
            ["Escena", "Fuentes", "Agregar", "Audio"])

    def test_al_abrir_la_escena_al_aire_la_descripcion_y_las_fuentes(self):
        self.anuncios.clear()
        dialogo = self._crear()
        pagina = dialogo._pagina_escena
        self.assertEqual(pagina.cho_escena.GetStringSelection(), "Principal")
        self.assertTrue(pagina.txt_descripcion.GetValue().startswith(
            "Escena: Principal."))
        self.assertEqual(dialogo._pagina_fuentes.cho_fuente.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])
        self.assertTrue(any(a.startswith("Escena: Principal.")
                            for a in self.anuncios))
        self.assertIs(dialogo.FindFocus(), pagina.cho_escena)

    def test_la_escena_al_aire_es_la_elegida(self):
        self.gestor.escena_resultante = "Juego"
        dialogo = self._crear()
        self.assertEqual(dialogo._pagina_escena.cho_escena.GetStringSelection(),
                         "Juego")
        self.assertEqual(dialogo._pagina_fuentes.cho_fuente.GetStrings(),
                         ["Captura"])
        self.assertTrue(
            dialogo._pagina_escena.txt_descripcion.GetValue().startswith(
                "Escena: Juego."))

    def test_al_abrir_llama_al_asegurador_de_obs(self):
        self._crear()
        self.asegurar.assert_called_once()
        self.assertTrue(callable(self.asegurar.call_args.args[0]))
        self.assertTrue(callable(self.asegurar.call_args.kwargs["al_anunciar"]))

    def test_sin_conexion_conecta_antes_de_leer_aunque_obs_ya_corra(self):
        gestor = GestorConexion(conectado=False)
        with mock.patch.object(escena_ventana.obs_lanzador, "asegurar_obs",
                               return_value=False) as asegurar:
            dialogo = self._crear(gestor=gestor)
        asegurar.assert_called_once()
        self.assertEqual(gestor.veces_conectar, 1)
        self.assertTrue(gestor.conectado)
        self.assertEqual(dialogo._pagina_fuentes.cho_fuente.GetStrings(),
                         ["Cámara", "Chat en el vídeo", "Juego"])

    def test_con_la_conexion_abierta_no_reconecta(self):
        gestor = GestorConexion(conectado=True)
        with mock.patch.object(escena_ventana.obs_lanzador, "asegurar_obs",
                               return_value=False) as asegurar:
            dialogo = self._crear(gestor=gestor)
        asegurar.assert_called_once()
        self.assertEqual(gestor.veces_conectar, 0)
        self.assertEqual(dialogo._pagina_escena.cho_escena.GetStringSelection(),
                         "Principal")

    def test_elegir_otra_escena_recarga_sin_cambiarla_al_aire(self):
        self.gestor.poner_escena_al_aire = mock.Mock()
        pagina = self.dialogo._pagina_escena
        pagina.cho_escena.SetStringSelection("Juego")
        self._elegir(pagina.cho_escena)
        self.gestor.poner_escena_al_aire.assert_not_called()
        self.assertEqual(self.dialogo._pagina_fuentes.cho_fuente.GetStrings(),
                         ["Captura"])
        self.assertTrue(pagina.txt_descripcion.GetValue().startswith(
            "Escena: Juego."))

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
        pagina.cho_posicion.SetSelection(8)
        self._pulsar(pagina.btn_colocar)
        pagina.sp_ancho.SetValue(800)
        pagina.sp_alto.SetValue(500)
        self._pulsar(pagina.btn_tamano)
        self._marcar(pagina.chk_mostrar, False)
        self._marcar(pagina.chk_fijar, True)
        self._pulsar(pagina.btn_frente)
        self._pulsar(pagina.btn_restaurar)
        self.assertIn(("colocar", "Principal", "inferior-derecha"),
                      self.gestor.llamadas)
        self.assertIn(("redimensionar", "Principal", 800, 500),
                      self.gestor.llamadas)
        self.assertIn(("mostrar", "Principal", False), self.gestor.llamadas)
        self.assertIn(("fijar", "Principal", True), self.gestor.llamadas)
        self.assertIn(("al_frente", "Principal"), self.gestor.llamadas)
        self.assertIn("Cambios deshechos", self.anuncios)

    def test_el_detalle_de_la_fuente_se_actualiza(self):
        self.gestor.snap_nuevo = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=800, alto=500,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=32, arriba=18,
            visible=False, bloqueada=True)
        pagina = self.dialogo._pagina_fuentes
        self._pulsar(pagina.btn_frente)
        self.assertIn("800 por 500", pagina.txt_detalle.GetValue())
        self.assertIn("Fuente:", pagina.txt_detalle.GetValue())

    def test_cada_boton_de_capa_llama_a_mover_capa_con_su_movimiento(self):
        pagina = self.dialogo._pagina_fuentes
        for boton, movimiento in (
                (pagina.btn_adelante, "adelante"),
                (pagina.btn_atras, "atras"),
                (pagina.btn_fondo, "fondo")):
            pagina.cho_fuente.SetStringSelection("Chat en el vídeo")
            self._pulsar(boton)
            self.assertIn(("mover_capa", "Principal", movimiento),
                          self.gestor.llamadas)

    def test_mover_anuncia_el_lugar_y_despues_la_descripcion(self):
        pagina = self.dialogo._pagina_fuentes
        pagina.cho_fuente.SetStringSelection("Chat en el vídeo")
        self._pulsar(pagina.btn_adelante)
        aviso = next(anuncio for anuncio in self.anuncios
                     if anuncio.startswith("Chat en el vídeo: capa 1 de 3."))
        self.assertIn("Chat en el vídeo.", aviso)

    def test_mover_en_el_extremo_anuncia_que_ya_esta_en_el_borde(self):
        pagina = self.dialogo._pagina_fuentes
        pagina.cho_fuente.SetStringSelection("Cámara")
        self._pulsar(pagina.btn_adelante)
        self.assertIn("Cámara ya está al frente.", self.anuncios)
        pagina.cho_fuente.SetStringSelection("Juego")
        self._pulsar(pagina.btn_fondo)
        self.assertIn("Juego ya está al fondo.", self.anuncios)

    def test_la_lista_fuente_queda_ordenada_y_con_la_misma_fuente(self):
        pagina = self.dialogo._pagina_fuentes
        pagina.cho_fuente.SetStringSelection("Chat en el vídeo")
        self._pulsar(pagina.btn_adelante)
        self.assertEqual(pagina.cho_fuente.GetStrings(),
                         ["Chat en el vídeo", "Cámara", "Juego"])
        self.assertEqual(pagina.cho_fuente.GetStringSelection(),
                         "Chat en el vídeo")

    def test_los_tres_movimientos_entran_en_deshacer(self):
        pagina = self.dialogo._pagina_fuentes
        for fuente, boton in (("Cámara", pagina.btn_adelante),
                              ("Chat en el vídeo", pagina.btn_atras),
                              ("Juego", pagina.btn_fondo)):
            pagina.cho_fuente.SetStringSelection(fuente)
            self._pulsar(boton)
        self.gestor.llamadas.clear()
        self._pulsar(pagina.btn_restaurar)
        self.assertEqual(
            len([llamada for llamada in self.gestor.llamadas
                 if llamada[0] == "posicionar"]), 3)

    def test_capturar_ventana_recarga_la_escena(self):
        pagina = self.dialogo._pagina_agregar
        pagina.cho_ventana.SetSelection(0)
        with mock.patch.object(
                self.gestor, "descripcion_escena",
                wraps=self.gestor.descripcion_escena) as descripcion:
            self._pulsar(pagina.btn_usar_ventana)
        self.assertIn("Ahora se captura Champions, de juego.exe.",
                      self.anuncios)
        descripcion.assert_called()

    def test_agregar_camara_recarga_la_escena(self):
        pagina = self.dialogo._pagina_agregar

        def agregar(dialogo, al_agregar):
            al_agregar(("Cámara",))

        with mock.patch.object(escena_pagina_agregar.agregar_camara,
                               "agregar", side_effect=agregar) as llamada, \
                mock.patch.object(
                    self.gestor, "descripcion_escena",
                    wraps=self.gestor.descripcion_escena) as descripcion:
            self._pulsar(pagina.btn_camara)
        self.assertIs(llamada.call_args.args[0], self.dialogo)
        self.assertTrue(callable(llamada.call_args.args[1]))
        descripcion.assert_called()

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
        with mock.patch.object(escena_ventana, "GestorPanelObs",
                               return_value=self.gestor):
            dialogo = escena_ventana.VentanaEscena(None, self.principal)
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

    def test_si_obs_no_responde_lo_dice_en_la_descripcion(self):
        self.anuncios.clear()
        dialogo = self._crear(gestor=GestorFalso(fallo=True))
        self.assertEqual(dialogo._pagina_escena.txt_descripcion.GetValue(),
                         "OBS no está disponible")
        self.assertIn("OBS no está disponible", self.anuncios)

    def test_nombres_accesibles(self):
        escena = self.dialogo._pagina_escena
        self.assertEqual(escena.cho_escena.GetName(), "Escena")
        self.assertEqual(escena.btn_cambiar.GetName(), "Cambiar escena")
        self.assertEqual(escena.txt_descripcion.GetName(),
                         "Descripción de la escena")
        self.assertEqual(escena.btn_imagen.GetName(), "Guardar imagen…")
        fuentes = self.dialogo._pagina_fuentes
        self.assertEqual(fuentes.cho_fuente.GetName(), "Fuente")
        self.assertEqual(fuentes.cho_posicion.GetName(), "Posición")
        self.assertEqual(fuentes.btn_colocar.GetName(), "Mover fuente")
        self.assertEqual(fuentes.btn_tamano.GetName(), "Cambiar tamaño")
        self.assertEqual(fuentes.chk_mostrar.GetName(), "Mostrar en la escena")
        self.assertEqual(fuentes.chk_fijar.GetName(), "Bloquear posición")
        self.assertEqual(fuentes.btn_frente.GetName(), "Traer al frente")
        self.assertEqual(fuentes.btn_adelante.GetName(), "Traer adelante")
        self.assertEqual(fuentes.btn_atras.GetName(), "Enviar atrás")
        self.assertEqual(fuentes.btn_fondo.GetName(), "Enviar al fondo")
        self.assertEqual(fuentes.btn_ajuste.GetName(), "Mover con flechas")
        self.assertEqual(fuentes.btn_restaurar.GetName(), "Deshacer cambios")
        self.assertEqual(fuentes.txt_detalle.GetName(), "Detalle de la fuente")
        agregar = self.dialogo._pagina_agregar
        self.assertEqual(agregar.cho_ventana.GetName(), "Ventana")
        self.assertEqual(agregar.btn_usar_ventana.GetName(), "Capturar ventana")
        self.assertEqual(agregar.btn_camara.GetName(), "Agregar cámara…")
        audio = self.dialogo._pagina_audio
        self.assertEqual(audio.chk_silenciar.GetName(), "Silenciar micrófono")
        self.assertEqual(audio.btn_microfono.GetName(), "Elegir micrófono…")
        self.assertEqual(self.dialogo.btn_ayuda.GetName(), "Ayuda")
        self.assertEqual(self.dialogo.btn_cerrar.GetName(), "Cerrar")

    def test_orden_de_tab_de_cada_pestana(self):
        self.assertEqual(self._nombres(self.dialogo._pagina_escena), [
            "Escena", "Cambiar escena", "Descripción de la escena",
            "Guardar imagen…"])
        self.assertEqual(self._nombres(self.dialogo._pagina_fuentes), [
            "Fuente", "Detalle de la fuente", "Posición", "Mover fuente",
            "Ancho en píxeles", "Alto en píxeles", "Cambiar tamaño",
            "Mostrar en la escena", "Bloquear posición", "Traer al frente",
            "Traer adelante", "Enviar atrás", "Enviar al fondo",
            "Mover con flechas", "Deshacer cambios"])
        self.assertEqual(self._nombres(self.dialogo._pagina_agregar), [
            "Ventana", "Capturar ventana", "Agregar cámara…"])
        self.assertEqual(self._nombres(self.dialogo._pagina_audio), [
            "Silenciar micrófono", "Elegir micrófono…"])
        self.assertEqual(self._nombres(self.dialogo)[-2:], ["Ayuda", "Cerrar"])

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

    def test_ayuda_titulo_y_texto(self):
        with mock.patch.object(escena_ventana.wx, "MessageBox") as aviso:
            self._pulsar(self.dialogo.btn_ayuda)
        self.assertEqual(aviso.call_args.args[0],
                         escena_ventana.TEXTO_AYUDA_ESCENA)
        self.assertEqual(aviso.call_args.args[1], "Ayuda de Escena")


if __name__ == "__main__":
    unittest.main()
