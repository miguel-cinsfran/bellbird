"""Pruebas del diálogo de Transmisión sin conectar con OBS."""

import types
import threading
import unittest
from unittest import mock

from bellbird.ui import confirmar_transmision as modulo_confirmar
from bellbird.ui import operaciones_obs
from bellbird.ui import gui_transmision
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_cliente
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_lanzador
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
        self.escalable = True
        self.llamadas = []
        self.fuentes_enviadas = []
        self.instantaneas = []
        self.snap = obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=460, alto=620,
            lienzo_ancho=1600, lienzo_alto=900, izquierda=32, arriba=18,
            visible=True, bloqueada=False)
        self.snap_nuevo = self.snap
        self.transformacion_inicial = {"positionX": 32, "positionY": 18, "alignment": 5}
        self.tiene_panel = True
        self.perfil = ""
        self.transmitiendo = False
        self.grabando = False
        self.grabacion_en_pausa = False
        self.escena_resultante = "Principal"
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
    def captura_de_escena(self, *args): self.llamadas.append(("captura_de_escena",) + args)
    def estado_transmision(self):
        return {"outputActive": self.transmitiendo, "outputDuration": 61,
                "outputSkippedFrames": 0, "outputTotalFrames": 100}
    def estado_grabacion(self):
        return {"outputActive": self.grabando, "outputPaused": self.grabacion_en_pausa,
                "outputTimecode": "00:01:02.000"}
    def alternar_transmision(self):
        self.transmitiendo = not self.transmitiendo
        self.llamadas.append(("alternar_transmision",))
        return self.transmitiendo
    def alternar_grabacion(self):
        self.grabando = not self.grabando
        self.llamadas.append(("alternar_grabacion",))
        return self.grabando
    def alternar_pausa_grabacion(self):
        self.grabacion_en_pausa = not self.grabacion_en_pausa
        self.llamadas.append(("alternar_pausa_grabacion",))
        return self.grabacion_en_pausa
    def perfil_actual(self, parada=None):
        self.llamadas.append(("perfil_actual",))
        return self.perfil
    def preparar_destino(self, destino, parada=None):
        self.llamadas.append(("preparar_destino", destino))
        self.perfil = destino
        vertical = destino == "TikTok"
        return {"destino": destino, "perfil": destino,
                "coleccion": destino if vertical else "Sin Título",
                "ancho": 720 if vertical else 1280,
                "alto": 1280 if vertical else 720}

    def revisar(self, destino, parada=None):
        from bellbird.obs import obs_prevuelo
        problemas = getattr(self, "problemas_revision", ())
        return obs_prevuelo.Revision(
            destino, destino, destino, 720, 1280, "Principal",
            (), (), None, tuple(problemas))

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
    # Doble del lanzador real: no toca OBS y finge que ya estaba en ejecución.
    return False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestTransmisionDialog(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.anuncios = []
        self.categorias = []
        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)
            self.categorias.append(categoria)
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter", lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(gui_transmision.sound_player, "reproducir"),
        ]
        for parche in self.parches: parche.start()
        self.gestor = GestorFalso()
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, asegurar=_asegurar_sin_obs)
        self.anuncios.clear()

    def tearDown(self):
        destruir(self.dialogo)
        for parche in reversed(self.parches): parche.stop()

    def test_fallo_al_abrir_desactiva_controles_y_muestra_error(self):
        destruir(self.dialogo)
        gestor = GestorFalso(fallo=True)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, gestor, asegurar=_asegurar_sin_obs)
        self.assertIn("OBS no está disponible", self.dialogo.txt_estado.GetValue())
        self.assertFalse(self.dialogo.cho_escena.IsEnabled())
        self.assertFalse(self.dialogo.btn_organizar.IsEnabled())

    def test_una_excepcion_no_prevista_libera_el_dialogo_y_avisa(self):
        # Solo se capturaba ObsError: un TypeError (la fuente elegida ya no
        # existe en OBS) mataba el hilo y dejaba todo desactivado para siempre.
        def falla():
            raise TypeError("'NoneType' object is not subscriptable")
        with mock.patch.object(operaciones_obs.logger, "warning"):
            self.dialogo._en_hilo(falla)
        self.assertFalse(self.dialogo._operaciones.en_vuelo)
        self.assertIn("OBS no pudo completar la operación",
                      self.dialogo.txt_estado.GetValue())

    def test_un_fallo_habilita_y_enfoca_actualizar_estado(self):
        with mock.patch.object(self.dialogo.btn_actualizar, "SetFocus") as foco:
            self.dialogo._fallo("OBS no contesta")
        self.assertTrue(self.dialogo.btn_actualizar.IsEnabled())
        foco.assert_called_once_with()

    def test_casilla_del_panel_alterna_el_servidor(self):
        destruir(self.dialogo)
        alternar = mock.Mock(side_effect=(True, False))
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, alternar_panel=alternar,
            asegurar=_asegurar_sin_obs)

        self.dialogo.chk_panel_chat.SetValue(True)
        self.dialogo._alternar_panel_chat(Evento())
        self.dialogo.chk_panel_chat.SetValue(False)
        self.dialogo._alternar_panel_chat(Evento())

        self.assertEqual(alternar.call_args_list, [mock.call(True), mock.call(False)])

    def test_casilla_del_panel_se_desmarca_si_no_se_pudo_encender(self):
        destruir(self.dialogo)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, alternar_panel=mock.Mock(return_value=False),
            asegurar=_asegurar_sin_obs)

        self.dialogo.chk_panel_chat.SetValue(True)
        self.dialogo._alternar_panel_chat(Evento())

        self.assertFalse(self.dialogo.chk_panel_chat.GetValue())

    def test_casilla_del_panel_sin_ventana_principal_esta_desactivada(self):
        self.assertIsNotNone(self.dialogo.chk_panel_chat)
        self.assertFalse(self.dialogo.chk_panel_chat.IsEnabled())

    def test_activar_fallo_mantiene_habilitada_la_casilla_con_callback(self):
        destruir(self.dialogo)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, alternar_panel=mock.Mock(),
            asegurar=_asegurar_sin_obs)

        self.dialogo._activar(False)

        self.assertTrue(self.dialogo.chk_panel_chat.IsEnabled())
        self.assertFalse(self.dialogo.btn_actualizar.IsEnabled())

    def test_activar_exito_habilita_la_casilla_con_callback(self):
        destruir(self.dialogo)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, alternar_panel=mock.Mock(),
            asegurar=_asegurar_sin_obs)

        self.dialogo._activar(True)

        self.assertTrue(self.dialogo.chk_panel_chat.IsEnabled())

    def test_activar_sin_callback_mantiene_deshabilitada_la_casilla(self):
        self.dialogo._activar(False)
        self.assertFalse(self.dialogo.chk_panel_chat.IsEnabled())
        self.dialogo._activar(True)
        self.assertFalse(self.dialogo.chk_panel_chat.IsEnabled())






    def test_apertura_anuncia_el_estado_sin_preparar_nada(self):
        gestor = GestorFalso()
        encender = mock.Mock()
        with mock.patch.object(gui_transmision.overlay_servidor, "esta_encendido",
                               return_value=False), \
             mock.patch.object(gui_transmision.overlay_servidor, "puerto_actual",
                               return_value=None), \
             mock.patch.object(gui_transmision.overlay_servidor, "encender", encender):
            dialogo = gui_transmision.TransmisionDialog(
                None, gestor, asegurar=_asegurar_sin_obs)
        self.addCleanup(destruir, dialogo)
        self.assertIn("El chat en el vídeo está desactivado.", self.anuncios)
        self.assertIn("Escena actual: Principal", self.anuncios)
        encender.assert_not_called()

    def test_preparar_panel_enciende_y_crea_solo_lo_necesario(self):
        for encendido, tiene_panel in ((False, False), (True, False),
                                       (False, True), (True, True)):
            with self.subTest(encendido=encendido, tiene_panel=tiene_panel):
                self.gestor.tiene_panel = tiene_panel
                self.gestor.llamadas.clear()
                encender = mock.Mock()
                with mock.patch.object(gui_transmision.overlay_servidor, "esta_encendido",
                                       return_value=encendido), \
                     mock.patch.object(gui_transmision.overlay_servidor, "puerto_actual",
                                       return_value=8730), \
                     mock.patch.object(gui_transmision.overlay_servidor, "encender", encender):
                    self.dialogo._preparar(Evento())
                self.assertEqual(encender.call_count, int(not encendido))
                llamadas = [llamada for llamada in self.gestor.llamadas
                            if llamada[0] == "asegurar_fuente"]
                self.assertEqual(len(llamadas), int(not tiene_panel))
                if llamadas:
                    self.assertEqual(llamadas[0], ("asegurar_fuente", "Principal",
                                                    "http://127.0.0.1:8730/chat", 460, 620))

    def test_preparar_panel_anuncia_si_el_puerto_esta_ocupado(self):
        with mock.patch.object(gui_transmision.overlay_servidor, "esta_encendido",
                               return_value=False), \
             mock.patch.object(gui_transmision.overlay_servidor, "puerto_actual",
                               return_value=8765), \
             mock.patch.object(gui_transmision.overlay_servidor, "encender",
                               side_effect=gui_transmision.overlay_servidor.OverlayPuertoOcupadoError):
            self.dialogo._preparar(Evento())
        self.assertEqual(self.anuncios[-1],
                         "No se pudo encender el panel, el puerto 8765 está ocupado")



    def test_poner_al_aire_usa_la_escena_elegida_y_anuncia_la_devuelta(self):
        self.dialogo.cho_escena.SetStringSelection("Juego")
        self.gestor.escena_resultante = "Principal"
        self.dialogo._poner_al_aire(Evento())
        self.assertIn(("poner_escena_al_aire", "Juego"), self.gestor.llamadas)
        self.assertEqual(self.anuncios[-1], "Escena actual: Principal")

    def test_boton_poner_al_aire_sigue_a_escena_en_las_acciones(self):
        indice = self.dialogo._acciones.index(self.dialogo.cho_escena)
        self.assertIs(self.dialogo._acciones[indice + 1], self.dialogo.btn_poner_al_aire)
        self.assertEqual(self.dialogo.btn_poner_al_aire.GetName(), "Poner al aire")































    def test_los_hilos_no_leen_controles_de_wx(self):
        # Escena se captura en el hilo principal y viaja como argumento; leer
        # un wx.Choice desde otro hilo no es seguro.
        original = gui_transmision.diagnostico.crear_hilo
        dialogo = self.dialogo
        fuera_del_hilo = AssertionError("control de wx leído desde un hilo")

        def crear_hilo(funcion, nombre, **kwargs):
            def envuelta():
                pendientes = []
                with mock.patch.object(dialogo, "_escena", side_effect=fuera_del_hilo),                         mock.patch.object(gui_transmision.wx, "CallAfter",
                                          lambda f, *a: pendientes.append((f, a))):
                    funcion()
                for funcion_pendiente, argumentos in pendientes:
                    funcion_pendiente(*argumentos)
            return original(envuelta, nombre, **kwargs)

        with mock.patch.object(gui_transmision.diagnostico, "crear_hilo", crear_hilo),                 mock.patch.object(gui_transmision.logger, "warning") as aviso,                 mock.patch.object(operaciones_obs.logger, "warning") as aviso_obs,                 mock.patch.object(gui_transmision.overlay_servidor, "esta_encendido",
                                  return_value=True),                 mock.patch.object(gui_transmision.overlay_servidor, "puerto_actual",
                                  return_value=8730):
            for accion in (dialogo._actualizar, dialogo._poner_al_aire,
                           dialogo._preparar):
                with self.subTest(accion=accion.__name__):
                    accion(Evento())
                    self.assertFalse(dialogo._operaciones.en_vuelo)
        aviso.assert_not_called()
        aviso_obs.assert_not_called()
        self.assertNotIn("OBS no pudo completar la operación. Inténtalo de nuevo.", self.anuncios)

    def test_organizar_escena_abre_con_la_escena_elegida_y_devuelve_el_foco(self):
        self.dialogo.cho_escena.SetStringSelection("Juego")
        creado = mock.Mock()
        with mock.patch.object(gui_transmision, "OrganizarEscenaDialog",
                               return_value=creado) as fabrica,                 mock.patch.object(self.dialogo.btn_organizar, "SetFocus") as foco:
            self.dialogo._organizar_escena(Evento())
        fabrica.assert_called_once_with(self.dialogo, self.gestor, "Juego")
        creado.ShowModal.assert_called_once_with()
        creado.Destroy.assert_called_once_with()
        foco.assert_called_once_with()

    def test_organizar_escena_cierra_el_cuadro_aunque_falle(self):
        creado = mock.Mock()
        creado.ShowModal.side_effect = RuntimeError("roto")
        with mock.patch.object(gui_transmision, "OrganizarEscenaDialog",
                               return_value=creado):
            with self.assertRaises(RuntimeError):
                self.dialogo._organizar_escena(Evento())
        creado.Destroy.assert_called_once_with()

    def test_el_panel_ya_no_tiene_los_controles_que_salieron(self):
        for nombre in ("Ventana que se captura", "Usar esa ventana", "Fuente",
                       "Posición del panel", "Colocar en esa posición",
                       "Ancho del panel en píxeles", "Alto del panel en píxeles",
                       "AplicarTamano", "MostrarPanel", "FijarPanel",
                       "PonerAlFrente", "AjusteFino", "Cómo se coloca el panel",
                       "QueEsElLienzo", "RestablecerTransmision",
                       "GuardarCaptura", "NotaTransmision"):
            with self.subTest(nombre=nombre):
                self.assertIsNone(
                    self._control_por_nombre(self.dialogo, nombre))
        self.assertEqual(self.dialogo.btn_organizar.GetLabel(),
                         "&Organizar escena…")

    def test_elegir_escena_en_el_panel_no_recarga_ni_pone_al_aire(self):
        self.gestor.fuentes = mock.Mock()
        self.gestor.poner_escena_al_aire = mock.Mock()
        self.dialogo.cho_escena.SetStringSelection("Juego")
        self.dialogo.cho_escena.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            self.dialogo.cho_escena.GetId()))
        self.gestor.fuentes.assert_not_called()
        self.gestor.poner_escena_al_aire.assert_not_called()

    def test_actualizar_estado_no_pide_fuente_ventanas_ni_descripcion(self):
        self.gestor.instantanea = mock.Mock()
        self.gestor.ventanas = mock.Mock()
        self.gestor.descripcion_escena = mock.Mock()
        self.dialogo._actualizar(Evento())
        self.gestor.instantanea.assert_not_called()
        self.gestor.ventanas.assert_not_called()
        self.gestor.descripcion_escena.assert_not_called()

    def test_estado_del_panel_muestra_la_frase_de_preparacion(self):
        self.dialogo._panel_preparado("Chat en el vídeo activado.")
        self.assertEqual(self.dialogo.txt_estado.GetValue(),
                         "Chat en el vídeo activado.")
        self.assertEqual(self.anuncios[-1], "Chat en el vídeo activado.")

    def test_cerrar_no_anuncia_ni_depende_del_error_de_obs(self):
        self.gestor.cerrar = mock.Mock(side_effect=obs_cliente.ObsError("sin red"))
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        self.gestor.cerrar.assert_called_once_with()
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_consulta_rapida_no_anuncia_la_espera(self):
        temporizador = mock.Mock()
        self.dialogo._operaciones._temporizador_consulta = temporizador
        self.dialogo._actualizar(Evento())
        temporizador.StartOnce.assert_called_once_with(400)
        temporizador.Stop.assert_called_once_with()
        self.assertNotIn("Consultando OBS", self.anuncios)

    def test_consulta_lenta_anuncia_la_espera(self):
        self.dialogo._operaciones.en_vuelo = True
        self.dialogo._operaciones._anunciar_consulta(Evento())
        self.assertIn("Consultando OBS", self.anuncios)

    def test_cerrar_detiene_el_aviso_pendiente(self):
        temporizador = mock.Mock()
        self.dialogo._operaciones._temporizador_consulta = temporizador
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        temporizador.Stop.assert_called_once_with()


    def test_botones_de_transmision_y_grabacion_llaman_al_gestor_y_anuncian(self):
        self.dialogo._transmitir(Evento())
        self.dialogo._grabar(Evento())
        self.dialogo._pausar_grabacion(Evento())
        self.assertEqual(self.gestor.llamadas[-3:], [
            ("alternar_transmision",), ("alternar_grabacion",),
            ("alternar_pausa_grabacion",)])
        self.assertEqual(self.anuncios[-3:], ["Transmisión iniciada", "Grabación iniciada",
                                               "Grabación en pausa"])

    def test_cada_resultado_reproduce_su_sonido_y_anuncia_la_frase(self):
        with mock.patch.object(gui_transmision.sound_player,
                               "reproducir") as reproducir:
            self.dialogo._transmision_alternada(True)
            self.dialogo._transmision_alternada(False)
            self.dialogo._grabacion_alternada(True)
            self.dialogo._grabacion_alternada(False)
            self.dialogo._pausa_grabacion_alternada(True)
            self.dialogo._pausa_grabacion_alternada(False)
        self.assertEqual([llamada.args[0]
                          for llamada in reproducir.call_args_list], [
            "al_aire", "transmision_detenida", "grabacion_iniciada",
            "grabacion_detenida", "grabacion_en_pausa", "grabacion_reanudada"])
        self.assertEqual(self.anuncios[-6:], [
            "Transmisión iniciada", "Transmisión detenida",
            "Grabación iniciada", "Grabación detenida",
            "Grabación en pausa", "Grabación reanudada"])

    def test_el_sonido_suena_antes_del_anuncio(self):
        orden = []
        with mock.patch.object(
                gui_transmision.sound_player, "reproducir",
                side_effect=lambda evento: orden.append(("sonido", evento))), \
                mock.patch.object(
                    gui_transmision, "anunciar",
                    side_effect=lambda frase, *a: orden.append(("frase", frase))):
            self.dialogo._grabacion_alternada(True)
        self.assertEqual([paso[0] for paso in orden], ["sonido", "frase"])

    def test_actualizar_estado_cambia_etiquetas_nombres_y_pausa(self):
        self.gestor.transmitiendo = True
        self.gestor.grabando = True
        self.dialogo._actualizar(Evento())
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_DETENER_TRANSMISION)
        self.assertEqual(self.dialogo.btn_transmitir.GetName(), "Detener la transmisión")
        self.assertEqual(self.dialogo.btn_grabar.GetLabel(),
                         gui_transmision._ETIQUETA_DETENER_GRABACION)
        self.assertEqual(self.dialogo.btn_grabar.GetName(), "Detener la grabación")
        self.assertTrue(self.dialogo.btn_pausar_grabacion.IsEnabled())
        self.assertIn("Transmitiendo desde hace 1 min", self.anuncios)
        self.assertIn("Grabando, 00:01:02", self.anuncios)

    def test_pausa_esta_deshabilitada_si_no_se_esta_grabando(self):
        self.assertFalse(self.dialogo.btn_pausar_grabacion.IsEnabled())

    def test_organizar_y_actualizar_van_juntos_en_una_fila_partible(self):
        botones = (self.dialogo.btn_organizar, self.dialogo.btn_actualizar)
        fila = botones[0].GetContainingSizer()
        self.assertIsInstance(fila, wx.WrapSizer)
        self.assertIs(botones[1].GetContainingSizer(), fila)
        self.assertEqual([hijo.GetWindow() for hijo in fila.GetChildren()],
                         list(botones))

    def test_destino_va_antes_de_transmitir_en_las_acciones(self):
        acciones = self.dialogo._acciones
        self.assertLess(acciones.index(self.dialogo.btn_grabar),
                        acciones.index(self.dialogo.cho_escena))
        self.assertLess(acciones.index(self.dialogo.btn_actualizar),
                        acciones.index(self.dialogo.chk_panel_chat))

    def test_destino_va_antes_de_transmitir_en_el_sizer(self):
        sizer = self.dialogo._zona_desplazable.GetSizer()
        cajas = [elemento.GetSizer().GetStaticBox().GetLabel()
                 for elemento in sizer.GetChildren()
                 if elemento.GetSizer() is not None]
        self.assertEqual(cajas, ["Transmitir", "Escena",
                                "Panel de chat, solo YouTube"])
        exterior = self.dialogo.btn_cerrar.GetParent().GetSizer()
        ventanas = [elemento.GetWindow() for elemento in exterior.GetChildren()
                    if elemento.GetWindow() is not None]
        self.assertIs(ventanas[-1], self.dialogo.btn_cerrar)

    def _nombres_en_orden(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.Button,
                                 wx.CheckBox, wx.SpinCtrl)):
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres_en_orden(hijo))
        return nombres

    def test_orden_de_tab_en_el_orden_de_uso(self):
        self.assertEqual(self._nombres_en_orden(self.dialogo), [
            "Transmitir a", "Usuario de TikTok", "Preparar destino",
            "Transmitir", "Grabar", "Pausar grabación",
            "Escena", "Poner al aire", "Organizar escena…",
            "ActualizarEstado",
            "Panel de chat para transmitir", "Preparar panel",
            "Estado del panel", "CerrarTransmision",
        ])

    @staticmethod
    def _letra_de_atajo(etiqueta):
        posicion = etiqueta.find("&")
        if posicion < 0 or posicion + 1 >= len(etiqueta):
            return ""
        return etiqueta[posicion + 1].upper()

    def test_letras_de_atajo_unicas_y_ascii(self):
        letras = [self._letra_de_atajo(etiqueta)
                  for etiqueta in self._etiquetas_de_botones(self.dialogo)]
        letras = [letra for letra in letras if letra]
        self.assertEqual(len(letras), len(set(letras)), letras)
        for letra in letras:
            self.assertTrue(letra.isascii(), letra)
        self.assertEqual(
            self._letra_de_atajo(gui_transmision._ETIQUETA_DETENER_TRANSMISION),
            self._letra_de_atajo(gui_transmision._ETIQUETA_TRANSMITIR))
        self.assertEqual(
            self._letra_de_atajo(gui_transmision._ETIQUETA_DETENER_GRABACION),
            self._letra_de_atajo(gui_transmision._ETIQUETA_GRABAR))

    def _etiquetas_de_botones(self, ventana):
        etiquetas = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, wx.Button):
                etiquetas.append(hijo.GetLabel())
            etiquetas.extend(self._etiquetas_de_botones(hijo))
        return etiquetas

    def test_tres_secciones_con_sus_titulos(self):
        titulos = [hijo.GetLabel() for hijo in self._cajas(self.dialogo)]
        self.assertEqual(titulos, ["Transmitir", "Escena",
                                  "Panel de chat, solo YouTube"])

    def _cajas(self, ventana):
        cajas = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, wx.StaticBox):
                cajas.append(hijo)
            cajas.extend(self._cajas(hijo))
        return cajas

    def test_foco_inicial_en_transmitir_a(self):
        self.assertIs(self.dialogo.FindFocus(), self.dialogo.cho_destino)

    def test_controles_de_destino_tienen_nombres_y_opciones(self):
        self.assertEqual(self.dialogo.cho_destino.GetStrings(),
                         ["TikTok", "YouTube"])
        self.assertEqual(self.dialogo.cho_destino.GetName(), "Transmitir a")
        self.assertEqual(self.dialogo.btn_destino.GetName(), "Preparar destino")
        self.assertEqual(self.dialogo.btn_destino.GetLabel(), "Preparar desti&no")

    def test_destino_inicial_muestra_el_perfil_actual_si_es_un_destino(self):
        destruir(self.dialogo)
        self.gestor.perfil = "YouTube"
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, asegurar=_asegurar_sin_obs)
        self.anuncios.clear()
        self.assertEqual(self.dialogo.cho_destino.GetStringSelection(),
                         "YouTube")

    def test_destino_inicial_sin_seleccion_si_el_perfil_no_es_un_destino(self):
        destruir(self.dialogo)
        self.gestor.perfil = "N5000-Grabacion"
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, asegurar=_asegurar_sin_obs)
        self.anuncios.clear()
        self.assertEqual(self.dialogo.cho_destino.GetSelection(), wx.NOT_FOUND)

    def test_preparar_destino_sin_seleccion_solo_avisa(self):
        self.dialogo.cho_destino.SetSelection(wx.NOT_FOUND)
        self.dialogo.btn_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, self.dialogo.btn_destino.GetId()))
        self.assertEqual(
            self.anuncios,
            ["Elige primero a dónde transmitir, en Transmitir a."])
        self.assertNotIn("preparar_destino",
                         [llamada[0] for llamada in self.gestor.llamadas])

    def test_elegir_en_el_desplegable_no_prepara_nada(self):
        self.gestor.preparar_destino = mock.Mock()
        self.dialogo.cho_destino.SetStringSelection("TikTok")
        evento = wx.CommandEvent(wx.EVT_CHOICE.typeId,
                                 self.dialogo.cho_destino.GetId())
        self.dialogo.cho_destino.GetEventHandler().ProcessEvent(evento)
        self.gestor.preparar_destino.assert_not_called()

    def test_cambiar_la_lista_guarda_el_destino_sin_anunciar(self):
        guardar = mock.Mock()
        self.dialogo._guardar_destino = guardar
        self.dialogo.cho_destino.SetStringSelection("YouTube")
        self.dialogo.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            self.dialogo.cho_destino.GetId()))
        guardar.assert_called_once_with("YouTube")
        self.assertEqual(self.anuncios, [])

    def test_boton_prepara_con_el_destino_elegido_y_enfoca_transmitir(self):
        self.dialogo.cho_destino.SetStringSelection("TikTok")
        with mock.patch.object(self.dialogo.btn_transmitir, "SetFocus") as foco:
            self.dialogo.btn_destino.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_BUTTON.typeId, self.dialogo.btn_destino.GetId()))
        self.assertIn(("preparar_destino", "TikTok"), self.gestor.llamadas)
        self.assertEqual(
            self.anuncios,
            ["Preparando OBS para TikTok. Puede tardar unos segundos.",
             "OBS preparado para transmitir a TikTok. "
             "Formato vertical, 720 por 1280."])
        foco.assert_called_once_with()
        self.assertEqual(self.dialogo.cho_destino.GetStringSelection(),
                         "TikTok")

    def _dialogo_con_supervisor(self, usuario=""):
        supervisar = mock.Mock(return_value=False)
        guardar = mock.Mock()
        destruir(self.dialogo)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, supervisar=supervisar,
            guardar_usuario=guardar, usuario_tiktok=usuario,
            asegurar=_asegurar_sin_obs)
        self.anuncios.clear()
        return supervisar, guardar

    def _dialogo_falso(self, creados, resultado):
        def fabrica(*args, **kwargs):
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = resultado
            creados.append((args, kwargs, dialogo))
            return dialogo
        return fabrica

    def _pulsar_transmitir(self):
        self.dialogo.btn_transmitir.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId,
                            self.dialogo.btn_transmitir.GetId()))

    def test_campo_usuario_va_entre_destino_y_preparar(self):
        dialogo = self.dialogo
        self.assertEqual(dialogo.txt_usuario_tiktok.GetName(),
                         "Usuario de TikTok")
        acciones = dialogo._acciones
        indice = acciones.index(dialogo.cho_destino)
        self.assertIs(acciones[indice + 1], dialogo.txt_usuario_tiktok)
        self.assertIs(acciones[indice + 2], dialogo.btn_destino)
        sizer = dialogo._sizer_transmitir
        # Cada campo va en su fila horizontal y los botones de la sección
        # van juntos en una fila partible, en el mismo orden de creación.
        filas = [elemento.GetSizer()
                 for elemento in sizer.GetChildren()]
        self.assertEqual(len(filas), 3)
        for fila, control in ((filas[0], dialogo.cho_destino),
                              (filas[1], dialogo.txt_usuario_tiktok)):
            with self.subTest(control=control.GetName()):
                ventanas = [hijo.GetWindow()
                            for hijo in fila.GetChildren()]
                self.assertIs(ventanas[1], control)
        botones = (dialogo.btn_destino, dialogo.btn_transmitir,
                   dialogo.btn_grabar, dialogo.btn_pausar_grabacion)
        self.assertIsInstance(filas[2], wx.WrapSizer)
        self.assertEqual([hijo.GetWindow()
                          for hijo in filas[2].GetChildren()],
                         list(botones))

    def test_cada_campo_tiene_su_rotulo_visible_antes(self):
        casos = [
            (self.dialogo.cho_destino, "Transmitir a:"),
            (self.dialogo.txt_usuario_tiktok, "Usuario de TikTok:"),
            (self.dialogo.cho_escena, "Escena:"),
            (self.dialogo.txt_estado, "Estado del panel:"),
        ]
        for control, esperado in casos:
            with self.subTest(control=control.GetName()):
                hijos = list(control.GetParent().GetChildren())
                indice = hijos.index(control)
                self.assertGreater(indice, 0)
                rotulo = hijos[indice - 1]
                self.assertIsInstance(rotulo, wx.StaticText)
                self.assertEqual(rotulo.GetLabel(), esperado)

    def test_estado_muestra_varias_lineas(self):
        self.assertGreaterEqual(
            self.dialogo.txt_estado.GetMinSize().GetHeight(), 110)

    def test_estado_del_panel_nombre_padre_y_orden(self):
        self.assertEqual(self.dialogo.txt_estado.GetName(), "Estado del panel")
        self.assertIs(self.dialogo.txt_estado.GetParent(),
                      self.dialogo.btn_preparar.GetParent())
        hijos = list(self.dialogo.btn_preparar.GetParent().GetChildren())
        self.assertEqual(hijos.index(self.dialogo.txt_estado),
                         hijos.index(self.dialogo.btn_preparar) + 2)
        rotulo = hijos[hijos.index(self.dialogo.btn_preparar) + 1]
        self.assertIsInstance(rotulo, wx.StaticText)
        self.assertEqual(rotulo.GetLabel(), "Estado del panel:")

    def test_estado_del_panel_sigue_siendo_lectura_multilinea(self):
        estilo = self.dialogo.txt_estado.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_READONLY)
        self.assertTrue(estilo & wx.TE_MULTILINE)




    def test_mostrar_estados_no_toca_el_estado_del_panel(self):
        self.dialogo.txt_estado.SetValue("La frase de preparación.")
        self.dialogo._mostrar_estados(self.gestor.estado_transmision(),
                                      self.gestor.estado_grabacion(),
                                      "Principal")
        self.assertEqual(self.dialogo.txt_estado.GetValue(),
                         "La frase de preparación.")

    def test_mostrar_estados_sigue_actualizando_los_botones(self):
        self.gestor.transmitiendo = True
        self.gestor.grabando = True
        self.dialogo._mostrar_estados(self.gestor.estado_transmision(),
                                      self.gestor.estado_grabacion(),
                                      "Principal")
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_DETENER_TRANSMISION)
        self.assertEqual(self.dialogo.btn_grabar.GetLabel(),
                         gui_transmision._ETIQUETA_DETENER_GRABACION)
        self.assertTrue(self.dialogo.btn_pausar_grabacion.IsEnabled())

    def test_contenido_en_zona_desplazable_y_cerrar_fuera(self):
        zona = self.dialogo._zona_desplazable
        self.assertIsInstance(zona, wx.ScrolledWindow)
        self.assertTrue(zona.GetWindowStyleFlag() & wx.VSCROLL)
        self.assertTrue(self._esta_dentro(self.dialogo.cho_destino, zona))
        self.assertFalse(self._esta_dentro(self.dialogo.btn_cerrar, zona))


    def _control_por_nombre(self, ventana, nombre):
        for hijo in ventana.GetChildren():
            if hijo.GetName() == nombre:
                return hijo
            encontrado = self._control_por_nombre(hijo, nombre)
            if encontrado is not None:
                return encontrado
        return None

    @staticmethod
    def _esta_dentro(control, antecesor):
        ventana = control.GetParent()
        while ventana is not None:
            if ventana is antecesor:
                return True
            ventana = ventana.GetParent()
        return False

    def test_campo_usuario_arranca_con_el_guardado(self):
        destruir(self.dialogo)
        dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, usuario_tiktok="amigo",
            asegurar=_asegurar_sin_obs)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.txt_usuario_tiktok.GetValue(), "amigo")

    def test_transmitir_tiktok_sin_usuario_avisa_y_enfoca(self):
        supervisar, _ = self._dialogo_con_supervisor()
        self.dialogo.cho_destino.SetStringSelection("TikTok")
        self.dialogo.txt_usuario_tiktok.SetValue("")
        with mock.patch.object(self.dialogo.txt_usuario_tiktok,
                               "SetFocus") as foco:
            self._pulsar_transmitir()
        self.assertEqual(
            self.anuncios,
            ["Escribe tu usuario de TikTok en Usuario de TikTok."])
        foco.assert_called_once_with()
        self.assertNotIn(mock.call("iniciar", "TikTok", mock.ANY),
                         supervisar.call_args_list)

    def test_transmitir_aceptar_inicia_y_guarda_el_usuario(self):
        supervisar, guardar = self._dialogo_con_supervisor()
        self.dialogo.cho_destino.SetStringSelection("TikTok")
        self.dialogo.txt_usuario_tiktok.SetValue("@usuario")
        creados = []
        with mock.patch.object(gui_transmision.wx, "MessageDialog",
                               self._dialogo_falso(creados, wx.ID_OK)):
            self._pulsar_transmitir()
        supervisar.assert_any_call("iniciar", "TikTok", "usuario")
        guardar.assert_called_once_with("usuario")
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_DETENER_TRANSMISION)
        self.assertEqual(self.dialogo.btn_transmitir.GetName(),
                         "Detener la transmisión")
        dialogo_falso = creados[0][2]
        dialogo_falso.SetOKCancelLabels.assert_called_once_with(
            "&Transmitir", "&Cancelar")

    def test_transmitir_cancelar_no_inicia(self):
        supervisar, guardar = self._dialogo_con_supervisor()
        self.dialogo.cho_destino.SetStringSelection("YouTube")
        creados = []
        with mock.patch.object(gui_transmision.wx, "MessageDialog",
                               self._dialogo_falso(creados, wx.ID_CANCEL)):
            self._pulsar_transmitir()
        self.assertNotIn(mock.call("iniciar", mock.ANY, mock.ANY),
                         supervisar.call_args_list)
        self.assertEqual(self.anuncios[-1], "No se transmitió.")
        guardar.assert_not_called()
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_TRANSMITIR)

    def test_revision_con_problemas_deja_cancelar_por_defecto(self):
        supervisar, _ = self._dialogo_con_supervisor()
        self.gestor.problemas_revision = ("La imagen está vacía.",)
        self.dialogo.cho_destino.SetStringSelection("YouTube")
        creados = []
        with mock.patch.object(gui_transmision.wx, "MessageDialog",
                               self._dialogo_falso(creados, wx.ID_CANCEL)):
            self._pulsar_transmitir()
        args, _, _ = creados[0]
        estilo = args[3]
        self.assertTrue(estilo & wx.CANCEL_DEFAULT)
        self.assertNotIn(mock.call("iniciar", mock.ANY, mock.ANY),
                         supervisar.call_args_list)

    def test_revision_sin_problemas_no_fuerza_cancelar(self):
        self._dialogo_con_supervisor()
        self.dialogo.cho_destino.SetStringSelection("YouTube")
        creados = []
        with mock.patch.object(gui_transmision.wx, "MessageDialog",
                               self._dialogo_falso(creados, wx.ID_CANCEL)):
            self._pulsar_transmitir()
        args, _, _ = creados[0]
        self.assertFalse(args[3] & wx.CANCEL_DEFAULT)

    def test_transmitir_con_supervisor_activo_detiene_sin_repetir_anuncio(self):
        supervisar, _ = self._dialogo_con_supervisor()
        supervisar.side_effect = lambda accion: accion == "activo"
        self.dialogo._mostrar_transmision(True)
        self.anuncios.clear()
        self._pulsar_transmitir()
        supervisar.assert_any_call("detener")
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_TRANSMITIR)
        self.assertNotIn("Transmisión detenida", self.anuncios)

    def test_transmitir_con_supervisor_deteniendo_avisa_y_no_toca_la_etiqueta(self):
        supervisar, _ = self._dialogo_con_supervisor()
        supervisar.side_effect = lambda accion: accion == "deteniendo"
        self.anuncios.clear()
        self._pulsar_transmitir()
        supervisar.assert_called_once_with("deteniendo")
        self.assertEqual(
            self.anuncios,
            ["Deteniendo la transmisión. Esperando a que OBS confirme."])
        self.assertEqual(self.dialogo.btn_transmitir.GetLabel(),
                         gui_transmision._ETIQUETA_TRANSMITIR)

    def test_transmitir_sin_supervisor_sigue_el_camino_viejo(self):
        self.dialogo.cho_destino.SetStringSelection("YouTube")
        self._pulsar_transmitir()
        self.assertIn(("alternar_transmision",), self.gestor.llamadas)
        self.assertEqual(self.anuncios[-1], "Transmisión iniciada")

    def test_transmitir_con_etiqueta_traducida_y_estado_activo_alterna(self):
        supervisar, _ = self._dialogo_con_supervisor()
        supervisar.side_effect = lambda accion: False
        self.dialogo._mostrar_transmision(True)
        self.dialogo.btn_transmitir.SetLabel("Stop streaming")
        self.gestor.revisar = mock.Mock()
        self._pulsar_transmitir()
        self.assertIn(("alternar_transmision",), self.gestor.llamadas)
        self.gestor.revisar.assert_not_called()


