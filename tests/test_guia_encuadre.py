"""Pruebas de la guía de encuadre en marcha.

Sin wx.App ni ventanas: el marco, OBS y el detector son dobles, y
`wx.CallAfter` se reemplaza por un registro para ejecutar sus finales a
mano. El tiempo entra por argumento en `_paso`, sin parches globales.
"""

import threading
import unittest
from unittest import mock

from bellbird.camera import encuadre, guia
from bellbird.camera.detector_rostros import Cuadro
from bellbird.obs.obs_camara import CamaraNoEncontrada, CamaraObs
from bellbird.ui import guia_encuadre
from bellbird.ui.guia_encuadre import Guia


ANCHO = 320
ALTO = 240


def _rostro(centro_x, ojos_y):
    ancho, alto = 80.0, 100.0
    x = centro_x * ANCHO - ancho / 2
    ojos = ojos_y * ALTO
    return encuadre.Rostro(
        x=x, y=20.0, ancho=ancho, alto=alto,
        ojo_izquierda=(x + 20.0, ojos), ojo_derecha=(x + 60.0, ojos),
        nariz=(x + 40.0, ojos + 20.0), confianza=0.99)


def _cuadro_con(rostros):
    return Cuadro(rostros=tuple(rostros), ancho=ANCHO, alto=ALTO,
                  luz_rostro=120.0, luz_fondo=90.0, huella=b"huella")


class WorkerFalso:
    """Doble de la lectura: pausada o no, y cuántas veces cambió."""

    def __init__(self, pausado=False):
        self._pausado = pausado
        self.cambios = 0

    def esta_pausado(self):
        return self._pausado

    def toggle_pausa(self):
        self._pausado = not self._pausado
        self.cambios += 1


class MarcoFalso:
    """Doble del marco principal: config, lectura y bandera de vivo."""

    def __init__(self, pausado=False):
        self._config = {"camara_fuente": "", "camara_invertir": False}
        self._worker = WorkerFalso(pausado)

    def IsBeingDeleted(self):
        return False


class _Testigo(unittest.TestCase):

    def parchear(self, nombre, **kwargs):
        parche = mock.patch.object(guia_encuadre, nombre, **kwargs)
        self.addCleanup(parche.stop)
        return parche.start()

    def parchear_wx(self):
        llamadas = []

        def _callafter(funcion, *args):
            llamadas.append((funcion, args))

        falso_wx = mock.Mock()
        falso_wx.CallAfter.side_effect = _callafter
        self.parchear("wx", new=falso_wx)
        return llamadas

    def obs_abierto(self, camara=None):
        self.parchear("disponible", return_value=True)
        self.parchear("obs_activacion").obs_esta_en_ejecucion.return_value = True
        cliente = mock.Mock()
        self.parchear("obs_cliente").ClienteObs.return_value = cliente
        self.parchear("obs_camara").buscar_camara.return_value = \
            camara or CamaraObs("Cam", False)
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        return cliente

    def correr(self, llamadas):
        for funcion, args in llamadas:
            funcion(*args)


class TestIniciar(_Testigo):

    def test_anuncia_pausa_y_arranca(self):
        marco = MarcoFalso(pausado=False)
        self.obs_abierto()
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        al_terminar = mock.Mock()
        guiada = Guia()
        self.assertTrue(guiada.iniciar(marco, "", False, al_terminar))
        anunciar.assert_called_once_with(
            "Guía de encuadre. Sigue los pitidos.")
        self.assertEqual(marco._worker.cambios, 1)
        self.assertTrue(marco._worker.esta_pausado())
        crear.assert_called_once()
        self.assertTrue(guiada.en_marcha() or guiada._hilo is not None)

    def test_con_lectura_en_pausa_no_la_toca(self):
        marco = MarcoFalso(pausado=True)
        self.obs_abierto()
        self.parchear("anunciar")
        self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertTrue(guiada.iniciar(marco, "", False, mock.Mock()))
        self.assertEqual(marco._worker.cambios, 0)
        self.assertTrue(marco._worker.esta_pausado())

    def test_sin_detector_lo_dice_y_no_arranca(self):
        marco = MarcoFalso()
        self.parchear("disponible", return_value=False)
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertFalse(guiada.iniciar(marco, "", False, mock.Mock()))
        anunciar.assert_called_once_with(
            "El detector de rostros no está instalado.")
        crear.assert_not_called()

    def test_con_obs_cerrado_lo_dice_y_no_arranca(self):
        marco = MarcoFalso()
        self.parchear("disponible", return_value=True)
        self.parchear("obs_activacion").obs_esta_en_ejecucion.return_value = False
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertFalse(guiada.iniciar(marco, "", False, mock.Mock()))
        anunciar.assert_called_once_with("OBS no está abierto.")
        crear.assert_not_called()

    def test_en_marcha_no_duplica(self):
        marco = MarcoFalso()
        self.obs_abierto()
        self.parchear("anunciar")
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        guiada = Guia()
        guiada._hilo = hilo
        crear = self.parchear("diagnostico").crear_hilo
        self.assertFalse(guiada.iniciar(marco, "", False, mock.Mock()))
        crear.assert_not_called()


