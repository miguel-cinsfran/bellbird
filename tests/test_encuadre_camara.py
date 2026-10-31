"""Pruebas del encuadre de cámara en la ventana principal.

Sin wx.App ni ventanas: el marco es un doble, OBS y el detector son
dobles, y `wx.CallAfter` se reemplaza por un registro para ejecutar sus
vueltas a mano. Solo la prueba real usa el detector de verdad, sobre
`tests/datos/rostro.jpg`.
"""

import unittest
from pathlib import Path
from unittest import mock

from bellbird.camera import detector_rostros, encuadre
from bellbird.camera.detector_rostros import Cuadro
from bellbird.capture import estado_sesion
from bellbird.core import atajos
from bellbird.obs.obs_camara import CamaraNoEncontrada, CamaraObs
from bellbird.obs.obs_captura_ia import CapturaFallida
from bellbird.ui import encuadre_camara


def _rostro_centrado():
    return encuadre.Rostro(x=120.0, y=60.0, ancho=80.0, alto=100.0,
                           ojo_izquierda=(140.0, 90.0),
                           ojo_derecha=(180.0, 90.0),
                           nariz=(160.0, 110.0), confianza=0.99)


def _cuadro_con(rostros, huella=b"huella"):
    return Cuadro(rostros=tuple(rostros), ancho=320, alto=240,
                  luz_rostro=120.0, luz_fondo=90.0, huella=huella)


class MarcoFalso:
    """Doble del marco principal: config, casilla y bandera de vivo."""

    def __init__(self, config=None):
        self._config = dict(config or {})
        self._alive = True
        self.mi_avisos_encuadre = mock.Mock()

    def IsBeingDeleted(self):
        return False


def _nuevo_marco(**config):
    base = {"avisar_encuadre": False, "camara_fuente": "",
            "camara_invertir": False}
    base.update(config)
    return MarcoFalso(base)


def _parche_obs(testigo, camara=None, falla=None):
    """OBS abierto con una cámara, o `falla` al buscarla."""
    testigo.patch_obj(encuadre_camara.obs_activacion,
                      "obs_esta_en_ejecucion", return_value=True)
    cliente = mock.Mock()
    testigo.patch_obj(encuadre_camara.obs_cliente, "ClienteObs",
                      return_value=cliente).start()
    if falla is not None:
        testigo.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                          side_effect=falla).start()
    else:
        testigo.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                          return_value=camara).start()
    testigo.patch_obj(encuadre_camara.obs_camara, "capturar_cuadro",
                      return_value=b"cuadro").start()
    return cliente


class _Testigo(unittest.TestCase):
    """Atajos para parchar los bordes del módulo bajo prueba."""

    def parchear_modulo(self, nombre, **kwargs):
        parche = mock.patch.object(encuadre_camara, nombre, **kwargs)
        self.addCleanup(parche.stop)
        return parche.start()

    def patch_obj(self, objetivo, nombre, **kwargs):
        parche = mock.patch.object(objetivo, nombre, **kwargs)
        self.addCleanup(parche.stop)
        return parche.start()

    def parchear_wx(self):
        llamadas = []

        def _callafter(funcion, *args):
            llamadas.append((funcion, args))

        falso_wx = mock.Mock()
        falso_wx.CallAfter.side_effect = _callafter
        self.parchear_modulo("wx", new=falso_wx)
        return llamadas

    def correr_llamadas(self, llamadas):
        for funcion, args in llamadas:
            funcion(*args)

    def inst(self, marco):
        encuadre_camara._INSTANCIAS.pop(id(marco), None)
        self.addCleanup(encuadre_camara._INSTANCIAS.pop, id(marco), None)
        return encuadre_camara._instancia_para(marco)