class TestCargaInicialAseguraObs(unittest.TestCase):
    # Sin ventana: se llama a _cargar_inicial como función sobre un objeto
    # falso, así no se crea ningún diálogo ni se toca OBS.

    def _falso(self, orden, asegurar):
        gestor = mock.Mock()
        gestor.conectar.side_effect = lambda: orden.append("conectar")
        gestor.escenas.return_value = ("Principal",)
        gestor.escena_al_aire.return_value = "Principal"
        gestor.fuentes.return_value = ("Chat en el vídeo",)
        gestor.instantanea.return_value = mock.sentinel.snap
        gestor.transformacion.return_value = {}
        gestor.estado_transmision.return_value = {}
        gestor.estado_grabacion.return_value = {}
        gestor.perfil_actual.return_value = ""
        gestor.ventanas.return_value = ((), "")
        return types.SimpleNamespace(_gestor=gestor, _asegurar=asegurar)

    def test_asegurar_se_llama_antes_de_conectar(self):
        orden = []

        def asegurar(probar, **kwargs):
            orden.append("asegurar")
            return False

        falso = self._falso(orden, asegurar)
        gui_transmision.TransmisionDialog._cargar_inicial(falso)
        self.assertEqual(orden[:2], ["asegurar", "conectar"])
        falso._gestor.conectar.assert_called_once_with()

    def test_sin_obs_instalado_no_conecta_y_deja_salir_el_error(self):
        orden = []

        def asegurar(probar, **kwargs):
            orden.append("asegurar")
            raise obs_lanzador.ObsNoInstalado("OBS no está instalado")

        falso = self._falso(orden, asegurar)
        with self.assertRaises(obs_lanzador.ObsNoInstalado):
            gui_transmision.TransmisionDialog._cargar_inicial(falso)
        self.assertEqual(orden, ["asegurar"])
        falso._gestor.conectar.assert_not_called()




