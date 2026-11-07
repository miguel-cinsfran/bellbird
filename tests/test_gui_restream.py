"""Pruebas de la ventana de Restream y del diálogo de perfil.

Crean ventanas de wx: se corren en la PC donde no molestan al lector, no en
la del dueño. La cuenta y los destinos son dobles; los perfiles viven en una
carpeta temporal.
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import wx

from guyrapu.core.idioma import _
from guyrapu.restream import eventos as eventos_restream
from guyrapu.restream import perfiles
from guyrapu.restream.api import Canal, ErrorApi
from guyrapu.restream.perfiles import Perfil
from guyrapu.ui import restream_acciones_destino
from guyrapu.ui import restream_pagina_destinos
from guyrapu.ui import restream_pagina_eventos
from guyrapu.ui import restream_pagina_perfiles
from guyrapu.ui import restream_perfil
from guyrapu.ui import restream_ventana
from guyrapu.ui.preferencias_comun import nombre_de_etiqueta
from guyrapu.youtube.emision import (
    ETIQUETAS_LATENCIA,
    ETIQUETAS_PRIVACIDAD,
    LATENCIA_INICIAL,
    LATENCIAS,
    PRIVACIDAD_INICIAL,
    PRIVACIDADES,
)
from tests.letras_acceso import (
    _letra_de_acceso, letras_repetidas, repetidas_con_lo_de_fuera)
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import app_de_prueba, destruir


class CuentaFalsa:
    def __init__(self, conectada=False):
        self.estado = conectada

    def conectada(self):
        return self.estado


def _perfil(nombre="Canal", canales=(1,), orientacion="horizontal", **cambios):
    datos = dict(nombre=nombre, canales=canales, orientacion=orientacion,
                 titulo="", descripcion="", privacidad=PRIVACIDAD_INICIAL,
                 latencia=LATENCIA_INICIAL)
    datos.update(cambios)
    return Perfil(**datos)


def _canales():
    return [(1, "TikTok: uno"), (2, "YouTube: dos")]


def _destinos():
    return [Canal(1, 67, "TikTok", "uno", "", True),
            Canal(2, 5, "YouTube", "dos", "", True)]


def _avisar_de(anunciar, sonar):
    def _avisar(texto, sonido=None, *, error=False):
        anunciar(texto)
        if sonido:
            sonar(sonido)
    return _avisar


def _esperar(prueba, limite=5.0):
    """Atiende eventos de wx hasta que se cumpla la condición o venza."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        wx.Yield()
        if prueba():
            return True
        time.sleep(0.01)
    wx.Yield()
    return prueba()


def _es_hilo_principal():
    return threading.current_thread() is threading.main_thread()


def _falla_sin_mensaje(_parada):
    raise ValueError()


def _controles_en_orden(ventana):
    """Controles que toman foco, en el orden en que wx los recorre."""
    orden = []
    for hijo in ventana.GetChildren():
        if isinstance(hijo, (wx.ScrolledWindow, wx.Panel, wx.StaticBox)):
            orden.extend(_controles_en_orden(hijo))
        elif hijo.IsShown() and hijo.AcceptsFocus():
            orden.append(hijo)
    return orden


class _DialogoFalso:
    def __init__(self, perfil):
        self._perfil = perfil

    def ShowModal(self):
        return wx.ID_OK

    def perfil(self):
        return self._perfil

    def Destroy(self):
        pass


