"""Pruebas de la ventana de Restream y del diálogo de perfil.

Crean ventanas de wx: se corren en la PC donde no molestan al lector, no en
la del dueño. La cuenta y los canales son dobles; los perfiles viven en una
carpeta temporal.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from bellbird.core.idioma import _
from bellbird.restream import perfiles
from bellbird.restream.perfiles import Perfil
from bellbird.ui import restream_perfil
from bellbird.ui import restream_ventana
from bellbird.ui.preferencias_comun import nombre_de_etiqueta
from bellbird.youtube.emision import (
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
from tests.ventanas_prueba import destruir


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


def _controles_en_orden(ventana):
    """Controles que toman foco, en el orden en que wx los recorre."""
    orden = []
    for hijo in ventana.GetChildren():
        if isinstance(hijo, (wx.ScrolledWindow, wx.Panel, wx.StaticBox)):
            orden.extend(_controles_en_orden(hijo))
        elif hijo.AcceptsFocus():
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
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "perfiles_restream.json"

    def _ventana(self, cuenta=None, guardados=None, al_conectar=None,
                 al_reautorizar=None, al_desconectar=None, canales=None):
        if guardados is not None:
            perfiles.guardar(self.ruta, guardados)
        dialogo = restream_ventana.VentanaRestream(
            None, cuenta or CuentaFalsa(), canales or _canales, self.ruta,
            al_conectar=al_conectar, al_reautorizar=al_reautorizar,
            al_desconectar=al_desconectar)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_p1_dos_pestanas_con_cerrar_y_escape(self):
        dialogo = self._ventana()
        self.assertEqual("PestanasRestream", dialogo.nb.GetName())
        self.assertEqual(2, dialogo.nb.GetPageCount())
        self.assertEqual(["Cuenta", "Perfiles"],
                         [dialogo.nb.GetPageText(i)
                          for i in range(dialogo.nb.GetPageCount())])
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

    def test_p2_desconectada_muestra_conectar(self):
        dialogo = self._ventana(cuenta=CuentaFalsa(False))
        self.assertEqual("Sin cuenta de Restream conectada.",
                         dialogo.txt_estado.GetValue())
        self.assertTrue(dialogo.btn_conectar.IsShown())
        self.assertFalse(dialogo.btn_reautorizar.IsShown())
        self.assertFalse(dialogo.btn_desconectar.IsShown())

    def test_p2_conectar_conecta_actualiza_y_anuncia(self):
        cuenta = CuentaFalsa(False)
        llamadas = []

        def conectar():
            llamadas.append(True)
            cuenta.estado = True

        dialogo = self._ventana(cuenta=cuenta, al_conectar=conectar)
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._conectar()

        self.assertEqual([True], llamadas)
        self.assertEqual("Cuenta de Restream conectada.",
                         dialogo.txt_estado.GetValue())
        self.assertFalse(dialogo.btn_conectar.IsShown())
        self.assertTrue(dialogo.btn_reautorizar.IsShown())
        self.assertTrue(dialogo.btn_desconectar.IsShown())
        anunciar.assert_called_once_with("Cuenta de Restream conectada.")

    def test_p2_conectar_que_falla_no_anuncia(self):
        cuenta = CuentaFalsa(False)
        dialogo = self._ventana(cuenta=cuenta, al_conectar=lambda: None)
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._conectar()

        anunciar.assert_not_called()
        self.assertFalse(cuenta.conectada())
        self.assertTrue(dialogo.btn_conectar.IsShown())

    def test_p2_reautorizar_y_desconectar(self):
        cuenta = CuentaFalsa(True)

        def desconectar():
            cuenta.estado = False

        dialogo = self._ventana(
            cuenta=cuenta, al_reautorizar=lambda: None,
            al_desconectar=desconectar)
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._reautorizar()
            anunciar.assert_called_once_with("Cuenta de Restream conectada.")
            anunciar.reset_mock()
            dialogo._desconectar()
            anunciar.assert_called_once_with(
                "Cuenta de Restream desconectada.")

        self.assertFalse(cuenta.conectada())
        self.assertTrue(dialogo.btn_conectar.IsShown())

    def test_p3_lista_con_nombre_orientacion_y_canales(self):
        primera = _perfil(nombre="TikTok", canales=(1,), orientacion="vertical")
        segunda = _perfil(nombre="TikTok y YouTube", canales=(1, 2))
        dialogo = self._ventana(guardados=[primera, segunda])

        self.assertEqual("Perfiles de Restream",
                         dialogo.lista_perfiles.GetName())
        self.assertEqual(
            ["TikTok, vertical, 1 canal",
             "TikTok y YouTube, horizontal, 2 canales"],
            list(dialogo.lista_perfiles.GetStrings()))
        self.assertEqual("&Nuevo…", dialogo.btn_nuevo.GetLabel())
        self.assertEqual("&Editar…", dialogo.btn_editar.GetLabel())
        self.assertEqual("D&uplicar", dialogo.btn_duplicar.GetLabel())
        self.assertEqual("E&liminar", dialogo.btn_eliminar.GetLabel())

    def test_p3_sin_seleccion_anuncia_y_no_hace_nada(self):
        dialogo = self._ventana()
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._editar()
            dialogo._duplicar()
            dialogo._eliminar()

        self.assertEqual([mock.call("Sin selección")] * 3,
                         anunciar.call_args_list)
        self.assertFalse(self.ruta.exists())

    def test_p3_intro_edita_y_supr_elimina(self):
        dialogo = self._ventana(guardados=[_perfil()])
        lista = dialogo.lista_perfiles
        lista.SetSelection(0)

        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_RETURN
        evento.GetEventObject.return_value = lista
        with mock.patch.object(dialogo, "_editar") as editar:
            dialogo._al_tecla(evento)
        editar.assert_called_once_with()

        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_DELETE
        evento.GetEventObject.return_value = lista
        with mock.patch.object(dialogo, "_eliminar") as eliminar:
            dialogo._al_tecla(evento)
        eliminar.assert_called_once_with()

    def test_p5_nuevo_guarda_y_anuncia(self):
        nuevo = _perfil(nombre="Nuevo", canales=(1,))
        dialogo = self._ventana(guardados=[])
        with mock.patch.object(restream_ventana, "DialogoPerfilRestream",
                               return_value=_DialogoFalso(nuevo)), \
                mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._nuevo()

        self.assertEqual([nuevo], perfiles.cargar(self.ruta))
        self.assertEqual(0, dialogo.lista_perfiles.GetSelection())
        anunciar.assert_called_once_with("Perfil guardado.")

    def test_p5_duplicar_escribe_copia_de_x_y_su_numero(self):
        original = _perfil(nombre="Canal")
        dialogo = self._ventana(guardados=[original])
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._duplicar()
        self.assertEqual(
            [original, _perfil(nombre="Copia de Canal")],
            perfiles.cargar(self.ruta))
        anunciar.assert_called_once_with("Perfil duplicado.")

        dialogo.lista_perfiles.SetSelection(0)
        with mock.patch.object(restream_ventana, "anunciar"):
            dialogo._duplicar()
        self.assertEqual(
            [original, _perfil(nombre="Copia de Canal"),
             _perfil(nombre="Copia de Canal 2")],
            perfiles.cargar(self.ruta))

    def test_p5_eliminar_escribe_y_anuncia(self):
        primera = _perfil(nombre="Primero")
        segunda = _perfil(nombre="Segundo")
        dialogo = self._ventana(guardados=[primera, segunda])
        dialogo.lista_perfiles.SetSelection(0)
        with mock.patch.object(restream_ventana, "anunciar") as anunciar:
            dialogo._eliminar()

        self.assertEqual([segunda], perfiles.cargar(self.ruta))
        self.assertEqual(0, dialogo.lista_perfiles.GetSelection())
        anunciar.assert_called_once_with("Perfil eliminado.")

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


class PruebaDialogoPerfil(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
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

    def test_p4_sin_canales_muestra_la_nota_y_valida(self):
        dialogo = self._dialogo(canales=[])
        dialogo.txt_nombre.SetValue("Prueba")
        with mock.patch.object(restream_perfil, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)

        texto = anunciar.call_args.args[0]
        self.assertIn("Agrega al menos un canal al perfil.", texto)
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

        anunciar.assert_called_once_with("Ya existe un perfil con ese nombre.")
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

    def test_p6_canal_sobrante_avisa_y_queda_fuera_al_guardar(self):
        perfil = _perfil(nombre="Viejo", canales=(1, 99))
        dialogo = self._dialogo(
            perfil=perfil, canales=[(1, "TikTok: uno")])
        self.assertEqual(1, len(dialogo._casillas))
        self.assertIn(
            "Hay 1 canal del perfil que ya no está en Restream. Se eliminará "
            "al guardar.", dialogo._nota_sobrantes.GetLabel())

        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._guardar(None)
        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual((1,), dialogo.perfil().canales)

        plural = self._dialogo(perfil=_perfil(canales=(98, 99)))
        self.assertIn(
            "Hay 2 canales del perfil que ya no están en Restream. Se "
            "eliminarán al guardar.", plural._nota_sobrantes.GetLabel())

    def test_p6_sin_canales_la_caja_lo_dice(self):
        dialogo = self._dialogo(canales=[])
        caja = dialogo._caja_canales.GetStaticBox()
        textos = [hijo.GetLabel() for hijo in caja.GetChildren()
                  if isinstance(hijo, wx.StaticText)]
        self.assertIn(
            "No hay canales. Conecta la cuenta de Restream y agrega los "
            "canales en su página.", textos)

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