class TestPanelSinConsultasDeFuente(unittest.TestCase):
    # Sin ventana: el panel ya no pide instantánea, ventanas ni descripción.

    def test_leer_estados_pide_solo_lo_del_panel(self):
        gestor = mock.Mock()
        gestor.escena_al_aire.return_value = "Principal"
        gestor.estado_transmision.return_value = mock.sentinel.transmision
        gestor.estado_grabacion.return_value = mock.sentinel.grabacion
        falso = types.SimpleNamespace(_gestor=gestor)
        datos = gui_transmision.TransmisionDialog._leer_estados(falso)
        self.assertEqual(datos, ("Principal", mock.sentinel.transmision,
                                 mock.sentinel.grabacion))
        gestor.instantanea.assert_not_called()
        gestor.ventanas.assert_not_called()
        gestor.descripcion_escena.assert_not_called()

    def test_estados_leidos_muestra_y_anuncia_sin_la_descripcion(self):
        falso = mock.Mock()
        gui_transmision.TransmisionDialog._estados_leidos(
            falso, ("Principal", mock.sentinel.transmision,
                    mock.sentinel.grabacion))
        falso._mostrar_estados.assert_called_once_with(
            mock.sentinel.transmision, mock.sentinel.grabacion, "Principal")
        falso._anunciar_estados.assert_called_once_with(
            mock.sentinel.transmision, mock.sentinel.grabacion, "Principal")
        falso._mostrar_vista.assert_not_called()

    def test_inicial_cargada_escribe_la_frase_sin_instantanea(self):
        datos = types.SimpleNamespace(
            escenas=("Principal",), escena="Principal",
            al_aire=mock.sentinel.al_aire,
            fuentes=("Chat en el vídeo",),
            transmision=mock.sentinel.transmision,
            grabacion=mock.sentinel.grabacion, perfil="")
        falso = mock.Mock()
        with mock.patch.object(gui_transmision.overlay_servidor,
                               "esta_encendido", return_value=False),                 mock.patch.object(gui_transmision.overlay_servidor,
                                  "puerto_actual", return_value=None),                 mock.patch.object(gui_transmision, "anunciar"):
            gui_transmision.TransmisionDialog._inicial_cargada(falso, datos)
        falso.txt_estado.SetValue.assert_called_once()
        falso._poblar_inicial.assert_called_once_with(datos)