class PruebaVentanaRestream(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "perfiles_restream.json"

    def _ventana(self, cuenta=None, guardados=None, al_conectar=None,
                 al_reautorizar=None, al_desconectar=None, canales=None,
                 destinos=None, perfil=None, eliminar=None, eventos=None,
                 estadisticas=None, id_canal=None):
        if guardados is not None:
            perfiles.guardar(self.ruta, guardados)
        dialogo = restream_ventana.VentanaRestream(
            None, cuenta or CuentaFalsa(), canales or _canales, self.ruta,
            al_conectar=al_conectar, al_reautorizar=al_reautorizar,
            al_desconectar=al_desconectar, destinos=destinos, perfil=perfil,
            eliminar=eliminar, eventos=eventos,
            estadisticas=estadisticas,
            id_canal=id_canal if id_canal is not None else (lambda: ""))
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_p1_cuatro_pestanas_en_orden_y_abre_en_cuenta_sin_conectar(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(False))
        self.assertEqual("PestanasRestream", dialogo.nb.GetName())
        self.assertEqual(4, dialogo.nb.GetPageCount())
        self.assertEqual(
            ["Cuenta", "Destinos", "Perfiles", "Eventos"],
            [dialogo.nb.GetPageText(i)
             for i in range(dialogo.nb.GetPageCount())])
        self.assertEqual(0, dialogo.nb.GetSelection())
        self.assertIs(dialogo._pagina_eventos,
                      dialogo.nb.GetPage(3))
        self.assertEqual("Cerrar", dialogo.btn_cerrar.GetLabel())
        self.assertEqual(wx.ID_CANCEL, dialogo.btn_cerrar.GetId())
        self.assertEqual("Cerrar", dialogo.btn_cerrar.GetName())

        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_tecla_ventana(evento)
        fin.assert_called_once_with(wx.ID_CANCEL)

        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_TAB
        dialogo._al_tecla_ventana(evento)
        evento.Skip.assert_called_once_with()

    def test_p14_f1_abre_el_manual(self):
        dialogo = self._ventana()
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_F1
        with mock.patch(
                "guyrapu.ui.gui_menu.abrir_documento_paquete") as abrir:
            dialogo._al_tecla_ventana(evento)
        abrir.assert_called_once_with(
            dialogo, "MANUAL", "Manual de uso")
        evento.Skip.assert_not_called()

    def test_p2_con_cuenta_tambien_abre_en_cuenta(self):
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), canales=lambda: [])
        self.assertEqual(0, dialogo.nb.GetSelection())

    def test_p2_desconectada_muestra_conectar(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(False))
        self.assertEqual(
            "Sin cuenta de Restream conectada. Restream transmite a varias "
            "plataformas a la vez: conecta la cuenta para elegir los destinos "
            "y armar perfiles.",
            dialogo._pagina_cuenta.txt_estado.GetValue())
        self.assertTrue(dialogo._pagina_cuenta.btn_conectar.IsShown())
        self.assertFalse(dialogo._pagina_cuenta.btn_reautorizar.IsShown())
        self.assertFalse(dialogo._pagina_cuenta.btn_desconectar.IsShown())

    def test_p2_p3_conectar_en_hilo_desactiva_y_al_terminar_anuncia(self):
        cuenta = CuentaFalsa(False)
        llamadas = []
        soltar = threading.Event()
        hilo = {}
        lecturas = []

        def conectar(parada):
            hilo["parada"] = parada
            hilo["principal"] = _es_hilo_principal()
            soltar.wait(5)
            llamadas.append(True)
            cuenta.estado = True

        def leer_canales():
            lecturas.append(_es_hilo_principal())
            return _canales()

        dialogo = self._ventana(
            cuenta=cuenta, al_conectar=conectar, canales=leer_canales)
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            dialogo._conectar()

            self.assertIn(
                "Abriendo el navegador para iniciar sesión en Restream. "
                "Autoriza y vuelve aquí.",
                [llamada.args[0] for llamada in anunciar.call_args_list])
            for boton in (dialogo._pagina_cuenta.btn_conectar,
                          dialogo._pagina_cuenta.btn_reautorizar,
                          dialogo._pagina_cuenta.btn_desconectar):
                self.assertFalse(boton.IsEnabled())

            self.assertTrue(_esperar(lambda: "parada" in hilo))
            self.assertFalse(hilo["principal"])
            self.assertIs(hilo["parada"], dialogo._parada)
            wx.Yield()
            self.assertFalse(soltar.is_set())

            soltar.set()
            self.assertTrue(_esperar(lambda: sonar.called))

        self.assertEqual([True], llamadas)
        sonar.assert_called_once_with("conectado")
        anunciar.assert_any_call("Cuenta de Restream conectada.")
        self.assertTrue(_esperar(lambda: lecturas))
        self.assertFalse(lecturas[0])
        self.assertTrue(_esperar(
            lambda: "2 destinos, 2 activos. 0 perfiles."
            in dialogo._pagina_cuenta.txt_estado.GetValue()))
        texto_estado = dialogo._pagina_cuenta.txt_estado.GetValue()
        self.assertTrue(texto_estado.startswith(
            "Cuenta de Restream conectada."))
        self.assertIn("2 destinos, 2 activos. 0 perfiles.", texto_estado)
        self.assertIn(
            "Todavía no hay perfiles. Créalos en la pestaña Perfiles.",
            texto_estado)
        self.assertFalse(dialogo._pagina_cuenta.btn_conectar.IsShown())
        self.assertTrue(dialogo._pagina_cuenta.btn_reautorizar.IsShown())
        self.assertTrue(dialogo._pagina_cuenta.btn_desconectar.IsShown())
        for boton in (dialogo._pagina_cuenta.btn_reautorizar,
                      dialogo._pagina_cuenta.btn_desconectar):
            self.assertTrue(boton.IsEnabled())

    def test_p3_conectar_que_falla_suena_error_y_muestra_el_mensaje(self):
        cuenta = CuentaFalsa(False)

        def conectar(_parada):
            raise ValueError("Credenciales rechazadas")

        dialogo = self._ventana(cuenta=cuenta, al_conectar=conectar)
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            dialogo._conectar()
            self.assertTrue(_esperar(lambda: sonar.called))

        sonar.assert_called_once_with("error")
        anunciar.assert_any_call("Credenciales rechazadas")
        self.assertIn("Credenciales rechazadas",
                      dialogo._pagina_cuenta.txt_estado.GetValue())
        self.assertFalse(cuenta.conectada())
        self.assertTrue(dialogo._pagina_cuenta.btn_conectar.IsShown())
        for boton in (dialogo._pagina_cuenta.btn_conectar,
                      dialogo._pagina_cuenta.btn_reautorizar,
                      dialogo._pagina_cuenta.btn_desconectar):
            self.assertTrue(boton.IsEnabled())

    def test_p3_sin_mensaje_anuncia_el_texto_de_respaldo(self):
        dialogo = self._ventana(
            cuenta=CuentaFalsa(False),
            al_conectar=_falla_sin_mensaje)
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            dialogo._conectar()
            self.assertTrue(_esperar(lambda: sonar.called))

        sonar.assert_called_once_with("error")
        anunciar.assert_any_call("No se pudo conectar con Restream.")
        self.assertIn("No se pudo conectar con Restream.",
                      dialogo._pagina_cuenta.txt_estado.GetValue())

    def test_p2_reautorizar_y_desconectar(self):
        cuenta = CuentaFalsa(True)

        def desconectar():
            cuenta.estado = False

        dialogo = self._ventana(
            cuenta=cuenta, al_reautorizar=lambda _parada: None,
            al_desconectar=desconectar)
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            dialogo._reautorizar()
            self.assertIn(
                "Abriendo el navegador para iniciar sesión en Restream. "
                "Autoriza y vuelve aquí.",
                [llamada.args[0] for llamada in anunciar.call_args_list])
            self.assertTrue(_esperar(
                lambda: mock.call("conectado") in sonar.call_args_list))
            anunciar.assert_any_call("Cuenta de Restream conectada.")

            sonar.reset_mock()
            anunciar.reset_mock()
            dialogo._desconectar()
            self.assertTrue(_esperar(
                lambda: mock.call("desconectado") in sonar.call_args_list))
            anunciar.assert_called_once_with(
                "Cuenta de Restream desconectada.")

        self.assertFalse(cuenta.conectada())
        self.assertTrue(dialogo._pagina_cuenta.btn_conectar.IsShown())

    def test_p4_cerrar_corta_la_espera_y_no_toca_la_ventana_cerrada(self):
        cuenta = CuentaFalsa(False)
        recibidas = []
        pendientes = []

        def conectar(parada):
            recibidas.append(parada)
            parada.wait(5)

        def diferir(funcion, *args):
            pendientes.append((funcion, args))

        dialogo = self._ventana(cuenta=cuenta, al_conectar=conectar)
        with mock.patch.object(restream_ventana.wx, "CallAfter",
                               side_effect=diferir), \
                mock.patch.object(restream_ventana, "anunciar"):
            dialogo._conectar()
            self.assertTrue(_esperar(lambda: recibidas))
            wx.Yield()
            self.assertFalse(recibidas[0].is_set())

            dialogo.Destroy()
            self.assertTrue(recibidas[0].is_set())
            self.assertTrue(_esperar(lambda: pendientes))

        for funcion, args in pendientes:
            funcion(*args)

    def test_p5_destinos_que_fallan_van_a_la_segunda_linea_sin_sonido(self):
        def canales():
            raise ValueError("sin red")

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), canales=canales)
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            self.assertTrue(_esperar(
                lambda: "No se pudieron leer los destinos."
                in dialogo._pagina_cuenta.txt_estado.GetValue()))
            wx.Yield()

        lineas = dialogo._pagina_cuenta.txt_estado.GetValue().splitlines()
        self.assertEqual("Cuenta de Restream conectada.", lineas[0])
        self.assertIn("No se pudieron leer los destinos.", lineas)
        sonar.assert_not_called()
        anunciar.assert_not_called()

    def test_fallo_al_leer_con_errorapi_usa_solo_su_mensaje(self):
        error = ErrorApi()

        def canales():
            raise error

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), canales=canales)
        self.assertTrue(_esperar(
            lambda: str(error)
            in dialogo._pagina_cuenta.txt_estado.GetValue()))

        lineas = dialogo._pagina_cuenta.txt_estado.GetValue().splitlines()
        self.assertEqual("Cuenta de Restream conectada.", lineas[0])
        self.assertIn(str(error), lineas)

    def test_p6_el_editor_recibe_los_destinos_leidos_y_no_consulta_la_red(
            self):
        llamadas = []
        recibidos = []

        def canales():
            llamadas.append(True)
            return _canales()

        def abrir_editor(_padre, perfil, canales_leidos, _existentes,
                         **_cambios):
            recibidos.append(list(canales_leidos))
            return _DialogoFalso(perfil or _perfil(nombre="Nuevo"))

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), canales=canales,
            guardados=[_perfil(nombre="Canal")])
        self.assertTrue(_esperar(lambda: dialogo._destinos))
        with mock.patch.object(restream_pagina_perfiles,
                               "DialogoPerfilRestream",
                               side_effect=abrir_editor), \
                mock.patch.object(restream_pagina_perfiles, "anunciar"):
            dialogo._pagina_perfiles.nuevo()
            dialogo._pagina_perfiles.lista_perfiles.SetSelection(0)
            dialogo._pagina_perfiles.editar()

        self.assertEqual(1, len(llamadas))
        self.assertEqual([_canales(), _canales()], recibidos)

    def test_p9_lista_con_nombre_orientacion_y_destinos_por_nombre(self):
        primera = _perfil(nombre="TikTok", canales=(1,), orientacion="vertical")
        segunda = _perfil(nombre="TikTok y YouTube", canales=(1, 2))
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=_destinos,
            guardados=[primera, segunda])
        pagina = dialogo._pagina_perfiles
        self.assertTrue(_esperar(
            lambda: pagina.lista_perfiles.GetCount() == 2
            and "TikTok: uno" in pagina.lista_perfiles.GetString(0)))
        lista = pagina.lista_perfiles

        self.assertEqual("Perfiles", lista.GetName())
        self.assertEqual(
            ["TikTok, vertical: TikTok: uno",
             "TikTok y YouTube, horizontal: TikTok: uno, YouTube: dos"],
            list(lista.GetStrings()))
        self.assertEqual("&Nuevo perfil…", pagina.btn_nuevo.GetLabel())
        self.assertEqual("Nuevo perfil", pagina.btn_nuevo.GetName())
        self.assertFalse(hasattr(pagina, "btn_editar"))
        self.assertFalse(hasattr(pagina, "btn_duplicar"))
        self.assertFalse(hasattr(pagina, "btn_eliminar"))

    def test_p3_sin_seleccion_anuncia_y_no_hace_nada(self):
        dialogo = self._ventana()
        pagina = dialogo._pagina_perfiles
        with mock.patch.object(restream_pagina_perfiles,
                               "anunciar") as anunciar:
            pagina.editar()
            pagina.duplicar()
            pagina.eliminar()

        self.assertEqual([mock.call("Sin selección")] * 3,
                         anunciar.call_args_list)
        self.assertFalse(self.ruta.exists())

    def test_p7_cada_tecla_llama_a_su_accion(self):
        dialogo = self._ventana(guardados=[_perfil()])
        pagina = dialogo._pagina_perfiles
        lista = pagina.lista_perfiles
        lista.SetSelection(0)

        for tecla, accion in ((wx.WXK_RETURN, "editar"),
                              (wx.WXK_F2, "renombrar"),
                              (wx.WXK_DELETE, "eliminar")):
            evento = mock.Mock()
            evento.GetKeyCode.return_value = tecla
            evento.GetEventObject.return_value = lista
            with mock.patch.object(pagina, accion) as llamada:
                pagina._al_tecla(evento)
            llamada.assert_called_once_with()

        evento = mock.Mock()
        evento.GetKeyCode.return_value = ord("D")
        evento.ControlDown.return_value = True
        evento.GetEventObject.return_value = lista
        with mock.patch.object(pagina, "duplicar") as duplicar:
            pagina._al_tecla(evento)
        duplicar.assert_called_once_with()

    def test_p7_la_tecla_de_menu_abre_el_menu_contextual(self):
        dialogo = self._ventana(guardados=[_perfil()])
        pagina = dialogo._pagina_perfiles
        pagina.lista_perfiles.SetSelection(0)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_WINDOWS_MENU
        evento.GetEventObject.return_value = pagina.lista_perfiles
        with mock.patch.object(pagina, "_menu_contextual") as menu:
            pagina._al_tecla(evento)
        menu.assert_called_once_with(evento)

    def test_p10_nuevo_guarda_y_anuncia(self):
        nuevo = _perfil(nombre="Nuevo", canales=(1,))
        dialogo = self._ventana(guardados=[])
        with mock.patch.object(restream_pagina_perfiles,
                               "DialogoPerfilRestream",
                               return_value=_DialogoFalso(nuevo)), \
                mock.patch.object(restream_pagina_perfiles,
                                  "anunciar") as anunciar:
            dialogo._pagina_perfiles.nuevo()

        self.assertEqual([nuevo], perfiles.cargar(self.ruta))
        self.assertEqual(0,
                         dialogo._pagina_perfiles.lista_perfiles.GetSelection())
        anunciar.assert_called_once_with(
            "Perfil de Restream guardado. Elígelo en Transmitir a, al pulsar "
            "Transmitir en directo.")

    def test_p8_duplicar_escribe_nombre_copia_y_su_numero(self):
        original = _perfil(nombre="Canal")
        dialogo = self._ventana(guardados=[original])
        with mock.patch.object(restream_pagina_perfiles,
                               "anunciar") as anunciar:
            dialogo._pagina_perfiles.duplicar()
        self.assertEqual(
            [original, _perfil(nombre="Canal - copia")],
            perfiles.cargar(self.ruta))
        anunciar.assert_called_once_with("Perfil de Restream duplicado.")

        dialogo._pagina_perfiles.lista_perfiles.SetSelection(0)
        with mock.patch.object(restream_pagina_perfiles, "anunciar"):
            dialogo._pagina_perfiles.duplicar()
        self.assertEqual(
            [original, _perfil(nombre="Canal - copia"),
             _perfil(nombre="Canal - copia 2")],
            perfiles.cargar(self.ruta))

    def test_p8_duplicar_tres_veces_no_repite_nombres(self):
        original = _perfil(nombre="Canal")
        dialogo = self._ventana(guardados=[original])
        with mock.patch.object(restream_pagina_perfiles, "anunciar"):
            for _ in range(3):
                dialogo._pagina_perfiles.lista_perfiles.SetSelection(0)
                dialogo._pagina_perfiles.duplicar()

        nombres = [perfil.nombre for perfil in perfiles.cargar(self.ruta)]
        self.assertEqual(
            ["Canal", "Canal - copia", "Canal - copia 2",
             "Canal - copia 3"], nombres)
        self.assertEqual(len(nombres),
                         len({nombre.casefold() for nombre in nombres}))

    def test_p7_eliminar_pide_confirmacion_y_con_si_borra(self):
        primera = _perfil(nombre="Primero")
        segunda = _perfil(nombre="Segundo")
        dialogo = self._ventana(guardados=[primera, segunda])
        pagina = dialogo._pagina_perfiles
        pagina.lista_perfiles.SetSelection(0)
        with mock.patch.object(pagina, "confirmar",
                               return_value=True) as confirmar, \
                mock.patch.object(restream_pagina_perfiles,
                                  "anunciar") as anunciar:
            pagina.eliminar()

        confirmar.assert_called_once_with(primera)
        self.assertEqual([segunda], perfiles.cargar(self.ruta))
        self.assertEqual(0, pagina.lista_perfiles.GetSelection())
        self.assertTrue(pagina.lista_perfiles.HasFocus())
        anunciar.assert_called_once_with("Perfil de Restream eliminado.")

    def test_p7_supr_con_cancelar_no_borra(self):
        dialogo = self._ventana(guardados=[_perfil(nombre="Canal")])
        pagina = dialogo._pagina_perfiles
        pagina.lista_perfiles.SetSelection(0)
        with mock.patch.object(pagina, "confirmar", return_value=False):
            pagina.eliminar()

        self.assertEqual(1, len(perfiles.cargar(self.ruta)))

    def test_p7_la_confirmacion_dice_el_nombre_y_cancelar_es_predeterminado(
            self):
        from guyrapu.ui import confirmar

        dialogo = self._ventana(guardados=[_perfil(nombre="Canal")])
        pagina = dialogo._pagina_perfiles
        with mock.patch.object(confirmar, "preguntar",
                               return_value=False) as preguntar:
            pagina.confirmar(_perfil(nombre="Canal"))
        preguntar.assert_called_once_with(
            pagina, "¿Eliminar el perfil Canal?", "Eliminar perfil",
            "&Eliminar", "&Cancelar", predeterminado_si=False)

    def test_p7_renombrar_rechaza_vacio_y_repetido(self):
        original = _perfil(nombre="Canal")
        otro = _perfil(nombre="Otro")
        dialogo = self._ventana(guardados=[original, otro])
        pagina = dialogo._pagina_perfiles
        pagina.lista_perfiles.SetSelection(0)

        nombres = ["", "Otro", "Nuevo"]

        class _DialogoNombre:
            def __init__(self, _padre, nombre):
                self._nombre = nombres.pop(0)

            def ShowModal(self):
                return wx.ID_OK

            def nombre(self):
                return self._nombre

            def Destroy(self):
                pass

        with mock.patch.object(restream_pagina_perfiles,
                               "DialogoNombrePerfil", _DialogoNombre), \
                mock.patch.object(restream_pagina_perfiles,
                                  "anunciar") as anunciar:
            pagina.renombrar()

        self.assertEqual(
            ["Escribe un nombre para el perfil de Restream.",
             "Ya existe un perfil de Restream con ese nombre.",
             "Nombre cambiado."],
            [llamada.args[0] for llamada in anunciar.call_args_list])
        self.assertEqual(
            ["Nuevo", "Otro"],
            [perfil.nombre for perfil in perfiles.cargar(self.ruta)])

    def test_p6_destinos_muestra_plataforma_nombre_y_desactivado(self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True),
                    Canal(2, 5, "YouTube", "dos", "", False)]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos))
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))

        self.assertEqual(["TikTok: uno", "YouTube: dos, desactivado"],
                         list(pagina.lista.GetStrings()))
        self.assertEqual("Destinos", pagina.lista.GetName())
        self.assertEqual("&Agregar destino…", pagina.btn_agregar.GetLabel())
        self.assertEqual("A&ctualizar", pagina.btn_actualizar.GetLabel())
        self.assertEqual("Agregar destino", pagina.btn_agregar.GetName())
        self.assertEqual("Actualizar", pagina.btn_actualizar.GetName())
        self.assertFalse(hasattr(pagina, "btn_eliminar"))
        self.assertFalse(hasattr(pagina, "btn_activar"))
        self.assertFalse(hasattr(pagina, "btn_titulo"))

    def test_p6_espacio_activa_o_desactiva(self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True),
                    Canal(2, 5, "YouTube", "dos", "", False)]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos))
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))
        pagina.lista.SetSelection(0)

        evento = mock.Mock()
        evento.GetEventObject.return_value = pagina.lista
        evento.GetKeyCode.return_value = wx.WXK_SPACE
        with mock.patch.object(pagina, "_al_activar") as activar:
            pagina._al_tecla(evento)
        activar.assert_called_once_with()

    def test_p6_cada_tecla_llama_a_su_accion(self):
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=_destinos)
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))
        pagina.lista.SetSelection(0)

        for tecla, accion in ((wx.WXK_DELETE, "_al_eliminar"),
                              (wx.WXK_F5, "_al_actualizar")):
            evento = mock.Mock()
            evento.GetEventObject.return_value = pagina.lista
            evento.GetKeyCode.return_value = tecla
            with mock.patch.object(pagina, accion) as llamada:
                pagina._al_tecla(evento)
            llamada.assert_called_once_with()

        evento = mock.Mock()
        evento.GetEventObject.return_value = pagina.lista
        evento.GetKeyCode.return_value = wx.WXK_WINDOWS_MENU
        with mock.patch.object(pagina, "_menu_contextual") as menu:
            pagina._al_tecla(evento)
        menu.assert_called_once_with(evento)

    def test_p6_el_menu_contextual_de_destino_en_orden_y_con_teclas(self):
        from guyrapu.ui import restream_menus

        acciones = mock.Mock()
        menu = restream_menus.menu_destino(
            Canal(1, 67, "TikTok", "uno", "https://a", True), acciones)
        self.addCleanup(menu.Destroy)

        self.assertEqual(
            ["&Activo\tSpace", "Cambiar &título…", "", "Abrir en el "
             "&navegador", "&Copiar enlace\tCtrl+C", "", "&Eliminar\tDel"],
            [elemento.GetItemLabel() for elemento in menu.GetMenuItems()])

    def test_p6_agregar_destino_abre_el_menu_de_los_dos_caminos(self):
        dialogo = self._ventana()
        pagina = dialogo._pagina_destinos
        with mock.patch.object(restream_pagina_destinos.restream_menus,
                               "menu_agregar") as menu, \
                mock.patch.object(pagina.btn_agregar, "PopupMenu"):
            pagina._abrir_menu_agregar(mock.Mock())
        menu.assert_called_once_with(pagina._agregar,
                                     pagina._agregar_manual)

    def _destino_con_url(self, url):
        destinos = [Canal(1, 67, "TikTok", "uno", url, True)]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos))
        self.assertTrue(_esperar(
            lambda: dialogo._pagina_destinos.lista.GetCount() == 1))
        dialogo._pagina_destinos.lista.SetSelection(0)
        return dialogo

    def test_p6_abrir_enlace_usa_la_url_del_destino(self):
        dialogo = self._destino_con_url("https://a")
        with mock.patch.object(restream_acciones_destino,
                               "abrir_navegador") as abrir,                 mock.patch.object(restream_acciones_destino,
                                  "anunciar") as anunciar:
            restream_acciones_destino.abrir_enlace(dialogo)
        abrir.assert_called_once_with("https://a")
        anunciar.assert_not_called()

    def test_p6_abrir_enlace_vacio_anuncia_y_no_abre(self):
        dialogo = self._destino_con_url("")
        with mock.patch.object(restream_acciones_destino,
                               "abrir_navegador") as abrir,                 mock.patch.object(restream_acciones_destino,
                                  "anunciar") as anunciar:
            restream_acciones_destino.abrir_enlace(dialogo)
        abrir.assert_not_called()
        anunciar.assert_called_once_with("Este destino no tiene enlace.")

    def test_p6_copiar_enlace_usa_la_url_y_suena(self):
        dialogo = self._destino_con_url("https://a")
        with mock.patch.object(restream_acciones_destino,
                               "copiar_al_portapapeles") as copiar,                 mock.patch.object(restream_acciones_destino,
                                  "anunciar") as anunciar,                 mock.patch.object(restream_acciones_destino._snd,
                                  "reproducir") as sonar:
            restream_acciones_destino.copiar_enlace(dialogo)
        copiar.assert_called_once_with("https://a")
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Enlace copiado.")

    def test_p6_copiar_enlace_vacio_anuncia_y_no_toca_el_portapapeles(self):
        dialogo = self._destino_con_url("")
        with mock.patch.object(restream_acciones_destino,
                               "copiar_al_portapapeles") as copiar,                 mock.patch.object(restream_acciones_destino,
                                  "anunciar") as anunciar,                 mock.patch.object(restream_acciones_destino._snd,
                                  "reproducir") as sonar:
            restream_acciones_destino.copiar_enlace(dialogo)
        copiar.assert_not_called()
        sonar.assert_not_called()
        anunciar.assert_called_once_with("Este destino no tiene enlace.")

    def test_p2_activar_desde_la_pestana_actualiza_y_anuncia(self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True),
                    Canal(2, 5, "YouTube", "dos", "", True)]
        llamadas = []

        def activar(identificador, activo, cliente=None):
            llamadas.append((identificador, activo))

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos))
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))
        pagina.lista.SetSelection(0)

        with mock.patch.object(restream_acciones_destino.cuenta,
                               "activar_canal", side_effect=activar), \
                mock.patch.object(restream_acciones_destino,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_acciones_destino._snd,
                                  "reproducir") as sonar, \
                mock.patch.object(restream_acciones_destino, "avisar",
                                  _avisar_de(anunciar, sonar)):
            pagina._activar()
            self.assertTrue(_esperar(lambda: llamadas))
            self.assertTrue(_esperar(lambda: anunciar.called))

        self.assertEqual([(1, False)], llamadas)
        self.assertFalse(dialogo._destinos[0].activo)
        self.assertEqual(["TikTok: uno, desactivado", "YouTube: dos"],
                         list(pagina.lista.GetStrings()))
        self.assertEqual(0, pagina.lista.GetSelection())
        anunciar.assert_called_once_with("TikTok: uno desactivado")
        sonar.assert_not_called()

    def test_p3_destinos_instala_la_busqueda_por_teclado(self):
        with mock.patch.object(restream_pagina_destinos,
                               "instalar_busqueda_tipo") as instalar:
            dialogo = self._ventana()
        instalar.assert_called_once()
        self.assertIs(dialogo._pagina_destinos.lista,
                      instalar.call_args.args[0])

    def test_p3_destinos_supr_elimina(self):
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=_destinos)
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))
        pagina.lista.SetSelection(0)

        evento = mock.Mock()
        evento.GetEventObject.return_value = pagina.lista
        evento.GetKeyCode.return_value = wx.WXK_DELETE
        with mock.patch.object(pagina, "_al_eliminar") as eliminar:
            pagina._al_tecla(evento)
        eliminar.assert_called_once_with()

    def test_p4_agregar_destino_abre_la_pagina_y_al_volver_anuncia_los_nuevos(
            self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True)]
        lecturas = []

        def leer():
            lecturas.append(True)
            return list(destinos)

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=leer)
        self.assertTrue(_esperar(lambda: dialogo._destinos))
        with mock.patch.object(restream_pagina_destinos,
                               "abrir_navegador") as abrir, \
                mock.patch.object(restream_ventana,
                                  "anunciar") as anunciar:
            dialogo._pagina_destinos._agregar()
            abrir.assert_called_once_with(restream_pagina_destinos.URL_DESTINOS)
            anunciar.assert_called_once_with(
                "Restream se abre en el navegador. Agrega el destino ahí y "
                "vuelve a Guyrapu.")

            destinos.append(Canal(2, 5, "YouTube", "dos", "", True))
            evento = mock.Mock()
            evento.GetActive.return_value = True
            dialogo._al_activar(evento)
            self.assertTrue(_esperar(
                lambda: "Destino agregado: YouTube: dos."
                in [llamada.args[0] for llamada in anunciar.call_args_list]))
            evento.Skip.assert_called()

            anunciar.reset_mock()
            antes = len(lecturas)
            dialogo._al_activar(evento)
            wx.Yield()
            self.assertEqual(antes, len(lecturas))
            anunciar.assert_not_called()

    def test_p5_la_pregunta_nombra_el_destino_y_los_perfiles(self):
        dialogo = self._ventana()
        self.assertEqual(
            "¿Eliminar TikTok: uno de la cuenta de Restream? Los perfiles "
            "de Restream que lo usan dejan de transmitir ahí.",
            dialogo._pagina_destinos.pregunta("TikTok: uno"))

    def test_p5_eliminar_destino_pregunta_lo_borra_y_anuncia(self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True),
                    Canal(2, 5, "YouTube", "dos", "", True)]
        eliminados = []

        def eliminar(identificador):
            eliminados.append(identificador)

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
            eliminar=eliminar)
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 2))
        pagina.lista.SetSelection(0)

        with mock.patch.object(pagina, "confirmar",
                               return_value=True) as confirmar, \
                mock.patch.object(restream_ventana,
                                  "anunciar") as anunciar:
            dialogo._eliminar_destino()
            confirmar.assert_called_once_with("TikTok: uno")
            self.assertTrue(_esperar(lambda: eliminados))
            self.assertTrue(_esperar(
                lambda: "Destino eliminado."
                in [llamada.args[0] for llamada in anunciar.call_args_list]))

        self.assertEqual([1], eliminados)
        self.assertEqual([2], [destino.id for destino in dialogo._destinos])
        self.assertEqual(["YouTube: dos"], list(pagina.lista.GetStrings()))

    def test_p5_eliminar_destino_que_falla_suena_anuncia_y_deja_su_texto(
            self):
        destinos = [Canal(1, 67, "TikTok", "uno", "", True)]

        def eliminar(_identificador):
            raise ErrorApi()

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
            eliminar=eliminar)
        pagina = dialogo._pagina_destinos
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)

        sonar = mock.Mock()
        with mock.patch.object(pagina, "confirmar", return_value=True), \
                mock.patch.object(restream_ventana,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)):
            dialogo._eliminar_destino()
            self.assertTrue(_esperar(lambda: sonar.called))
            self.assertTrue(_esperar(lambda: anunciar.called))

        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with(
            "No se pudo eliminar el destino. Vuelve a intentarlo.")
        lineas = dialogo._pagina_cuenta.txt_estado.GetValue().splitlines()
        self.assertEqual("Cuenta de Restream conectada.", lineas[0])
        self.assertIn(
            "No se pudo eliminar el destino. Vuelve a intentarlo.", lineas)
        self.assertEqual([1], [destino.id for destino in dialogo._destinos])

    def test_p3_la_cuenta_dice_correo_cantidades_y_el_paso_que_falta(self):
        datos = SimpleNamespace(correo="manu@example.com",
                                usuario="manolopez643")
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=_destinos,
            perfil=lambda: datos)
        self.assertTrue(_esperar(
            lambda: "manu@example.com"
            in dialogo._pagina_cuenta.txt_estado.GetValue()))
        self.assertTrue(_esperar(
            lambda: "2 destinos, 2 activos. 0 perfiles."
            in dialogo._pagina_cuenta.txt_estado.GetValue()))

        lineas = dialogo._pagina_cuenta.txt_estado.GetValue().splitlines()
        self.assertEqual("Cuenta conectada: manu@example.com.", lineas[0])
        self.assertEqual("2 destinos, 2 activos. 0 perfiles.", lineas[1])
        self.assertEqual(
            "Todavía no hay perfiles. Créalos en la pestaña Perfiles.",
            lineas[2])

    def test_p3_sin_correo_usa_el_nombre_de_usuario(self):
        datos = SimpleNamespace(correo="", usuario="manolopez643")
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: [],
            perfil=lambda: datos)
        self.assertTrue(_esperar(
            lambda: "manolopez643"
            in dialogo._pagina_cuenta.txt_estado.GetValue()))
        self.assertEqual(
            "Cuenta conectada: manolopez643.",
            dialogo._pagina_cuenta.txt_estado.GetValue().splitlines()[0])

    def test_p3_dice_que_el_youtube_de_restream_es_el_de_la_sesion(self):
        destinos = [Canal(1, 5, "YouTube", "uno", "", True, "UCsesion")]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
            id_canal=lambda: "UCsesion")

        self.assertTrue(_esperar(
            lambda: "YouTube en Restream" in
            dialogo._pagina_cuenta.txt_estado.GetValue()))
        self.assertIn(
            "YouTube en Restream: uno, el mismo canal de la sesión de "
            "Guyrapu.",
            dialogo._pagina_cuenta.txt_estado.GetValue().splitlines())

    def test_p3_dice_que_el_youtube_de_restream_no_es_el_de_la_sesion(self):
        destinos = [Canal(1, 5, "YouTube", "uno", "", True, "UCotro")]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
            id_canal=lambda: "UCsesion")

        self.assertTrue(_esperar(
            lambda: "YouTube en Restream" in
            dialogo._pagina_cuenta.txt_estado.GetValue()))
        self.assertIn(
            "YouTube en Restream: uno, que no es el canal de la sesión de "
            "Guyrapu.",
            dialogo._pagina_cuenta.txt_estado.GetValue().splitlines())

    def test_p4_sin_identificador_de_la_sesion_no_hay_linea(self):
        destinos = [Canal(1, 5, "YouTube", "uno", "", True, "UCsesion")]
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
            id_canal=lambda: "")

        self.assertTrue(_esperar(lambda: dialogo._destinos))
        wx.Yield()
        self.assertNotIn(
            "YouTube en Restream",
            dialogo._pagina_cuenta.txt_estado.GetValue())

    def test_p4_un_fallo_al_pedir_el_identificador_no_deja_linea_ni_avisa(
            self):
        def id_canal():
            raise ValueError("sin red")

        destinos = [Canal(1, 5, "YouTube", "uno", "", True, "UCsesion")]
        sonar = mock.Mock()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana, "avisar",
                                  _avisar_de(anunciar, sonar)), \
                self.assertLogs(restream_ventana.logger, level="WARNING"):
            dialogo = self._ventana(
                cuenta=CuentaFalsa(True), destinos=lambda: list(destinos),
                id_canal=id_canal)
            self.assertTrue(_esperar(lambda: dialogo._destinos))
            wx.Yield()

        self.assertNotIn(
            "YouTube en Restream",
            dialogo._pagina_cuenta.txt_estado.GetValue())
        self.assertIn("1 destino, 1 activo. 0 perfiles.",
                      dialogo._pagina_cuenta.txt_estado.GetValue())
        anunciar.assert_not_called()
        sonar.assert_not_called()

    def test_p4_lo_pide_una_vez_por_lectura_y_no_al_cambiar_de_pestana(self):
        llamadas = []
        principal = []

        def id_canal():
            llamadas.append(True)
            principal.append(_es_hilo_principal())
            return ""

        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=_destinos, id_canal=id_canal)
        self.assertTrue(_esperar(lambda: len(llamadas) == 1))
        wx.Yield()
        self.assertEqual([False], principal)

        evento = mock.Mock()
        evento.GetSelection.return_value = 3
        dialogo._al_cambiar_pestana(evento)
        wx.Yield()
        self.assertEqual(1, len(llamadas))

        dialogo._leer_canales()
        self.assertTrue(_esperar(lambda: len(llamadas) == 2))

    def test_p7_al_cambiar_a_eventos_la_pestana_se_muestra(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(True))
        with mock.patch.object(dialogo._pagina_eventos,
                               "al_mostrarse") as mostrar:
            evento = mock.Mock()
            evento.GetSelection.return_value = 3
            dialogo._al_cambiar_pestana(evento)

        mostrar.assert_called_once_with()
        evento.Skip.assert_called_once_with()

    def test_p7_el_menu_de_perfil_en_orden_y_con_teclas(self):
        from guyrapu.ui import restream_menus

        acciones = mock.Mock()
        menu = restream_menus.menu_perfil(acciones)
        self.addCleanup(menu.Destroy)
        self.assertEqual(
            ["&Editar…\tEnter", "Cambiar &nombre…\tF2",
             "&Duplicar\tCtrl+D", "", "E&liminar\tDel"],
            [elemento.GetItemLabel() for elemento in menu.GetMenuItems()])

    def test_p5_desconectar_pide_confirmacion_y_cancelar_no_desconecta(self):
        from guyrapu.ui import confirmar

        desconectadas = []
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True),
            al_desconectar=lambda: desconectadas.append(True))
        pagina = dialogo._pagina_cuenta
        with mock.patch.object(confirmar, "preguntar",
                               return_value=False) as preguntar:
            pagina._desconectar()

        preguntar.assert_called_once_with(
            pagina,
            "¿Desconectar la cuenta de Restream? Para volver a usarla hay "
            "que iniciar sesión otra vez en el navegador.",
            "Desconectar cuenta", "&Desconectar", "&Cancelar",
            predeterminado_si=False)
        self.assertEqual([], desconectadas)

    def test_p11_un_fallo_de_actualizar_en_destinos_suena_y_se_anuncia(self):
        dialogo = self._ventana(
            cuenta=CuentaFalsa(True), destinos=lambda: [])
        pagina = dialogo._pagina_destinos

        def falla():
            raise ValueError("sin red")

        dialogo._fuente_destinos = falla
        with mock.patch.object(restream_ventana, "anunciar") as anunciar, \
                mock.patch.object(restream_ventana._snd,
                                  "reproducir") as sonar:
            pagina._al_actualizar()
            self.assertTrue(_esperar(lambda: sonar.called))
            self.assertTrue(_esperar(lambda: anunciar.called))

        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with("No se pudieron leer los destinos.")

    def test_p13_sin_cuenta_avisa_una_vez_al_enfocar_las_listas(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(False))
        with mock.patch.object(restream_pagina_destinos,
                               "anunciar") as en_destinos, \
                mock.patch.object(restream_pagina_perfiles,
                                  "anunciar") as en_perfiles:
            evento = mock.Mock()
            dialogo._pagina_destinos._al_foco(evento)
            dialogo._pagina_destinos._al_foco(evento)
            dialogo._pagina_perfiles._al_foco(evento)
        en_destinos.assert_called_once_with(
            "Sin cuenta de Restream. Conéctala en la pestaña Cuenta.")
        en_perfiles.assert_not_called()
        self.assertTrue(evento.Skip.called)

    def test_p13_el_cuadro_de_perfil_sin_cuenta_dice_lo_mismo(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(False))
        recibidos = []

        def abrir(_padre, perfil, canales, existentes, **cambios):
            recibidos.append(cambios.get("sin_cuenta"))
            return _DialogoFalso(perfil)

        with mock.patch.object(restream_pagina_perfiles,
                               "DialogoPerfilRestream",
                               side_effect=abrir):
            dialogo._pagina_perfiles._pedir_perfil(None, [])
        self.assertEqual([True], recibidos)

    def test_letras_de_acceso_sin_repetir_en_cada_pestana(self):
        dialogo = self._ventana(guardados=[_perfil()])
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                dialogo, dialogo.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._ventana(guardados=[_perfil(nombre="TikTok")])
            sin_marcar = textos_sin_marcar(dialogo, propios=("TikTok",))
        self.assertEqual([], sin_marcar)


