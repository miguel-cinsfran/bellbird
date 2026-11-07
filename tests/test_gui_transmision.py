"""Pruebas de la pestaña Transmisión dentro del panel de OBS."""

import pathlib
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from guyrapu.obs import consultas_transmision
from guyrapu.obs import obs_cliente
from guyrapu.obs import obs_disposicion
from guyrapu.obs import obs_prevuelo
from guyrapu.obs.obs_escena import FilaFuente
from guyrapu.ui import confirmar_transmision as modulo_confirmar
from guyrapu.ui import control_grabacion
from guyrapu.ui import directo_panel
from guyrapu.ui import escena_captura_ventana
from guyrapu.ui import escena_pagina_escena
from guyrapu.ui import escena_pagina_fuentes
from guyrapu.ui import gui_grabaciones
from guyrapu.ui import gui as modulo_gui
from guyrapu.ui import gui_microfono
from guyrapu.ui import gui_transmision
from guyrapu.ui import menu_transmision
from guyrapu.ui import mover_con_flechas
from guyrapu.ui import obs_ventana
from guyrapu.ui import operaciones_obs
from guyrapu.ui import tema
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import app_de_prueba, destruir

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
    def conectado(self): return not self.fallo
    def escenas(self): return ("Principal", "Juego")
    def escena_al_aire(self): return self.escena_resultante
    def poner_escena_al_aire(self, escena):
        self.llamadas.append(("poner_escena_al_aire", escena))
        return self.escena_resultante
    def fuentes(self, escena):
        return {"Principal": tuple(fuente for fuente in ("Cámara", "Chat en el vídeo", "Juego")
                                    if fuente != "Chat en el vídeo" or self.tiene_panel),
                "Juego": ("Captura",)}.get(escena, ())

    def filas_escena(self, escena, parada=None):
        return tuple(FilaFuente(nombre, nombre, True, False)
                     for nombre in self.fuentes(escena))
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
    def _pedir(self, tipo, datos=None, parada=None):
        return {}
    def silenciada(self, fuente):
        return self.silenciado
    def alternar_silencio(self, fuente):
        self.silenciado = not self.silenciado
        self.llamadas.append(("alternar_silencio", fuente))
        return self.silenciado
    def dispositivo(self, fuente, predeterminado):
        return "", False
    def elementos(self, escena, parada=None):
        return [{"sceneItemId": indice + 1, "sourceName": nombre,
                 "sceneItemIndex": indice,
                 "sceneItemTransform": {
                     "positionX": 32, "positionY": 18, "alignment": 5,
                     "rotation": 0, "scaleX": 1, "scaleY": 1,
                     "boundsType": "OBS_BOUNDS_NONE",
                     "boundsAlignment": 0, "boundsWidth": 0, "boundsHeight": 0,
                     "cropLeft": 0, "cropRight": 0, "cropTop": 0,
                     "cropBottom": 0}}
                for indice, nombre in enumerate(self.fuentes(escena))]
    def _llamar(self, nombre, args, kwargs):
        self.llamadas.append((nombre,) + args)
        self.fuentes_enviadas.append((nombre, kwargs.get("fuente")))
        self.snap = self.snap_nuevo
    def colocar(self, *args, **kwargs): self._llamar("colocar", args, kwargs)
    def transformar(self, escena, transformacion, parada=None, *, fuente=""):
        self._llamar("transformar", (escena, transformacion), {"fuente": fuente})
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


def _avisar_de(anunciar, sonar):
    def _avisar(texto, sonido=None, *, error=False):
        anunciar(texto)
        if sonido:
            sonar(sonido)
    return _avisar


def _asegurar_conecta(probar_conexion, al_anunciar=None, parada=None):
    return probar_conexion()


def _revision(problemas=()):
    return obs_prevuelo.Revision(
        "TikTok", "TikTok", "TikTok", 720, 1280, "Principal",
        (), (), None, tuple(problemas))


def _perfil_restream(nombre="Uno", orientacion="vertical", canales=(1,)):
    from guyrapu.restream.perfiles import Perfil
    return Perfil(nombre=nombre, canales=canales, orientacion=orientacion)