class TestConfirmarTransmisionSinVentana(unittest.TestCase):
    # Sin ventana: el MessageDialog va simulado, así no se abre nada.

    def _revision(self, problemas=()):
        from bellbird.obs import obs_prevuelo
        return obs_prevuelo.Revision(
            "TikTok", "TikTok", "TikTok", 720, 1280, "Principal",
            (), (), None, tuple(problemas))

    def _confirmar(self, revision, resultado):
        creados = []

        def fabrica(*args, **kwargs):
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = resultado
            creados.append((args, dialogo))
            return dialogo

        with mock.patch.object(modulo_confirmar.wx, "MessageDialog", fabrica):
            acepta = modulo_confirmar.confirmar_transmision(
                mock.sentinel.padre, revision)
        return acepta, creados

    def test_aceptar_devuelve_verdadero_con_mismo_texto_y_etiquetas(self):
        from bellbird.obs import obs_prevuelo
        revision = self._revision()
        acepta, creados = self._confirmar(revision, wx.ID_OK)
        self.assertTrue(acepta)
        args, dialogo = creados[0]
        self.assertEqual(args[0], mock.sentinel.padre)
        self.assertEqual(args[1], obs_prevuelo.frase_revision(revision))
        self.assertEqual(args[2], "Antes de transmitir")
        self.assertEqual(args[3], wx.OK | wx.CANCEL)
        dialogo.SetOKCancelLabels.assert_called_once_with(
            "&Transmitir", "&Cancelar")
        dialogo.Destroy.assert_called_once_with()

    def test_cancelar_devuelve_falso(self):
        acepta, creados = self._confirmar(self._revision(), wx.ID_CANCEL)
        self.assertFalse(acepta)
        creados[0][1].Destroy.assert_called_once_with()

    def test_con_problemas_cancelar_queda_por_defecto(self):
        _acepta, creados = self._confirmar(
            self._revision(("La imagen está vacía.",)), wx.ID_CANCEL)
        self.assertEqual(creados[0][0][3],
                         wx.OK | wx.CANCEL | wx.CANCEL_DEFAULT)