class TestAnunciarEncuadre(_Testigo):

    def _hilo_directo(self):
        fabrica = mock.Mock()

        def _crear(target, nombre, **kwargs):
            hilo = mock.Mock()
            hilo.start.side_effect = lambda: target()
            fabrica.return_value = hilo
            return hilo

        fabrica.side_effect = _crear
        return self.patch_obj(encuadre_camara.diagnostico, "crear_hilo",
                              new=fabrica)

    def _dobles_captura(self, frase="Rostro centrado."):
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs")
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       return_value=CamaraObs("Cam", False))
        self.patch_obj(encuadre_camara.obs_camara, "capturar_cuadro",
                       return_value=b"cuadro")
        self.patch_obj(encuadre_camara, "DetectorRostros")
        self.patch_obj(encuadre_camara.encuadre, "analizar",
                       return_value=encuadre.Encuadre(cantidad=1, problemas=()))
        self.patch_obj(encuadre_camara.encuadre, "frase", return_value=frase)
        return frase

    def test_con_camara_anuncia_la_frase(self):
        marco = _nuevo_marco()
        inst = self.inst(marco)
        self._dobles_captura(frase="Rostro centrado.")
        anunciar = self.parchear_modulo("anunciar")
        llamadas = self.parchear_wx()
        self._hilo_directo()
        encuadre_camara.anunciar_encuadre(marco)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("Rostro centrado.")
        self.assertFalse(inst._en_curso)

    def test_sin_detector_dice_que_no_esta_instalado(self):
        marco = _nuevo_marco()
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=False)
        anunciar = self.parchear_modulo("anunciar")
        crear = self.patch_obj(encuadre_camara.diagnostico, "crear_hilo")
        encuadre_camara.anunciar_encuadre(marco)
        anunciar.assert_called_once_with(
            "El detector de rostros no está instalado.")
        crear.assert_not_called()

    def test_con_obs_cerrado_lo_dice(self):
        marco = _nuevo_marco()
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=False)
        anunciar = self.parchear_modulo("anunciar")
        crear = self.patch_obj(encuadre_camara.diagnostico, "crear_hilo")
        encuadre_camara.anunciar_encuadre(marco)
        anunciar.assert_called_once_with("OBS no está abierto.")
        crear.assert_not_called()

    def test_sin_camara_anuncia_su_texto(self):
        marco = _nuevo_marco()
        self.inst(marco)
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs")
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       side_effect=CamaraNoEncontrada(
                           "No hay ninguna cámara en OBS."))
        anunciar = self.parchear_modulo("anunciar")
        llamadas = self.parchear_wx()
        self._hilo_directo()
        encuadre_camara.anunciar_encuadre(marco)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("No hay ninguna cámara en OBS.")

    def test_fallo_de_captura_anuncia_su_texto(self):
        marco = _nuevo_marco()
        self.inst(marco)
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs")
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       return_value=CamaraObs("Cam", False))
        self.patch_obj(encuadre_camara.obs_camara, "capturar_cuadro",
                       side_effect=CapturaFallida("No se pudo capturar Cam."))
        anunciar = self.parchear_modulo("anunciar")
        llamadas = self.parchear_wx()
        self._hilo_directo()
        encuadre_camara.anunciar_encuadre(marco)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("No se pudo capturar Cam.")

    def test_otro_fallo_de_obs_dice_el_fallo_traducido(self):
        marco = _nuevo_marco()
        self.inst(marco)
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs",
                       side_effect=RuntimeError("se cayó el socket"))
        self.patch_obj(encuadre_camara.obs_cliente, "mensaje_de_fallo_obs",
                       return_value="Fallo traducido de OBS.")
        anunciar = self.parchear_modulo("anunciar")
        llamadas = self.parchear_wx()
        self._hilo_directo()
        encuadre_camara.anunciar_encuadre(marco)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("Fallo traducido de OBS.")

    def test_dos_pulsaciones_lanzan_una_sola_consulta(self):
        marco = _nuevo_marco()
        self.inst(marco)
        self.patch_obj(encuadre_camara.detector_rostros, "disponible",
                       return_value=True)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        crear = self.patch_obj(encuadre_camara.diagnostico, "crear_hilo")
        encuadre_camara.anunciar_encuadre(marco)
        encuadre_camara.anunciar_encuadre(marco)
        self.assertEqual(crear.call_count, 1)


class TestEspejo(_Testigo):

    def _espejo_usado(self, espejo_camara, invertir):
        marco = _nuevo_marco(camara_invertir=invertir)
        inst = self.inst(marco)
        inst._detector = mock.Mock()
        inst._detector.analizar.return_value = _cuadro_con(
            [_rostro_centrado()], b"espejo")
        _parche_obs(self, camara=CamaraObs("Cam", espejo_camara))
        with mock.patch.object(encuadre_camara.encuadre, "analizar",
                               return_value=encuadre.Encuadre(
                                   cantidad=0, problemas=("sin_rostro",))
                               ) as analizar:
            encuadre_camara._paso(inst, 0.0)
        return analizar.call_args.kwargs["espejo"]

    def test_sin_espejo_ni_inversion_no_invierte(self):
        self.assertFalse(self._espejo_usado(False, False))

    def test_solo_espejo_invierte(self):
        self.assertTrue(self._espejo_usado(True, False))

    def test_solo_inversion_invierte(self):
        self.assertTrue(self._espejo_usado(False, True))

    def test_espejo_con_inversion_no_invierte(self):
        self.assertFalse(self._espejo_usado(True, True))


