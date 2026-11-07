"""Pruebas del botón directo de transmisión.

Las clases con ventana abren ventanas de verdad y aquí no se corren:
aquí solo se corre TestGuardarDestino, sin ventana.
"""

import queue
import threading
import unittest


def _avisar_de(anunciar, sonar):
    def _avisar(texto, sonido=None, *, error=False):
        anunciar(texto)
        if sonido:
            sonar(sonido)
    return _avisar
from types import SimpleNamespace
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from guyrapu.ui import gui
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import app_de_prueba, destruir


class TestGuardarDestino(unittest.TestCase):
    # Sin ventana: _guardar_destino_transmision solo toca el dict y el INI.

    def _frame(self):
        frame = gui.VentanaPrincipal.__new__(gui.VentanaPrincipal)
        frame._config = {}
        return frame

    def test_destino_valido_se_guarda(self):
        frame = self._frame()
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = frame._guardar_destino_transmision("TikTok")
        self.assertEqual(resultado, "TikTok")
        self.assertEqual(frame._config["transmision_destino"], "TikTok")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "TikTok")

    def test_destino_invalido_se_guarda_vacio(self):
        frame = self._frame()
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = frame._guardar_destino_transmision("Twitch")
        self.assertEqual(resultado, "")
        self.assertEqual(frame._config["transmision_destino"], "")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "")


