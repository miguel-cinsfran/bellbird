"""Pestaña Audio de la ventana Escena: la lista de fuentes y sus acciones.

Abre ventanas: se corre en la PC de pruebas, no en la del dueño.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from guyrapu.obs import escucha_microfono, nivel_microfono
from guyrapu.obs.filtros_microfono import Estado
from guyrapu.obs.obs_cliente import ObsError
from guyrapu.ui import escena_pagina_audio
from tests.ventanas_prueba import app_de_prueba, destruir

TEXTO_INICIO = ("Probando Mic/Aux. Prueba del micrófono iniciada. "
                "Habla como en un directo.")
TEXTO_SILENCIADO = ("La fuente Mic/Aux está silenciada en OBS. "
                    "Desmárcala y vuelve a probar.")
AVISO_SIN_FUENTE = "Elige una fuente de audio."


class GestorFalso:
    def __init__(self, fuentes=("Mic/Aux",), silencios=None):
        self.fuentes = tuple(fuentes)
        self.silencios = dict(silencios or {})
        self.alternadas = []

    def fuentes_audio(self, parada=None):
        return self.fuentes

    def silenciada(self, fuente, parada=None):
        return self.silencios.get(fuente, False)

    def alternar_silencio(self, fuente, parada=None):
        self.alternadas.append(fuente)
        self.silencios[fuente] = not self.silencios.get(fuente, False)
        return self.silencios[fuente]

    def entradas_audio(self, parada=None):
        return tuple((nombre, "wasapi_input_capture") for nombre in self.fuentes)

    def microfono_especial(self, parada=None):
        return ""

    def dispositivo(self, fuente, predeterminado, parada=None):
        return "", False


def _filtro(tipo, activo=True, **ajustes):
    return {"filterKind": tipo, "filterEnabled": activo,
            "filterSettings": ajustes}


class OperacionesFalsas:
    def en_hilo(self, funcion, al_terminar=None):
        resultado = funcion()
        if al_terminar is not None:
            al_terminar(resultado)


class OperacionesConFallo(OperacionesFalsas):
    def __init__(self):
        self.fallos = []

    def en_hilo(self, funcion, al_terminar=None):
        try:
            resultado = funcion()
        except ObsError as error:
            self.fallo(str(error))
            return
        if al_terminar is not None:
            al_terminar(resultado)

    def fallo(self, mensaje):
        self.fallos.append(mensaje)


class HiloInmediato:
    def __init__(self, target, args=(), kwargs=None, **resto):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class BaseAudio(unittest.TestCase):
    FUENTES = ("Mic/Aux",)
    SILENCIOS = None
    FILTROS = {}

    def setUp(self):
        self.app = app_de_prueba()
        self.marco = wx.Frame(None)
        self.addCleanup(destruir, self.marco)
        self.principal = SimpleNamespace(_config={"obs_microfono": "Mic/Aux"})
        self.gestor = GestorFalso(self.FUENTES, self.SILENCIOS)
        self.filtros = dict(self.FILTROS)
        self._parches = [
            mock.patch.object(
                escena_pagina_audio.filtros_microfono, "leer_filtros_de",
                side_effect=lambda nombres: {
                    nombre: self.filtros.get(nombre, ())
                    for nombre in nombres}),
            mock.patch.object(
                escena_pagina_audio.filtros_microfono, "leer_filtros",
                side_effect=lambda nombre: self.filtros.get(nombre, ())),
        ]
        for parche in self._parches:
            parche.start()
            self.addCleanup(parche.stop)

    def _crear(self, operaciones=None):
        pagina = escena_pagina_audio.PaginaAudio(
            self.marco, self.principal, self.gestor,
            operaciones or OperacionesFalsas())
        self.addCleanup(destruir, pagina)
        return pagina

    def _sembrar(self, pagina, preferido="Mic/Aux"):
        datos = tuple((nombre, self.gestor.silenciada(nombre),
                       self.filtros.get(nombre, ()))
                      for nombre in self.gestor.fuentes)
        pagina._poner_filas(datos, preferido)


class TestPaginaAudioPrueba(BaseAudio):
    def setUp(self):
        super().setUp()
        self.parche_preparar = mock.patch.object(
            escena_pagina_audio.prueba_microfono, "preparar_fuente",
            return_value=("Mic/Aux", False, "Micrófono USB"))
        self.parche_clase = mock.patch.object(
            escena_pagina_audio.prueba_microfono, "PruebaMicrofono")
        self.parche_anunciar = mock.patch.object(
            escena_pagina_audio, "anunciar")
        self.parche_sonido = mock.patch.object(
            escena_pagina_audio.sound_player, "reproducir")
        self.parche_callafter = mock.patch.object(
            escena_pagina_audio.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs:
            funcion(*args, **kwargs))
        self.preparar = self.parche_preparar.start()
        self.clase = self.parche_clase.start()
        self.anunciar = self.parche_anunciar.start()
        self.reproducir = self.parche_sonido.start()
        self.parche_callafter.start()
        for parche in (self.parche_preparar, self.parche_clase,
                       self.parche_anunciar, self.parche_sonido,
                       self.parche_callafter):
            self.addCleanup(parche.stop)
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def _pulsar(self):
        evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                 self.pagina.btn_probar.GetId())
        self.pagina.btn_probar.GetEventHandler().ProcessEvent(evento)

    def _iniciar(self):
        self._pulsar()
        self.anunciar.reset_mock()
        return self.clase.return_value

    def test_el_boton_inicia_y_cambia_su_rotulo_y_nombre(self):
        self._pulsar()
        self.preparar.assert_called_once_with(self.gestor, "Mic/Aux")
        self.clase.assert_called_once()
        self.clase.return_value.iniciar.assert_called_once_with()
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Detener prueba")
        self.assertEqual(self.pagina.btn_probar.GetName(), "Detener prueba")
        self.anunciar.assert_any_call(TEXTO_INICIO)

    def test_un_tramo_reproduce_su_sonido_y_anuncia_sin_interrumpir(self):
        instancia = self._iniciar()
        al_tramo = self.clase.call_args.args[1]
        al_tramo(nivel_microfono.Nivel(nivel_microfono.BIEN, -3.0))
        self.reproducir.assert_called_once_with("microfono_bien")
        self.anunciar.assert_called_once_with("Nivel correcto.", False)
        instancia.detener.assert_not_called()

    def test_pulsar_otra_vez_detiene_la_prueba(self):
        instancia = self._iniciar()
        self._pulsar()
        instancia.detener.assert_called_once_with()
        self.clase.assert_called_once()

    def test_al_terminar_vuelve_el_rotulo_y_lo_anuncia(self):
        self._iniciar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("detenida")
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar nivel")
        self.assertEqual(self.pagina.btn_probar.GetName(), "Probar nivel")
        self.anunciar.assert_called_once_with(
            "Prueba de nivel de Mic/Aux detenida.")

    def test_un_fallo_anuncia_que_no_se_pudo_medir(self):
        self._iniciar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("fallo")
        self.anunciar.assert_called_once_with(
            "No se pudo medir Mic/Aux en OBS. Prueba detenida.")

    def test_al_destruir_detiene_y_un_tramo_posterior_no_toca_controles(self):
        instancia = self._iniciar()
        al_tramo = self.clase.call_args.args[1]
        self.anunciar.reset_mock()
        self.reproducir.reset_mock()
        destruir(self.pagina)
        instancia.detener.assert_called_once_with()
        al_tramo(nivel_microfono.Nivel(nivel_microfono.BIEN, -3.0))
        self.reproducir.assert_not_called()
        self.anunciar.assert_not_called()

    def test_terminar_deja_empezar_otra_prueba(self):
        primera = mock.Mock()
        segunda = mock.Mock()
        self.clase.side_effect = [primera, segunda]
        self._pulsar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("detenida")
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar nivel")
        self._pulsar()
        primera.detener.assert_not_called()
        self.assertEqual(self.clase.call_count, 2)
        segunda.iniciar.assert_called_once_with()
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Detener prueba")

    def test_silenciado_no_inicia_y_dice_por_que(self):
        self.preparar.return_value = ("Mic/Aux", True, "Micrófono USB")
        self._pulsar()
        self.clase.assert_not_called()
        self.anunciar.assert_called_once_with(TEXTO_SILENCIADO)
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar nivel")

    def test_sin_fuente_no_inicia_y_lo_dice(self):
        self.preparar.return_value = ("", False, "")
        self._pulsar()
        self.clase.assert_not_called()
        self.anunciar.assert_called_once_with(AVISO_SIN_FUENTE)


class TestPaginaAudioFiltros(BaseAudio):
    def setUp(self):
        super().setUp()
        self.estado = Estado(True, False, 6)
        self.parches = [
            mock.patch.object(
                escena_pagina_audio.filtros_microfono, "leer",
                return_value=self.estado),
            mock.patch.object(
                escena_pagina_audio.filtros_microfono, "aplicar"),
            mock.patch.object(
                escena_pagina_audio.escena_filtros, "pedir_filtros",
                return_value=None),
            mock.patch.object(escena_pagina_audio, "anunciar"),
            mock.patch.object(
                escena_pagina_audio.wx, "CallAfter",
                side_effect=lambda funcion, *args, **kwargs:
                funcion(*args, **kwargs)),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def _pulsar(self):
        evento = wx.CommandEvent(
            wx.EVT_BUTTON.typeId, self.pagina.btn_filtros.GetId())
        self.pagina.btn_filtros.GetEventHandler().ProcessEvent(evento)

    def test_abre_el_cuadro_con_el_estado_leido(self):
        self._pulsar()
        escena_pagina_audio.escena_filtros.pedir_filtros.assert_called_once_with(
            self.pagina, "Mic/Aux", self.estado)

    def test_aceptar_aplica_y_anuncia_lo_que_quedo(self):
        elegido = Estado(False, True, 3)
        escena_pagina_audio.escena_filtros.pedir_filtros.return_value = elegido
        self._pulsar()
        escena_pagina_audio.filtros_microfono.aplicar.assert_called_once_with(
            "Mic/Aux", elegido)
        self.assertTrue(
            escena_pagina_audio.anunciar.call_args.args[0].startswith(
                "Mic/Aux: "))

    def test_sin_fuente_anuncia_y_no_abre_el_cuadro(self):
        self.pagina._poner_filas((), "")
        self._pulsar()
        escena_pagina_audio.escena_filtros.pedir_filtros.assert_not_called()
        escena_pagina_audio.anunciar.assert_called_once_with(AVISO_SIN_FUENTE)

    def test_el_foco_vuelve_al_boton(self):
        with mock.patch.object(self.pagina.btn_filtros, "SetFocus") as foco:
            self._pulsar()
        foco.assert_called_once_with()


class TestPaginaAudioEscucha(BaseAudio):
    def setUp(self):
        super().setUp()
        self.parches = [
            mock.patch.object(
                escena_pagina_audio.escena_escucha.escucha_microfono,
                "activar", return_value=escucha_microfono.NINGUNA),
            mock.patch.object(
                escena_pagina_audio.escena_escucha.escucha_microfono,
                "restaurar"),
            mock.patch.object(
                escena_pagina_audio.escena_escucha, "anunciar"),
            mock.patch.object(
                escena_pagina_audio.escena_escucha.threading, "Thread",
                HiloInmediato),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.activar = (
            escena_pagina_audio.escena_escucha.escucha_microfono.activar)
        self.restaurar = (
            escena_pagina_audio.escena_escucha.escucha_microfono.restaurar)
        self.anunciar = escena_pagina_audio.escena_escucha.anunciar
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def _marcar(self, valor):
        self.pagina.chk_escuchar.SetValue(valor)
        self.pagina.chk_escuchar.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHECKBOX.typeId,
                            self.pagina.chk_escuchar.GetId()))

    def test_marcar_activa_y_anuncia_el_acople(self):
        with mock.patch.object(self.pagina.chk_escuchar, "SetFocus") as foco:
            self._marcar(True)
        self.activar.assert_called_once_with("Mic/Aux")
        self.assertTrue(self.pagina.chk_escuchar.GetValue())
        self.anunciar.assert_called_once_with(
            "Mic/Aux: Monitorización activada. Te oyes por el dispositivo de "
            "monitorización de OBS. Usa auriculares para evitar acople.")
        foco.assert_called_once_with()

    def test_desmarcar_restaura_el_tipo_anterior_y_anuncia(self):
        self._marcar(True)
        self.anunciar.reset_mock()
        with mock.patch.object(self.pagina.chk_escuchar, "SetFocus") as foco:
            self._marcar(False)
        self.restaurar.assert_called_once_with(
            "Mic/Aux", escucha_microfono.NINGUNA)
        self.assertFalse(self.pagina.chk_escuchar.GetValue())
        self.anunciar.assert_called_once_with(
            "Mic/Aux: Monitorización desactivada.")
        foco.assert_called_once_with()

    def test_sin_fuente_anuncia_y_queda_desmarcada(self):
        self.pagina._poner_filas((), "")
        self._marcar(True)
        self.activar.assert_not_called()
        self.assertFalse(self.pagina.chk_escuchar.GetValue())
        self.anunciar.assert_called_once_with(AVISO_SIN_FUENTE)

    def test_un_fallo_de_activar_deja_la_casilla_como_estaba(self):
        self.activar.side_effect = ObsError("sin conexión")
        operaciones = OperacionesConFallo()
        pagina = self._crear(operaciones)
        self._sembrar(pagina)
        pagina.chk_escuchar.SetValue(True)
        pagina.chk_escuchar.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHECKBOX.typeId,
                            pagina.chk_escuchar.GetId()))
        self.assertFalse(pagina.chk_escuchar.GetValue())
        self.assertEqual(operaciones.fallos, ["sin conexión"])
        self.anunciar.assert_not_called()

    def test_destruir_con_la_escucha_activa_restaura_sin_anunciar(self):
        self._marcar(True)
        self.anunciar.reset_mock()
        destruir(self.pagina)
        self.restaurar.assert_called_once_with(
            "Mic/Aux", escucha_microfono.NINGUNA)
        self.anunciar.assert_not_called()


class TestPaginaAudioLista(BaseAudio):
    FUENTES = ("Mic/Aux", "Audio del escritorio")
    FILTROS = {
        "Mic/Aux": (_filtro("noise_suppress_filter_v2"),
                    _filtro("gain_filter", db=6)),
        "Audio del escritorio": (),
    }

    def setUp(self):
        super().setUp()
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def test_la_lista_tiene_una_fila_por_fuente_en_el_orden_de_obs(self):
        self.assertEqual(
            self.pagina.lst_audio.GetStrings(),
            ["Mic/Aux, activa, eliminación de ruido, ganancia +6 dB",
             "Audio del escritorio, activa, sin filtros"])

    def test_la_lectura_trae_cada_fuente_con_su_silencio_y_sus_filtros(self):
        self.gestor.silencios["Audio del escritorio"] = True
        self.assertEqual(
            self.pagina._leer_fuentes(),
            (("Mic/Aux", False, self.filtros["Mic/Aux"]),
             ("Audio del escritorio", True, ())))

    def test_el_microfono_preferido_queda_elegido(self):
        self.pagina._poner_filas((), "")
        self._sembrar(self.pagina, "Audio del escritorio")
        self.assertEqual(self.pagina.fuente(), "Audio del escritorio")
        self.assertFalse(self.pagina.chk_silenciar.GetValue())

    def test_si_el_preferido_no_esta_queda_la_primera(self):
        self.pagina._poner_filas((), "")
        self._sembrar(self.pagina, "No existe")
        self.assertEqual(self.pagina.fuente(), "Mic/Aux")

    def test_silenciar_la_fila_elegida_actualiza_su_fila_sin_mover_la(self):
        self.pagina.lst_audio.SetSelection(1)
        self.pagina._al_cambiar_seleccion(
            SimpleNamespace(Skip=lambda: None))
        self.pagina.chk_silenciar.SetValue(True)
        with mock.patch.object(
                self.pagina.lst_audio, "SetFocus") as foco:
            self.pagina.chk_silenciar.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_CHECKBOX.typeId,
                                self.pagina.chk_silenciar.GetId()))
        self.assertEqual(self.gestor.alternadas, ["Audio del escritorio"])
        self.assertEqual(self.pagina.fuente(), "Audio del escritorio")
        self.assertEqual(
            self.pagina.lst_audio.GetString(1),
            "Audio del escritorio, silenciada, sin filtros")
        self.assertTrue(self.pagina.chk_silenciar.GetValue())
        foco.assert_not_called()

    def test_filtros_y_escuchar_reciben_la_fuente_de_la_fila(self):
        self.pagina.lst_audio.SetSelection(1)
        with mock.patch.object(
                escena_pagina_audio.filtros_microfono, "leer",
                return_value=Estado(False, False, 0)) as leer, \
                mock.patch.object(
                    escena_pagina_audio.escena_filtros, "pedir_filtros",
                    return_value=None):
            self.pagina._al_filtros()
        leer.assert_called_once_with("Audio del escritorio")
        self.pagina.lst_audio.SetSelection(1)
        with mock.patch.object(
                escena_pagina_audio.escena_escucha.escucha_microfono,
                "activar", return_value=escucha_microfono.NINGUNA) as activar:
            self.pagina._al_escuchar()
        activar.assert_called_once_with("Audio del escritorio")

    def test_el_menu_tiene_las_cuatro_acciones(self):
        menu = self.pagina._menu_de_audio()
        self.addCleanup(menu.Destroy)
        self.assertEqual(
            [item.GetItemLabelText() for item in menu.GetMenuItems()
             if item.GetItemLabelText()],
            ["Silenciar", "Probar nivel", "Filtros…", "Escuchar"])

    def test_las_acciones_del_menu_llegan_a_la_fila_elegida(self):
        self.pagina.lst_audio.SetSelection(1)
        with mock.patch.object(self.pagina, "_al_probar") as probar, \
                mock.patch.object(self.pagina, "_al_filtros") as filtros, \
                mock.patch.object(self.pagina, "_al_escuchar") as escuchar:
            menu = self.pagina._menu_de_audio()
            self.addCleanup(menu.Destroy)
            for item in menu.GetMenuItems():
                if item.GetItemLabelText():
                    menu.ProcessEvent(
                        wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId()))
        probar.assert_called_once_with()
        filtros.assert_called_once_with()
        escuchar.assert_called_once_with()

    def test_sin_conexion_la_lista_queda_vacia_y_los_controles_apagados(self):
        self.pagina._poner_filas((), "")
        self.assertEqual(self.pagina.lst_audio.GetStrings(), [])
        self.assertEqual(self.pagina.lst_audio.GetSelection(), wx.NOT_FOUND)
        self.assertFalse(self.pagina.chk_silenciar.GetValue())
        self.assertIn(self.pagina.lst_audio, self.pagina.acciones)

    def test_al_mostrar_la_pestana_se_vuelve_a_leer(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        libro = wx.Notebook(marco)
        otra = wx.Panel(libro)
        pagina = escena_pagina_audio.PaginaAudio(
            libro, self.principal, self.gestor, OperacionesFalsas())
        libro.AddPage(otra, "Otra")
        libro.AddPage(pagina, "Audio")
        libro.SetSelection(0)
        pagina.fijar(False)
        libro.SetSelection(1)
        self.assertEqual(
            pagina.lst_audio.GetStrings(),
            ["Mic/Aux, activa, eliminación de ruido, ganancia +6 dB",
             "Audio del escritorio, activa, sin filtros"])
        self.assertEqual(pagina.fuente(), "Mic/Aux")


class TestPaginaAudioPruebaFueraDeEntradas(BaseAudio):
    FUENTES = ("Mic/Aux", "Audio del escritorio")

    def setUp(self):
        super().setUp()
        self.gestor.entradas_audio = (
            lambda parada=None: (("Mic/Aux", "wasapi_input_capture"),))
        self.parche_clase = mock.patch.object(
            escena_pagina_audio.prueba_microfono, "PruebaMicrofono")
        self.parche_anunciar = mock.patch.object(
            escena_pagina_audio, "anunciar")
        self.parche_callafter = mock.patch.object(
            escena_pagina_audio.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs:
            funcion(*args, **kwargs))
        self.clase = self.parche_clase.start()
        self.parche_anunciar.start()
        self.parche_callafter.start()
        for parche in (self.parche_clase, self.parche_anunciar,
                       self.parche_callafter):
            self.addCleanup(parche.stop)
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def test_probar_nivel_mide_la_fuente_de_la_fila(self):
        self.pagina.lst_audio.SetSelection(1)
        self.pagina._al_probar()
        self.assertEqual(
            self.clase.call_args.args[0], "Audio del escritorio")


class TestPaginaAudioTeclas(BaseAudio):
    FUENTES = ("Mic/Aux", "Audio del escritorio")

    def setUp(self):
        super().setUp()
        self.pagina = self._crear()
        self._sembrar(self.pagina)

    def test_la_tecla_aplicaciones_abre_el_menu_de_la_fila(self):
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_WINDOWS_MENU
        with mock.patch.object(
                self.pagina, "_mostrar_menu_audio") as mostrar:
            self.pagina.lst_audio.ProcessEvent(evento)
        mostrar.assert_called_once_with(self.pagina.lst_audio)

    def test_mayus_f10_abre_el_mismo_menu(self):
        evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
        evento.KeyCode = wx.WXK_F10
        evento.SetShiftDown(True)
        with mock.patch.object(
                self.pagina, "_mostrar_menu_audio") as mostrar:
            self.pagina.lst_audio.ProcessEvent(evento)
        mostrar.assert_called_once_with(self.pagina.lst_audio)

    def test_sin_seleccion_anuncia_y_no_abre_el_menu(self):
        self.pagina.lst_audio.SetSelection(wx.NOT_FOUND)
        with mock.patch.object(self.pagina.lst_audio, "PopupMenu") as popup:
            self.pagina._mostrar_menu_audio(self.pagina.lst_audio)
        popup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