class TestGuardarDestinoSinVentana(unittest.TestCase):
    # Sin ventana: los métodos del diálogo se llaman sin ligar sobre un
    # objeto falso, así no se crea ningún control.

    def _falso(self, **extras):
        falso = mock.Mock()
        falso._guardar_destino = mock.Mock()
        falso._supervisar = mock.Mock()
        for clave, valor in extras.items():
            setattr(falso, clave, valor)
        falso._recordar_destino = lambda destino: (
            gui_transmision.TransmisionDialog._recordar_destino(
                falso, destino))
        return falso

    def test_al_confirmar_guarda_el_destino_e_inicia(self):
        falso = self._falso()
        revision = mock.sentinel.revision
        with mock.patch.object(gui_transmision, "confirmar_transmision",
                               return_value=True) as confirmar:
            gui_transmision.TransmisionDialog._revision_lista(
                falso, revision, "TikTok", "usuario")
        confirmar.assert_called_once_with(falso, revision)
        falso._guardar_destino.assert_called_once_with("TikTok")
        falso._supervisar.assert_called_once_with(
            "iniciar", "TikTok", "usuario")

    def test_al_cancelar_no_guarda_ni_inicia(self):
        falso = self._falso()
        with mock.patch.object(gui_transmision, "confirmar_transmision",
                               return_value=False), \
                mock.patch.object(gui_transmision, "anunciar") as anunciar:
            gui_transmision.TransmisionDialog._revision_lista(
                falso, mock.sentinel.revision, "TikTok", "usuario")
        falso._guardar_destino.assert_not_called()
        falso._supervisar.assert_not_called()
        anunciar.assert_called_once_with("No se transmitió.")

    def test_si_guardar_falla_igual_inicia(self):
        falso = self._falso()
        falso._guardar_destino.side_effect = RuntimeError("disco lleno")
        with mock.patch.object(gui_transmision, "confirmar_transmision",
                               return_value=True):
            gui_transmision.TransmisionDialog._revision_lista(
                falso, mock.sentinel.revision, "YouTube", "")
        falso._supervisar.assert_called_once_with("iniciar", "YouTube", "")

    def test_al_preparar_destino_lo_guarda_y_anuncia_listo(self):
        from bellbird.obs import obs_destinos
        falso = self._falso()
        resultado = {"destino": "TikTok", "perfil": "TikTok",
                     "coleccion": "TikTok", "ancho": 720, "alto": 1280}
        with mock.patch.object(gui_transmision, "anunciar") as anunciar:
            gui_transmision.TransmisionDialog._destino_preparado(
                falso, (resultado, mock.sentinel.inicial, "TikTok"))
        falso._poblar_inicial.assert_called_once_with(mock.sentinel.inicial)
        falso._guardar_destino.assert_called_once_with("TikTok")
        anunciar.assert_called_once_with(
            obs_destinos.frase_destino_listo(resultado))
        falso.btn_transmitir.SetFocus.assert_called_once_with()

    def test_preparar_en_hilo_devuelve_resultado_inicial_y_destino(self):
        gestor = mock.Mock()
        gestor.preparar_destino.return_value = mock.sentinel.resultado
        falso = types.SimpleNamespace(
            _gestor=gestor, _cargar_inicial=mock.Mock(
                return_value=mock.sentinel.inicial))
        datos = gui_transmision.TransmisionDialog._preparar_destino_en_hilo(
            falso, "TikTok")
        gestor.preparar_destino.assert_called_once_with("TikTok")
        self.assertEqual(datos, (mock.sentinel.resultado,
                                 mock.sentinel.inicial, "TikTok"))


