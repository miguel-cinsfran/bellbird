"""Pruebas del panel de transmisión sin conectar con OBS."""

import pathlib
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from bellbird.obs import consultas_transmision
from bellbird.obs import obs_cliente
from bellbird.obs import obs_disposicion
from bellbird.obs import estado_panel
from bellbird.obs import obs_prevuelo
from bellbird.ui import confirmar_transmision as modulo_confirmar
from bellbird.ui import control_grabacion
from bellbird.ui import directo_panel
from bellbird.ui import gui_microfono
from bellbird.ui import gui_transmision
from bellbird.ui import menu_transmision
from bellbird.ui import operaciones_obs
from bellbird.ui import tema
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class GestorFalso:

    def __init__(self, fallo=False):
        self.fallo = fallo
        self.llamadas = []
        self.fuentes_enviadas = []
        self.snap = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=460, alto=620,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=32, arriba=18,
            visible=True, bloqueada=False)
        self.tiene_panel = True
        self.perfil = ""
        self.transmitiendo = False
        self.grabando = False
        self.grabacion_en_pausa = False
        self.ruta_grabacion = ""
        self.silenciado = False
        self.escena_resultante = "Principal"
        self.problemas_revision = ()
        self.escalable = True
        self.instantaneas = []
        self.snap_nuevo = self.snap
        self.transformacion_inicial = {"positionX": 32, "positionY": 18,
                                       "alignment": 5}
        self.opciones_ventana = (("Champions, de juego.exe",
                                  "Champions:Ventana:juego.exe"),
                                 ("Charla, de otro.exe",
                                  "Charla:Ventana:otro.exe"))
        self.actual_ventana = "Champions:Ventana:juego.exe"

    def conectar(self):
        if self.fallo:
            raise obs_cliente.ObsError("OBS no está disponible")
        self.llamadas.append(("conectar",))

    def cerrar(self): self.llamadas.append(("cerrar",))
    @property
    def conectado(self): return True
    def escenas(self): return ("Principal", "Juego")
    def escena_al_aire(self): return self.escena_resultante
    def poner_escena_al_aire(self, escena):
        self.llamadas.append(("poner_escena_al_aire", escena))
        return self.escena_resultante
    def fuentes(self, escena):
        return {"Principal": tuple(fuente for fuente in ("Cámara", "Chat en el vídeo", "Juego")
                                    if fuente != "Chat en el vídeo" or self.tiene_panel),
                "Juego": ("Captura",)}.get(escena, ())
    def asegurar_fuente(self, *args):
        self.llamadas.append(("asegurar_fuente",) + args)
        self.tiene_panel = True
    def estado_transmision(self):
        return {"outputActive": self.transmitiendo, "outputDuration": 61,
                "outputSkippedFrames": 0, "outputTotalFrames": 100}
    def estado_grabacion(self):
        return {"outputActive": self.grabando, "outputPaused": self.grabacion_en_pausa,
                "outputTimecode": "00:01:02.000"}
    def alternar_grabacion(self):
        self.grabando = not self.grabando
        self.llamadas.append(("alternar_grabacion",))
        return self.grabando
    def alternar_grabacion_con_ruta(self):
        self.grabando = not self.grabando
        self.llamadas.append(("alternar_grabacion_con_ruta",))
        return self.grabando, "" if self.grabando else self.ruta_grabacion
    def alternar_pausa_grabacion(self):
        anterior = self.grabacion_en_pausa
        self.grabacion_en_pausa = not self.grabacion_en_pausa
        self.llamadas.append(("alternar_pausa_grabacion",))
        return self.grabacion_en_pausa, anterior
    def alternar_transmision(self):
        self.transmitiendo = not self.transmitiendo
        self.llamadas.append(("alternar_transmision",))
        return self.transmitiendo
    def perfil_actual(self, parada=None): return self.perfil
    def estadisticas(self, parada=None):
        return {"cpuUsage": 12.6, "outputSkippedFrames": 3,
                "outputTotalFrames": 100, "renderSkippedFrames": 5,
                "renderTotalFrames": 200, "availableDiskSpace": 2048}
    def preparar_destino(self, destino, parada=None):
        self.llamadas.append(("preparar_destino", destino))
        self.perfil = destino
        return {"destino": destino, "perfil": destino,
                "coleccion": destino, "ancho": 720, "alto": 1280}
    def revisar(self, destino, parada=None):
        return obs_prevuelo.Revision(
            destino, destino, destino, 720, 1280, "Principal",
            (), (), None, tuple(self.problemas_revision))
    def entradas_audio(self):
        return (("Mic/Aux", "wasapi_input_capture"),)
    def microfono_especial(self):
        return ""
    def silenciada(self, fuente):
        return self.silenciado
    def alternar_silencio(self, fuente):
        self.silenciado = not self.silenciado
        self.llamadas.append(("alternar_silencio", fuente))
        return self.silenciado
    def dispositivo(self, fuente, predeterminado):
        return "", False
    def _llamar(self, nombre, args, kwargs):
        self.llamadas.append((nombre,) + args)
        self.fuentes_enviadas.append((nombre, kwargs.get("fuente")))
        self.snap = self.snap_nuevo
    def colocar(self, *args, **kwargs): self._llamar("colocar", args, kwargs)
    def posicionar(self, *args, **kwargs): self._llamar("posicionar", args, kwargs)
    def transformacion(self, *args, **kwargs): return self.transformacion_inicial
    def mover(self, *args, **kwargs): self._llamar("mover", args, kwargs)
    def redimensionar(self, *args, **kwargs): self._llamar("redimensionar", args, kwargs)
    def escalar(self, *args, **kwargs):
        self._llamar("escalar", args, kwargs)
        return self.escalable
    def mostrar(self, *args, **kwargs): self._llamar("mostrar", args, kwargs)
    def fijar(self, *args, **kwargs): self._llamar("fijar", args, kwargs)
    def al_frente(self, *args, **kwargs): self._llamar("al_frente", args, kwargs)
    def instantanea(self, *args, **kwargs):
        self.instantaneas.append((args, kwargs.get("fuente")))
        return self.snap
    def descripcion_escena(self, escena=None, parada=None):
        if escena:
            return (f"Escena: {escena}. 1 fuente, de adelante hacia atrás.\n"
                    "1: Juego, captura de pantalla, ocupa todo el vídeo, se ve.")
        return ("Escena actual: Principal. 1 fuente, de adelante hacia atrás.\n"
                "1: Juego, captura de pantalla, ocupa todo el vídeo, se ve.")
    def captura_de_escena(self, *args):
        self.llamadas.append(("captura_de_escena",) + args)
    def ventanas(self, escena, parada=None):
        self.llamadas.append(("ventanas", escena))
        return tuple(self.opciones_ventana), self.actual_ventana
    def usar_ventana(self, escena, valor, parada=None):
        self.llamadas.append(("usar_ventana", escena, valor))
        return "Ahora se captura Champions, de juego.exe."