class TestTransmitirSinVentana(unittest.TestCase):
    # Sin ventana: pedir_destino y la revisión de OBS van con dobles.

    def _boton(self, **config):
        from guyrapu.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(
            boton_directo.BotonDirecto)
        marco = mock.Mock()
        marco._alive = True
        marco._config = {"transmision_destino": "TikTok",
                         "tiktok_usuario": "guardado"}
        marco._config.update(config)
        marco._guardar_destino_transmision = mock.Mock(
            side_effect=lambda d: marco._config.update(
                {"transmision_destino": d}) or d)
        marco._guardar_usuario_tiktok = mock.Mock(
            side_effect=lambda u: marco._config.update(
                {"tiktok_usuario": u}) or u)
        marco._supervisar_transmision = mock.Mock()
        marco._actualizar_boton_directo = mock.Mock()
        boton._marco = marco
        boton.boton = mock.Mock()
        return boton, marco

    def test_cancelar_anuncia_y_no_revisa(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=None) as pedir, \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo") as hilos, \
                mock.patch.object(boton_directo, "anunciar") as anunciar:
            boton._transmitir()
        pedir.assert_called_once_with(marco, "TikTok", "guardado")
        anunciar.assert_called_once_with("No se transmitió.")
        hilos.assert_not_called()
        marco._guardar_destino_transmision.assert_not_called()

    def test_youtube_guarda_y_revisa_aunque_el_guardado_decia_tiktok(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton(transmision_destino="TikTok",
                                   tiktok_usuario="guardado")
        hilos = []
        revision = mock.sentinel.revision
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=revision)

        class Hilo:
            def __init__(self, target, *args, **kwargs):
                self.target = target

            def start(self):
                hilos.append(self.target)
                self.target()

        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=("YouTube", "")), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo",
                                  side_effect=lambda f, n: Hilo(f)), \
                mock.patch.object(boton_directo.transmision_directa,
                                  "preparar",
                                  return_value=preparacion) as preparar, \
                mock.patch.object(boton_directo, "anunciar"), \
                mock.patch.object(boton_directo._snd, "reproducir"), \
                mock.patch.object(boton_directo.wx,
                                  "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            boton._transmitir()
        marco._guardar_destino_transmision.assert_called_once_with(
            "YouTube")
        preparar.assert_called_once()
        args, _ = preparar.call_args
        self.assertEqual(args[1], "YouTube")
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "YouTube", "", revision=revision)

    def test_restream_sin_cuenta_avisa_y_no_revisa(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=("restream:Uno", "")), \
                mock.patch.object(boton_directo.ganchos,
                                  "cuenta_conectada",
                                  return_value=False), \
                mock.patch.object(boton_directo, "anunciar") as anunciar, \
                mock.patch.object(boton_directo._snd,
                                  "reproducir") as sonido, \
                mock.patch.object(boton_directo, "avisar",
                                  _avisar_de(anunciar, sonido)), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo") as hilos:
            boton._transmitir()
        anunciar.assert_called_once_with(
            "Para transmitir con un perfil de Restream hace falta conectar "
            "la cuenta, en el cuadro Restream, pestaña Cuenta.")
        sonido.assert_called_once_with("transmision_problema")
        hilos.assert_not_called()
        marco._guardar_destino_transmision.assert_called_once_with(
            "restream:Uno")

    def test_restream_prepara_obs_y_supervisa_la_opcion(self):
        from guyrapu.restream.perfiles import Perfil
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        perfil = Perfil(nombre="Vertical", canales=(1,),
                        orientacion="vertical")

        class Hilo:
            def __init__(self, target, *args, **kwargs):
                self.target = target

            def start(self):
                self.target()

        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=("restream:Vertical", "")), \
                mock.patch.object(boton_directo.ganchos,
                                  "cuenta_conectada", return_value=True), \
                mock.patch.object(boton_directo.ganchos,
                                  "cargar_perfiles",
                                  return_value=[perfil]), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo",
                                  side_effect=lambda f, n: Hilo(f)), \
                mock.patch.object(boton_directo.transmision_directa,
                                  "preparar",
                                  return_value=preparacion) as preparar, \
                mock.patch.object(boton_directo, "anunciar"), \
                mock.patch.object(boton_directo._snd, "reproducir"), \
                mock.patch.object(boton_directo.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            boton._transmitir()
        args, _ = preparar.call_args
        self.assertEqual(args[1], "TikTok")
        marco._guardar_destino_transmision.assert_called_once_with(
            "restream:Vertical")
        marco._guardar_usuario_tiktok.assert_not_called()
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "restream:Vertical", "")

    def test_tiktok_guarda_usuario_y_revisa(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)

        class Hilo:
            def __init__(self, target, *args, **kwargs):
                self.target = target

            def start(self):
                self.target()

        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=("TikTok", "nuevo")), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo",
                                  side_effect=lambda f, n: Hilo(f)), \
                mock.patch.object(boton_directo.transmision_directa,
                                  "preparar",
                                  return_value=preparacion), \
                mock.patch.object(boton_directo, "anunciar"), \
                mock.patch.object(boton_directo._snd, "reproducir"), \
                mock.patch(
                    "guyrapu.ui.boton_directo.confirmar_transmision",
                    return_value=True), \
                mock.patch.object(boton_directo.wx,
                                  "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            boton._transmitir()
        marco._guardar_destino_transmision.assert_called_once_with(
            "TikTok")
        marco._guardar_usuario_tiktok.assert_called_once_with("nuevo")


class TestRevisionListaSinVentana(unittest.TestCase):
    # Sin ventana: confirmar y supervisar van con dobles.

    def _boton(self):
        from guyrapu.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(
            boton_directo.BotonDirecto)
        marco = mock.Mock()
        marco._alive = True
        marco._supervisar_transmision = mock.Mock()
        marco._actualizar_boton_directo = mock.Mock()
        boton._marco = marco
        boton.boton = mock.Mock()
        return boton, marco

    def test_youtube_no_confirma_y_pasa_la_revision(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        revision = mock.sentinel.revision
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=revision)
        with mock.patch(
                "guyrapu.ui.boton_directo.confirmar_transmision") as confirmar:
            boton._revision_lista(preparacion, "YouTube", "YouTube", "")
        confirmar.assert_not_called()
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "YouTube", "", revision=revision)

    def test_tiktok_confirma_como_hoy(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch(
                "guyrapu.ui.boton_directo.confirmar_transmision",
                return_value=True) as confirmar:
            boton._revision_lista(preparacion, "TikTok", "TikTok", "usuario")
        confirmar.assert_called_once_with(marco, preparacion.revision)
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "TikTok", "usuario")

    def test_tiktok_cancelar_anuncia_y_no_inicia(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch(
                "guyrapu.ui.boton_directo.confirmar_transmision",
                return_value=False), \
                mock.patch.object(boton_directo, "anunciar") as anunciar:
            boton._revision_lista(preparacion, "TikTok", "TikTok", "usuario")
        anunciar.assert_called_once_with("No se transmitió.")
        marco._supervisar_transmision.assert_not_called()


class TestActualizarDeteniendoSinVentana(unittest.TestCase):
    # Sin ventana: el botón es un doble, así se mira lo que dice sin crearlo.

    def _boton(self):
        from guyrapu.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(boton_directo.BotonDirecto)
        boton._conectar = mock.Mock()
        boton._transmitiendo = False
        boton._deteniendo = False
        boton._marco = mock.Mock()
        boton._marco.mi_directo = None
        boton.boton = mock.Mock()
        boton.boton.GetParent.return_value = mock.Mock()
        boton.boton.HasFocus.return_value = False
        return boton

    def test_actualizar_con_deteniendo_cambia_etiqueta_y_guarda_el_estado(self):
        boton = self._boton()
        boton.actualizar(False, False, False, True, deteniendo=True)
        self.assertTrue(boton._deteniendo)
        boton.boton.SetLabel.assert_called_once_with("Finalizando el directo")
        boton.boton.SetName.assert_called_once_with(
            "Finalizando el directo, esperando a OBS")
        boton.boton.Hide.assert_not_called()

    def test_actualizar_sin_deteniendo_vuelve_a_finalizar(self):
        boton = self._boton()
        boton._deteniendo = True
        boton.actualizar(False, False, False, True)
        self.assertFalse(boton._deteniendo)
        boton.boton.SetLabel.assert_called_once_with("&Finalizar directo")

    def test_actualizar_copia_la_etiqueta_al_comando_del_menu(self):
        boton = self._boton()
        item = mock.Mock()
        boton._marco.mi_directo = item
        boton.actualizar(False, False, True, False)
        item.SetItemLabel.assert_called_once_with("Transm&itir en directo")

    def test_el_comando_dice_lo_mismo_que_el_boton_en_cada_estado(self):
        for argumentos, etiqueta in (
                ((False, False, True, False), "Transm&itir en directo"),
                ((False, False, True, True), "&Finalizar directo"),
                ((False, False, True, True, True), "Finalizando el directo")):
            with self.subTest(etiqueta=etiqueta):
                boton = self._boton()
                item = mock.Mock()
                boton._marco.mi_directo = item
                boton.actualizar(*argumentos)
                item.SetItemLabel.assert_called_once_with(etiqueta)

    def test_actualizar_deshabilita_el_comando_cuando_el_boton_se_oculta(self):
        boton = self._boton()
        item = mock.Mock()
        boton._marco.mi_directo = item
        boton.actualizar(True, False, False, False)
        boton.boton.Hide.assert_called_once()
        item.Enable.assert_called_once_with(False)

    def test_actualizar_vuelve_a_habilitar_el_comando(self):
        boton = self._boton()
        item = mock.Mock()
        boton._marco.mi_directo = item
        boton.actualizar(False, False, False, False)
        item.Enable.assert_called_once_with(True)


class TestPulsarSinVentana(unittest.TestCase):
    # Sin ventana: pulsar es el único camino que comparten el botón y el menú.

    def _boton(self, transmitiendo=False, deteniendo=False):
        from guyrapu.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(boton_directo.BotonDirecto)
        boton._transmitiendo = transmitiendo
        boton._deteniendo = deteniendo
        boton._marco = mock.Mock()
        boton.boton = mock.Mock()
        return boton

    def test_pulsar_sin_directo_transmite(self):
        boton = self._boton()
        with mock.patch.object(boton, "_transmitir") as transmitir:
            boton.pulsar()
        transmitir.assert_called_once_with()

    def test_pulsar_transmitiendo_finaliza(self):
        boton = self._boton(transmitiendo=True)
        with mock.patch.object(boton, "_finalizar") as finalizar:
            boton.pulsar()
        finalizar.assert_called_once_with()

    def test_pulsar_deteniendo_solo_avisa(self):
        from guyrapu.ui import boton_directo
        boton = self._boton(transmitiendo=True, deteniendo=True)
        with (
                mock.patch.object(boton, "_finalizar") as finalizar,
                mock.patch.object(boton, "_transmitir") as transmitir,
                mock.patch.object(boton_directo, "anunciar") as anunciar,
        ):
            boton.pulsar()
        finalizar.assert_not_called()
        transmitir.assert_not_called()
        anunciar.assert_called_once_with(
            "Deteniendo la transmisión. Esperando a que OBS confirme.")

    def test_al_pulsar_delega_en_pulsar(self):
        boton = self._boton()
        with mock.patch.object(boton, "pulsar") as pulsar:
            boton._al_pulsar(mock.Mock())
        pulsar.assert_called_once_with()


class TestMenuDirectoSinVentana(unittest.TestCase):
    # Sin ventana: el comando del menú llama a pulsar, el mismo camino.

    def _frame(self, boton):
        from guyrapu.ui import menu_transmision

        class Menu:
            def __init__(self):
                self.items = []

            def Append(self, *args):
                item = mock.Mock()
                self.items.append(item)
                return item

            def AppendCheckItem(self, *args):
                item = mock.Mock()
                self.items.append(item)
                return item

            def AppendSeparator(self):
                self.items.append(None)

        enlaces = {}
        frame = mock.Mock()
        frame._config = {"grabar_al_transmitir": False}
        frame._accel.return_value = ""
        frame._bind_menu.side_effect = lambda item, fn, *a: enlaces.__setitem__(
            item, (fn, a))
        frame._boton_directo = boton
        with mock.patch.object(menu_transmision.wx, "Menu", Menu):
            menu_transmision.construir(frame, mock.Mock())
        return frame, enlaces

    def test_elegir_mi_directo_llama_a_pulsar(self):
        boton = mock.Mock()
        frame, enlaces = self._frame(boton)
        fn, args = enlaces[frame.mi_directo]
        fn(*args)
        boton.pulsar.assert_called_once_with()


class TestAlPulsarDeteniendoSinVentana(unittest.TestCase):
    # Sin ventana: se comprueba que pulsar mientras se detiene solo avisa.

    def _boton(self):
        from guyrapu.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(boton_directo.BotonDirecto)
        boton._transmitiendo = True
        boton._deteniendo = True
        marco = mock.Mock()
        marco._alive = True
        boton._marco = marco
        boton.boton = mock.Mock()
        return boton, marco

    def test_pulsar_deteniendo_anuncia_y_no_dialoga_ni_detiene(self):
        from guyrapu.ui import boton_directo
        boton, marco = self._boton()
        with mock.patch.object(boton_directo.wx, "MessageDialog") as dialogo, \
                mock.patch.object(boton_directo, "anunciar") as anunciar, \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo") as hilos:
            boton._al_pulsar(mock.Mock())
        dialogo.assert_not_called()
        hilos.assert_not_called()
        marco._supervisar_transmision.assert_not_called()
        anunciar.assert_called_once_with(
            "Deteniendo la transmisión. Esperando a que OBS confirme.")


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestBotonDirectoVentana(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def _ventana(self, **config_extra):
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": False, "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False, "tiktok_usuario": "",
            "transmision_destino": "",
        }
        configuracion.update(config_extra)
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100)
        with mock.patch.object(gui.diagnostico, "crear_hilo"):
            frame = gui.VentanaPrincipal(None, configuracion, queue.Queue(),
                                    stats, worker, threading.Event())
        self.addCleanup(destruir, frame)
        frame.ShowWithoutActivating()
        gui.wx.Yield()
        return frame

    @staticmethod
    def _sin_reproductor_ni_comentarios(frame):
        # configurar_tiktok no necesita el reproductor de verdad para lo
        # que aquí se comprueba (visibilidad del botón).
        frame._rep_panel = mock.Mock()
        frame._com_panel = mock.Mock()

    def test_en_inicio_hijo_del_panel_visible_tras_conectar_y_con_nombre(self):
        frame = self._ventana()
        boton = frame._boton_directo.boton
        self.assertIs(boton.GetParent(), frame._panel_principal)
        self.assertTrue(boton.IsShown())
        hijos = list(frame._panel_principal.GetChildren())
        self.assertEqual(hijos.index(boton),
                         hijos.index(frame.btn_conectar) + 1)
        self.assertEqual(boton.GetLabel(), "Transm&itir en directo")
        self.assertEqual(boton.GetName(), "Transmitir en directo")

    def test_con_usuario_ajeno_queda_oculto(self):
        frame = self._ventana(tiktok_usuario="mio")
        self._sin_reproductor_ni_comentarios(frame)
        frame.set_conectado(True)
        gui.wx.Yield()
        frame.configurar_tiktok("otro", "http://flujo")
        gui.wx.Yield()
        self.assertFalse(frame._boton_directo.boton.IsShown())

    def test_con_usuario_guardado_queda_visible(self):
        frame = self._ventana(tiktok_usuario="mio")
        self._sin_reproductor_ni_comentarios(frame)
        frame.set_conectado(True)
        gui.wx.Yield()
        frame.configurar_tiktok("mio", "http://flujo")
        gui.wx.Yield()
        boton = frame._boton_directo.boton
        self.assertTrue(boton.IsShown())
        self.assertEqual(boton.GetLabel(), "Transm&itir en directo")
        self.assertEqual(boton.GetName(), "Transmitir en directo")

    def test_set_conectado_sin_conexion_propia_oculta(self):
        # Prueba de cableado: sin la llamada a _actualizar_boton_directo
        # en _set_conectado_ui, el botón seguiría visible y fallaría.
        frame = self._ventana()
        self.assertTrue(frame._boton_directo.boton.IsShown())
        frame.set_conectado(True)
        gui.wx.Yield()
        self.assertFalse(frame._boton_directo.boton.IsShown())