class PrincipalFalsa:

    def __init__(self, config=None):
        self._config = {"tiktok_usuario": "", "obs_microfono": "Mic/Aux",
                        "grabar_al_transmitir": False}
        self._config.update(config or {})
        self._atajos = {}
        self.alternar_panel = mock.Mock(return_value=True)
        self.supervisar = mock.Mock(return_value=False)
        self.guardar_usuario = mock.Mock()
        self.guardar_destino = mock.Mock()

    def _cambiar_overlay(self, encender):
        return self.alternar_panel(encender)

    def _supervisar_transmision(self, *args, **kwargs):
        return self.supervisar(*args, **kwargs)

    def _guardar_usuario_tiktok(self, usuario):
        return self.guardar_usuario(usuario)

    def _guardar_destino_transmision(self, destino):
        return self.guardar_destino(destino)


class OperacionesFalsas:

    def __init__(self):
        self.cerrando = False
        self.en_vuelo = False
        self.mensajes = []

    def en_hilo(self, funcion, al_terminar=None):
        self.en_vuelo = True
        try:
            resultado = funcion()
        except Exception as error:
            self.fallo(str(error))
            return
        self.en_vuelo = False
        if al_terminar is not None:
            al_terminar(resultado)

    def fallo(self, mensaje):
        self.en_vuelo = False
        self.mensajes.append(mensaje)

    def cerrar(self):
        self.cerrando = True


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPanelTransmision(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.anuncios = []
        self.categorias = []
        self.sonar = mock.Mock()
        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)
        self.encender = mock.Mock()
        self.apagar = mock.Mock()
        self.sonido = mock.Mock()
        self.recargar = mock.Mock()
        self.guardar_opcion = mock.Mock()
        self.diagnostico = mock.Mock()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.overlay_servidor,
                              "esta_encendido", return_value=False),
            mock.patch.object(gui_transmision.overlay_servidor, "encender",
                              self.encender),
            mock.patch.object(gui_transmision.overlay_servidor, "apagar",
                              self.apagar),
            mock.patch.object(gui_transmision, "sound_player", self.sonido),
            mock.patch.object(gui_transmision.obs_panel_recarga,
                              "recargar_fuente_panel", self.recargar),
            mock.patch.object(gui_transmision, "diagnostico",
                              self.diagnostico),
            mock.patch.object(modulo_gui, "guardar_opcion",
                              self.guardar_opcion),
            mock.patch.object(obs_ventana.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(obs_ventana, "anunciar", anunciar),
            mock.patch.object(gui_transmision, "anunciar", anunciar),
            mock.patch.object(gui_transmision.ganchos, "cargar_perfiles",
                              return_value=[]),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(gui_microfono, "anunciar", anunciar),
            mock.patch.object(escena_pagina_escena, "anunciar", anunciar),
            mock.patch.object(escena_pagina_fuentes, "anunciar", anunciar),
            mock.patch.object(escena_captura_ventana, "anunciar", anunciar),
            mock.patch.object(mover_con_flechas, "anunciar", anunciar),
            mock.patch.object(directo_panel, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "avisar",
                              _avisar_de(anunciar, self.sonar)),
            mock.patch.object(control_grabacion, "avisar",
                              _avisar_de(anunciar, self.sonar)),
            mock.patch.object(directo_panel, "avisar",
                              _avisar_de(anunciar, self.sonar)),
            mock.patch.object(directo_panel.sound_player, "reproducir"),
            mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                              return_value=[]),
            mock.patch.object(gui_microfono, "abrir_microfono_obs"),
        ]
        for parche in self.parches:
            parche.start()
        self.addCleanup(self._frenar)
        self.asegurar = mock.patch.object(
            obs_ventana.obs_lanzador, "asegurar_obs", _asegurar_sin_obs)
        self.asegurar_mock = self.asegurar.start()
        self.addCleanup(self.asegurar.stop)
        self.principal = PrincipalFalsa()
        self.gestor = GestorFalso()
        self.ventana = self._crear()
        self.dialogo = self.ventana._pagina_transmision

    def _frenar(self):
        for parche in reversed(self.parches):
            parche.stop()

    def _crear(self, gestor=None, principal=None,
               pestana=obs_ventana.PESTANA_TRANSMISION, alternar_panel=None,
               supervisar=None, guardar_usuario=None, guardar_destino=None,
               usuario_tiktok=None, asegurar=None):
        principal = principal or self.principal
        if alternar_panel is not None:
            principal.alternar_panel = alternar_panel
        if supervisar is not None:
            principal.supervisar = supervisar
        if guardar_usuario is not None:
            principal.guardar_usuario = guardar_usuario
        if guardar_destino is not None:
            principal.guardar_destino = guardar_destino
        if usuario_tiktok is not None:
            principal._config["tiktok_usuario"] = usuario_tiktok
        self.asegurar_mock.side_effect = asegurar or _asegurar_sin_obs
        ventana = obs_ventana.VentanaObs(
            None, principal, gestor=self.gestor if gestor is None else gestor,
            pestana=pestana)
        self.addCleanup(destruir, ventana)
        return ventana

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
        for relativo in ("guyrapu/ui/gui_transmision.py",
                         "guyrapu/obs/obs_prevuelo.py",
                         "guyrapu/obs/obs_destinos.py",
                         "guyrapu/obs/obs_disposicion.py"):
            with self.subTest(archivo=relativo):
                texto = (raiz / relativo).read_text(encoding="utf-8")
                self.assertNotIn("Preparar destino", texto)
                self.assertNotIn("Preparar panel", texto)

    def test_titulo_y_grupos(self):
        self.assertEqual(self.ventana.GetTitle(), "Panel de OBS")
        titulos = [caja.GetLabel() for caja in self._cajas(self.dialogo)]
        self.assertEqual(titulos, ["Directo"])

    def test_el_panel_abre_en_general_y_general_es_la_pagina_cero(self):
        ventana = self._crear(pestana=obs_ventana.PESTANA_GENERAL)
        self.assertEqual(ventana.nb.GetSelection(), 0)
        self.assertEqual(
            [ventana.nb.GetPageText(i)
             for i in range(ventana.nb.GetPageCount())],
            ["General", "Escena", "Transmisión", "Audio", "Grabación"])

    def test_pasar_a_general_vuelve_a_leer_el_estado(self):
        self.gestor.grabando = True
        evento = wx.BookCtrlEvent(
            wx.EVT_NOTEBOOK_PAGE_CHANGED.typeId, self.ventana.nb.GetId())
        evento.SetSelection(obs_ventana.PESTANA_GENERAL)
        self.ventana.nb.GetEventHandler().ProcessEvent(evento)
        self.assertIn("Grabación: en curso, 00:01:02",
                      self.ventana._pagina_general.texto())

    def test_f1_abre_el_manual_de_uso(self):
        from guyrapu.ui import gui_menu

        with mock.patch.object(gui_menu, "abrir_documento_paquete") as abrir:
            self.ventana._al_tecla(EventoTecla(wx.WXK_F1))
        abrir.assert_called_once_with(self.ventana, "MANUAL", "Manual de uso")

    def _cajas(self, ventana):
        cajas = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, wx.StaticBox):
                cajas.append(hijo)
            cajas.extend(self._cajas(hijo))
        return cajas

    def test_orden_de_tab_con_youtube_en_reposo(self):
        self._elegir("YouTube")
        self.assertEqual(self._nombres_en_orden(self.dialogo), [
            "Transmitir a", "Transmitir en directo", "Restream…"])

    def test_orden_de_tab_con_tiktok_en_reposo(self):
        self._elegir("TikTok")
        self.assertEqual(self._nombres_en_orden(self.dialogo), [
            "Transmitir a", "Usuario de TikTok",
            "Transmitir en directo", "Restream…"])

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
        ventana = self._crear(supervisar=supervisar)
        pagina = ventana._pagina_transmision
        for control in (pagina.cho_destino, pagina.btn_directo,
                        pagina.btn_restream):
            with self.subTest(control=control.GetName()):
                control.SetFocus()
                evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
                evento.KeyCode = wx.WXK_RETURN
                control.GetEventHandler().ProcessEvent(evento)
        supervisar.assert_not_called()

    def test_al_abrir_no_anuncia_el_estado(self):
        self.anuncios.clear()
        ventana = self._crear()
        self.assertEqual(self.anuncios, [])
        self.assertEqual(ventana._pagina_general.texto().splitlines()[0],
                         "Elige a dónde transmitir")

    def test_si_cambia_de_pestana_durante_la_carga_el_foco_no_va_a_general(self):
        with mock.patch.object(obs_ventana.VentanaObs, "_inicial_cargada"):
            ventana = self._crear(pestana=obs_ventana.PESTANA_GENERAL)
        ventana.nb.SetSelection(obs_ventana.PESTANA_TRANSMISION)
        ventana._pagina_transmision.cho_destino.SetFocus()
        ventana._inicial_cargada(ventana._cargar_inicial())
        self.assertIs(ventana.FindFocus(),
                      ventana._pagina_transmision.cho_destino)

    def test_al_abrir_en_transmision_enfoca_el_boton_si_el_destino_esta_oculto(self):
        pagina = self.dialogo
        pagina._directo.sincronizar(True)
        pagina._aplicar_visibilidad()
        with mock.patch.object(pagina.btn_directo, "SetFocus") as foco:
            pagina.enfocar_inicial()
        foco.assert_called_once_with()

    def test_general_tiene_un_campo_multilinea_de_solo_lectura(self):
        campo = self.ventana._pagina_general.txt_estado
        estilo = campo.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_READONLY)
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertEqual(campo.GetName(), "Estado")
        hijos = list(campo.GetParent().GetChildren())
        indice = hijos.index(campo)
        self.assertEqual(hijos[indice - 1].GetLabel(), "&Estado:")

    def test_ventana_mide_al_menos_600_de_ancho(self):
        self.assertGreaterEqual(self.ventana.GetSize().GetWidth(), 600)

    def test_actualizar_estado_anuncia_el_cuadro_entero(self):
        self._elegir("YouTube")
        self.anuncios.clear()
        self._pulsar(self.ventana._pagina_general.btn_actualizar)
        self.assertEqual(len(self.anuncios), 1)
        self.assertIn("Preparado para transmitir a YouTube", self.anuncios[0])
        self.assertIn("Escena actual: Principal", self.anuncios[0])
        self.assertIn("Grabación: detenida", self.anuncios[0])

    def test_fallo_se_escribe_en_estado(self):
        self.ventana._escribir_fallo("OBS no contesta")
        self.assertEqual(self.ventana._pagina_general.texto(),
                         "OBS no contesta")

    def test_tras_un_fallo_el_foco_queda_donde_estaba(self):
        with mock.patch.object(self.ventana.btn_cerrar, "SetFocus") as cerrar, \
                mock.patch.object(
                    self.ventana._pagina_general.txt_estado,
                    "SetFocus") as estado:
            self.ventana._enfocar_tras_fallo()
        cerrar.assert_not_called()
        estado.assert_not_called()

    def test_fallo_al_abrir_desactiva_controles_y_muestra_error(self):
        gestor = GestorFalso(fallo=True)
        ventana = self._crear(gestor=gestor, asegurar=_asegurar_conecta)
        pagina = ventana._pagina_transmision
        self.assertEqual(ventana._pagina_general.texto(),
                         "OBS no está disponible")
        self.assertFalse(pagina.btn_restream.IsEnabled())

    def test_una_excepcion_no_prevista_libera_el_dialogo_y_avisa(self):
        def falla():
            raise TypeError("'NoneType' object is not subscriptable")
        with mock.patch.object(operaciones_obs.logger, "warning"):
            self.ventana._en_hilo(falla)
        self.assertFalse(self.ventana._operaciones.en_vuelo)
        self.assertIn("OBS no pudo completar la operación",
                      self.ventana._pagina_general.texto())
        self.assertTrue(any("OBS no pudo completar la operación" in aviso
                            for aviso in self.anuncios))

    def _estado_chat(self, tiene_chat):
        return SimpleNamespace(
            escena="Principal", transmision={"outputActive": False},
            grabacion={"outputActive": False}, perfil="", problemas=(),
            microfono="", silenciado=False, tiene_chat=tiene_chat)

    def test_estado_con_fuente_y_servicio_apagado_enciende_sin_anunciar(self):
        self.principal._config["overlay_puerto"] = 9100
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.dialogo.sincronizar_chat(self._estado_chat(True))
        self.encender.assert_called_once_with(9100)
        self.assertEqual(self.anuncios, [])
        self.assertTrue(self.principal._config["overlay_activo"])
        self.guardar_opcion.assert_called_once_with(
            modulo_gui.RUTA_CONFIG, "overlay", "activo", "true")
        self.diagnostico.crear_hilo.assert_called_once_with(
            self.recargar, "RecargarPanelObs")

    def test_estado_sin_fuente_y_servicio_encendido_apaga_y_guarda(self):
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=True):
            self.dialogo.sincronizar_chat(self._estado_chat(False))
        self.apagar.assert_called_once_with()
        self.assertEqual(self.anuncios, [])
        self.assertFalse(self.principal._config["overlay_activo"])
        self.guardar_opcion.assert_called_once_with(
            modulo_gui.RUTA_CONFIG, "overlay", "activo", "false")

    def test_puerto_ocupado_anuncia_una_sola_vez(self):
        self.encender.side_effect = (
            gui_transmision.overlay_servidor.OverlayPuertoOcupadoError("ocupado"))
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.dialogo.sincronizar_chat(self._estado_chat(True))
            self.dialogo.sincronizar_chat(self._estado_chat(True))
        self.assertEqual(
            self.anuncios,
            ["No se pudo activar el chat en el vídeo: el puerto 8730 está en "
             "uso. Cámbialo en Preferencias, categoría Transmisión."])
        self.sonido.reproducir.assert_called_once_with("error")
        self.guardar_opcion.assert_not_called()

    def test_la_casilla_del_chat_no_existe_con_youtube_ni_tiktok(self):
        self.assertFalse(hasattr(self.dialogo, "chk_chat"))
        for destino in ("YouTube", "TikTok"):
            with self.subTest(destino=destino):
                self._elegir(destino)
                self.assertIsNone(self._control_por_nombre(
                    self.dialogo, "Mostrar chat en el vídeo"))

    def test_sin_obs_conectado_no_toca_el_servicio(self):
        self.gestor.fallo = True
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.dialogo.sincronizar_chat(self._estado_chat(True))
        self.encender.assert_not_called()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=True):
            self.dialogo.sincronizar_chat(self._estado_chat(False))
        self.apagar.assert_not_called()

    def test_una_lectura_de_general_con_fuente_enciende(self):
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.ventana._general_leida((self._estado_chat(True), {}))
        self.encender.assert_called_once_with(8730)
        self.assertEqual(self.anuncios, [])

    def test_una_lectura_de_general_actualizada_con_fuente_enciende(self):
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.ventana._general_actualizada((self._estado_chat(True), {}))
        self.encender.assert_called_once_with(8730)

    def test_una_lectura_de_grabacion_con_fuente_enciende(self):
        self.anuncios.clear()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.ventana._grabacion_leida(self._estado_chat(True))
        self.encender.assert_called_once_with(8730)

    def test_al_encender_por_p3_recarga_la_fuente(self):
        self.diagnostico.crear_hilo.side_effect = (
            lambda funcion, nombre: HiloInmediato(funcion))
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False):
            self.dialogo.sincronizar_chat(self._estado_chat(True))
        self.recargar.assert_called_once_with()

    def test_el_estado_de_general_dice_microfono_y_escena_al_aire(self):
        self.ventana._general_leida((SimpleNamespace(
            escena="Principal", transmision={"outputActive": False},
            grabacion={"outputActive": False}, perfil="", problemas=(),
            microfono="Mic/Aux", silenciado=True), {}))
        texto = self.ventana._pagina_general.texto()
        self.assertIn("Escena actual: Principal", texto)
        self.assertIn("Micrófono Mic/Aux: silenciado", texto)

    def test_la_pestana_no_tiene_el_panel_de_grabacion(self):
        for nombre in ("_grabacion", "btn_grabar", "btn_pausar",
                       "btn_grabaciones"):
            with self.subTest(nombre=nombre):
                self.assertFalse(hasattr(self.dialogo, nombre))

    def test_la_pestana_no_tiene_campo_de_estado_ni_actualizar(self):
        self.assertFalse(hasattr(self.dialogo, "txt_estado"))
        self.assertFalse(hasattr(self.dialogo, "btn_actualizar"))

    def test_el_estado_de_general_sigue_diciendo_si_se_graba(self):
        self.ventana._general_leida((SimpleNamespace(
            escena="Principal", transmision={"outputActive": False},
            grabacion={"outputActive": True, "outputPaused": False,
                       "outputTimecode": "00:01:02.000"},
            microfono="Mic/Aux", silenciado=False, perfil="", problemas=()),
            {}))
        self.assertIn("Grabación: en curso, 00:01:02",
                      self.ventana._pagina_general.texto())

    def test_tras_una_operacion_de_transmision_se_relee_general(self):
        self.gestor.grabando = True
        self.dialogo._al_cambiar_directo()
        self.assertIn("Grabación: en curso, 00:01:02",
                      self.ventana._pagina_general.texto())

    def test_consulta_rapida_no_anuncia_la_espera(self):
        temporizador = mock.Mock()
        self.ventana._operaciones._temporizador_consulta = temporizador
        self._pulsar(self.ventana._pagina_general.btn_actualizar)
        temporizador.StartOnce.assert_called_once_with(400)
        temporizador.Stop.assert_called_once_with()
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_la_pestana_no_tiene_los_botones_que_salieron(self):
        for nombre in ("btn_escena", "btn_grabacion", "btn_mostrar_obs",
                       "btn_actualizar", "btn_cerrar"):
            with self.subTest(nombre=nombre):
                self.assertFalse(hasattr(self.dialogo, nombre))

    def test_restream_abre_la_ventana_como_el_menu(self):
        with mock.patch.object(menu_transmision, "abrir_restream") as abrir:
            self._pulsar(self.dialogo.btn_restream)
        abrir.assert_called_once_with(self.principal)

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
        self.assertEqual(self.dialogo.btn_restream.GetName(), "Restream…")

    def test_destino_inicial_muestra_el_perfil_actual_si_es_un_destino(self):
        self.gestor.perfil = "YouTube"
        ventana = self._crear()
        self.assertEqual(
            ventana._pagina_transmision.cho_destino.GetStringSelection(),
            "YouTube")

    def test_destino_inicial_sin_seleccion_si_el_perfil_no_es_un_destino(self):
        self.gestor.perfil = "N5000-Grabacion"
        ventana = self._crear()
        self.assertEqual(
            ventana._pagina_transmision.cho_destino.GetSelection(),
            wx.NOT_FOUND)

    def test_cambiar_la_lista_guarda_el_destino_y_anuncia_el_titular(self):
        guardar = mock.Mock()
        ventana = self._crear(guardar_destino=guardar)
        pagina = ventana._pagina_transmision
        self.anuncios.clear()
        pagina.cho_destino.SetStringSelection("YouTube")
        pagina.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            pagina.cho_destino.GetId()))
        guardar.assert_called_once_with("YouTube")
        self.assertIn("Preparado para transmitir a YouTube", self.anuncios)

    def test_campo_usuario_arranca_con_el_guardado(self):
        ventana = self._crear(usuario_tiktok="amigo")
        self.assertEqual(
            ventana._pagina_transmision.txt_usuario_tiktok.GetValue(),
            "amigo")

    def _con_perfiles(self, *perfiles):
        return mock.patch.object(gui_transmision.ganchos, "cargar_perfiles",
                                 return_value=list(perfiles))

    def _elegir_en(self, pagina, texto):
        pagina.cho_destino.SetStringSelection(texto)
        pagina.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId, pagina.cho_destino.GetId()))

    def _enfocar_destino(self, pagina):
        pagina.cho_destino.GetEventHandler().ProcessEvent(
            wx.FocusEvent(wx.EVT_SET_FOCUS.typeId,
                          pagina.cho_destino.GetId()))

    def test_los_perfiles_aparecen_despues_de_youtube_y_tiktok(self):
        with self._con_perfiles(_perfil_restream()):
            ventana = self._crear()
        self.assertEqual(
            ventana._pagina_transmision.cho_destino.GetStrings(),
            ["TikTok", "YouTube", "Restream: Uno"])

    def test_al_recibir_foco_relee_perfiles_y_conserva_la_seleccion(self):
        pagina = self.dialogo
        self._elegir_en(pagina, "YouTube")
        with self._con_perfiles(_perfil_restream()), \
                mock.patch.object(wx.Choice, "SetFocus") as foco:
            self._enfocar_destino(pagina)
        self.assertIn("Restream: Uno", pagina.cho_destino.GetStrings())
        self.assertEqual(pagina.cho_destino.GetStringSelection(), "YouTube")
        foco.assert_not_called()

    def test_si_los_perfiles_no_cambiaron_no_toca_el_control(self):
        pagina = self.dialogo
        with mock.patch.object(pagina, "_poner_opciones") as poner:
            self._enfocar_destino(pagina)
        poner.assert_not_called()

    def test_perfil_guardado_se_recupera_al_abrir(self):
        self.principal._config["transmision_destino"] = "restream:Uno"
        with self._con_perfiles(_perfil_restream()):
            ventana = self._crear()
        self.assertEqual(
            ventana._pagina_transmision.cho_destino.GetStringSelection(),
            "Restream: Uno")

    def test_perfil_guardado_que_ya_no_existe_cae_al_perfil_de_obs(self):
        self.principal._config["transmision_destino"] = "restream:Viejo"
        self.gestor.perfil = "YouTube"
        with self._con_perfiles():
            ventana = self._crear()
        self.assertEqual(
            ventana._pagina_transmision.cho_destino.GetStringSelection(),
            "YouTube")

    def test_cambiar_a_un_perfil_guarda_la_opcion(self):
        with self._con_perfiles(_perfil_restream()):
            ventana = self._crear()
        pagina = ventana._pagina_transmision
        self._elegir_en(pagina, "Restream: Uno")
        self.principal.guardar_destino.assert_called_once_with(
            "restream:Uno")

    def test_el_perfil_oculta_el_usuario_y_sin_cuenta_no_transmite(self):
        with self._con_perfiles(_perfil_restream()):
            ventana = self._crear()
        pagina = ventana._pagina_transmision
        self._elegir_en(pagina, "Restream: Uno")
        self.assertFalse(pagina.txt_usuario_tiktok.IsShown())
        with mock.patch.object(directo_panel.ganchos, "cuenta_conectada",
                               return_value=False), \
                mock.patch.object(directo_panel, "avisar") as avisar:
            self._pulsar(pagina.btn_directo)
        self.assertEqual(
            avisar.call_args.args[0],
            "Para transmitir con un perfil de Restream hace falta conectar "
            "la cuenta, en el cuadro Restream, pestaña Cuenta.")
        self.assertEqual(avisar.call_args.args[1], "transmision_problema")
        self.assertTrue(avisar.call_args.kwargs["error"])
        self.principal.supervisar.assert_not_called()

    def test_elegir_restream_prepara_obs_y_supervisa_los_ganchos(self):
        with self._con_perfiles(_perfil_restream("Vertical", "vertical")):
            ventana = self._crear()
        pagina = ventana._pagina_transmision
        self._elegir_en(pagina, "Restream: Vertical")
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch.object(directo_panel.ganchos, "cuenta_conectada",
                               return_value=True), \
                mock.patch.object(directo_panel.transmision_directa,
                                  "preparar",
                                  return_value=preparacion) as preparar:
            self._pulsar(pagina.btn_directo)
        args, _ = preparar.call_args
        self.assertEqual(args[1], "TikTok")
        self.principal.supervisar.assert_any_call(
            "iniciar", "restream:Vertical", "")
        self.principal.guardar_destino.assert_called_with("restream:Vertical")
        self.principal.guardar_usuario.assert_not_called()

    def test_cerrar_no_anuncia_ni_depende_del_error_de_obs(self):
        with mock.patch.object(obs_ventana, "GestorPanelObs",
                               return_value=self.gestor):
            ventana = obs_ventana.VentanaObs(None, self.principal)
        self.addCleanup(destruir, ventana)
        self.gestor.cerrar = mock.Mock(side_effect=obs_cliente.ObsError("sin red"))
        ventana.EndModal = mock.Mock()
        ventana._cerrar(Evento())
        self.gestor.cerrar.assert_called_once_with()
        ventana.EndModal.assert_called_once_with(wx.ID_CANCEL)
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_cerrar_detiene_el_aviso_pendiente(self):
        temporizador = mock.Mock()
        self.ventana._operaciones._temporizador_consulta = temporizador
        self.ventana.EndModal = mock.Mock()
        self.ventana._cerrar(Evento())
        temporizador.Stop.assert_called_once_with()

    def test_cerrar_el_panel_cierra_el_directo_de_la_pestana(self):
        self.ventana.EndModal = mock.Mock()
        with mock.patch.object(self.dialogo._directo, "cerrar") as cerrar:
            self.ventana._cerrar(Evento())
        cerrar.assert_called_once_with()

    def test_consulta_lenta_anuncia_la_espera(self):
        self.ventana._operaciones.en_vuelo = True
        self.ventana._operaciones._anunciar_consulta(Evento())
        self.assertIn("Consultando OBS", self.anuncios)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoTransmisionVentana(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.sonar = mock.Mock()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.overlay_servidor,
                              "esta_encendido", return_value=False),
            mock.patch.object(gui_transmision.overlay_servidor, "encender"),
            mock.patch.object(gui_transmision.overlay_servidor, "apagar"),
            mock.patch.object(gui_transmision, "diagnostico"),
            mock.patch.object(modulo_gui, "guardar_opcion"),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "avisar",
                              lambda *args, **kwargs: None),
            mock.patch.object(control_grabacion, "avisar",
                              lambda *args, **kwargs: None),
            mock.patch.object(directo_panel, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(directo_panel, "avisar",
                              lambda *args, **kwargs: None),
            mock.patch.object(gui_transmision.ganchos, "cargar_perfiles",
                              return_value=[]),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        with con_pseudo():
            pagina = gui_transmision.PaginaTransmision(
                marco, PrincipalFalsa(), GestorFalso(), OperacionesFalsas())
            sin_marcar = textos_sin_marcar(pagina, propios=(
                "TikTok", "YouTube", "Principal", "Juego", "Mic/Aux",
                "Finalizando el directo", "Finalizando el directo, esperando a OBS"))
        self.addCleanup(destruir, pagina)
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
        gestor._pedir.return_value = {}
        datos = consultas_transmision.leer_estado(gestor, "")
        self.assertEqual(datos.escena, "Principal")
        gestor.ventanas.assert_not_called()
        gestor.descripcion_escena.assert_not_called()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestEnfocarInicialDeLaPagina(unittest.TestCase):

    def test_enfocar_inicial_no_anuncia_el_estado(self):
        app = app_de_prueba()
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        with mock.patch.object(gui_transmision, "anunciar") as anunciar, \
                mock.patch.object(gui_transmision.ganchos, "cargar_perfiles",
                                  return_value=[]), \
                mock.patch.object(gui_transmision.overlay_servidor,
                                  "esta_encendido", return_value=False):
            pagina = gui_transmision.PaginaTransmision(
                marco, PrincipalFalsa(), mock.Mock(), OperacionesFalsas())
            self.addCleanup(destruir, pagina)
            datos = SimpleNamespace(
                escenas=("Principal",), escena="Principal",
                al_aire="Principal", fuentes=(),
                transmision={"outputActive": False},
                grabacion={"outputActive": False}, perfil="",
                problemas=(), microfono="", silenciado=False)
            pagina.cargar(datos)
            pagina.enfocar_inicial()
        anunciar.assert_not_called()
        self.assertIsNotNone(app)


class TestConfirmarFinalizarSinVentana(unittest.TestCase):

    def _confirmar(self, resultado):
        creados = []

        def fabrica(*args, **kwargs):
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = resultado
            creados.append((args, dialogo))
            return dialogo

        with mock.patch.object(modulo_confirmar.confirmar, "MessageDialog",
                               fabrica):
            acepta = modulo_confirmar.confirmar_finalizar(mock.sentinel.padre)
        return acepta, creados

    def test_aceptar_devuelve_verdadero_con_los_textos_de_siempre(self):
        acepta, creados = self._confirmar(wx.ID_OK)
        self.assertTrue(acepta)
        args, dialogo = creados[0]
        self.assertEqual(args[0], mock.sentinel.padre)
        self.assertEqual(
            args[1],
            "¿Finalizar el directo? Quienes te están viendo dejarán de verte.")
        self.assertEqual(args[2], "Finalizar directo")
        self.assertTrue(args[3] & wx.OK)
        self.assertTrue(args[3] & wx.CANCEL)
        self.assertTrue(args[3] & wx.CANCEL_DEFAULT)
        dialogo.SetOKCancelLabels.assert_called_once_with(
            "&Finalizar directo", "&Seguir transmitiendo")
        dialogo.Destroy.assert_called_once_with()

    def test_no_devuelve_falso_y_cierra(self):
        acepta, creados = self._confirmar(wx.ID_CANCEL)
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

        with con_pseudo(), \
                mock.patch.object(modulo_confirmar.confirmar,
                                  "MessageDialog", fabrica):
            modulo_confirmar.confirmar_finalizar(mock.sentinel.padre)
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        for etiqueta in creados[0].SetOKCancelLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"))


class TestElegirFuente(unittest.TestCase):

    def test_prefiere_la_del_chat_si_esta(self):
        self.assertEqual(
            consultas_transmision.elegir_fuente(
                ("Cámara", consultas_transmision.NOMBRE_FUENTE)),
            consultas_transmision.NOMBRE_FUENTE)

    def test_sin_la_del_chat_devuelve_la_primera(self):
        self.assertEqual(
            consultas_transmision.elegir_fuente(("Cámara", "Juego")), "Cámara")

    def test_lista_vacia_devuelve_vacio(self):
        self.assertEqual(consultas_transmision.elegir_fuente(()), "")


if __name__ == "__main__":
    unittest.main()