class HiloInmediato:

    def __init__(self, target, **kwargs): self.target = target
    def start(self): self.target()


class Evento:
    def Skip(self): pass


class EventoTecla:

    def __init__(self, codigo, ctrl=False, shift=False):
        self.codigo = codigo
        self.ctrl = ctrl
        self.shift = shift
        self.se_omitio = False

    def GetKeyCode(self): return self.codigo
    def ControlDown(self): return self.ctrl
    def ShiftDown(self): return self.shift
    def Skip(self): self.se_omitio = True


def _asegurar_sin_obs(*args, **kwargs):
    return False


def _revision(problemas=()):
    return obs_prevuelo.Revision(
        "TikTok", "TikTok", "TikTok", 720, 1280, "Principal",
        (), (), None, tuple(problemas))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPanelTransmision(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self.categorias = []
        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(control_grabacion, "anunciar", anunciar),
            mock.patch.object(gui_microfono, "anunciar", anunciar),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
            mock.patch.object(control_grabacion.sound_player, "reproducir"),
            mock.patch.object(directo_panel, "anunciar", anunciar),
            mock.patch.object(directo_panel.sound_player, "reproducir"),
        ]
        for parche in self.parches: parche.start()
        self.addCleanup(self._frenar)
        self.gestor = GestorFalso()
        self.dialogo = self._crear()

    def _frenar(self):
        for parche in reversed(self.parches): parche.stop()

    def _crear(self, **kwargs):
        datos = dict(gestor=self.gestor, asegurar=_asegurar_sin_obs)
        datos.update(kwargs)
        dialogo = gui_transmision.TransmisionDialog(None, **datos)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _nombres_en_orden(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.Button,
                                 wx.CheckBox, wx.SpinCtrl)) and hijo.IsShown():
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres_en_orden(hijo))
        return nombres

    def _pulsar(self, boton_):
        boton_.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, boton_.GetId()))

    def _elegir(self, destino):
        self.dialogo.cho_destino.SetStringSelection(destino)
        self.dialogo.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            self.dialogo.cho_destino.GetId()))

    def test_boton_directo_se_pinta_como_principal(self):
        if tema.ALTO_CONTRASTE:
            self.skipTest("Windows está en alto contraste")
        self.assertEqual(self.dialogo.btn_directo.GetBackgroundColour(),
                         tema._T.primary)

    def test_no_queda_texto_con_preparar_destino_ni_panel(self):
        raiz = pathlib.Path(__file__).resolve().parents[1]
        for relativo in ("bellbird/ui/gui_transmision.py",
                         "bellbird/obs/obs_prevuelo.py",
                         "bellbird/obs/obs_destinos.py",
                         "bellbird/obs/obs_disposicion.py"):
            with self.subTest(archivo=relativo):
                texto = (raiz / relativo).read_text(encoding="utf-8")
                self.assertNotIn("Preparar destino", texto)
                self.assertNotIn("Preparar panel", texto)

    def test_titulo_y_grupos(self):
        self.assertEqual(self.dialogo.GetTitle(), "Panel de transmisión")
        titulos = [caja.GetLabel() for caja in self._cajas(self.dialogo)]
        self.assertEqual(titulos, ["Directo"])

    def _cajas(self, ventana):
        cajas = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, wx.StaticBox):
                cajas.append(hijo)
            cajas.extend(self._cajas(hijo))
        return cajas

    def test_orden_de_tab_con_youtube_en_reposo(self):
        self.dialogo._alternar_panel = mock.Mock(return_value=True)
        self._elegir("YouTube")
        self.dialogo._aplicar_visibilidad()
        self.assertEqual(self._nombres_en_orden(self.dialogo), [
            "Estado", "Transmitir a", "Transmitir en directo",
            "Mostrar chat en el vídeo", "Escena…", "Grabación…",
            "Mostrar OBS", "Actualizar estado", "Cerrar"])

    def test_orden_de_tab_con_tiktok_en_reposo(self):
        self._elegir("TikTok")
        self.assertEqual(self._nombres_en_orden(self.dialogo), [
            "Estado", "Transmitir a", "Usuario de TikTok",
            "Transmitir en directo", "Escena…", "Grabación…",
            "Mostrar OBS", "Actualizar estado", "Cerrar"])

    def test_durante_el_directo_se_ocultan_destino_y_usuario(self):
        self._elegir("TikTok")
        self.dialogo._directo.sincronizar(True)
        self.dialogo._aplicar_visibilidad()
        self.assertFalse(self.dialogo.cho_destino.IsShown())
        self.assertFalse(self.dialogo.txt_usuario_tiktok.IsShown())
        self.assertEqual(self.dialogo.btn_directo.GetLabel(),
                         "&Finalizar directo")

    def test_intro_con_el_foco_en_cualquier_control_no_transmite(self):
        supervisar = mock.Mock(return_value=False)
        dialogo = self._crear(supervisar=supervisar)
        self.assertIsNone(dialogo.GetDefaultItem())
        for control in (dialogo.txt_estado, dialogo.cho_destino,
                        dialogo.btn_escena,
                        dialogo.btn_directo, dialogo.btn_actualizar):
            with self.subTest(control=control.GetName()):
                control.SetFocus()
                evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
                evento.KeyCode = wx.WXK_RETURN
                control.GetEventHandler().ProcessEvent(evento)
        supervisar.assert_not_called()

    def test_al_abrir_se_anuncia_solo_el_titular(self):
        self.anuncios.clear()
        dialogo = self._crear()
        self.assertEqual(self.anuncios, ["Elige a dónde transmitir"])
        self.assertEqual(dialogo.txt_estado.GetValue().splitlines()[0],
                         "Elige a dónde transmitir")

    def test_estado_alto_para_seis_lineas_y_sin_barra_vertical(self):
        estilo = self.dialogo.txt_estado.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_READONLY)
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertTrue(estilo & wx.TE_RICH2)
        self.assertFalse(estilo & wx.TE_NO_VSCROLL)
        self.assertGreaterEqual(self.dialogo.txt_estado.GetMinSize().GetHeight(),
                                6 * self.dialogo.txt_estado.GetCharHeight())

    def test_primera_linea_en_negrita_y_el_resto_normal(self):
        titular = "Revisa antes de transmitir: algo"
        self.dialogo._mostrar_estado(estado_panel.EstadoPanel(
            titular, "aviso", ("Escena actual: Principal",)))
        primera = wx.TextAttr()
        segunda = wx.TextAttr()
        self.assertTrue(self.dialogo.txt_estado.GetStyle(0, primera))
        self.assertTrue(self.dialogo.txt_estado.GetStyle(
            len(titular) + 1, segunda))
        self.assertGreaterEqual(primera.GetFont().GetWeight(),
                                wx.FONTWEIGHT_BOLD)
        self.assertLess(segunda.GetFont().GetWeight(), wx.FONTWEIGHT_BOLD)
        if not tema.ALTO_CONTRASTE:
            self.assertEqual(primera.GetTextColour(), tema._T.red)
            self.assertNotEqual(segunda.GetTextColour(), tema._T.red)

    def test_ventana_mide_al_menos_600_de_ancho(self):
        self.assertGreaterEqual(self.dialogo.GetSize().GetWidth(), 600)
        self._elegir("TikTok")
        self.assertGreaterEqual(self.dialogo.GetSize().GetWidth(), 600)

    def test_al_pasar_de_tiktok_a_youtube_baja_el_alto(self):
        self._elegir("TikTok")
        alto_tiktok = self.dialogo.GetSize().GetHeight()
        self._elegir("YouTube")
        alto_youtube = self.dialogo.GetSize().GetHeight()
        self.assertLess(alto_youtube, alto_tiktok)
        zona = self.dialogo._zona_desplazable
        self.assertGreaterEqual(zona.GetClientSize().GetHeight(),
                                zona.GetVirtualSize().GetHeight())

    def test_zona_sin_barra_vertical_al_abrir(self):
        zona = self.dialogo._zona_desplazable
        self.assertGreaterEqual(zona.GetClientSize().GetHeight(),
                                zona.GetVirtualSize().GetHeight())

    def test_actualizar_estado_anuncia_el_cuadro_entero(self):
        self._elegir("YouTube")
        self.anuncios.clear()
        self._pulsar(self.dialogo.btn_actualizar)
        self.assertEqual(len(self.anuncios), 1)
        self.assertIn("Preparado para transmitir a YouTube", self.anuncios[0])
        self.assertIn("Escena actual: Principal", self.anuncios[0])
        self.assertIn("Grabación: detenida", self.anuncios[0])

    def test_fallo_se_escribe_en_estado_con_tono_aviso(self):
        with mock.patch.object(tema, "ALTO_CONTRASTE", False):
            self.dialogo._fallo("OBS no contesta")
        self.assertEqual(self.dialogo.txt_estado.GetValue(), "OBS no contesta")
        if not tema.ALTO_CONTRASTE:
            attr = wx.TextAttr()
            self.assertTrue(self.dialogo.txt_estado.GetStyle(0, attr))
            self.assertEqual(attr.GetTextColour(), tema._T.red)

    def test_fallo_enfoca_actualizar_estado(self):
        with mock.patch.object(self.dialogo.btn_actualizar, "SetFocus") as foco:
            self.dialogo._fallo("OBS no contesta")
        self.assertTrue(self.dialogo.btn_actualizar.IsEnabled())
        foco.assert_called_once_with()

    def test_fallo_al_abrir_desactiva_controles_y_muestra_error(self):
        gestor = GestorFalso(fallo=True)
        dialogo = self._crear(gestor=gestor)
        self.assertEqual(dialogo.txt_estado.GetValue(),
                         "OBS no está disponible")
        self.assertFalse(dialogo.btn_escena.IsEnabled())

    def test_una_excepcion_no_prevista_libera_el_dialogo_y_avisa(self):
        def falla():
            raise TypeError("'NoneType' object is not subscriptable")
        with mock.patch.object(operaciones_obs.logger, "warning"):
            self.dialogo._en_hilo(falla)
        self.assertFalse(self.dialogo._operaciones.en_vuelo)
        self.assertIn("OBS no pudo completar la operación",
                      self.dialogo.txt_estado.GetValue())

    def test_chat_enciende_y_agrega_la_fuente_solo_si_falta(self):
        self.gestor.tiene_panel = False
        self.gestor.llamadas.clear()
        alternar = mock.Mock(return_value=True)
        dialogo = self._crear(alternar_panel=alternar)
        dialogo.chk_chat.SetValue(True)
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "puerto_actual", return_value=8730):
            dialogo._alternar_chat(Evento())
        alternar.assert_called_once_with(True)
        self.assertIn(("asegurar_fuente", "Principal",
                       "http://127.0.0.1:8730/chat", 460, 620),
                      self.gestor.llamadas)
        self.assertIn("Chat en el vídeo agregado a la escena Principal.",
                      self.anuncios)

    def test_chat_no_repone_la_fuente_si_ya_esta(self):
        self.gestor.tiene_panel = True
        self.gestor.llamadas.clear()
        dialogo = self._crear(alternar_panel=mock.Mock(return_value=True))
        dialogo.chk_chat.SetValue(True)
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "puerto_actual", return_value=8730):
            dialogo._alternar_chat(Evento())
        self.assertNotIn("asegurar_fuente",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_apagar_el_chat_no_elimina_la_fuente(self):
        dialogo = self._crear(alternar_panel=mock.Mock(return_value=False))
        dialogo.chk_chat.SetValue(False)
        dialogo._alternar_chat(Evento())
        self.assertNotIn("eliminar",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_chat_si_el_puerto_esta_ocupado_queda_apagado(self):
        dialogo = self._crear(alternar_panel=mock.Mock(return_value=False))
        dialogo.chk_chat.SetValue(True)
        dialogo._alternar_chat(Evento())
        self.assertFalse(dialogo.chk_chat.GetValue())
        self.assertNotIn("asegurar_fuente",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_el_estado_sigue_diciendo_microfono_y_escena_al_aire(self):
        self.dialogo._estado_leido(SimpleNamespace(
            escena="Principal", transmision={"outputActive": False},
            grabacion={"outputActive": False}, perfil="", problemas=(),
            microfono="Mic/Aux", silenciado=True))
        texto = self.dialogo.txt_estado.GetValue()
        self.assertIn("Escena actual: Principal", texto)
        self.assertIn("Micrófono Mic/Aux: silenciado", texto)

    def test_el_panel_ya_no_tiene_los_botones_de_grabacion(self):
        for nombre in ("_grabacion", "btn_grabar", "btn_pausar",
                       "btn_grabaciones"):
            with self.subTest(nombre=nombre):
                self.assertFalse(hasattr(self.dialogo, nombre))

    def test_boton_grabacion_abre_el_panel_en_grabacion(self):
        from bellbird.ui import obs_ventana

        with mock.patch.object(obs_ventana, "abrir_obs") as abrir, \
                mock.patch.object(self.dialogo, "_refrescar_estado") as refrescar, \
                mock.patch.object(self.dialogo.btn_grabacion,
                                  "SetFocus") as foco:
            self._pulsar(self.dialogo.btn_grabacion)
        abrir.assert_called_once_with(
            self.dialogo, self.dialogo.GetParent(), gestor=self.gestor,
            pestana=obs_ventana.PESTANA_GRABACION)
        refrescar.assert_called_once_with()
        foco.assert_called_once_with()

    def test_el_estado_sigue_diciendo_si_se_graba(self):
        self.dialogo._aplicar_datos(SimpleNamespace(
            escena="Principal", transmision={"outputActive": False},
            grabacion={"outputActive": True, "outputPaused": False,
                       "outputTimecode": "00:01:02.000"},
            microfono="Mic/Aux", silenciado=False, al_aire="Principal",
            perfil="", problemas=()))
        self.assertIn("Grabación: en curso, 00:01:02",
                      self.dialogo.txt_estado.GetValue())

    def test_consulta_rapida_no_anuncia_la_espera(self):
        temporizador = mock.Mock()
        self.dialogo._operaciones._temporizador_consulta = temporizador
        self._pulsar(self.dialogo.btn_actualizar)
        temporizador.StartOnce.assert_called_once_with(400)
        temporizador.Stop.assert_called_once_with()
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_mostrar_obs_llama_al_comando_del_menu(self):
        with mock.patch.object(menu_transmision, "mostrar_obs") as mostrar:
            self._pulsar(self.dialogo.btn_mostrar_obs)
        mostrar.assert_called_once_with()

    def test_el_panel_no_tiene_los_controles_que_salieron_y_si_el_de_escena(self):
        for nombre in ("chk_silenciar", "cho_escena", "btn_organizar",
                       "btn_microfono", "btn_cambiar_escena"):
            with self.subTest(nombre=nombre):
                self.assertFalse(hasattr(self.dialogo, nombre))
        self.assertEqual(self.dialogo.btn_escena.GetLabel(), "Esce&na…")
        self.assertEqual(self.dialogo.btn_escena.GetName(), "Escena…")
        self.assertEqual(self.dialogo.btn_grabacion.GetLabel(), "Gra&bación…")
        self.assertEqual(self.dialogo.btn_grabacion.GetName(), "Grabación…")

    def test_boton_escena_abre_el_panel_en_escena(self):
        from bellbird.ui import obs_ventana

        with mock.patch.object(obs_ventana, "abrir_obs") as abrir, \
                mock.patch.object(self.dialogo, "_refrescar_estado") as refrescar, \
                mock.patch.object(self.dialogo.btn_escena, "SetFocus") as foco:
            self._pulsar(self.dialogo.btn_escena)
        abrir.assert_called_once_with(
            self.dialogo, self.dialogo.GetParent(), gestor=self.gestor,
            pestana=obs_ventana.PESTANA_ESCENA)
        refrescar.assert_called_once_with()
        foco.assert_called_once_with()

    def test_el_panel_ya_no_tiene_los_controles_que_salieron(self):
        for nombre in ("Preparar destino", "Preparar panel",
                       "Panel de chat para transmitir", "Estado del panel",
                       "Poner al aire", "Transmitir"):
            with self.subTest(nombre=nombre):
                self.assertIsNone(
                    self._control_por_nombre(self.dialogo, nombre))

    def _control_por_nombre(self, ventana, nombre):
        for hijo in ventana.GetChildren():
            if hijo.GetName() == nombre:
                return hijo
            encontrado = self._control_por_nombre(hijo, nombre)
            if encontrado is not None:
                return encontrado
        return None

    def test_cada_campo_tiene_su_rotulo_visible_justo_antes(self):
        casos = [
            (self.dialogo.txt_estado, "&Estado:"),
            (self.dialogo.cho_destino, "Transmitir &a:"),
            (self.dialogo.txt_usuario_tiktok, "&Usuario de TikTok:"),
        ]
        for control, esperado in casos:
            with self.subTest(control=control.GetName()):
                hijos = list(control.GetParent().GetChildren())
                indice = hijos.index(control)
                self.assertGreater(indice, 0)
                rotulo = hijos[indice - 1]
                self.assertIsInstance(rotulo, wx.StaticText)
                self.assertEqual(rotulo.GetLabel(), esperado)

    def test_letras_de_atajo_unicas_y_ascii(self):
        letras = [self._letra_de_atajo(etiqueta)
                  for etiqueta in self._etiquetas(self.dialogo)]
        letras = [letra for letra in letras if letra]
        self.assertEqual(len(letras), len(set(letras)), letras)
        for letra in letras:
            self.assertTrue(letra.isascii(), letra)

    @staticmethod
    def _letra_de_atajo(etiqueta):
        posicion = etiqueta.find("&")
        if posicion < 0 or posicion + 1 >= len(etiqueta):
            return ""
        return etiqueta[posicion + 1].upper()

    def _etiquetas(self, ventana):
        etiquetas = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Button, wx.CheckBox, wx.StaticText)):
                etiquetas.append(hijo.GetLabel())
            etiquetas.extend(self._etiquetas(hijo))
        return etiquetas

    def test_foco_inicial_en_transmitir_a(self):
        self.assertIs(self.dialogo.FindFocus(), self.dialogo.cho_destino)

    def test_controles_de_destino_tienen_nombres_y_opciones(self):
        self.assertEqual(self.dialogo.cho_destino.GetStrings(),
                         ["TikTok", "YouTube"])
        self.assertEqual(self.dialogo.cho_destino.GetName(), "Transmitir a")
        self.assertEqual(self.dialogo.txt_usuario_tiktok.GetName(),
                         "Usuario de TikTok")
        self.assertEqual(self.dialogo.btn_directo.GetName(),
                         "Transmitir en directo")

    def test_destino_inicial_muestra_el_perfil_actual_si_es_un_destino(self):
        self.gestor.perfil = "YouTube"
        dialogo = self._crear()
        self.assertEqual(dialogo.cho_destino.GetStringSelection(), "YouTube")

    def test_destino_inicial_sin_seleccion_si_el_perfil_no_es_un_destino(self):
        self.gestor.perfil = "N5000-Grabacion"
        dialogo = self._crear()
        self.assertEqual(dialogo.cho_destino.GetSelection(), wx.NOT_FOUND)

    def test_cambiar_la_lista_guarda_el_destino_sin_anunciar(self):
        guardar = mock.Mock()
        dialogo = self._crear(guardar_destino=guardar)
        dialogo.cho_destino.SetStringSelection("YouTube")
        dialogo.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            dialogo.cho_destino.GetId()))
        guardar.assert_called_once_with("YouTube")

    def test_campo_usuario_arranca_con_el_guardado(self):
        dialogo = self._crear(usuario_tiktok="amigo")
        self.assertEqual(dialogo.txt_usuario_tiktok.GetValue(), "amigo")

    def test_cerrar_no_anuncia_ni_depende_del_error_de_obs(self):
        self.gestor.cerrar = mock.Mock(side_effect=obs_cliente.ObsError("sin red"))
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        self.gestor.cerrar.assert_called_once_with()
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_cerrar_detiene_el_aviso_pendiente(self):
        temporizador = mock.Mock()
        self.dialogo._operaciones._temporizador_consulta = temporizador
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        temporizador.Stop.assert_called_once_with()

    def test_consulta_lenta_anuncia_la_espera(self):
        self.dialogo._operaciones.en_vuelo = True
        self.dialogo._operaciones._anunciar_consulta(Evento())
        self.assertIn("Consultando OBS", self.anuncios)

    def test_contenido_en_zona_desplazable_y_cerrar_fuera(self):
        zona = self.dialogo._zona_desplazable
        self.assertIsInstance(zona, wx.ScrolledWindow)
        self.assertTrue(self._esta_dentro(self.dialogo.cho_destino, zona))
        self.assertFalse(self._esta_dentro(self.dialogo.btn_cerrar, zona))

    @staticmethod
    def _esta_dentro(control, antecesor):
        ventana = control.GetParent()
        while ventana is not None:
            if ventana is antecesor:
                return True
            ventana = ventana.GetParent()
        return False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoTransmisionVentana(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
            mock.patch.object(control_grabacion.sound_player, "reproducir"),
            mock.patch.object(directo_panel, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(directo_panel.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = gui_transmision.TransmisionDialog(
                None, GestorFalso(), asegurar=_asegurar_sin_obs)
            sin_marcar = textos_sin_marcar(dialogo, propios=(
                "TikTok", "YouTube", "Principal", "Juego", "Mic/Aux",
                "Finalizando el directo", "Finalizando el directo, esperando a OBS"))
        self.addCleanup(destruir, dialogo)
        self.assertEqual([], sin_marcar)


class TestPanelSinConsultasDeFuente(unittest.TestCase):

    def test_leer_estado_no_pide_ventanas_ni_descripcion(self):
        gestor = mock.Mock()
        gestor.escena_al_aire.return_value = "Principal"
        gestor.estado_transmision.return_value = {}
        gestor.estado_grabacion.return_value = {}
        gestor.perfil_actual.return_value = ""
        gestor.entradas_audio.return_value = ()
        gestor.microfono_especial.return_value = ""
        datos = consultas_transmision.leer_estado(gestor, "")
        self.assertEqual(datos.escena, "Principal")
        gestor.ventanas.assert_not_called()
        gestor.descripcion_escena.assert_not_called()

    def test_inicial_cargada_anuncia_solo_el_titular(self):
        falso = mock.Mock()
        datos = SimpleNamespace(
            escenas=("Principal",), escena="Principal", al_aire="Principal",
            fuentes=(), transmision={"outputActive": False},
            grabacion={"outputActive": False}, perfil="",
            problemas=(), microfono="", silenciado=False)
        with mock.patch.object(gui_transmision, "anunciar") as anunciar:
            gui_transmision.TransmisionDialog._inicial_cargada(falso, datos)
        anunciar.assert_called_once()


class TestConfirmarFinalizarSinVentana(unittest.TestCase):

    def _confirmar(self, resultado):
        creados = []

        def fabrica(*args, **kwargs):
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = resultado
            creados.append((args, dialogo))
            return dialogo

        with mock.patch.object(modulo_confirmar.wx, "MessageDialog", fabrica):
            acepta = modulo_confirmar.confirmar_finalizar(mock.sentinel.padre)
        return acepta, creados

    def test_aceptar_devuelve_verdadero_con_los_textos_de_siempre(self):
        acepta, creados = self._confirmar(wx.ID_YES)
        self.assertTrue(acepta)
        args, dialogo = creados[0]
        self.assertEqual(args[0], mock.sentinel.padre)
        self.assertEqual(
            args[1],
            "¿Finalizar el directo? Quienes te están viendo dejarán de verte.")
        self.assertEqual(args[2], "Finalizar directo")
        self.assertEqual(args[3], wx.YES_NO | wx.NO_DEFAULT)
        dialogo.SetYesNoLabels.assert_called_once_with(
            "&Finalizar directo", "&Seguir transmitiendo")
        dialogo.Destroy.assert_called_once_with()

    def test_no_devuelve_falso_y_cierra(self):
        acepta, creados = self._confirmar(wx.ID_NO)
        self.assertFalse(acepta)
        creados[0][1].Destroy.assert_called_once_with()


class TestPseudoConfirmarTransmision(unittest.TestCase):

    def test_titulo_mensaje_y_botones_pasan_por_gettext(self):
        revision = _revision()
        captado = {}
        creados = []

        def fabrica(padre, mensaje, titulo, estilo):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = wx.ID_OK
            creados.append(dialogo)
            return dialogo

        with con_pseudo(), \
                mock.patch.object(modulo_confirmar.wx, "MessageDialog", fabrica):
            esperada = obs_prevuelo.frase_revision(revision)
            modulo_confirmar.confirmar_transmision(mock.sentinel.padre, revision)
        self.assertEqual(captado["mensaje"], esperada)
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        for etiqueta in creados[0].SetOKCancelLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"))

    def test_finalizar_pasa_por_gettext(self):
        captado = {}
        creados = []

        def fabrica(padre, mensaje, titulo, estilo):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = wx.ID_NO
            creados.append(dialogo)
            return dialogo

        with con_pseudo(),                 mock.patch.object(modulo_confirmar.wx, "MessageDialog", fabrica):
            modulo_confirmar.confirmar_finalizar(mock.sentinel.padre)
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        for etiqueta in creados[0].SetYesNoLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"))


class TestElegirFuente(unittest.TestCase):

    def test_prefiere_la_del_chat_si_esta(self):
        self.assertEqual(
            consultas_transmision.elegir_fuente(
                ("Cámara", gui_transmision.NOMBRE_FUENTE)),
            gui_transmision.NOMBRE_FUENTE)

    def test_sin_la_del_chat_devuelve_la_primera(self):
        self.assertEqual(
            consultas_transmision.elegir_fuente(("Cámara", "Juego")), "Cámara")

    def test_lista_vacia_devuelve_vacio(self):
        self.assertEqual(consultas_transmision.elegir_fuente(()), "")


if __name__ == "__main__":
    unittest.main()