class PruebaPaginaEventos(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    @staticmethod
    def _evento(estado="upcoming", destinos=None, **cambios):
        datos = dict(
            id="fa2f5c54-4de5-4118-a4b0-925c648c49d6",
            estado=estado, titulo="Charla",
            descripcion="Una charla", programado=1000.0,
            empezado=None, terminado=None,
            destinos=tuple(destinos or ()))
        datos.update(cambios)
        return eventos_restream.Evento(**datos)

    def _pagina(self, leer_eventos=None, leer_estadisticas=None,
                conectada=True, nombres=None):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        pagina = restream_pagina_eventos.PaginaEventos(
            marco,
            leer_eventos or (lambda tipo: []),
            leer_estadisticas or (
                lambda identificador: eventos_restream.Estadisticas(0, 0, 0, 0)),
            lambda: nombres or {},
            lambda: conectada)
        self.addCleanup(destruir, pagina)
        return pagina

    def test_p12_controles_en_orden_de_tab_y_sus_rotulos(self):
        pagina = self._pagina()

        self.assertEqual(
            ["Mostrar", "Eventos", "Detalle del evento", "Actualizar"],
            [control.GetName() for control in _controles_en_orden(pagina)])
        self.assertEqual("&Mostrar:", pagina.lbl_mostrar.GetLabel())
        self.assertEqual(["Próximos", "En directo", "Historial"],
                         list(pagina.cho_mostrar.GetStrings()))
        self.assertEqual(0, pagina.cho_mostrar.GetSelection())
        self.assertEqual("&Detalle del evento:",
                         pagina.lbl_detalle.GetLabel())
        self.assertFalse(pagina.detalle.IsEditable())
        self.assertEqual("A&ctualizar", pagina.btn_actualizar.GetLabel())
        self.assertFalse(hasattr(pagina, "btn_copiar"))
        self.assertFalse(hasattr(pagina, "btn_estadisticas"))

    def test_p12_cada_tecla_llama_a_su_accion(self):
        pagina = self._pagina()
        eventos = (
            (wx.WXK_F5, "actualizar"),
            (wx.WXK_RETURN, "estadisticas"),
        )
        for tecla, accion in eventos:
            evento = mock.Mock()
            evento.GetEventObject.return_value = pagina.lista
            evento.GetKeyCode.return_value = tecla
            with mock.patch.object(pagina, accion) as llamada:
                pagina._al_tecla(evento)
            llamada.assert_called_once_with()

        evento = mock.Mock()
        evento.GetEventObject.return_value = pagina.lista
        evento.GetKeyCode.return_value = ord("C")
        evento.ControlDown.return_value = True
        with mock.patch.object(pagina, "copiar_enlaces") as copiar:
            pagina._al_tecla(evento)
        copiar.assert_called_once_with()

        evento = mock.Mock()
        evento.GetEventObject.return_value = pagina.lista
        evento.GetKeyCode.return_value = wx.WXK_WINDOWS_MENU
        with mock.patch.object(pagina, "_menu_contextual") as menu:
            pagina._al_tecla(evento)
        menu.assert_called_once_with(evento)

    def test_p12_el_menu_de_evento_en_orden_y_con_teclas(self):
        from guyrapu.ui import restream_menus

        acciones = mock.Mock()
        menu = restream_menus.menu_evento(
            acciones, [("TikTok: uno", "https://a")])
        self.addCleanup(menu.Destroy)
        self.assertEqual(
            ["&Copiar enlaces\tCtrl+C", "Copiar &información",
             "&Abrir el directo", "&Estadísticas\tEnter"],
            [elemento.GetItemLabel() for elemento in menu.GetMenuItems()])

        menu = restream_menus.menu_evento(
            acciones, [("TikTok: uno", "https://a"),
                       ("YouTube: dos", "https://b")])
        self.addCleanup(menu.Destroy)
        abrir = next(elemento for elemento in menu.GetMenuItems()
                     if elemento.GetItemLabel() == "&Abrir el directo")
        self.assertIsNotNone(abrir.GetSubMenu())
        self.assertEqual(
            ["TikTok: uno", "YouTube: dos"],
            [elemento.GetItemLabel()
             for elemento in abrir.GetSubMenu().GetMenuItems()])

    def test_p12_copiar_informacion_copia_el_detalle(self):
        evento = self._evento()
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)
        pagina._al_elegir(mock.Mock())
        detalle = pagina.detalle.GetValue()

        with mock.patch.object(restream_pagina_eventos,
                               "copiar_al_portapapeles") as copiar, \
                mock.patch.object(restream_pagina_eventos,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_pagina_eventos._snd,
                                  "reproducir") as sonar:
            pagina.copiar_informacion()

        copiar.assert_called_once_with(detalle)
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Información copiada.")

    def test_p12_abrir_el_directo_con_un_solo_enlace(self):
        evento = self._evento(destinos=(
            eventos_restream.DestinoEvento(10, 10, 67, "https://a"),))
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)
        with mock.patch.object(restream_pagina_eventos,
                               "abrir_navegador") as abrir:
            pagina.abrir_directo()
        abrir.assert_called_once_with("https://a")

    def test_p12_abrir_el_directo_sin_enlaces_lo_dice(self):
        evento = self._evento(destinos=(
            eventos_restream.DestinoEvento(10, 10, 67, ""),))
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)
        with mock.patch.object(restream_pagina_eventos,
                               "abrir_navegador") as abrir, \
                mock.patch.object(restream_pagina_eventos,
                                  "anunciar") as anunciar:
            pagina.abrir_directo()
        abrir.assert_not_called()
        anunciar.assert_called_once_with(
            "Este evento no tiene enlaces todavía.")

    def test_p5_copiar_enlaces_escribe_uno_por_linea_y_avisa(self):
        evento = self._evento(destinos=(
            eventos_restream.DestinoEvento(10, 10, 67, "https://a"),
            eventos_restream.DestinoEvento(11, 11, 5, "https://b"),
        ))
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)

        with mock.patch.object(restream_pagina_eventos,
                               "copiar_al_portapapeles") as copiar, \
                mock.patch.object(restream_pagina_eventos,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_pagina_eventos._snd,
                                  "reproducir") as sonar:
            pagina.copiar_enlaces()

        copiar.assert_called_once_with("https://a\nhttps://b")
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Enlaces copiados.")

    def test_p5_sin_enlaces_suena_error_y_lo_dice(self):
        evento = self._evento(destinos=(
            eventos_restream.DestinoEvento(10, 10, 67, ""),
        ))
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)

        with mock.patch.object(restream_pagina_eventos,
                               "copiar_al_portapapeles") as copiar, \
                mock.patch.object(restream_pagina_eventos,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_pagina_eventos._snd,
                                  "reproducir") as sonar:
            pagina.copiar_enlaces()

        copiar.assert_not_called()
        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with(
            "Este evento no tiene enlaces todavía.")

    def test_p6_estadisticas_se_agregan_al_detalle_y_se_anuncian(self):
        evento = self._evento(
            estado="finished", programado=None, empezado=1000.0,
            terminado=1100.0)
        leidas = eventos_restream.Estadisticas(
            promedio=3, maximo=8, vistas=20, tiempo_visto=90)
        llamadas = []

        def leer(identificador):
            llamadas.append(identificador)
            return leidas

        pagina = self._pagina(
            leer_eventos=lambda tipo: [evento], leer_estadisticas=leer)
        pagina.cho_mostrar.SetSelection(2)
        pagina._al_cambiar_mostrar(None)
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)
        frase = eventos_restream.frase_estadisticas(leidas)

        with mock.patch.object(restream_pagina_eventos,
                               "anunciar") as anunciar:
            pagina.estadisticas()
            self.assertTrue(_esperar(lambda: anunciar.called))

        self.assertEqual(
            ["fa2f5c54-4de5-4118-a4b0-925c648c49d6"], llamadas)
        self.assertTrue(pagina.detalle.GetValue().endswith(frase))
        anunciar.assert_called_once_with(frase)

    def test_p6_en_proximos_suena_error_y_no_pide_estadisticas(self):
        evento = self._evento()
        pagina = self._pagina(leer_eventos=lambda tipo: [evento])
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: pagina.lista.GetCount() == 1))
        pagina.lista.SetSelection(0)

        with mock.patch.object(pagina, "_leer_estadisticas") as leer, \
                mock.patch.object(restream_pagina_eventos,
                                  "anunciar") as anunciar, \
                mock.patch.object(restream_pagina_eventos._snd,
                                  "reproducir") as sonar:
            pagina.estadisticas()

        leer.assert_not_called()
        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with(
            "Un evento que no empezó no tiene estadísticas.")

    def test_p7_al_mostrarse_lee_una_sola_vez(self):
        llamadas = []

        def leer(tipo):
            llamadas.append(tipo)
            return []

        pagina = self._pagina(leer_eventos=leer)
        pagina.al_mostrarse()
        self.assertTrue(_esperar(lambda: llamadas))
        pagina.al_mostrarse()
        wx.Yield()

        self.assertEqual([eventos_restream.TIPO_PROXIMOS], llamadas)

    def test_p7_cambiar_mostrar_pide_el_tipo_correcto(self):
        llamadas = []

        def leer(tipo):
            llamadas.append(tipo)
            return []

        pagina = self._pagina(leer_eventos=leer)
        pagina.cho_mostrar.SetSelection(1)
        pagina._al_cambiar_mostrar(None)
        self.assertTrue(_esperar(
            lambda: llamadas == [eventos_restream.TIPO_EN_DIRECTO]))

        pagina.cho_mostrar.SetSelection(2)
        pagina._al_cambiar_mostrar(None)
        self.assertTrue(_esperar(
            lambda: llamadas == [eventos_restream.TIPO_EN_DIRECTO,
                                 eventos_restream.TIPO_HISTORIAL]))

    def test_p7_actualizar_vuelve_a_leer(self):
        llamadas = []

        def leer(tipo):
            llamadas.append(tipo)
            return []

        pagina = self._pagina(leer_eventos=leer)
        pagina.actualizar()
        self.assertTrue(_esperar(lambda: len(llamadas) == 1))
        pagina.actualizar()
        self.assertTrue(_esperar(lambda: len(llamadas) == 2))
        self.assertEqual([eventos_restream.TIPO_PROXIMOS] * 2, llamadas)

    def test_p7_sin_cuenta_deja_la_lista_vacia_y_lo_dice(self):
        llamadas = []

        def leer(tipo):
            llamadas.append(tipo)
            return []

        pagina = self._pagina(leer_eventos=leer, conectada=False)
        pagina.al_mostrarse()
        wx.Yield()

        self.assertEqual(0, pagina.lista.GetCount())
        self.assertEqual(
            "Conecta una cuenta de Restream en la pestaña Cuenta.",
            pagina.detalle.GetValue())
        self.assertEqual([], llamadas)

    def test_p7_un_fallo_de_red_suena_y_se_anuncia(self):
        error = ErrorApi()

        def leer(_tipo):
            raise error

        pagina = self._pagina(leer_eventos=leer)
        with mock.patch.object(restream_pagina_eventos,
                               "anunciar") as anunciar, \
                mock.patch.object(restream_pagina_eventos._snd,
                                  "reproducir") as sonar:
            pagina.al_mostrarse()
            self.assertTrue(_esperar(lambda: sonar.called))

        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with(str(error))
        self.assertEqual(0, pagina.lista.GetCount())

    def test_p8_sin_evento_elegido_las_dos_acciones_lo_dicen(self):
        pagina = self._pagina()

        with mock.patch.object(restream_pagina_eventos,
                               "anunciar") as anunciar:
            pagina.copiar_enlaces()
            pagina.estadisticas()

        self.assertEqual([mock.call("Sin selección")] * 2,
                         anunciar.call_args_list)