# Las etiquetas del botón las arma `transmision_directa.etiqueta`, fuera
# del alcance: quedan como pendientes. La comparación es exacta en los dos
# sentidos: falla si aparece un texto nuevo sin envolver y si un pendiente
# ya no está en el recorrido, para vaciar la lista cuando ese módulo pase
# por gettext.
PENDIENTES_BOTON_DIRECTO = ()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoBotonDirectoVentana(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def test_no_queda_ningun_texto_propio_sin_envolver(self):
        from guyrapu.ui import boton_directo
        with con_pseudo():
            cuadro = wx.Frame(None)
            panel = wx.Panel(cuadro)
            conectar = wx.Button(panel, label="Conectar")
            boton = boton_directo.BotonDirecto(panel, conectar, mock.Mock())
            vistos = list(textos_sin_marcar(boton.boton))
            boton.actualizar(False, False, False, True)
            vistos.extend(textos_sin_marcar(boton.boton))
            boton.actualizar(False, False, False, True, deteniendo=True)
            vistos.extend(textos_sin_marcar(boton.boton))
        self.addCleanup(destruir, cuadro)
        self.assertEqual(sorted(vistos), sorted(PENDIENTES_BOTON_DIRECTO))


class TestPseudoAnunciosBotonDirecto(unittest.TestCase):
    # Sin ventana: controles y marco con dobles, así se corre acá. Los
    # textos que arman otros módulos (`mensaje_de_fallo_obs` y el error
    # del cierre en YouTube) no entran.

    def setUp(self):
        from guyrapu.ui import boton_directo
        self.modulo = boton_directo
        self.captados = []
        parches = [
            mock.patch.object(boton_directo, "anunciar",
                              self.captados.append),
            mock.patch.object(boton_directo, "avisar",
                              lambda texto, sonido=None, **k:
                              self.captados.append(texto)),
            mock.patch.object(boton_directo._snd, "reproducir"),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        pseudo = con_pseudo()
        pseudo.__enter__()
        self.addCleanup(pseudo.__exit__, None, None, None)

    def _exigir_marcados(self, cantidad):
        self.assertEqual(len(self.captados), cantidad)
        for frase in self.captados:
            self.assertTrue(frase.startswith("[¡"), frase)
        del self.captados[:]

    def _boton(self, **config):
        boton = self.modulo.BotonDirecto.__new__(self.modulo.BotonDirecto)
        marco = mock.Mock()
        marco._alive = True
        marco._config = {"transmision_destino": "TikTok",
                         "tiktok_usuario": "guardado"}
        marco._config.update(config)
        marco._guardar_destino_transmision = mock.Mock(
            side_effect=lambda d: marco._config.update(
                {"transmision_destino": d}) or d)
        marco._guardar_usuario_tiktok = mock.Mock(
            side_effect=lambda u: marco._config.update(
                {"tiktok_usuario": u}) or u)
        marco._supervisar_transmision = mock.Mock()
        marco._actualizar_boton_directo = mock.Mock()
        boton._marco = marco
        boton.boton = mock.Mock()
        boton._transmitiendo = False
        boton._deteniendo = False
        return boton, marco

    def test_pulsar_deteniendo_avisa_marcado(self):
        boton, marco = self._boton()
        boton._transmitiendo = True
        boton._deteniendo = True
        with mock.patch.object(self.modulo.diagnostico,
                               "crear_hilo") as hilos:
            boton._al_pulsar(mock.Mock())
        hilos.assert_not_called()
        marco._supervisar_transmision.assert_not_called()
        self._exigir_marcados(1)

    def test_transmitir_cancelado_avisa_marcado(self):
        boton, _marco = self._boton()
        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=None), \
                mock.patch.object(self.modulo.diagnostico,
                                  "crear_hilo") as hilos:
            boton._transmitir()
        hilos.assert_not_called()
        self._exigir_marcados(1)

    def test_transmitir_revisa_marcado(self):
        boton, marco = self._boton()
        with mock.patch(
                "guyrapu.ui.gui_elegir_destino.pedir_destino",
                return_value=("TikTok", "nuevo")), \
                mock.patch.object(self.modulo.diagnostico, "crear_hilo"):
            boton._transmitir()
        marco._guardar_usuario_tiktok.assert_called_once_with("nuevo")
        self._exigir_marcados(1)

    def test_revision_ya_transmitiendo_avisa_marcado(self):
        boton, _marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=True,
                                      revision=mock.sentinel.revision)
        boton._revision_lista(preparacion, "YouTube", "YouTube", "")
        self._exigir_marcados(1)

    def test_revision_tiktok_cancelado_avisa_marcado(self):
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch(
                "guyrapu.ui.boton_directo.confirmar_transmision",
                return_value=False):
            boton._revision_lista(preparacion, "TikTok", "TikTok", "usuario")
        marco._supervisar_transmision.assert_not_called()
        self._exigir_marcados(1)

    def test_finalizar_pide_confirmacion_y_sigue_marcado(self):
        boton, marco = self._boton()
        boton._transmitiendo = True
        with mock.patch.object(self.modulo, "confirmar_finalizar",
                               return_value=False) as confirmar:
            boton._finalizar()
        confirmar.assert_called_once_with(marco)
        marco._supervisar_transmision.assert_not_called()
        self._exigir_marcados(1)

    def test_finalizada_avisa_marcado(self):
        boton, _marco = self._boton()
        boton._finalizada()
        self._exigir_marcados(1)


if __name__ == "__main__":
    unittest.main()