class TestConsultasPasanCadaCampoASuLugar(unittest.TestCase):
    # Sin ventana: los métodos se llaman sobre un objeto falso, así no se
    # crea ningún control ni hace falta wx.App. Cada campo lleva un valor
    # distinto para que un cruce de argumentos falle.

    def _inicial(self):
        return consultas_transmision.CargaInicial(
            escenas=("Principal", "Juego"), escena="Principal",
            al_aire=mock.sentinel.al_aire,
            fuentes=("Cámara", "Chat en el vídeo"),
            transmision=mock.sentinel.transmision,
            grabacion=mock.sentinel.grabacion, perfil="TikTok")

    def test_poblar_inicial_reparte_cada_campo(self):
        falso = mock.Mock()
        datos = self._inicial()
        gui_transmision.TransmisionDialog._poblar_inicial(falso, datos)
        falso.cho_escena.Set.assert_called_once_with(["Principal", "Juego"])
        falso.cho_escena.SetStringSelection.assert_called_once_with("Principal")
        falso._mostrar_estados.assert_called_once_with(
            mock.sentinel.transmision, mock.sentinel.grabacion,
            mock.sentinel.al_aire)

    def test_inicial_cargada_anuncia_los_estados_en_orden(self):
        falso = mock.Mock()
        datos = self._inicial()
        with mock.patch.object(gui_transmision, "anunciar"), \
                mock.patch.object(gui_transmision.overlay_servidor,
                                  "esta_encendido", return_value=False), \
                mock.patch.object(gui_transmision.overlay_servidor,
                                  "puerto_actual", return_value=None):
            gui_transmision.TransmisionDialog._inicial_cargada(falso, datos)
        falso._poblar_inicial.assert_called_once_with(datos)
        falso.txt_estado.SetValue.assert_called_once()
        falso._anunciar_estados.assert_called_once_with(
            mock.sentinel.transmision, mock.sentinel.grabacion,
            mock.sentinel.al_aire)



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


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestCampoUsuarioSegunDestino(unittest.TestCase):
    # El campo de usuario solo sirve con TikTok: con otro destino o sin
    # selección queda deshabilitado y fuera del Tab.

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter", lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar", lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar", lambda *args, **kwargs: None),
            mock.patch.object(gui_transmision.sound_player, "reproducir"),
        ]
        for parche in self.parches: parche.start()
        self.gestor = GestorFalso()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)
        for parche in reversed(self.parches): parche.stop()

    def _dialogo_con_perfil(self, perfil):
        self.gestor.perfil = perfil
        self.dialogo = gui_transmision.TransmisionDialog(
            None, self.gestor, asegurar=_asegurar_sin_obs)
        return self.dialogo

    def _elegir(self, dialogo, destino):
        dialogo.cho_destino.SetStringSelection(destino)
        dialogo.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            dialogo.cho_destino.GetId()))

    def test_abrir_con_tiktok_guardado_deja_el_campo_habilitado(self):
        dialogo = self._dialogo_con_perfil("TikTok")
        self.assertEqual(dialogo.cho_destino.GetStringSelection(), "TikTok")
        self.assertTrue(dialogo.txt_usuario_tiktok.IsEnabled())

    def test_abrir_con_youtube_deja_el_campo_deshabilitado(self):
        dialogo = self._dialogo_con_perfil("YouTube")
        self.assertEqual(dialogo.cho_destino.GetStringSelection(), "YouTube")
        self.assertFalse(dialogo.txt_usuario_tiktok.IsEnabled())

    def test_abrir_sin_destino_deja_el_campo_deshabilitado(self):
        dialogo = self._dialogo_con_perfil("N5000-Grabacion")
        self.assertEqual(dialogo.cho_destino.GetSelection(), wx.NOT_FOUND)
        self.assertFalse(dialogo.txt_usuario_tiktok.IsEnabled())

    def test_cambiar_destino_reevalua_el_campo(self):
        dialogo = self._dialogo_con_perfil("YouTube")
        self.assertFalse(dialogo.txt_usuario_tiktok.IsEnabled())
        self._elegir(dialogo, "TikTok")
        self.assertTrue(dialogo.txt_usuario_tiktok.IsEnabled())
        self._elegir(dialogo, "YouTube")
        self.assertFalse(dialogo.txt_usuario_tiktok.IsEnabled())

    def test_campo_usuario_tiene_el_rotulo_y_el_nombre_nuevo(self):
        dialogo = self._dialogo_con_perfil("")
        self.assertEqual(dialogo.txt_usuario_tiktok.GetName(),
                         "Usuario de TikTok")
        hijos = list(dialogo.txt_usuario_tiktok.GetParent().GetChildren())
        indice = hijos.index(dialogo.txt_usuario_tiktok)
        rotulo = hijos[indice - 1]
        self.assertIsInstance(rotulo, wx.StaticText)
        self.assertEqual(rotulo.GetLabel(), "Usuario de TikTok:")


