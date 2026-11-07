"""Pruebas de los cuadros de destino de Restream y de sus acciones.

Crean ventanas de wx: se corren en la PC donde no molestan al lector. Las
llamadas a Restream son dobles y las acciones vuelven al hilo principal con
un doble que las deja pendientes para ejecutarlas en la prueba.
"""

import logging
import threading
import time
import unittest
from unittest import mock

import wx

from guyrapu.restream.api import Canal, ErrorApi, MetaCanal
from guyrapu.ui import restream_acciones_destino as acciones
from guyrapu.ui import restream_dialogos_destino as dialogos
from tests.letras_acceso import letras_repetidas
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import app_de_prueba, destruir


def _orden(ventana):
    """Controles que toman foco, en el orden en que wx los recorre."""
    orden = []
    for hijo in ventana.GetChildren():
        if isinstance(hijo, (wx.ScrolledWindow, wx.Panel, wx.StaticBox)):
            orden.extend(_orden(hijo))
        elif hijo.IsShown() and hijo.AcceptsFocus():
            orden.append(hijo)
    return orden


def _esperar(prueba, limite=5.0):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if prueba():
            return True
        time.sleep(0.01)
    return prueba()


class PruebaDialogoMeta(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def _dialogo(self, titulo="Título", descripcion="Descripción"):
        dialogo = dialogos.DialogoMetaDestino(
            None, MetaCanal(titulo, descripcion))
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_p3_campos_llenados_nombres_y_orden_de_tab(self):
        dialogo = self._dialogo("Uno", "Dos")

        self.assertEqual("Cambiar título", dialogo.GetTitle())
        self.assertEqual("Uno", dialogo.txt_titulo.GetValue())
        self.assertEqual("Dos", dialogo.txt_descripcion.GetValue())
        self.assertEqual(
            ["Título", "Descripción", "Aceptar", "Cancelar"],
            [control.GetName() for control in _orden(dialogo)])
        self.assertEqual("&Título:", dialogo.lbl_titulo.GetLabel())
        self.assertEqual("&Descripción:",
                         dialogo.lbl_descripcion.GetLabel())
        self.assertEqual("Aceptar", dialogo.btn_aceptar.GetName())
        self.assertEqual("Cancelar", dialogo.btn_cancelar.GetName())

    def test_p3_aceptar_devuelve_lo_escrito(self):
        dialogo = self._dialogo()
        dialogo.txt_titulo.SetValue("Nuevo")
        dialogo.txt_descripcion.SetValue("Otra")
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._aceptar(None)

        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual(("Nuevo", "Otra"), dialogo.datos())

    def test_escape_cancela(self):
        dialogo = self._dialogo()
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_tecla(evento)

        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_letras_de_acceso_sin_repetir(self):
        self.assertEqual({}, letras_repetidas(self._dialogo()))

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(dialogo)
        self.assertEqual([], sin_marcar)


class PruebaDialogoManual(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.plataformas = {67: "TikTok", 5: "YouTube", 10: "Facebook"}

    def _dialogo(self):
        dialogo = dialogos.DialogoDestinoManual(None, self.plataformas)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_p4_campos_nombres_orden_y_plataformas_ordenadas(self):
        dialogo = self._dialogo()

        self.assertEqual("Agregar destino manual", dialogo.GetTitle())
        self.assertEqual(
            ["Plataforma", "Nombre", "Servidor", "Clave de transmisión",
             "Aceptar", "Cancelar"],
            [control.GetName() for control in _orden(dialogo)])
        self.assertEqual(["Facebook", "TikTok", "YouTube"],
                         list(dialogo.cho_plataforma.GetStrings()))
        self.assertEqual("&Plataforma:", dialogo.lbl_plataforma.GetLabel())
        self.assertEqual("&Nombre:", dialogo.lbl_nombre.GetLabel())
        self.assertEqual("&Servidor:", dialogo.lbl_servidor.GetLabel())
        self.assertEqual("&Clave de transmisión:",
                         dialogo.lbl_clave.GetLabel())
        self.assertTrue(
            dialogo.txt_clave.GetWindowStyleFlag() & wx.TE_PASSWORD)

    def test_p5_falta_plataforma_avisa_y_enfoca(self):
        dialogo = self._dialogo()
        dialogo.txt_servidor.SetValue("rtmp://servidor")
        dialogo.txt_clave.SetValue("secreta")
        with mock.patch.object(dialogos, "anunciar") as anunciar, \
                mock.patch.object(dialogo.cho_plataforma,
                                  "SetFocus") as foco, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._aceptar(None)

        anunciar.assert_called_once_with("Falta la plataforma.")
        foco.assert_called_once_with()
        fin.assert_not_called()
        self.assertIsNone(dialogo.datos())

    def test_p5_falta_servidor_avisa_y_enfoca(self):
        dialogo = self._dialogo()
        dialogo.cho_plataforma.SetSelection(1)
        dialogo.txt_clave.SetValue("secreta")
        with mock.patch.object(dialogos, "anunciar") as anunciar, \
                mock.patch.object(dialogo.txt_servidor,
                                  "SetFocus") as foco, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._aceptar(None)

        anunciar.assert_called_once_with("Falta el servidor.")
        foco.assert_called_once_with()
        fin.assert_not_called()
        self.assertIsNone(dialogo.datos())

    def test_p5_falta_clave_avisa_y_enfoca(self):
        dialogo = self._dialogo()
        dialogo.cho_plataforma.SetSelection(1)
        dialogo.txt_servidor.SetValue("rtmp://servidor")
        with mock.patch.object(dialogos, "anunciar") as anunciar, \
                mock.patch.object(dialogo.txt_clave, "SetFocus") as foco, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._aceptar(None)

        anunciar.assert_called_once_with("Falta la clave de transmisión.")
        foco.assert_called_once_with()
        fin.assert_not_called()
        self.assertIsNone(dialogo.datos())

    def test_p4_aceptar_devuelve_plataforma_nombre_servidor_y_clave(self):
        dialogo = self._dialogo()
        dialogo.cho_plataforma.SetSelection(1)
        dialogo.txt_nombre.SetValue("Canal")
        dialogo.txt_servidor.SetValue("rtmp://servidor")
        dialogo.txt_clave.SetValue("secreta")
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._aceptar(None)

        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual(
            (67, "Canal", "rtmp://servidor", "secreta"), dialogo.datos())

    def test_escape_cancela(self):
        dialogo = self._dialogo()
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_tecla(evento)

        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_letras_de_acceso_sin_repetir(self):
        self.assertEqual({}, letras_repetidas(self._dialogo()))

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(
                dialogo, propios=("Facebook", "TikTok", "YouTube"))
        self.assertEqual([], sin_marcar)


class _PaginaFalsa:

    def __init__(self, elegido=None):
        self._elegido = elegido
        self.mostradas = []
        self.lista = mock.Mock()

    def seleccionado(self):
        return self._elegido

    def mostrar(self, destinos, elegido=None):
        self.mostradas.append((list(destinos), elegido))


class _VentanaFalsa:

    def __init__(self, destinos, elegido=None):
        self._destinos = list(destinos)
        self._pagina_destinos = _PaginaFalsa(elegido)
        self._pagina_eventos = mock.Mock()
        self._error_destinos = ""
        self._actualizar_cuenta = mock.Mock()
        self.pendientes = []

    def _en_hilo_principal(self, funcion, *args):
        self.pendientes.append((funcion, args))


def _completar(ventana, veces=1):
    """Espera y ejecuta en este hilo las vueltas que deja la acción."""
    for _ in range(veces):
        if not _esperar(lambda: ventana.pendientes):
            return False
        funcion, args = ventana.pendientes.pop(0)
        funcion(*args)
    return True


class PruebaAccionesDestino(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def test_p2_desactivar_llama_en_otro_hilo_actualiza_y_anuncia(self):
        destino = Canal(1, 67, "TikTok", "uno", "", True)
        ventana = _VentanaFalsa([destino], destino)
        llamadas = []

        def activar(identificador, activo, cliente=None):
            llamadas.append((identificador, activo,
                             threading.current_thread()
                             is threading.main_thread()))

        with mock.patch.object(acciones.cuenta, "activar_canal",
                               side_effect=activar), \
                mock.patch.object(acciones, "anunciar") as anunciar, \
                mock.patch.object(acciones._snd,
                                  "reproducir") as sonar:
            acciones.alternar(ventana)
            self.assertTrue(_completar(ventana))

        self.assertEqual([(1, False, False)], llamadas)
        self.assertFalse(ventana._destinos[0].activo)
        self.assertEqual((ventana._destinos, None),
                         ventana._pagina_destinos.mostradas[-1])
        anunciar.assert_called_once_with("TikTok: uno desactivado")
        sonar.assert_not_called()

    def test_p2_activar_llama_con_el_estado_contrario(self):
        destino = Canal(1, 67, "TikTok", "uno", "", False)
        ventana = _VentanaFalsa([destino], destino)
        llamadas = []

        def activar(identificador, activo, cliente=None):
            llamadas.append((identificador, activo))

        with mock.patch.object(acciones.cuenta, "activar_canal",
                               side_effect=activar), \
                mock.patch.object(acciones, "anunciar") as anunciar:
            acciones.alternar(ventana)
            self.assertTrue(_completar(ventana))

        self.assertEqual([(1, True)], llamadas)
        self.assertTrue(ventana._destinos[0].activo)
        anunciar.assert_called_once_with("TikTok: uno activado")

    def test_p6_si_la_llamada_falla_suena_dice_y_no_cambia_la_lista(self):
        destino = Canal(1, 67, "TikTok", "uno", "", True)
        ventana = _VentanaFalsa([destino], destino)
        error = ErrorApi("No se pudo activar el destino. Vuelve a intentarlo.")

        with mock.patch.object(acciones.cuenta, "activar_canal",
                               side_effect=error), \
                mock.patch.object(acciones, "anunciar") as anunciar, \
                mock.patch.object(acciones._snd,
                                  "reproducir") as sonar:
            acciones.alternar(ventana)
            self.assertTrue(_completar(ventana))

        self.assertEqual([destino], ventana._destinos)
        self.assertEqual([], ventana._pagina_destinos.mostradas)
        self.assertEqual(str(error), ventana._error_destinos)
        sonar.assert_called_once_with("error")
        anunciar.assert_called_once_with(str(error))

    def test_p3_lee_la_meta_llena_el_cuadro_y_guarda_lo_aceptado(self):
        destino = Canal(1, 67, "TikTok", "uno", "", True)
        ventana = _VentanaFalsa([destino], destino)
        meta = MetaCanal("Título", "Descripción")
        recibidas = []
        enviados = []

        def leer(identificador, cliente=None):
            return meta

        def cambiar(identificador, titulo, descripcion, cliente=None):
            enviados.append((identificador, titulo, descripcion))

        class _DialogoFalso:

            def __init__(self, _padre, recibida):
                recibidas.append(recibida)

            def ShowModal(self):
                return wx.ID_OK

            def datos(self):
                return ("Nuevo", "Otra")

            def Destroy(self):
                pass

        with mock.patch.object(acciones.cuenta, "leer_meta",
                               side_effect=leer), \
                mock.patch.object(acciones.cuenta, "cambiar_meta",
                                  side_effect=cambiar), \
                mock.patch.object(acciones, "DialogoMetaDestino",
                                  _DialogoFalso), \
                mock.patch.object(ventana._pagina_destinos.lista,
                                  "SetFocus") as foco, \
                mock.patch.object(acciones, "anunciar") as anunciar:
            acciones.cambiar_titulo(ventana)
            self.assertTrue(_completar(ventana, veces=2))

        self.assertEqual([meta], recibidas)
        self.assertEqual([(1, "Nuevo", "Otra")], enviados)
        foco.assert_called_once_with()
        anunciar.assert_called_once_with("Título cambiado.")

    def test_p4_pide_las_plataformas_y_agrega_el_destino_manual(self):
        ventana = _VentanaFalsa([])
        canal = Canal(9, 67, "TikTok", "Canal", "")
        recibidas = []
        agregados = []
        secreto = "clave-secreta-123"

        class _DialogoFalso:

            def __init__(self, _padre, plataformas):
                recibidas.append(plataformas)

            def ShowModal(self):
                return wx.ID_OK

            def datos(self):
                return (67, "Canal", "rtmp://servidor", secreto)

            def Destroy(self):
                pass

        def agregar(plataforma_id, nombre, servidor, clave, cliente=None):
            agregados.append((plataforma_id, nombre, servidor, clave))
            return canal

        registros = []

        class _Captura(logging.Handler):

            def emit(self, registro):
                registros.append(registro.getMessage())

        captura = _Captura()
        logging.getLogger().addHandler(captura)
        self.addCleanup(logging.getLogger().removeHandler, captura)

        with mock.patch.object(acciones.api, "plataformas",
                               return_value={67: "TikTok"}), \
                mock.patch.object(acciones.cuenta, "agregar_canal_manual",
                                  side_effect=agregar), \
                mock.patch.object(acciones, "DialogoDestinoManual",
                                  _DialogoFalso), \
                mock.patch.object(acciones, "anunciar") as anunciar:
            acciones.agregar_manual(ventana)
            self.assertTrue(_completar(ventana, veces=2))

        self.assertEqual([{67: "TikTok"}], recibidas)
        self.assertEqual([(67, "Canal", "rtmp://servidor", secreto)],
                         agregados)
        self.assertEqual([canal], ventana._destinos)
        self.assertEqual(([canal], 9),
                         ventana._pagina_destinos.mostradas[-1])
        ventana._pagina_eventos.actualizar_nombres.assert_called_once_with()
        anunciar.assert_called_once_with("Destino agregado.")
        self.assertFalse(any(secreto in registro for registro in registros))


    def test_p6_abrir_enlace_usa_la_url_del_destino(self):
        destino = Canal(1, 67, "TikTok", "uno", "https://a", True)
        ventana = _VentanaFalsa([destino], destino)
        with mock.patch.object(acciones, "abrir_navegador") as abrir, \
                mock.patch.object(acciones, "anunciar") as anunciar:
            acciones.abrir_enlace(ventana)
        abrir.assert_called_once_with("https://a")
        anunciar.assert_not_called()

    def test_p6_abrir_enlace_vacio_lo_dice_sin_abrir(self):
        destino = Canal(1, 67, "TikTok", "uno", "", True)
        ventana = _VentanaFalsa([destino], destino)
        with mock.patch.object(acciones, "abrir_navegador") as abrir, \
                mock.patch.object(acciones, "anunciar") as anunciar:
            acciones.abrir_enlace(ventana)
        abrir.assert_not_called()
        anunciar.assert_called_once_with("Este destino no tiene enlace.")

    def test_p6_copiar_enlace_usa_la_url_del_destino(self):
        destino = Canal(1, 67, "TikTok", "uno", "https://a", True)
        ventana = _VentanaFalsa([destino], destino)
        with mock.patch.object(acciones, "copiar_al_portapapeles") as copiar, \
                mock.patch.object(acciones, "anunciar") as anunciar, \
                mock.patch.object(acciones._snd, "reproducir") as sonar:
            acciones.copiar_enlace(ventana)
        copiar.assert_called_once_with("https://a")
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Enlace copiado.")

    def test_p6_copiar_enlace_vacio_lo_dice_sin_copiar(self):
        destino = Canal(1, 67, "TikTok", "uno", "", True)
        ventana = _VentanaFalsa([destino], destino)
        with mock.patch.object(acciones,
                               "copiar_al_portapapeles") as copiar, \
                mock.patch.object(acciones, "anunciar") as anunciar, \
                mock.patch.object(acciones._snd, "reproducir") as sonar:
            acciones.copiar_enlace(ventana)
        copiar.assert_not_called()
        sonar.assert_not_called()
        anunciar.assert_called_once_with("Este destino no tiene enlace.")


if __name__ == "__main__":
    unittest.main()