class TestDetener(_Testigo):

    def _en_marcha(self, marco, pausada=True):
        guiada = Guia()
        guiada._hilo = mock.Mock()
        guiada._parada = threading.Event()
        guiada._pausa_tomada = pausada
        guiada._al_terminar = mock.Mock()
        import weakref
        guiada._marco = weakref.ref(marco)
        return guiada

    def test_devuelve_pausa_reinicia_y_anuncia(self):
        marco = MarcoFalso(pausado=True)
        self.parchear("anunciar")
        anunciar = guia_encuadre.anunciar
        guiada = self._en_marcha(marco, pausada=True)
        terminar = guiada._al_terminar
        guiada.detener("Guía de encuadre detenida.")
        self.assertEqual(marco._worker.cambios, 1)
        self.assertFalse(marco._worker.esta_pausado())
        terminar.assert_called_once_with()
        anunciar.assert_called_once_with("Guía de encuadre detenida.")
        self.assertIsNone(guiada._hilo)
        self.assertIsNone(guiada._parada)
        self.assertFalse(guiada.en_marcha())

    def test_sin_pausa_tomada_no_reanuda(self):
        marco = MarcoFalso(pausado=False)
        self.parchear("anunciar")
        guiada = self._en_marcha(marco, pausada=False)
        guiada.detener("Guía de encuadre detenida.")
        self.assertEqual(marco._worker.cambios, 0)

    def test_con_marco_muerto_no_toca_nada(self):
        marco = MarcoFalso(pausado=True)
        self.parchear("anunciar")
        anunciar = guia_encuadre.anunciar
        guiada = self._en_marcha(marco, pausada=True)
        guiada._marco = lambda: None
        terminar = guiada._al_terminar
        guiada.detener("Guía de encuadre detenida.")
        self.assertEqual(marco._worker.cambios, 0)
        anunciar.assert_not_called()
        terminar.assert_called_once_with()


class TestPaso(_Testigo):

    def _marcha(self, rostros):
        detector = mock.Mock()
        detector.analizar.return_value = _cuadro_con(rostros)
        return guia.Marcha(
            inicio=0.0, cliente=mock.Mock(), camara=mock.Mock(),
            detector=detector, espejo=False)

    def test_un_cuadro_fuera_suena_el_pitido_que_toca(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        suena = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertTrue(guiada._paso(1.0))
        self.assertEqual(llamadas, [])
        (ruta,), _ = suena.call_args
        self.assertTrue(str(ruta).endswith("izquierda_medio.wav"))

    def test_sin_rostro_suena_cada_un_segundo(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        suena = self.parchear("reproducir_archivo")
        self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([])
        self.assertTrue(guiada._paso(1.0))
        self.assertTrue(str(suena.call_args[0][0]).endswith("sin_rostro.wav"))
        suena.reset_mock()
        self.assertTrue(guiada._paso(1.5))
        suena.assert_not_called()
        self.assertTrue(guiada._paso(2.1))
        self.assertTrue(str(suena.call_args[0][0]).endswith("sin_rostro.wav"))

    def test_centrada_tras_racha_termina_con_listo_y_frase(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        suena = self.parchear("reproducir_archivo")
        anunciar = self.parchear("anunciar")
        llamadas = self.parchear_wx()
        terminar = mock.Mock()
        marco = MarcoFalso(pausado=True)
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.5, 0.35)])
        guiada._al_terminar = terminar
        guiada._parada = threading.Event()
        guiada._marco = lambda: marco
        self.assertTrue(guiada._paso(1.0))
        self.assertFalse(guiada._paso(2.6))
        nombres = [str(llamada[0][0]) for llamada in suena.call_args_list]
        self.assertTrue(nombres[-1].endswith("listo.wav"))
        self.assertEqual(len(llamadas), 1)
        self.correr(llamadas)
        terminar.assert_called_once_with()
        anunciar.assert_called_once_with("Rostro centrado.")

    def test_a_los_60_segundos_se_detiene(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        suena = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertFalse(guiada._paso(60.0))
        suena.assert_not_called()
        self.assertEqual(len(llamadas), 1)
        funcion, args = llamadas[0]
        self.assertIs(funcion.__self__, guiada)
        self.assertIs(funcion.__func__, Guia.detener)
        self.assertEqual(args, ("Guía de encuadre detenida.",))

    def test_fallo_de_captura_cierra_con_su_texto(self):
        self.parchear("obs_camara").capturar_cuadro.side_effect = \
            CamaraNoEncontrada("No hay ninguna cámara en OBS.")
        suena = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertFalse(guiada._paso(1.0))
        suena.assert_not_called()
        self.assertEqual(llamadas[0][1],
                         ("No hay ninguna cámara en OBS.",))


class TestBucle(_Testigo):

    def test_con_marco_muerto_no_anuncia(self):
        anunciar = self.parchear("anunciar")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: None
        guiada._bucle("", False)
        self.assertEqual(len(llamadas), 1)
        self.correr(llamadas)
        anunciar.assert_not_called()

    def test_sin_camara_cierra_con_su_texto(self):
        marco = MarcoFalso()
        self.obs_abierto()
        self.parchear("obs_camara").buscar_camara.side_effect = \
            CamaraNoEncontrada("No hay ninguna cámara en OBS.")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: marco
        guiada._parada = threading.Event()
        guiada._bucle("", False)
        self.assertEqual(llamadas[0][1], ("No hay ninguna cámara en OBS.",))


class TestTextoFallo(_Testigo):

    def test_de_camara_y_captura_es_su_texto(self):
        self.assertEqual(
            guia_encuadre._texto_fallo(
                CamaraNoEncontrada("No hay ninguna cámara en OBS.")),
            "No hay ninguna cámara en OBS.")

    def test_otro_fallo_es_el_traducido_de_obs(self):
        self.parchear("obs_cliente").mensaje_de_fallo_obs.return_value = \
            "Fallo traducido de OBS."
        self.assertEqual(guia_encuadre._texto_fallo(RuntimeError("socket")),
                         "Fallo traducido de OBS.")


if __name__ == "__main__":
    unittest.main()