class TestTablaPosicionesSinVentana(unittest.TestCase):
    # Sin ventana: la tabla vive en el módulo, así no se crea ningún control.

    def test_tabla_cubre_los_anclajes_con_el_texto_de_hoy(self):
        etiquetas = {
            "superior-izquierda": "Arriba a la izquierda",
            "superior-centro": "Arriba al centro",
            "superior-derecha": "Arriba a la derecha",
            "centro-izquierda": "Centro a la izquierda",
            "centro": "Centro",
            "centro-derecha": "Centro a la derecha",
            "inferior-izquierda": "Abajo a la izquierda",
            "inferior-centro": "Abajo al centro",
            "inferior-derecha": "Abajo a la derecha",
        }
        self.assertEqual(set(etiquetas), set(obs_disposicion.ANCLAJES))
        for nombre, etiqueta in etiquetas.items():
            self.assertEqual(obs_disposicion.etiqueta_anclaje(nombre), etiqueta)


# Los nombres de escenas, fuentes y ventanas son datos del gestor de
# prueba y van como propios. La nota de `bellbird/obs/obs_estado.py`
# (NOTA_TRANSMISION) ya sale marcada porque este diálogo la traduce. La
# comparación es exacta en los dos sentidos: falla si aparece un texto
# nuevo sin envolver y si un pendiente ya no está en el recorrido.
PENDIENTES_TRANSMISION = ()