class PruebaVisibilidadYoutube(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def test_p7_privacidad_y_latencia_solo_con_youtube_marcado(self):
        dialogo = restream_perfil.DialogoPerfilRestream(
            None, None, _canales(), [])
        self.addCleanup(destruir, dialogo)

        nombres = [control.GetName() for control in _controles_en_orden(dialogo)]
        self.assertNotIn("Privacidad en YouTube", nombres)
        self.assertNotIn("Latencia en YouTube", nombres)

        dialogo._casillas[1][1].SetValue(True)
        dialogo._actualizar_youtube()
        nombres = [control.GetName() for control in _controles_en_orden(dialogo)]
        self.assertIn("Privacidad en YouTube", nombres)
        self.assertIn("Latencia en YouTube", nombres)

        dialogo._casillas[1][1].SetValue(False)
        dialogo._actualizar_youtube()
        nombres = [control.GetName() for control in _controles_en_orden(dialogo)]
        self.assertNotIn("Privacidad en YouTube", nombres)
        self.assertNotIn("Latencia en YouTube", nombres)


class PruebaDialogoPerfil(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.canales = _canales()

    def _dialogo(self, perfil=None, canales=None, existentes=None):
        dialogo = restream_perfil.DialogoPerfilRestream(
            None, perfil, self.canales if canales is None else canales,
            existentes or [])
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_p4_campos_nombres_y_orden_de_tab(self):
        dialogo = self._dialogo()
        self.assertEqual("DialogoPerfilRestream", dialogo.GetName())
        self.assertEqual("Nuevo perfil de Restream", dialogo.GetTitle())
        self.assertEqual(
            ["Nombre", "Orientación", "TikTok: uno", "YouTube: dos",
             "Título", "Descripción, opcional", "Guardar", "Cancelar"],
            [control.GetName() for control in _controles_en_orden(dialogo)])

        dialogo._casillas[1][1].SetValue(True)
        dialogo._actualizar_youtube()
        self.assertEqual(
            ["Nombre", "Orientación", "TikTok: uno", "YouTube: dos",
             "Título", "Descripción, opcional", "Privacidad en YouTube",
             "Latencia en YouTube", "Guardar", "Cancelar"],
            [control.GetName() for control in _controles_en_orden(dialogo)])

        self.assertEqual(
            [_(ETIQUETAS_PRIVACIDAD[p]) for p in PRIVACIDADES],
            list(dialogo.cho_privacidad.GetStrings()))
        self.assertEqual(
            [_(ETIQUETAS_LATENCIA[l]) for l in LATENCIAS],
            list(dialogo.cho_latencia.GetStrings()))
        self.assertEqual(PRIVACIDAD_INICIAL,
                         PRIVACIDADES[dialogo.cho_privacidad.GetSelection()])
        self.assertEqual(LATENCIA_INICIAL,
                         LATENCIAS[dialogo.cho_latencia.GetSelection()])
        self.assertEqual("Editar perfil de Restream",
                         self._dialogo(_perfil()).GetTitle())

    def test_p4_cada_rotulo_se_crea_antes_de_su_control(self):
        dialogo = self._dialogo()
        padre = dialogo.txt_nombre.GetParent()
        hijos = list(padre.GetChildren())
        rotulos = 0
        for posicion, hijo in enumerate(hijos):
            if not isinstance(hijo, wx.StaticText):
                continue
            if not _letra_de_acceso(hijo.GetLabel()):
                continue
            rotulos += 1
            with self.subTest(rotulo=hijo.GetLabel()):
                self.assertLess(posicion + 1, len(hijos))
                siguiente = hijos[posicion + 1]
                self.assertNotIsInstance(siguiente, wx.StaticText)
                self.assertEqual(
                    nombre_de_etiqueta(hijo.GetLabel()), siguiente.GetName())
        self.assertEqual(6, rotulos)

    def test_p4_sin_destinos_muestra_la_nota_y_valida(self):
        dialogo = self._dialogo(canales=[])
        dialogo.txt_nombre.SetValue("Prueba")
        with mock.patch.object(restream_perfil, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)

        texto = anunciar.call_args.args[0]
        self.assertIn("Agrega al menos un destino al perfil de Restream.",
                      texto)
        fin.assert_not_called()
        self.assertIsNone(dialogo.perfil())

    def test_p4_nombre_repetido_anuncia_y_enfoca_el_nombre(self):
        existente = _perfil(nombre="Canal")
        dialogo = self._dialogo(existentes=[existente])
        dialogo.txt_nombre.SetValue("Canal")
        dialogo._casillas[0][1].SetValue(True)
        with mock.patch.object(restream_perfil, "anunciar") as anunciar, \
                mock.patch.object(dialogo.txt_nombre, "SetFocus") as foco, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)

        anunciar.assert_called_once_with(
            "Ya existe un perfil de Restream con ese nombre.")
        foco.assert_called_once_with()
        fin.assert_not_called()

    def test_p4_guardar_valido_cierra_y_devuelve_el_perfil(self):
        dialogo = self._dialogo()
        dialogo.txt_nombre.SetValue("Nuevo")
        dialogo.cho_orientacion.SetSelection(1)
        dialogo._casillas[1][1].SetValue(True)
        dialogo.txt_titulo.SetValue("Título")
        dialogo.txt_descripcion.SetValue("Descripción")
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)

        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual(
            Perfil(nombre="Nuevo", canales=(2,), orientacion="vertical",
                   titulo="Título", descripcion="Descripción",
                   privacidad=PRIVACIDAD_INICIAL,
                   latencia=LATENCIA_INICIAL),
            dialogo.perfil())

    def test_p6_destino_sobrante_avisa_y_queda_fuera_al_guardar(self):
        perfil = _perfil(nombre="Viejo", canales=(1, 99))
        dialogo = self._dialogo(
            perfil=perfil, canales=[(1, "TikTok: uno")])
        self.assertEqual(1, len(dialogo._casillas))
        self.assertIn(
            "Hay 1 destino del perfil de Restream que ya no está en "
            "Restream. Se eliminará al guardar.",
            dialogo._nota_sobrantes.GetLabel())

        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)
        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual((1,), dialogo.perfil().canales)

        plural = self._dialogo(perfil=_perfil(canales=(98, 99)))
        self.assertIn(
            "Hay 2 destinos del perfil de Restream que ya no están en "
            "Restream. Se eliminarán al guardar.",
            plural._nota_sobrantes.GetLabel())

    def test_p6_sin_destinos_la_caja_lo_dice(self):
        dialogo = self._dialogo(canales=[])
        caja = dialogo._caja_canales.GetStaticBox()
        self.assertEqual("Destinos", caja.GetLabel())
        textos = [hijo.GetLabel() for hijo in caja.GetChildren()
                  if isinstance(hijo, wx.StaticText)]
        self.assertIn(
            "No hay destinos. Agrégalos en la pestaña Destinos.", textos)

    def test_p13_sin_cuenta_la_caja_lo_dice_en_lugar_de_agregar_destinos(
            self):
        dialogo = restream_perfil.DialogoPerfilRestream(
            None, _perfil(canales=(1, 2)), [], [], sin_cuenta=True)
        self.addCleanup(destruir, dialogo)
        self.assertIsNone(dialogo._nota_sobrantes)
        caja = dialogo._caja_canales.GetStaticBox()
        textos = [hijo.GetLabel() for hijo in caja.GetChildren()
                  if isinstance(hijo, wx.StaticText)]
        self.assertIn(
            "Sin cuenta de Restream. Conéctala en la pestaña Cuenta.",
            textos)
        self.assertNotIn(
            "No hay destinos. Agrégalos en la pestaña Destinos.", textos)

    def test_letras_de_acceso_sin_repetir_en_el_dialogo(self):
        self.assertEqual({}, letras_repetidas(self._dialogo()))

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(
                dialogo, propios=("TikTok: uno", "YouTube: dos"))
        self.assertEqual([], sin_marcar)


if __name__ == "__main__":
    unittest.main()