class TestVigilancia(_Testigo):

    def _inst_con_gris(self, marco):
        inst = self.inst(marco)
        inst._detector = mock.Mock()
        inst._detector.analizar.return_value = _cuadro_con([], b"gris")
        _parche_obs(self, camara=CamaraObs("Cam", False))
        return inst

    def test_fuera_anuncia_y_suena_encuadre_fuera(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self._inst_con_gris(marco)
        anunciar = self.parchear_modulo("anunciar")
        suena = self.parchear_modulo("reproducir")
        llamadas = self.parchear_wx()
        espera = None
        for ahora in (0.0, 1.0, 2.0, 3.0):
            espera = encuadre_camara._paso(inst, ahora)
        self.assertEqual(espera, encuadre_camara.INTERVALO_VUELTA)
        self.assertTrue(llamadas)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("Ningún rostro.")
        suena.assert_called_once_with("encuadre_fuera")

    def test_dentro_tras_fuera_suena_encuadre_dentro(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self._inst_con_gris(marco)
        self.parchear_modulo("anunciar")
        suena = self.parchear_modulo("reproducir")
        llamadas = self.parchear_wx()
        for ahora in (0.0, 1.0, 2.0, 3.0):
            encuadre_camara._paso(inst, ahora)
        inst._detector.analizar.return_value = _cuadro_con(
            [_rostro_centrado()], b"rostro")
        llamadas.clear()
        espera = None
        for ahora in (4.0, 5.0, 5.5):
            espera = encuadre_camara._paso(inst, ahora)
        self.assertEqual(espera, encuadre_camara.INTERVALO_VUELTA)
        self.correr_llamadas(llamadas)
        suena.assert_called_with("encuadre_dentro")

    def test_sin_camara_nada_y_vigia_reiniciado(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs")
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       side_effect=CamaraNoEncontrada(
                           "La cámara de OBS no está en la escena al aire."))
        anunciar = self.parchear_modulo("anunciar")
        suena = self.parchear_modulo("reproducir")
        llamadas = self.parchear_wx()
        espera = encuadre_camara._paso(inst, 0.0)
        self.assertEqual(espera, encuadre_camara.ESPERA_TRAS_FALLO)
        self.assertEqual(llamadas, [])
        anunciar.assert_not_called()
        suena.assert_not_called()
        self.assertEqual(inst._vigia._anunciado, "dentro")
        self.assertEqual(inst._ultima_frase,
                         "La cámara de OBS no está en la escena al aire.")

    def test_con_obs_cerrado_guarda_su_texto_y_calla(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=False)
        anunciar = self.parchear_modulo("anunciar")
        llamadas = self.parchear_wx()
        espera = encuadre_camara._paso(inst, 0.0)
        self.assertEqual(espera, encuadre_camara.ESPERA_TRAS_FALLO)
        self.assertEqual(llamadas, [])
        anunciar.assert_not_called()
        self.assertEqual(inst._ultima_frase, "OBS no está abierto.")


class TestAlternarAvisos(_Testigo):

    def test_activar_guarda_marca_anuncia_y_arranca(self):
        marco = _nuevo_marco(avisar_encuadre=False)
        anunciar = self.parchear_modulo("anunciar")
        sincronizar = self.parchear_modulo("sincronizar")
        import bellbird.ui.gui as _gui
        with mock.patch.object(_gui, "guardar_opcion") as guardar, \
                mock.patch.object(_gui, "RUTA_CONFIG",
                                  Path("config.ini")):
            encuadre_camara.alternar_avisos(marco)
            guardar.assert_called_once_with(
                Path("config.ini"), "transmision", "avisar_encuadre", "true")
        self.assertTrue(marco._config["avisar_encuadre"])
        marco.mi_avisos_encuadre.Check.assert_called_once_with(True)
        anunciar.assert_called_once_with("Avisos de encuadre activados")
        sincronizar.assert_called_once_with(marco)

    def test_desactivar_guarda_marca_anuncia_y_detiene(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        anunciar = self.parchear_modulo("anunciar")
        sincronizar = self.parchear_modulo("sincronizar")
        import bellbird.ui.gui as _gui
        with mock.patch.object(_gui, "guardar_opcion") as guardar, \
                mock.patch.object(_gui, "RUTA_CONFIG",
                                  Path("config.ini")):
            encuadre_camara.alternar_avisos(marco)
            guardar.assert_called_once_with(
                Path("config.ini"), "transmision", "avisar_encuadre", "false")
        self.assertFalse(marco._config["avisar_encuadre"])
        marco.mi_avisos_encuadre.Check.assert_called_once_with(False)
        anunciar.assert_called_once_with("Avisos de encuadre desactivados")
        sincronizar.assert_called_once_with(marco)


class TestSincronizar(_Testigo):

    def test_activa_arranca_y_no_duplica(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        crear = self.patch_obj(encuadre_camara.diagnostico, "crear_hilo")
        encuadre_camara.sincronizar(marco)
        encuadre_camara.sincronizar(marco)
        self.assertEqual(crear.call_count, 1)
        self.assertIsNotNone(inst._hilo)

    def test_apagada_detiene_sin_esperar(self):
        marco = _nuevo_marco(avisar_encuadre=False)
        inst = self.inst(marco)
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        inst._hilo = hilo
        inst._parada = mock.Mock()
        encuadre_camara.sincronizar(marco)
        inst._parada.set.assert_called_once_with()
        hilo.join.assert_not_called()
        self.assertIsNone(inst._hilo)

    def test_apagada_sin_hilo_no_hace_nada(self):
        marco = _nuevo_marco(avisar_encuadre=False)
        crear = self.patch_obj(encuadre_camara.diagnostico, "crear_hilo")
        encuadre_camara.sincronizar(marco)
        crear.assert_not_called()


class TestTextoEstado(_Testigo):

    def test_activa_devuelve_la_ultima_frase(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        inst._hilo = hilo
        inst._ultima_frase = "Rostro centrado."
        self.assertEqual(encuadre_camara.texto_estado(marco),
                         "Rostro centrado.")

    def test_activa_sin_frase_devuelve_vacio(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        inst._hilo = hilo
        self.assertEqual(encuadre_camara.texto_estado(marco), "")

    def test_sin_vigilancia_devuelve_vacio(self):
        marco = _nuevo_marco(avisar_encuadre=False)
        self.inst(marco)
        self.assertEqual(encuadre_camara.texto_estado(marco), "")


class TestF2(_Testigo):

    def test_con_componente_dice_camara(self):
        snap = estado_sesion.SnapshotSesion(camara="Rostro centrado.")
        self.assertEqual(estado_sesion.formatear_estado(snap, {"camara"}),
                         "Cámara: Rostro centrado.")
        self.assertIn("camara", estado_sesion.COMPONENTES)

    def test_sin_componente_no_dice_nada(self):
        snap = estado_sesion.SnapshotSesion(camara="Rostro centrado.")
        self.assertNotIn("Cámara", estado_sesion.formatear_estado(snap, set()))

    def test_vacio_no_dice_nada(self):
        snap = estado_sesion.SnapshotSesion(camara="")
        self.assertEqual(estado_sesion.formatear_estado(snap, {"camara"}),
                         "")

    def test_snapshot_trae_el_texto_de_la_vigilancia(self):
        from bellbird.ui import gui_estado
        marco = mock.Mock()
        marco._config = {}
        marco._conectado = False
        marco.sesion.es_tiktok = False
        marco.sesion.tipo_video = None
        marco._metadatos = {}
        marco._titulo_stream = ""
        marco._stats.descartados = 0
        marco._stats.leidos = 0
        marco._stats.superchats = 0
        marco._sc_totales = {}
        marco._obs_vigilante = None
        marco._supervisor = None
        with mock.patch.object(encuadre_camara, "texto_estado",
                               return_value="Rostro centrado."):
            snap = gui_estado.snapshot_sesion(marco)
        self.assertEqual(snap.camara, "Rostro centrado.")


class TestAtajosNuevos(unittest.TestCase):

    def test_de_fabrica(self):
        self.assertEqual(atajos.ATAJOS_DEFAULTS["anunciar_encuadre"],
                         "ctrl+f3")
        self.assertEqual(atajos.ATAJOS_DEFAULTS["avisos_encuadre"],
                         "ctrl+shift+f3")

    def test_area_f_y_grupo_de_voz(self):
        self.assertEqual(atajos.ATAJOS_AREA["anunciar_encuadre"], "f")
        self.assertEqual(atajos.ATAJOS_AREA["avisos_encuadre"], "f")
        grupos = dict(atajos.ATAJOS_GRUPOS)
        self.assertIn("anunciar_encuadre",
                      grupos["Voz y lectura (teclas F)"])
        self.assertIn("avisos_encuadre", grupos["Voz y lectura (teclas F)"])

    def test_ini_sin_ellos_recibe_los_de_fabrica(self):
        atajos_resueltos = atajos.parsear_atajos({})
        self.assertEqual(atajos_resueltos["anunciar_encuadre"].texto,
                         "ctrl+f3")
        self.assertEqual(atajos_resueltos["avisos_encuadre"].texto,
                         "ctrl+shift+f3")


class TestRecuperacion(_Testigo):

    def test_tras_un_fallo_la_vuelta_siguiente_usa_un_cliente_nuevo(self):
        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        inst._detector = mock.Mock()
        inst._detector.analizar.return_value = _cuadro_con(
            [_rostro_centrado()], b"rostro")
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        creados = []

        def _crear_cliente(*args, **kwargs):
            cliente = mock.Mock()
            creados.append(cliente)
            return cliente

        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs",
                       side_effect=_crear_cliente)
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       return_value=CamaraObs("Cam", False))
        self.patch_obj(encuadre_camara.obs_camara, "capturar_cuadro",
                       side_effect=[CapturaFallida("No se pudo capturar Cam."),
                                    b"cuadro"])
        self.parchear_wx()
        espera = encuadre_camara._paso(inst, 0.0)
        self.assertEqual(espera, encuadre_camara.ESPERA_TRAS_FALLO)
        self.assertIsNone(inst._cliente)
        creados[0].cerrar.assert_called_once_with()
        espera = encuadre_camara._paso(inst, 5.0)
        self.assertEqual(espera, encuadre_camara.INTERVALO_VUELTA)
        self.assertEqual(len(creados), 2)
        self.assertIs(inst._cliente, creados[1])
        self.assertEqual(inst._ultima_frase, "Rostro centrado.")


@unittest.skipUnless(detector_rostros.disponible(),
                     "sin OpenCV instalado no hay detector real")
class TestDetectorReal(_Testigo):
    """La vigilancia con el detector de verdad sobre la foto de prueba."""

    def test_gris_fuera_y_rostro_dentro(self):
        import cv2
        import numpy
        from bellbird.camera.detector_rostros import DetectorRostros
        raiz = Path(__file__).resolve().parent
        foto = (raiz / "datos" / "rostro.jpg").read_bytes()
        gris = numpy.full((240, 320, 3), 128, numpy.uint8)
        _, buf = cv2.imencode(".bmp", gris)
        cuadros = {"ahora": bytes(buf)}

        marco = _nuevo_marco(avisar_encuadre=True)
        inst = self.inst(marco)
        inst._detector = DetectorRostros()
        self.patch_obj(encuadre_camara.obs_activacion,
                       "obs_esta_en_ejecucion", return_value=True)
        self.patch_obj(encuadre_camara.obs_cliente, "ClienteObs")
        self.patch_obj(encuadre_camara.obs_camara, "buscar_camara",
                       return_value=CamaraObs("Cam", False))
        self.patch_obj(encuadre_camara.obs_camara, "capturar_cuadro",
                       side_effect=lambda _c, _cam: cuadros["ahora"])
        anunciar = self.parchear_modulo("anunciar")
        suena = self.parchear_modulo("reproducir")
        llamadas = self.parchear_wx()
        for ahora in (0.0, 1.0, 2.0, 3.0):
            encuadre_camara._paso(inst, ahora)
        self.correr_llamadas(llamadas)
        anunciar.assert_called_once_with("Ningún rostro.")
        suena.assert_called_once_with("encuadre_fuera")
        cuadros["ahora"] = foto
        llamadas.clear()
        for ahora in (4.0, 5.0, 5.5):
            encuadre_camara._paso(inst, ahora)
        self.correr_llamadas(llamadas)
        suena.assert_called_with("encuadre_dentro")


if __name__ == "__main__":
    unittest.main()