PROPIOS_TRANSMISION = (
    "TikTok", "YouTube",
    "Principal", "Juego",
    "Cámara", "Chat en el vídeo",
    "Champions, de juego.exe", "Charla, de otro.exe",
)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoTransmisionVentana(unittest.TestCase):
    """Pseudotraducción del diálogo Transmisión.

    Abre ventanas. Construye el diálogo con la pseudotraducción y exige que ningún texto
    visible propio quede sin envolver.
    """

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter", lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar", lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar", lambda *args, **kwargs: None),
            mock.patch.object(gui_transmision.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
        for parche in reversed(self.parches):
            self.addCleanup(parche.stop)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = gui_transmision.TransmisionDialog(
                None, GestorFalso(), asegurar=_asegurar_sin_obs)
            sin_marcar = textos_sin_marcar(
                dialogo, propios=PROPIOS_TRANSMISION)
        self.addCleanup(destruir, dialogo)
        # Wrap parte la nota en varias líneas: se comparan los espacios normalizados.
        normalizados = sorted(" ".join(texto.split()) for texto in sin_marcar)
        esperados = sorted(" ".join(texto.split()) for texto in PENDIENTES_TRANSMISION)
        self.assertEqual(normalizados, esperados)


class TestPseudoConfirmarTransmision(unittest.TestCase):
    # Sin ventana: el MessageDialog va simulado, así no se abre nada.

    def _revision(self, problemas=()):
        from bellbird.obs import obs_prevuelo
        return obs_prevuelo.Revision(
            "TikTok", "TikTok", "TikTok", 720, 1280, "Principal",
            (), (), None, tuple(problemas))

    def test_titulo_mensaje_y_botones_pasan_por_gettext(self):
        # El mensaje lo arma `bellbird/obs/obs_prevuelo.py` (frase_revision),
        # con los datos de ejemplo de la revisión.
        from bellbird.obs import obs_prevuelo
        revision = self._revision()
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
            modulo_confirmar.confirmar_transmision(
                mock.sentinel.padre, revision)
        self.assertEqual(captado["mensaje"], esperada)
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        creados[0].SetOKCancelLabels.assert_called_once()
        for etiqueta in creados[0].SetOKCancelLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"))


if __name__ == "__main__":
    unittest.main()
